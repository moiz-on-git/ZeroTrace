"""
Seeds pgvector embeddings for support tickets and call transcripts.
Plants ONE GHOST EMBEDDING — a chunk mentioning the hero but with no metadata link.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any

from src.core.config import get_settings
from src.core.logging import get_logger
from src.seed.subjects import HERO

logger = get_logger("vector_seeder")
cfg = get_settings()

GHOST_CHUNK_TEXT = (
    f"Transcript excerpt: The customer {HERO.full_name} "
    f"called to dispute a charge. Her registered mobile is {HERO.phone} "
    f"and email is {HERO.email}. This chunk has no metadata link."
)


def get_embedding_model():
    """Load the multilingual sentence-transformer model (cached after first load)."""
    from sentence_transformers import SentenceTransformer  # type: ignore[import]
    model_path = cfg.embed_model_path
    try:
        model = SentenceTransformer(model_path)
    except Exception:
        # Fall back to downloading from HuggingFace if path not baked in
        model = SentenceTransformer(cfg.embed_model)
        logger.warning("embed.fallback_download", model=cfg.embed_model)
    return model


def embed_texts(texts: list[str], model=None) -> list[list[float]]:
    if model is None:
        model = get_embedding_model()
    vectors = model.encode(texts, show_progress_bar=False, batch_size=64)
    return [v.tolist() for v in vectors]


def seed_vectors(
    tickets: list[dict],
    transcripts: list[dict],
    conn_str: str | None = None,
) -> dict[str, int]:
    """
    Embed support tickets and call transcripts into pgvector.
    Returns counts: {"embedded": N, "ghost_planted": 1}
    """
    import psycopg  # type: ignore[import]

    pg_dsn = conn_str or (
        f"host={cfg.pg_host} port={cfg.pg_port} "
        f"dbname={cfg.pg_db_rag} "
        f"user={cfg.pg_user} password={cfg.pg_password}"
    )

    model = get_embedding_model()
    logger.info("vector.seeding_start", tickets=len(tickets), transcripts=len(transcripts))

    chunks = []

    # Tickets
    for t in tickets:
        text = f"[Ticket {t['ticket_id']}] {t['description']}"
        chunks.append({
            "chunk_id": f"tick_{t['ticket_id']}",
            "source_table": "support_tickets",
            "source_pk": t["ticket_id"],
            "subject_ref": _ref(t["customer_id"]),
            "content": text,
            "is_ghost": False,
        })

    # Transcripts — with metadata link
    for t in transcripts:
        text = t["transcript_text"]
        chunks.append({
            "chunk_id": f"trx_{t['transcript_id']}",
            "source_table": "call_transcripts",
            "source_pk": t["transcript_id"],
            "subject_ref": _ref(t["customer_id"]),
            "content": text,
            "is_ghost": False,
        })

    # GHOST EMBEDDING — mentions hero, NO metadata link
    chunks.append({
        "chunk_id": "ghost_" + hashlib.sha256(GHOST_CHUNK_TEXT.encode()).hexdigest()[:12],
        "source_table": None,     # <── no metadata link — a metadata-based delete MISSES this
        "source_pk": None,
        "subject_ref": None,      # <── not tagged
        "content": GHOST_CHUNK_TEXT,
        "is_ghost": True,
    })

    # Batch embed
    texts = [c["content"] for c in chunks]
    vectors = embed_texts(texts, model)

    with psycopg.connect(pg_dsn) as conn:
        # Ensure pgvector extension
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id SERIAL PRIMARY KEY,
                chunk_id VARCHAR(64) UNIQUE NOT NULL,
                source_table VARCHAR(128),
                source_pk VARCHAR(128),
                subject_ref VARCHAR(64),
                content TEXT NOT NULL,
                embedding vector(384) NOT NULL,
                is_ghost BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_embed_subject ON embeddings(subject_ref)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_embed_ivfflat ON embeddings "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)"
        )
        conn.commit()

        inserted = 0
        for chunk, vector in zip(chunks, vectors):
            conn.execute(
                """
                INSERT INTO embeddings
                    (chunk_id, source_table, source_pk, subject_ref, content, embedding, is_ghost)
                VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
                ON CONFLICT (chunk_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embedding = EXCLUDED.embedding,
                    subject_ref = EXCLUDED.subject_ref
                """,
                (
                    chunk["chunk_id"],
                    chunk["source_table"],
                    chunk["source_pk"],
                    chunk["subject_ref"],
                    chunk["content"],
                    vector,
                    chunk["is_ghost"],
                ),
            )
            inserted += 1

        conn.commit()

    logger.info("vector.seeding_done", embedded=inserted - 1, ghost_planted=1)
    return {"embedded": inserted - 1, "ghost_planted": 1}


def clear_vectors(conn_str: str | None = None) -> None:
    import psycopg  # type: ignore[import]

    pg_dsn = conn_str or (
        f"host={cfg.pg_host} port={cfg.pg_port} "
        f"dbname={cfg.pg_db_rag} "
        f"user={cfg.pg_user} password={cfg.pg_password}"
    )
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("TRUNCATE TABLE embeddings RESTART IDENTITY")
        conn.commit()
    logger.info("vector.cleared")


def _ref(customer_id: str) -> str:
    """Simple pseudonymous reference for seeding."""
    return "sub_" + hashlib.sha256(customer_id.encode()).hexdigest()[:20]
