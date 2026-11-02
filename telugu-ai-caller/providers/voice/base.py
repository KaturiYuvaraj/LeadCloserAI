"""
Voice STT and TTS Provider Base Interfaces.
"""

from abc import abstractmethod
from typing import Optional
from providers.base import BaseProvider, ProviderType


class BaseVoiceSTTProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.VOICE_STT)

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: str = "unknown"
    ) -> str:
        """Transcribe spoken audio bytes into text."""
        pass


class BaseVoiceTTSProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.VOICE_TTS)

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language_code: Optional[str] = None,
        speaker: Optional[str] = None
    ) -> bytes:
        """Synthesize text into speech audio bytes (WAV/PCM)."""
        pass

