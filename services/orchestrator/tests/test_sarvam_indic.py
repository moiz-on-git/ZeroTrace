"""Unit tests for ZeroTrace Sarvam AI Indic Speech & Voice Adapter."""

import os
import sys
import pytest

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

try:
    from adapters.sarvam import SarvamAdapter
except ImportError:
    from src.adapters.sarvam import SarvamAdapter


@pytest.mark.asyncio
async def test_sarvam_adapter_initialization():
    adapter = SarvamAdapter()
    assert adapter.stt_model == "saaras:v4"
    assert adapter.tts_model == "bulbul:v4-flash"
    assert adapter.tts_speaker == "shubh_enhi_ads"
    assert adapter.endpoint is not None


@pytest.mark.asyncio
async def test_sarvam_tts_synthesis():
    adapter = SarvamAdapter()
    audio = await adapter.synthesize_speech(
        text="ZeroTrace verification is complete.",
        target_language_code="en-IN",
    )
    assert len(audio) > 0
    # Valid RIFF / WAV header
    assert audio.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_sarvam_transcription_offline_or_online():
    adapter = SarvamAdapter()
    transcript, lang, conf = await adapter.transcribe(
        audio_bytes=b"dummy-audio-bytes",
        language_hint="kn-IN",
    )
    assert "ಒಪ್ಪಿಗೆ" in transcript or len(transcript) > 0
    assert lang == "kn-IN"
    assert conf >= 0.90
