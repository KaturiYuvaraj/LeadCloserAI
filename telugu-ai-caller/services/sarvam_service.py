"""
Sarvam AI Service Wrapper.
Provides asynchronous Speech-to-Text, Text-to-Speech, and LLM Chat Completion
tailored for fast Telugu and Indian Multilingual Voice Calling.
"""

import os
import asyncio
import base64
import httpx
from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from services.language_utils import get_tts_speaker_and_lang

from config import (
    SARVAM_API_KEY,
    SARVAM_TTS_ENDPOINT,
    SARVAM_STT_ENDPOINT,
    SARVAM_CHAT_ENDPOINT,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_SPEAKER,
    DEFAULT_STT_MODEL,
    DEFAULT_LLM_MODEL
)


class SarvamService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or SARVAM_API_KEY
        self._http: Optional[httpx.AsyncClient] = None
        self._http_loop = None
        if not self.api_key:
            logger.warning("Sarvam API key is not configured! Please check .env")

    def _client(self) -> httpx.AsyncClient:
        """
        Shared HTTP client so STT, LLM and TTS calls reuse one kept-alive TLS
        connection (saves ~0.3s per request vs opening a new connection).
        Recreated if the event loop changed (e.g. separate asyncio.run calls in tests).
        """
        loop = asyncio.get_running_loop()
        if self._http is None or self._http.is_closed or self._http_loop is not loop:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(35.0, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=60.0),
            )
            self._http_loop = loop
        return self._http

    def _get_headers(self) -> Dict[str, str]:
        return {
            "api-subscription-key": self.api_key,
        }

    async def speech_to_text(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: str = "unknown",
        model: str = DEFAULT_STT_MODEL
    ) -> str:
        """
        Transcribe spoken audio (Telugu, Hindi, English, Tenglish, Hinglish) using Sarvam STT.
        Default language_code='unknown' enables automatic language detection.
        """
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set.")

        headers = self._get_headers()
        files = {
            "file": (filename, audio_bytes, "audio/wav")
        }
        data = {
            "model": model,
            "language_code": language_code
        }

        client = self._client()
        request_timeout = 25.0
        response = await client.post(
            SARVAM_STT_ENDPOINT,
            timeout=request_timeout,
            headers=headers,
            files=files,
            data=data
        )

        if response.status_code != 200:
            logger.error(f"Sarvam STT failed ({response.status_code}): {response.text}")
            raise RuntimeError(f"STT Error: {response.text}")

        result = response.json()
        transcript = result.get("transcript", "").strip()
        logger.info(f"STT Transcription success: {transcript[:80]}...")
        return transcript

    async def text_to_speech(
        self,
        text: str,
        language_code: Optional[str] = None,
        speaker: Optional[str] = None,
        model: str = DEFAULT_TTS_MODEL,
        sample_rate: int = 16000
    ) -> bytes:
        """
        Convert response text to high quality voice audio via Sarvam TTS.
        Dynamically detects language and routes appropriate voice (Telugu, Hindi, or English).
        Returns raw audio bytes (WAV format).
        """
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set.")

        # Clean text
        text = text.strip()
        if not text:
            return b""

        if len(text) > 2500:
            raise ValueError("Sarvam TTS supports at most 2,500 characters per request.")

        # Resolve language and speaker dynamically
        target_lang, resolved_speaker = get_tts_speaker_and_lang(
            text=text,
            target_language_code=language_code,
            speaker=speaker,
            model=model
        )

        # If bulbul:v3 is used and speaker is a conversational tag, adapt
        if model == "bulbul:v3" and "_" in resolved_speaker:
            resolved_speaker = resolved_speaker.split("_")[0]  # e.g. kavitha_te_conversation -> kavitha

        headers = {
            **self._get_headers(),
            "Content-Type": "application/json"
        }

        payload = {
            "inputs": [text],
            "target_language_code": target_lang,
            "speaker": resolved_speaker,
            "pace": 1.05,
            "speech_sample_rate": sample_rate,
            "model": model
        }

        # Sarvam accepts pitch, loudness, and preprocessing only for the legacy
        # Bulbul v2 model. Sending those fields with v3/v4 produces validation
        # errors, so keep the request shape model-specific.
        if model == "bulbul:v2":
            payload.update({"pitch": 0, "loudness": 1.5, "enable_preprocessing": True})
        elif model in {"bulbul:v3", "bulbul:v4-flash"}:
            payload["temperature"] = 0.6

        client = self._client()
        request_timeout = 25.0
        response = await client.post(
            SARVAM_TTS_ENDPOINT,
            timeout=request_timeout,
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            logger.error(f"Sarvam TTS failed ({response.status_code}): {response.text}")
            # Fallback to standard speaker if needed
            if "Speaker" in response.text and model == "bulbul:v3":
                payload["speaker"] = "kavitha"
                response = await client.post(SARVAM_TTS_ENDPOINT, headers=headers, json=payload, timeout=request_timeout)
            if response.status_code != 200:
                raise RuntimeError(f"TTS Error: {response.text}")

        result = response.json()
        audios = result.get("audios", [])
        if not audios:
            raise RuntimeError("No audio returned from Sarvam TTS")

        audio_b64 = audios[0]
        audio_bytes = base64.b64decode(audio_b64)
        return audio_bytes

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = DEFAULT_LLM_MODEL,
        temperature: float = 0.5,
        max_tokens: int = 200
    ) -> str:
        """
        Query Sarvam Conversational LLM for natural, persuasive sales responses.
        """
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set.")

        headers = {
            **self._get_headers(),
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        client = self._client()
        request_timeout = 35.0
        response = await client.post(
            SARVAM_CHAT_ENDPOINT,
            timeout=request_timeout,
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            logger.error(f"Sarvam LLM failed ({response.status_code}): {response.text}")
            raise RuntimeError(f"LLM Error: {response.text}")

        result = response.json()
        reply = result["choices"][0]["message"]["content"].strip()
        return reply


# Singleton instance
sarvam_client = SarvamService()

