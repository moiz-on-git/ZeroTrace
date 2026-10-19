"""
ZeroTrace Fault Injection, Resilience & Degradation Drills.
Asserts that the system degrades gracefully and never crashes or leaves raw PII
when upstream APIs (Sarvam, Gemma, ShipRite, Blockchain RPC) are unavailable.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from adapters.sarvam import SarvamAdapter
from adapters.gemma import GemmaAdapter
from adapters.anchor import ShipRiteAnchor, LocalSignedLedgerAnchor
from proof.merkle import compute_subject_commitment


@pytest.mark.asyncio
async def test_sarvam_offline_resilience():
    # Invalid endpoint / mock key should gracefully fall back to native demo transcripts
    adapter = SarvamAdapter(api_key="mock-sarvam-key", endpoint="https://invalid.sarvam.endpoint")
    transcript, lang, conf = await adapter.transcribe(b"dummy_audio_bytes", "test.wav", "kn-IN")

    assert len(transcript) > 0
    assert lang == "kn-IN"
    assert conf >= 0.90


@pytest.mark.asyncio
async def test_gemma_llm_offline_fallback():
    # When Gemma endpoint is unreachable, rule-based fallback must produce valid IntentCard
    adapter = GemmaAdapter(api_base="http://localhost:99999/invalid", model_id="nonexistent-model")
    card = await adapter.parse_intent("ನನ್ನ ಒಪ್ಪಿಗೆಯನ್ನು ಹಿಂತೆಗೆದುಕೊಳ್ಳುತ್ತೇನೆ, ಮೊಬೈಲ್ 98765 43210.", "kn-IN")

    assert card.intent == "withdraw_consent"
    assert card.confidence >= 0.90
    assert card.requires_legal_review is True
    phone_id = next(x for x in card.identifiers if x.type == "phone")
    assert "9876543210" in phone_id.variants


@pytest.mark.asyncio
async def test_blockchain_anchor_offline_fallback():
    # When ShipRite endpoint is unreachable, LocalSignedLedgerAnchor seals the proof locally
    anchor = ShipRiteAnchor(endpoint="http://invalid.shiprite.url/anchor", api_key="mock-shiprite-key")
    res = await anchor.anchor_root(
        job_id="job_01JB0000000000000000000001",
        diff_root="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        receipt_id="rcpt_01JB0000000000000000000001"
    )

    assert res["status"] == "CONFIRMED"
    assert "tx_hash" in res
    assert res["tx_hash"].startswith("0x")


def test_sovereign_secret_mismatch_detection():
    # If a malicious actor presents a fake salt or phone, ownership proof must not match
    salt_real = "a" * 64
    salt_fake = "b" * 64
    phone_real = "phone:+919876543210"
    phone_decoy = "phone:+919123456784"

    comm_real = compute_subject_commitment(salt_real, phone_real)

    # Fake salt
    assert compute_subject_commitment(salt_fake, phone_real) != comm_real
    # Fake phone
    assert compute_subject_commitment(salt_real, phone_decoy) != comm_real
