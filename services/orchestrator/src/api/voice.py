"""ZeroTrace Voice & Speech API Router (Sarvam AI & Indic Audio)."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from adapters.sarvam import SarvamAdapter
from core.logging import logger

router = APIRouter(prefix="/voice", tags=["Voice & Indic AI"])
sarvam_adapter = SarvamAdapter()


class SarvamTTSRequest(BaseModel):
    text: str = Field(..., description="Text to synthesize in Indian scheduled languages")
    target_language_code: str = Field("hi-IN", description="ISO language code: hi-IN, kn-IN, ta-IN, te-IN, en-IN")
    speaker: Optional[str] = Field("shubh_enhi_ads", description="Sarvam speaker identifier")


class SarvamTTSResponse(BaseModel):
    status: str
    language: str
    speaker: str
    audio_base64: str
    sample_rate: int = 8000
    model: str = "bulbul:v4-flash"


@router.post("/sarvam/tts", response_model=SarvamTTSResponse)
async def generate_sarvam_tts(req: SarvamTTSRequest):
    """Synthesize high-fidelity Indic voice using Sarvam AI 'bulbul:v4-flash'."""
    try:
        import base64
        audio_bytes = await sarvam_adapter.synthesize_speech(
            text=req.text,
            target_language_code=req.target_language_code,
            speaker=req.speaker,
        )
        return SarvamTTSResponse(
            status="ok",
            language=req.target_language_code,
            speaker=req.speaker or "shubh_enhi_ads",
            audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
        )
    except Exception as e:
        logger.error("sarvam_tts_api_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Sarvam TTS failed: {str(e)}")
