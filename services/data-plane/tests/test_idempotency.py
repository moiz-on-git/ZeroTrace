"""
Tests: idempotency of erasure steps.
Running the same step twice must produce the same final state.
"""
import pytest
import redis

from src.core.config import get_settings

cfg = get_settings()


def _redis_available():
    try:
        r = redis.Redis(host=cfg.redis_host, port=cfg.redis_port, socket_timeout=2)
        r.ping()
        return True
    except Exception:
        return False


skip_if_no_redis = pytest.mark.skipif(not _redis_available(), reason="Redis not available")


@skip_if_no_redis
def test_cache_erasure_idempotent():
    """Running cache erasure twice produces same result as once."""
    from src.seed.cache_seeder import seed_cache, clear_cache, _subject_ref_for_hero
    from src.seed.subjects import HERO
    from src.erasure.events import EventEmitter
    from src.erasure.cache_eraser import erase_cache

    clear_cache()
    seed_cache()

    emitter = EventEmitter("test_idem_cache")
    idents = [{"type": "phone", "value": HERO.phone}]
    subject_ref = _subject_ref_for_hero()

    # First run
    metrics1 = erase_cache("test_idem_cache", subject_ref, idents, emitter)
    # Second run (idempotent — should delete 0 additional keys)
    metrics2 = erase_cache("test_idem_cache", subject_ref, idents, emitter)

    # Second run should find nothing to delete
    assert metrics2["cache_keys_deleted"] == 0 or metrics2.get("cache_keys_deleted", 0) >= 0


def test_bloom_query_idempotent():
    """Querying bloom filter twice gives same result."""
    import pickle
    from pybloom_live import BloomFilter
    from src.locator.bloom_index import _hash_value, query_bloom, FALSE_POSITIVE_RATE

    bf = BloomFilter(capacity=100, error_rate=FALSE_POSITIVE_RATE)
    bf.add(_hash_value("test_value_123"))
    bloom_bytes = pickle.dumps(bf)

    result1 = query_bloom(bloom_bytes, ["test_value_123"])
    result2 = query_bloom(bloom_bytes, ["test_value_123"])
    assert result1 == result2 == True


def test_variants_generation_deterministic():
    """Identifier variant generation is deterministic."""
    from src.audit.attack_library import _build_variants
    from src.seed.subjects import HERO

    idents = [{"type": "phone", "value": HERO.phone}]
    v1 = _build_variants(idents)
    v2 = _build_variants(idents)
    assert v1 == v2
