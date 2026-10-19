"""
Vector (pgvector) erasure engine.
1. Delete embeddings linked by metadata (subject_ref)
2. Semantic sweep — embeds identifier variants, finds ghost chunks via cosine similarity
3. VACUUM + REINDEX — physically remove dead tuples
"""
from __future__ import annotations

import time
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger
from src.erasure.events import EventEmitter
from src.seed.vector_seeder import get_embedding_model

logger = get_logger("vector_eraser")
cfg = get_settings()

SIMILARITY_THRESHOLD = 0.75   # cosine similarity threshold for ghost detection
CONFIRM_TEXT_MATCH = True     # always text-confirm before deleting (avoid decoy deletion)


def erase_vectors(
    job_id: str,
    subject_ref: str,
    identifiers: list[dict],
    emitter: EventEmitter,
    skip_semantic_sweep: bool = False,
) -> dict:
    """
    Erase all vector embeddings for the subject.
    Returns metrics.
    """
    import psycopg  # type: ignore[import]

    stage = "ERASE_VECTOR"
    metrics: dict[str, Any] = {
        "vectors_deleted": 0,
        "ghost_vectors_found": 0,
        "dead_tuples_vacuumed": 0,
    }

    pg_dsn = (
        f"host={cfg.pg_host} port={cfg.pg_port} "
        f"dbname={cfg.pg_db_rag} "
        f"user={cfg.pg_user} password={cfg.pg_password}"
    )

    emitter.emit_sync(stage, "started", "vector", "Starting vector erasure")

    # Build all identifier string variants for text matching
    all_variants: list[str] = []
    for ident in identifiers:
        v = str(ident.get("value", ""))
        all_variants += [v, v.lower(), v.upper()]
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) == 10:
            all_variants += [f"+91{digits}", f"91{digits}", f"0{digits}"]

    with psycopg.connect(pg_dsn) as conn:
        # ── Step 1: Delete by metadata link ──────────────────────────────────
        emitter.emit_sync(stage, "progress", "vector",
                          "Step 1/3: Deleting embeddings by subject_ref")
        cur = conn.execute(
            "DELETE FROM embeddings WHERE subject_ref = %s RETURNING id",
            (subject_ref,),
        )
        deleted_by_meta = len(cur.fetchall())
        metrics["vectors_deleted"] += deleted_by_meta
        conn.commit()
        logger.info("vector.deleted_by_metadata", count=deleted_by_meta)
        emitter.emit_sync(stage, "metric", "vector",
                          f"Deleted {deleted_by_meta} embeddings by metadata",
                          {"vectors_deleted": deleted_by_meta})

        # ── Step 2: Semantic sweep (finds ghost embeddings) ───────────────────
        if not skip_semantic_sweep:
            emitter.emit_sync(stage, "progress", "vector",
                              "Step 2/3: Semantic sweep for ghost embeddings")
            ghost_deleted = _semantic_sweep(conn, identifiers, all_variants, emitter, stage)
            metrics["vectors_deleted"] += ghost_deleted
            metrics["ghost_vectors_found"] = ghost_deleted
        else:
            emitter.emit_sync(stage, "log", "vector",
                              "Semantic sweep SKIPPED (demo: ghost_miss=true) — "
                              "ghost embedding will remain for audit to find")

        # ── Step 3: VACUUM + REINDEX ──────────────────────────────────────────
        emitter.emit_sync(stage, "progress", "vector",
                          "Step 3/3: VACUUM + REINDEX to remove dead tuples")
        # Check dead tuples before
        try:
            cur = conn.execute(
                """
                SELECT n_dead_tup FROM pg_stat_user_tables
                WHERE relname = 'embeddings'
                """
            )
            row = cur.fetchone()
            dead_before = row[0] if row else 0
        except Exception:
            dead_before = 0

        conn.execute("VACUUM ANALYZE embeddings")
        try:
            conn.execute("REINDEX INDEX idx_embed_ivfflat")
        except Exception:
            pass
        conn.commit()

        try:
            cur = conn.execute(
                """
                SELECT n_dead_tup FROM pg_stat_user_tables
                WHERE relname = 'embeddings'
                """
            )
            row = cur.fetchone()
            dead_after = row[0] if row else 0
        except Exception:
            dead_after = 0

        vacuumed = max(0, dead_before - dead_after)
        metrics["dead_tuples_vacuumed"] = vacuumed
        logger.info("vector.vacuum_done", dead_before=dead_before, dead_after=dead_after)
        emitter.emit_sync(stage, "metric", "vector",
                          f"VACUUM done, {vacuumed} dead tuples removed",
                          {"dead_tuples_vacuumed": vacuumed})

    emitter.emit_sync(stage, "completed", "vector",
                      "Vector erasure complete", metrics)
    return metrics


def _semantic_sweep(
    conn,
    identifiers: list[dict],
    all_variants: list[str],
    emitter: EventEmitter,
    stage: str,
) -> int:
    """
    Embed each identifier variant and search for similar chunks.
    Confirm matches by text before deleting (avoids deleting decoy data).
    Returns number of ghost embeddings deleted.
    """
    model = get_embedding_model()
    deleted = 0

    # Build query texts from identifiers
    query_texts = []
    for ident in identifiers:
        v = str(ident.get("value", ""))
        t = ident.get("type", "")
        query_texts.append(v)
        if t == "phone":
            query_texts.append(f"phone number {v}")
            query_texts.append(f"mobile {v}")
        elif t in ("name", "full_name"):
            query_texts.append(f"customer {v}")

    query_texts = list(dict.fromkeys(query_texts))

    for qtext in query_texts:
        embedding = model.encode([qtext], show_progress_bar=False)[0].tolist()

        # Find similar chunks above threshold
        cur = conn.execute(
            """
            SELECT id, chunk_id, content, subject_ref, source_table
            FROM embeddings
            WHERE 1 - (embedding <=> %s::vector) > %s
            """,
            (embedding, SIMILARITY_THRESHOLD),
        )
        candidates = cur.fetchall()

        for row in candidates:
            row_id, chunk_id, content, s_ref, source_table = row

            # Skip if already tagged for this subject (handled in step 1)
            if s_ref == emitter.job_id:
                continue

            # Confirm by text match — prevents deleting decoy data
            if not _text_matches(content, all_variants):
                continue

            # Delete confirmed ghost
            conn.execute("DELETE FROM embeddings WHERE id = %s", (row_id,))
            deleted += 1
            logger.info("vector.ghost_deleted", chunk_id=chunk_id)
            emitter.emit_sync(stage, "finding", "vector",
                              f"Ghost embedding deleted (found via semantic sweep)",
                              {"chunk_id": chunk_id, "similarity_match": True})

    conn.commit()
    logger.info("vector.semantic_sweep_done", ghosts_deleted=deleted)
    return deleted


def _text_matches(content: str, variants: list[str]) -> bool:
    """Check if content contains any identifier variant."""
    content_lower = content.lower()
    for v in variants:
        if len(v) > 4 and v.lower() in content_lower:
            return True
    return False
