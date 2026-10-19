"""
ZeroTrace Audio Transcoder Adapter.
Transcodes webm, ogg, mp4, m4a, and wav audio to 16 kHz mono PCM WAV format.
Uses ffmpeg subprocess if installed, with seamless raw-bytes fallback.
"""

from __future__ import annotations
import shutil
import subprocess
import tempfile
import os
from typing import Tuple
from core.logging import logger


class AudioTranscoder:
    @staticmethod
    def is_ffmpeg_available() -> bool:
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def transcode_to_16k_mono_wav(audio_bytes: bytes, source_ext: str = "webm") -> Tuple[bytes, bool]:
        """
        Converts arbitrary audio stream into 16 kHz, 16-bit mono WAV.
        Returns: (transcoded_bytes, success_bool)
        """
        if not AudioTranscoder.is_ffmpeg_available():
            logger.warn("ffmpeg_not_available_using_raw_bytes")
            return audio_bytes, False

        ext = source_ext.lstrip(".")
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as in_file:
            in_file.write(audio_bytes)
            in_path = in_file.name

        out_path = in_path + ".wav"

        try:
            # ffmpeg -y -i <in> -ar 16000 -ac 1 -c:a pcm_s16le <out>
            cmd = [
                "ffmpeg",
                "-y",
                "-i", in_path,
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                out_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            with open(out_path, "rb") as f:
                transcoded = f.read()
            logger.info("audio_transcoded_to_16k_mono", in_bytes=len(audio_bytes), out_bytes=len(transcoded))
            return transcoded, True
        except Exception as e:
            logger.warn("ffmpeg_transcode_failed_fallback", error=str(e))
            return audio_bytes, False
        finally:
            if os.path.exists(in_path):
                os.remove(in_path)
            if os.path.exists(out_path):
                os.remove(out_path)
