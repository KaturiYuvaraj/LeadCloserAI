"""
Large Language Model (LLM) Provider Base Interface.
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional
from providers.base import BaseProvider, ProviderType


class BaseLLMProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.LLM)

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.5,
        max_tokens: int = 200
    ) -> str:
        """Generate conversational or analytical completion."""
        pass

    @abstractmethod
    async def extract_intelligence(
        self,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Extract structured sales deal analytics in executive English."""
        pass
