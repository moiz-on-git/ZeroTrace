"""
Tests: attack evidence masking, identifier variants, PII never in logs.
"""
import pytest
from src.audit.attack_library import _mask, _build_variants, _contains_any
from src.seed.subjects import HERO


def test_mask_phone():
    masked = _mask(HERO.phone)
    # Original phone must NOT appear in masked output
    assert HERO.phone not in masked
    assert "•" in masked


def test_mask_email():
    masked = _mask(HERO.email)
    assert HERO.email not in masked
    assert "•" in masked


def test_mask_short_value():
    assert _mask("ab") == "****"


def test_build_variants_phone():
    identifiers = [{"type": "phone", "value": HERO.phone}]
    variants = _build_variants(identifiers)
    assert HERO.phone in variants
    assert f"+91{HERO.phone}" in variants
    assert f"91{HERO.phone}" in variants
    assert f"0{HERO.phone}" in variants


def test_build_variants_email():
    identifiers = [{"type": "email", "value": HERO.email}]
    variants = _build_variants(identifiers)
    assert HERO.email in variants
    assert HERO.email.upper() in variants
    assert HERO.email.split("@")[0] in variants


def test_contains_any_found():
    text = f"Customer phone: {HERO.phone}"
    found, matched = _contains_any(text, [HERO.phone])
    assert found is True
    assert matched == HERO.phone


def test_contains_any_not_found():
    text = "No personal data here."
    found, matched = _contains_any(text, [HERO.phone, HERO.email])
    assert found is False
    assert matched == ""


def test_contains_any_case_insensitive():
    text = f"Email: {HERO.email.upper()}"
    found, matched = _contains_any(text, [HERO.email.lower()])
    assert found is True
