"""
Sarvam AI Text-to-Speech Provider Implementation.
"""

import time
from typing import Dict, Any, Optional
from loguru import logger

from providers.voice.base import BaseVoiceTTSProvider
from services.sarvam_service import sarvam_client
from config import SARVAM_API_KEY, DEFAULT_TTS_MODEL, DEFAULT_TTS_SPEAKER


class SarvamTTSProvider(BaseVoiceTTSProvider):
    def __init__(self):
        super().__init__(provider_name="sarvam_tts")
        self.api_key = SARVAM_API_KEY
        self.default_model = DEFAULT_TTS_MODEL
        self.default_speaker = DEFAULT_TTS_SPEAKER

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def get_masked_config(self) -> Dict[str, Any]:
        return {
            "api_key": self.mask_secret(self.api_key),
            "model": self.default_model,
            "default_speaker": self.default_speaker,
            "supported_voices": ["kavitha_te_conversation", "aditya_hi_sales", "simran_en_sales", "meera_ta_conversation", "shreya_kn_conversation", "arya_ml_conversation"]
        }

    async def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
        speaker: Optional[str] = None
    ) -> bytes:
        return await sarvam_client.text_to_speech(
            text=text,
            language_code=language_code,
            speaker=speaker or self.default_speaker,
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

        try:
            # Synthesize short test greeting
            test_phrase = "నమస్కారం! టెస్ట్ కాల్."
            audio_bytes = await self.synthesize(text=test_phrase, language_code="te-IN")
            latency = round((time.time() - start) * 1000, 1)

            if len(audio_bytes) > 100:
                return {
                    "success": True,
                    "latency_ms": latency,
                    "message": f"Sarvam TTS synthesis verified ({len(audio_bytes)} bytes audio, {latency}ms).",
                    "details": {"model": self.default_model, "bytes": len(audio_bytes)}
                }
            else:
                return {
                    "success": False,
                    "latency_ms": latency,
                    "message": "TTS returned empty or invalid audio buffer.",
                    "details": {}
                }
        except Exception as e:
            latency = round((time.time() - start) * 1000, 1)
            return {
                "success": False,
                "latency_ms": latency,
                "message": f"Sarvam TTS test failed: {str(e)}",
                "details": {"error": str(e)}
            }

