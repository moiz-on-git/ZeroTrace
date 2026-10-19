"""
Tests: seed determinism, hero/decoy presence, ghost embedding.
"""
import pytest
from src.seed.generator import generate_all_rows, PROFILES
from src.seed.subjects import HERO, DECOY_1, DECOY_2


def test_seed_determinism():
    """Same seed produces identical output on two runs."""
    rows_a = generate_all_rows("small", seed=42)
    rows_b = generate_all_rows("small", seed=42)
    assert rows_a["customers"][0]["customer_id"] == rows_b["customers"][0]["customer_id"]
    assert rows_a["customers"][0]["phone"] == rows_b["customers"][0]["phone"]
    assert len(rows_a["customers"]) == len(rows_b["customers"])


def test_hero_present():
    """Hero subject must be in the customers table."""
    rows = generate_all_rows("small", seed=42)
    customer_ids = {r["customer_id"] for r in rows["customers"]}
    assert HERO.customer_id in customer_ids


def test_decoys_present():
    """Both decoys must be present."""
    rows = generate_all_rows("small", seed=42)
    customer_ids = {r["customer_id"] for r in rows["customers"]}
    assert DECOY_1.customer_id in customer_ids
    assert DECOY_2.customer_id in customer_ids


def test_hero_not_same_as_decoy():
    """Hero and decoys must have different phones."""
    assert HERO.phone != DECOY_1.phone
    assert HERO.phone != DECOY_2.phone
    assert HERO.email != DECOY_1.email


def test_hero_has_tickets_and_transcripts():
    """Hero should have multiple tickets and transcripts (data spread across files)."""
    rows = generate_all_rows("small", seed=42)
    hero_tickets = [r for r in rows["support_tickets"] if r["customer_id"] == HERO.customer_id]
    hero_transcripts = [r for r in rows["call_transcripts"] if r["customer_id"] == HERO.customer_id]
    assert len(hero_tickets) >= 3
    assert len(hero_transcripts) >= 3


def test_profile_sizes():
    """Small profile produces fewer rows than showtime."""
    small = generate_all_rows("small", seed=42)
    assert len(small["customers"]) == PROFILES["small"]["n_customers"] + 3  # +3 for hero/decoys


def test_phone_variants():
    """Hero phone variants are generated correctly."""
    variants = HERO.phone_variants
    assert HERO.phone in variants
    assert f"+91{HERO.phone}" in variants
    assert f"0{HERO.phone}" in variants
    assert len(variants) >= 6
