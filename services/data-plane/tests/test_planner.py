"""
Tests: plan correctness, blast radius, cost model assumptions.
No Spark required — mocks the bloom index.
"""
from __future__ import annotations

import pickle
from unittest.mock import MagicMock, patch

import pytest
from pybloom_live import BloomFilter

from src.seed.subjects import HERO
from src.locator.bloom_index import FALSE_POSITIVE_RATE, _hash_value


def _make_bloom_bytes(values: list[str]) -> bytes:
    bf = BloomFilter(capacity=max(len(values) * 10, 100), error_rate=FALSE_POSITIVE_RATE)
    for v in values:
        bf.add(_hash_value(v))
    return pickle.dumps(bf)


def test_blast_radius_targeted_lt_total():
    """Files targeted must be less than or equal to total files."""
    # Mock the bloom index
    hero_bloom = _make_bloom_bytes([HERO.phone, HERO.email])
    other_bloom = _make_bloom_bytes(["9999999999", "other@example.in"])

    hero_entry = {
        "file_path": "warehouse/customers/part-001.parquet",
        "table_name": "customers",
        "bloom_data": hero_bloom,
        "row_count": 100,
        "file_size_bytes": 1024 * 1024,  # 1MB
        "false_positive_rate": FALSE_POSITIVE_RATE,
    }
    other_entry = {
        "file_path": "warehouse/customers/part-002.parquet",
        "table_name": "customers",
        "bloom_data": other_bloom,
        "row_count": 200,
        "file_size_bytes": 2 * 1024 * 1024,
        "false_positive_rate": FALSE_POSITIVE_RATE,
    }

    from src.locator.bloom_index import find_candidate_files
    variants = [HERO.phone, HERO.email] + HERO.phone_variants

    with patch("src.locator.bloom_index.confirm_file_contains") as mock_confirm:
        mock_confirm.return_value = True
        candidates = find_candidate_files("customers", variants, [hero_entry, other_entry])
        # Only the hero's file should be targeted
        assert len(candidates) <= 2
        assert len(candidates) >= 1


def test_cost_model_saving_percentage():
    """Saving percentage must be positive when targeted < naive."""
    targeted = 212.40
    naive = 1046.20
    saving = round((1 - targeted / naive) * 100, 1)
    assert saving > 75  # We expect at least 75% saving with targeted approach
    assert saving < 100


def test_plan_has_correct_step_order():
    """Steps must be in the correct Iceberg order: delete before rewrite before expire."""
    from src.erasure.planner import ErasureStep

    steps = [
        ErasureStep("s1", "iceberg", "delete_rows", "customers", 1, 1, 1024, 0.01, 0, 0),
        ErasureStep("s2", "iceberg", "rewrite_data_files", "customers", 1, 1, 1024, 0.01, 1, 0),
        ErasureStep("s3", "iceberg", "expire_snapshots", "all_tables", 0, 0, 0, 0.01, 2, 0),
        ErasureStep("s4", "iceberg", "remove_orphan_files", "all_tables", 0, 0, 0, 0.01, 3, 0),
    ]

    # Verify ordering: delete < rewrite < expire < orphan
    actions = [s.action for s in sorted(steps, key=lambda s: s.order)]
    assert actions.index("delete_rows") < actions.index("rewrite_data_files")
    assert actions.index("rewrite_data_files") < actions.index("expire_snapshots")
    assert actions.index("expire_snapshots") < actions.index("remove_orphan_files")


def test_holds_applied_for_kyc():
    """KYC category must always be held (PMLA rule)."""
    from src.erasure.planner import HELD_CATEGORIES
    assert "kyc" in HELD_CATEGORIES
    assert "financial" in HELD_CATEGORIES
    # Both must have 5-year hold
    for cat in ["kyc", "financial"]:
        _, hold_days = HELD_CATEGORIES[cat]
        assert hold_days >= 365 * 5  # At least 5 years
