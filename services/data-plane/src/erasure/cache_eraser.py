"""
Redis semantic cache erasure engine.
1. Delete tagged entries (zt:cache:subject:{subject_ref}:*)
2. Content scan for untagged entries containing identifier variants
3. Force persistence rewrite (AOF/RDB) so deleted keys are gone from disk
"""
from __future__ import annotations

import json
from typing import Any

import redis as syncredis

from src.core.config import get_settings
from src.core.logging import get_logger
from src.erasure.events import EventEmitter

logger = get_logger("cache_eraser")
cfg = get_settings()


def erase_cache(
    job_id: str,
    subject_ref: str,
    identifiers: list[dict],
    emitter: EventEmitter,
) -> dict:
    """
    Erase all Redis cache entries for the subject.
    Returns metrics.
    """
    stage = "ERASE_CACHE"
    metrics: dict[str, Any] = {
        "cache_keys_deleted": 0,
        "untagged_keys_found": 0,
    }

    r = syncredis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_cache_db,
        decode_responses=True,
        socket_timeout=10,
    )

    # Build identifier variants for content scan
    all_variants: list[str] = []
    for ident in identifiers:
        v = str(ident.get("value", ""))
        all_variants += [v, v.lower()]
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) == 10:
            all_variants += [f"+91{digits}", f"91{digits}", f"0{digits}"]
    all_variants = [v for v in all_variants if len(v) > 4]

    emitter.emit_sync(stage, "started", "cache", "Starting Redis cache erasure")

    # ── Step 1: Delete tagged entries ─────────────────────────────────────────
    emitter.emit_sync(stage, "progress", "cache",
                      "Step 1/3: Deleting tagged cache entries")
    tagged_keys = list(r.scan_iter(f"zt:cache:subject:{subject_ref}:*"))
    # Also get all keys in the subject's set
    set_key = f"zt:cache:subjects:{subject_ref}"
    set_members = list(r.smembers(set_key))
    all_tagged = list(set(tagged_keys + set_members + [set_key]))

    if all_tagged:
        r.delete(*all_tagged)

    metrics["cache_keys_deleted"] += len(all_tagged)
    logger.info("cache.tagged_deleted", count=len(all_tagged))
    emitter.emit_sync(stage, "metric", "cache",
                      f"Deleted {len(all_tagged)} tagged cache keys",
                      {"cache_keys_deleted": len(all_tagged)})

    # ── Step 2: Content scan (finds untagged entries) ─────────────────────────
    emitter.emit_sync(stage, "progress", "cache",
                      "Step 2/3: Content scan for untagged cache entries")
    untagged_deleted = _content_scan(r, all_variants, emitter, stage)
    metrics["cache_keys_deleted"] += untagged_deleted
    metrics["untagged_keys_found"] = untagged_deleted

    # ── Step 3: Force persistence rewrite ────────────────────────────────────
    emitter.emit_sync(stage, "progress", "cache",
                      "Step 3/3: Forcing persistence file rewrite")
    try:
        r.bgrewriteaof()
        emitter.emit_sync(stage, "metric", "cache",
                          "AOF rewrite triggered — deleted keys purged from disk")
    except Exception:
        try:
            r.bgsave()
            emitter.emit_sync(stage, "metric", "cache",
                              "BGSAVE triggered as fallback")
        except Exception as e:
            emitter.emit_sync(stage, "log", "cache",
                              f"Persistence rewrite failed: {e}")

    emitter.emit_sync(stage, "completed", "cache",
                      "Cache erasure complete", metrics)
    return metrics


def _content_scan(r: syncredis.Redis, variants: list[str], emitter: EventEmitter, stage: str) -> int:
    """
    Scan ALL zt:cache:* keys for content containing identifier variants.
    Deletes any matching untagged entry.
    """
    deleted = 0
    for key in r.scan_iter("zt:cache:*"):
        try:
            val = r.get(key)
            if not val:
                continue
            val_lower = val.lower()
            for v in variants:
                if v.lower() in val_lower:
                    r.delete(key)
                    deleted += 1
                    logger.info("cache.untagged_deleted", key=key[:30] + "...")
                    emitter.emit_sync(stage, "finding", "cache",
                                      "Untagged cache entry found and deleted via content scan",
                                      {"key_prefix": key[:20]})
                    break
        except Exception:
            continue
    return deleted
