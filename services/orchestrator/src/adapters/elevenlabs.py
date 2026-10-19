"""ZeroTrace ElevenLabs Voice Receipt Adapter (Experience Plane).

Provides DPDP Act Sec 5(3) accessibility-compliant multilingual spoken
verification receipts and voice alerts for Data Principals.

Under DPDP Act 2023 Sec 5(3), consent notices and confirmation of erasure must
be accessible to all citizens across Indian scheduled languages. ElevenLabs
generates ultra-realistic regional speech receipts for low-literacy or
visually impaired users.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
import httpx
import structlog

logger = structlog.get_logger("zerotrace.elevenlabs")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel / neutral default
DEFAULT_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


class ElevenLabsReceiptSpeaker:
    """Generates audio verification receipts for Data Principals."""

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None):
        self.api_key = api_key or ELEVENLABS_API_KEY
        self.voice_id = voice_id or ELEVENLABS_VOICE_ID

    def compose_receipt_script(
        self,
        receipt_id: str,
        solana_tx: str,
        records_erased: int,
        language: str = "en",
    ) -> str:
        """Compose legal confirmation script in specified language."""
        short_tx = solana_tx[:8] + "..." if len(solana_tx) > 8 else solana_tx
        
        if language == "hi":
            return (
                f"ज़ीरोट्रेस सत्यापन। डीपी डी पी अधिनियम 2023 की धारा 6(4) के तहत, "
                f"आपके {records_erased} रिकॉर्ड्स को हमेशा के लिए मिटा दिया गया है। "
                f"सोलाना ब्लॉकचेन पर पुष्टिकरण ट्रांजेक्शन है: {short_tx}।"
            )
        elif language == "kn":
            return (
                f"ಜೀರೋಟ್ರೇಸ್ ದೃಢೀಕರಣ. ಡಿಪಿಡಿಪಿ ಕಾಯ್ದೆ 2023 ರ ಅಡಿಯಲ್ಲಿ, "
                f"ನಿಮ್ಮ {records_erased} ದಾಖಲೆಗಳನ್ನು ಶಾಶ್ವತವಾಗಿ ಅಳಿಸಲಾಗಿದೆ. "
                f"ಸೊಲಾನಾ ಬ್ಲಾಕ್‌ಚೈನ್ ಪುರಾವೆ: {short_tx}."
            )
        elif language == "ta":
            return (
                f"ஜீரோட்ரேஸ் சரிபார்ப்பு. டிபிடிபி சட்டம் 2023 பிரிவு 6(4) படி, "
                f"உங்கள் {records_erased} பதிவுகள் நிரந்தரமாக நீக்கப்பட்டுள்ளன. "
                f"சோலானா பிளாக்செயின் சான்று: {short_tx}."
            )
        else:
            return (
                f"ZeroTrace verification confirmed. Under DPDP Act Section 6(4), "
                f"{records_erased} personal records have been permanently erased. "
                f"Cryptographic proof anchored on Solana with transaction {short_tx}. "
                f"Your digital trace is zero."
            )

    async def generate_speech_bytes(
        self,
        text: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> bytes:
        """Generate speech MP3 bytes. Falls back to simulated audio if API key is not configured."""
        if not self.api_key:
            logger.info("elevenlabs.offline_simulation", reason="no_api_key_configured")
            # Synthesize minimal valid MP3 frame header / placeholder
            return b"\xFF\xFB\x90\x00ZeroTraceAudioReceiptMock"

        url = f"{DEFAULT_API_URL}/{self.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        async with (client or httpx.AsyncClient(timeout=10.0)) as c:
            response = await c.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.content
            logger.warning("elevenlabs.api_error", status_code=response.status_code, body=response.text[:200])
            return b"\xFF\xFB\x90\x00ZeroTraceFallbackAudio"
