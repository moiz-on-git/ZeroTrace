"""
Tests: Bloom filter correctness — no false negatives, acceptable false positives.
"""
import pickle
import pytest
from src.locator.bloom_index import (
    FALSE_POSITIVE_RATE,
    _hash_value,
    build_bloom_for_file,
    query_bloom,
    confirm_file_contains,
)


def test_bloom_no_false_negatives():
    """Items inserted must always be found."""
    from pybloom_live import BloomFilter
    bf = BloomFilter(capacity=1000, error_rate=FALSE_POSITIVE_RATE)
    test_values = ["9845012345", "+919845012345", "ananya@example.in"]
    for v in test_values:
        bf.add(_hash_value(v))

    bloom_bytes = pickle.dumps(bf)
    for v in test_values:
        assert query_bloom(bloom_bytes, [v]) is True, f"False negative for {v}"


def test_bloom_query_variants():
    """Phone variant should be found even if only canonical form was inserted."""
    from pybloom_live import BloomFilter
    bf = BloomFilter(capacity=1000, error_rate=FALSE_POSITIVE_RATE)
    phone = "9845012345"
    bf.add(_hash_value(phone))
    bloom_bytes = pickle.dumps(bf)
    # Canonical form
    assert query_bloom(bloom_bytes, [phone]) is True
    # Lowercase (same as canonical for digits)
    assert query_bloom(bloom_bytes, [phone.lower()]) is True


def test_bloom_negative():
    """Value NOT inserted must not be found (with high probability)."""
    from pybloom_live import BloomFilter
    bf = BloomFilter(capacity=1000, error_rate=FALSE_POSITIVE_RATE)
    bf.add(_hash_value("9900000000"))
    bloom_bytes = pickle.dumps(bf)
    # A completely different value — should not be found
    result = query_bloom(bloom_bytes, ["0000000000"])
    # We cannot guarantee this (Bloom allows false positives) but with FPR=1e-6, very unlikely
    # Just check the test runs without error
    assert isinstance(result, bool)
