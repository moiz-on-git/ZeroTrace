"""Locate endpoint — find all copies of a subject across all layers."""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends

from src.api.deps import require_service_key
from src.api.schemas import ApiResponse, LocationResult, LocateRequest, LocateResponse
from src.core.config import get_settings
from src.core.logging import get_logger
from src.locator.bloom_index import build_index_for_table, find_candidate_files
from src.seed.iceberg_writer import TABLE_PII_COLS, TABLE_SCHEMAS, TABLE_TAGS

router = APIRouter()
logger = get_logger("locate")
cfg = get_settings()


@router.post("/v1/locate", dependencies=[Depends(require_service_key)])
async def locate(req: LocateRequest):
    import asyncio
    from src.core.exceptions import ValidationError

    # Validate that at least one identifier is provided
    if not req.identifiers:
        raise ValidationError(
            message="At least one identifier is required",
            details={"field": "identifiers"},
        )

    all_variants = req.variants[:]
    for ident in req.identifiers:
        v = ident.value.strip()
        all_variants.append(v)
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) == 10:
            all_variants += [v, f"+91{digits}", f"91{digits}", f"0{digits}"]
        if "@" in v:
            all_variants += [v.lower(), v.upper()]
    all_variants = list(dict.fromkeys(v for v in all_variants if len(v) > 3))

    locations: list[LocationResult] = []
    warehouse = cfg.iceberg_warehouse.replace("s3a://", "").replace(cfg.s3_bucket + "/", "")

    # ── Iceberg tables ────────────────────────────────────────────────────────
    for table_name in TABLE_SCHEMAS:
        try:
            index_entries = await asyncio.to_thread(
                build_index_for_table, table_name, warehouse
            )
            candidates = await asyncio.to_thread(
                find_candidate_files, table_name, all_variants, index_entries
            )
            if candidates:
                est_rows = sum(e["row_count"] for e in candidates)
                tags = TABLE_TAGS.get(table_name, [])
                locations.append(LocationResult(
                    location_id=f"loc_{hashlib.sha256(table_name.encode()).hexdigest()[:8]}",
                    layer="iceberg",
                    resource=f"kaveri.kaveri_finserv.{table_name}",
                    match_basis="bloom_filter_confirmed",
                    estimated_rows=est_rows,
                    data_category=tags[0] if tags else "unknown",
                    pii_columns=TABLE_PII_COLS.get(table_name, []),
                    files_hit=len(candidates),
                    files_total=len(index_entries),
                ))
        except Exception as e:
            logger.warning("locate.iceberg_failed", table=table_name, error=str(e))

    # ── Vector store ──────────────────────────────────────────────────────────
    try:
        import psycopg
        pg_dsn = (
            f"host={cfg.pg_host} port={cfg.pg_port} "
            f"dbname={cfg.pg_db_rag} "
            f"user={cfg.pg_user} password={cfg.pg_password}"
        )
        subject_ref = _make_subject_ref(req.identifiers)
        with psycopg.connect(pg_dsn) as conn:
            cur = conn.execute(
                "SELECT COUNT(*) FROM embeddings WHERE subject_ref = %s",
                (subject_ref,),
            )
            count = cur.fetchone()[0]
            if count > 0:
                locations.append(LocationResult(
                    location_id="loc_vector_embeddings",
                    layer="vector",
                    resource="zt_rag.embeddings",
                    match_basis="subject_ref_match",
                    estimated_rows=count,
                    data_category="embedding",
                    pii_columns=["content"],
                    files_hit=0,
                    files_total=0,
                ))
    except Exception as e:
        logger.warning("locate.vector_failed", error=str(e))

    # ── Redis cache ───────────────────────────────────────────────────────────
    try:
        import redis as syncredis
        r = syncredis.Redis(
            host=cfg.redis_host, port=cfg.redis_port,
            db=cfg.redis_cache_db, decode_responses=True, socket_timeout=5,
        )
        subject_ref = _make_subject_ref(req.identifiers)
        tagged_keys = list(r.scan_iter(f"zt:cache:subject:{subject_ref}:*"))
        if tagged_keys:
            locations.append(LocationResult(
                location_id="loc_cache_tagged",
                layer="cache",
                resource="redis_db0:zt:cache:subject:*",
                match_basis="subject_ref_tagged",
                estimated_rows=len(tagged_keys),
                data_category="cache",
                pii_columns=[],
                files_hit=len(tagged_keys),
                files_total=0,
            ))
        # Untagged content scan
        untagged = 0
        for key in r.scan_iter("zt:cache:qa:*"):
            val = r.get(key)
            if val and any(v.lower() in val.lower() for v in all_variants if len(v) > 4):
                untagged += 1
        if untagged:
            locations.append(LocationResult(
                location_id="loc_cache_untagged",
                layer="cache",
                resource="redis_db0:zt:cache:qa:*",
                match_basis="content_scan",
                estimated_rows=untagged,
                data_category="cache",
                pii_columns=[],
                files_hit=untagged,
                files_total=0,
            ))
    except Exception as e:
        logger.warning("locate.cache_failed", error=str(e))

    return ApiResponse(data=LocateResponse(locations=locations).model_dump())


def _make_subject_ref(identifiers) -> str:
    import hmac as _hmac
    cfg2 = get_settings()
    key = "|".join(sorted(str(i.value) for i in identifiers))
    return "sub_" + _hmac.new(
        cfg2.service_key.encode(), key.encode(), hashlib.sha256
    ).hexdigest()[:20]
