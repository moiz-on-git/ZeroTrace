"""Unit tests for ZeroTrace ElevenLabs Voice Receipt Adapter."""

import os
import sys
import pytest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

try:
    from adapters.elevenlabs import ElevenLabsReceiptSpeaker
except ImportError:
    from src.adapters.elevenlabs import ElevenLabsReceiptSpeaker


@pytest.mark.asyncio
async def test_elevenlabs_receipt_script_english():
    speaker = ElevenLabsReceiptSpeaker()
    script = speaker.compose_receipt_script(
        receipt_id="rec_12345",
        solana_tx="5Kz9DevnetAnchorTxHash1111111111111111",
        records_erased=42,
        language="en",
    )
    assert "DPDP Act Section 6(4)" in script
    assert "42 personal records" in script
    assert "5Kz9Devn..." in script


@pytest.mark.asyncio
async def test_elevenlabs_receipt_script_regional():
    speaker = ElevenLabsReceiptSpeaker()
    hindi = speaker.compose_receipt_script("rec_1", "tx_123", 5, "hi")
    assert "सत्यापन" in hindi
    kannada = speaker.compose_receipt_script("rec_1", "tx_123", 5, "kn")
    assert "ದೃಢೀಕರಣ" in kannada
    tamil = speaker.compose_receipt_script("rec_1", "tx_123", 5, "ta")
    assert "சரிபார்ப்பு" in tamil


@pytest.mark.asyncio
async def test_elevenlabs_offline_fallback():
    speaker = ElevenLabsReceiptSpeaker(api_key="")
    audio = await speaker.generate_speech_bytes("Test script")
    assert len(audio) > 0
    assert audio.startswith(b"\xFF\xFB\x90\x00")
