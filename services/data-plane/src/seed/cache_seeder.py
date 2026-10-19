"""
Seeds Redis semantic cache (db0) with question→answer pairs for Kaveri Finserv.
Some entries are tagged with a subject key; one is NOT tagged (found only by content scan).
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import redis as syncredis

from src.core.config import get_settings
from src.core.logging import get_logger
from src.seed.subjects import HERO

logger = get_logger("cache_seeder")
cfg = get_settings()

# Redis key conventions for semantic cache
# Tagged:   zt:cache:subject:{subject_ref}:{q_hash}  → JSON {q, a, ts}
# Untagged: zt:cache:qa:{q_hash}                     → JSON {q, a, ts}

TAGGED_QA_PAIRS = [
    {
        "question": f"What is the phone number of customer {HERO.full_name}?",
        "answer": (
            f"The registered mobile number for {HERO.full_name} "
            f"(Customer ID: {HERO.customer_id}) is {HERO.phone}."
        ),
    },
    {
        "question": f"Show me the email address of {HERO.full_name}",
        "answer": (
            f"{HERO.full_name}'s registered email address is {HERO.email}. "
            f"Customer ID: {HERO.customer_id}."
        ),
    },
    {
        "question": f"What loans does {HERO.customer_id} have?",
        "answer": (
            f"Customer {HERO.full_name} ({HERO.customer_id}) has an active home loan "
            f"sanctioned on 2022-08-01 for ₹25,00,000 at 9.5% p.a."
        ),
    },
]

# This entry is NOT tagged with subject_ref — only a content scan finds it
UNTAGGED_QA = {
    "question": "Tell me about recent fraud disputes in Bengaluru",
    "answer": (
        f"A recent dispute was filed by {HERO.full_name} (mobile: {HERO.phone}) "
        f"regarding an unauthorised transaction on their account. "
        f"Reference: {HERO.customer_id}."
    ),
}

GENERIC_QA_PAIRS = [
    {
        "question": "What is the PMLA compliance requirement for KYC?",
        "answer": "Under PMLA 2002, KYC records must be maintained for 5 years after the account closure.",
    },
    {
        "question": "How do I apply for a home loan?",
        "answer": "You can apply for a home loan via the Kaveri Finserv app or by visiting any branch. Documents required: income proof, address proof, and property documents.",
    },
    {
        "question": "What are the processing fees for a personal loan?",
        "answer": "Processing fee for personal loans is 1-2% of the loan amount, subject to a minimum of ₹1,000.",
    },
]


def _subject_ref_for_hero() -> str:
    return "sub_" + hashlib.sha256(
        f"{HERO.email}|{HERO.phone}".encode()
    ).hexdigest()[:20]


def _q_hash(question: str) -> str:
    return hashlib.sha256(question.lower().strip().encode()).hexdigest()[:16]


def seed_cache(conn_str: str | None = None) -> dict[str, int]:
    """Seed the Redis semantic cache. Returns counts."""
    r = _get_redis(conn_str)
    subject_ref = _subject_ref_for_hero()
    tagged_count = 0
    untagged_count = 0
    generic_count = 0
    now = int(time.time())

    # Tagged entries
    for pair in TAGGED_QA_PAIRS:
        qh = _q_hash(pair["question"])
        key = f"zt:cache:subject:{subject_ref}:{qh}"
        value = json.dumps({
            "q": pair["question"],
            "a": pair["answer"],
            "subject_ref": subject_ref,
            "ts": now,
        })
        r.set(key, value)
        # Also add to subject set for easy lookup
        r.sadd(f"zt:cache:subjects:{subject_ref}", key)
        tagged_count += 1

    # Untagged entry — no subject_ref in key or value's metadata
    qh = _q_hash(UNTAGGED_QA["question"])
    key = f"zt:cache:qa:{qh}"
    value = json.dumps({
        "q": UNTAGGED_QA["question"],
        "a": UNTAGGED_QA["answer"],
        "ts": now,
        # deliberately NO subject_ref field — this is the trap
    })
    r.set(key, value)
    untagged_count += 1

    # Generic entries
    for pair in GENERIC_QA_PAIRS:
        qh = _q_hash(pair["question"])
        key = f"zt:cache:qa:{qh}"
        value = json.dumps({"q": pair["question"], "a": pair["answer"], "ts": now})
        r.set(key, value)
        generic_count += 1

    logger.info(
        "cache.seeded",
        tagged=tagged_count,
        untagged=untagged_count,
        generic=generic_count,
    )
    return {"tagged": tagged_count, "untagged": untagged_count, "generic": generic_count}


def clear_cache(conn_str: str | None = None) -> int:
    """Flush all zt:cache:* keys from Redis db0."""
    r = _get_redis(conn_str)
    keys = list(r.scan_iter("zt:cache:*"))
    if keys:
        r.delete(*keys)
    logger.info("cache.cleared", keys_deleted=len(keys))
    return len(keys)


def force_persistence_rewrite(conn_str: str | None = None) -> None:
    """Force Redis AOF/RDB rewrite so deleted keys are gone from disk."""
    r = _get_redis(conn_str)
    try:
        r.bgrewriteaof()
        logger.info("cache.aof_rewrite_triggered")
    except Exception:
        try:
            r.bgsave()
            logger.info("cache.bgsave_triggered")
        except Exception as e:
            logger.warning("cache.persist_rewrite_failed", error=str(e))


def _get_redis(conn_str: str | None = None) -> syncredis.Redis:
    if conn_str:
        return syncredis.from_url(conn_str, decode_responses=True)
    return syncredis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        db=cfg.redis_cache_db,
        decode_responses=True,
        socket_timeout=10,
    )
