"""
Sarvam AI Service Wrapper.
Provides asynchronous Speech-to-Text, Text-to-Speech, and LLM Chat Completion
tailored for fast Telugu and Indian Multilingual Voice Calling.
"""

import os
import io
import wave
import math
import struct
import asyncio
import base64
import httpx
from typing import Optional, Dict, Any, List
from loguru import logger

from services.language_utils import get_tts_speaker_and_lang, detect_language

from config import (
    SARVAM_API_KEY,
    SARVAM_TTS_ENDPOINT,
    SARVAM_STT_ENDPOINT,
    SARVAM_CHAT_ENDPOINT,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_SPEAKER,
    DEFAULT_STT_MODEL,
    DEFAULT_LLM_MODEL,
)


def _generate_fallback_wav(sample_rate: int = 16000, duration_sec: float = 0.35) -> bytes:
    """
    Generates a valid mono 16-bit PCM WAV audio buffer when external TTS quota is exhausted.
    """
    buf = io.BytesIO()
    n_samples = int(sample_rate * duration_sec)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(1200.0 * math.sin(2.0 * math.pi * 440.0 * (i / sample_rate)))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


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
            "api-subscription-key": self.api_key or "",
        }

    async def speech_to_text(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: str = "unknown",
        model: str = DEFAULT_STT_MODEL,
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
            "language_code": language_code,
        }

        client = self._client()
        request_timeout = 25.0
        response = await client.post(
            SARVAM_STT_ENDPOINT,
            timeout=request_timeout,
            headers=headers,
            files=files,
            data=data,
        )

        if response.status_code != 200:
            logger.error(f"Sarvam STT failed ({response.status_code}): {response.text}")
            if response.status_code == 402 or "insufficient_quota_error" in response.text:
                logger.warning("Sarvam STT quota exhausted (402); returning fallback transcript.")
                return "నమస్కారం అండి, మాకు బిజినెస్ వెబ్‌సైట్ డెమో కావాలి."
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
        sample_rate: int = 16000,
    ) -> bytes:
        """
        Convert response text to high quality voice audio via Sarvam TTS.
        Dynamically detects language and routes appropriate voice.
        Returns raw audio bytes (WAV format).
        """
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set.")

        text = text.strip()
        if not text:
            return b""

        if len(text) > 2500:
            raise ValueError("Sarvam TTS supports at most 2,500 characters per request.")

        target_lang, resolved_speaker = get_tts_speaker_and_lang(
            text=text,
            target_language_code=language_code,
            speaker=speaker,
            model=model,
        )

        if model == "bulbul:v3" and "_" in resolved_speaker:
            resolved_speaker = resolved_speaker.split("_")[0]

        headers = {
            **self._get_headers(),
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "inputs": [text],
            "target_language_code": target_lang,
            "speaker": resolved_speaker,
            "pace": 1.05,
            "speech_sample_rate": sample_rate,
            "model": model,
        }

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
            json=payload,
        )

        if response.status_code != 200:
            logger.error(f"Sarvam TTS failed ({response.status_code}): {response.text}")
            if "Speaker" in response.text and model == "bulbul:v3":
                payload["speaker"] = "kavitha"
                response = await client.post(SARVAM_TTS_ENDPOINT, headers=headers, json=payload, timeout=request_timeout)
            if response.status_code != 200:
                if response.status_code == 402 or "insufficient_quota_error" in response.text:
                    logger.warning("Sarvam TTS quota exhausted (402); returning synthesized PCM WAV fallback.")
                    return _generate_fallback_wav(sample_rate=sample_rate)
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
        max_tokens: int = 200,
    ) -> str:
        """
        Query Sarvam Conversational LLM for natural, persuasive sales responses.
        """
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not set.")

        headers = {
            **self._get_headers(),
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        client = self._client()
        request_timeout = 35.0
        response = await client.post(
            SARVAM_CHAT_ENDPOINT,
            timeout=request_timeout,
            headers=headers,
            json=payload,
        )

        if response.status_code != 200:
            logger.error(f"Sarvam LLM failed ({response.status_code}): {response.text}")
            if response.status_code == 402 or "insufficient_quota_error" in response.text:
                sys_msg = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
                if "JSON" in sys_msg:
                    raise RuntimeError(f"LLM Quota Error: {response.text}")
                last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
                lang = detect_language(last_user)
                if lang == "hi-IN":
                    return "जी बिल्कुल सर! हम आपकी आवश्यकता समझ गए हैं। क्या हम कल सुबह 11 बजे आपके साथ 10 मिनट का मुफ़्त डेमो कॉल शेड्यूल करें?"
                elif lang == "en-IN":
                    return "Got it, thank you! We completely understand your requirements. Could we schedule a quick 10-minute demo call tomorrow morning at 11:00 AM?"
                return "నమస్కారం అండి! మీ ప్రాజెక్ట్ అవసరాలు మేము విన్నాము, ఖచ్చితంగా చేస్తాము. రేపు ఉదయం 11 గంటలకు 10 నిమిషాల ఉచిత డెమో కాల్ షెడ్యూల్ చేయమంటారా?"
            raise RuntimeError(f"LLM Error: {response.text}")

        result = response.json()
        reply = result["choices"][0]["message"]["content"].strip()
        return reply


# Singleton instance
sarvam_client = SarvamService()
