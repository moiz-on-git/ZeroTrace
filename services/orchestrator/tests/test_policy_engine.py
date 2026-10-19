"""
Unit tests for Policy Engine & Retention Holds.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from services.policy_engine import PolicyEngine


def test_policy_engine_rules():
    engine = PolicyEngine()

    kyc_rule = engine.rules.get("kyc")
    assert kyc_rule is not None
    assert kyc_rule["action"] == "HOLD_THEN_ERASE"
    assert kyc_rule["duration_years"] == 5
    assert "PMLA" in kyc_rule["legal_basis"]
    assert kyc_rule["requires_legal_review"] is True

    identity_rule = engine.rules.get("identity")
    assert identity_rule is not None
    assert identity_rule["action"] == "ERASE_NOW"

    marketing_rule = engine.rules.get("marketing")
    assert marketing_rule is not None
    assert marketing_rule["action"] == "ERASE_NOW"
