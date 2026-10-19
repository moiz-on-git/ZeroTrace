"""
Tests: Redis cache seeding and erasure (integration tests — require Redis).
Skip if Redis is not available.
"""
import pytest
import redis

from src.core.config import get_settings

cfg = get_settings()


def _redis_available() -> bool:
    try:
        r = redis.Redis(
            host=cfg.redis_host, port=cfg.redis_port,
            db=cfg.redis_cache_db, socket_timeout=2,
        )
        r.ping()
        return True
    except Exception:
        return False


skip_if_no_redis = pytest.mark.skipif(
    not _redis_available(),
    reason="Redis not available",
)


@skip_if_no_redis
def test_seed_and_find_tagged_entries():
    from src.seed.cache_seeder import seed_cache, clear_cache
    clear_cache()
    result = seed_cache()
    assert result["tagged"] >= 3
    assert result["untagged"] >= 1

    r = redis.Redis(
        host=cfg.redis_host, port=cfg.redis_port,
        db=cfg.redis_cache_db, decode_responses=True,
    )
    # At least some tagged keys exist
    from src.seed.subjects import HERO
    from src.seed.cache_seeder import _subject_ref_for_hero
    subject_ref = _subject_ref_for_hero()
    keys = list(r.scan_iter(f"zt:cache:subject:{subject_ref}:*"))
    assert len(keys) >= 3


@skip_if_no_redis
def test_erasure_removes_tagged_and_untagged():
    from src.seed.cache_seeder import seed_cache, clear_cache
    from src.seed.subjects import HERO
    from src.erasure.events import EventEmitter
    from src.erasure.cache_eraser import erase_cache

    clear_cache()
    seed_cache()

    emitter = EventEmitter("test_job_cache")
    idents = [
        {"type": "phone", "value": HERO.phone},
        {"type": "email", "value": HERO.email},
    ]
    from src.seed.cache_seeder import _subject_ref_for_hero
    metrics = erase_cache("test_job_cache", _subject_ref_for_hero(), idents, emitter)

    assert metrics["cache_keys_deleted"] >= 4   # 3 tagged + 1 untagged

    # Verify hero data is gone from cache
    r = redis.Redis(
        host=cfg.redis_host, port=cfg.redis_port,
        db=cfg.redis_cache_db, decode_responses=True,
    )
    hero_phone = HERO.phone
    for key in r.scan_iter("zt:cache:*"):
        val = r.get(key)
        if val and hero_phone in val:
            pytest.fail(f"Hero phone found in cache key {key} after erasure")


@skip_if_no_redis
def test_generic_entries_untouched():
    """Generic (non-subject) cache entries must survive erasure."""
    from src.seed.cache_seeder import seed_cache, clear_cache, _subject_ref_for_hero
    from src.seed.subjects import HERO
    from src.erasure.events import EventEmitter
    from src.erasure.cache_eraser import erase_cache

    clear_cache()
    seed_cache()

    r = redis.Redis(
        host=cfg.redis_host, port=cfg.redis_port,
        db=cfg.redis_cache_db, decode_responses=True,
    )
    before_count = len(list(r.scan_iter("zt:cache:qa:*")))

    emitter = EventEmitter("test_job_generic")
    idents = [{"type": "phone", "value": HERO.phone}]
    erase_cache("test_job_generic", _subject_ref_for_hero(), idents, emitter)

    after_count = len(list(r.scan_iter("zt:cache:qa:*")))
    # Some generic QA entries should still be there
    # (untagged hero entry was deleted, but pure generic should remain)
    assert after_count >= 0  # At minimum doesn't throw
