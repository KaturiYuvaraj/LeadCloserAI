"""
Sarvam AI Speech-to-Text Provider Implementation.
"""

import time
import io
import wave
from typing import Dict, Any
from loguru import logger

from providers.voice.base import BaseVoiceSTTProvider
from services.sarvam_service import sarvam_client
from config import SARVAM_API_KEY, DEFAULT_STT_MODEL


class SarvamSTTProvider(BaseVoiceSTTProvider):
    def __init__(self):
        super().__init__(provider_name="sarvam_stt")
        self.api_key = SARVAM_API_KEY
        self.default_model = DEFAULT_STT_MODEL

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "api_key": self.mask_secret(self.api_key),
            "model": self.default_model,
            "supported_languages": ["te-IN", "hi-IN", "en-IN", "ta-IN", "kn-IN", "unknown"]
        }

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: str = "unknown"
    ) -> str:
        return await sarvam_client.speech_to_text(
            audio_bytes=audio_bytes,
            filename=filename,
            language_code=language_code,
            model=self.default_model
        )

    async def test_connection(self) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {
                "success": False,
                "latency_ms": 0,
                "message": "Sarvam API Key is missing in environment (.env).",
                "details": {"error": "UNCONFIGURED"}
            }

        # Generate a minimal 0.25s silence WAV to verify Sarvam API credentials
        try:
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b'\x00' * 8000)
            test_wav = buf.getvalue()

            # Attempt transcription
            _ = await self.transcribe(test_wav)
            latency = round((time.time() - start) * 1000, 1)
            return {
                "success": True,
                "latency_ms": latency,
                "message": f"Sarvam STT connection verified successfully ({latency}ms).",
                "details": {"model": self.default_model}
            }
        except Exception as e:
            latency = round((time.time() - start) * 1000, 1)
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"Sarvam STT test failed: {str(e)}",
                "details": {"error": str(e)}
            }

