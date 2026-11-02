"""
Messaging Provider Base Interface.
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional
from providers.base import BaseProvider, ProviderType


class BaseMessagingProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.MESSAGING)

    @abstractmethod
    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str = "en",
        parameters: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send an approved business template message (e.g. brochure, meeting confirmation)."""
        pass

    @abstractmethod
    async def send_text_message(
        self,
        to_phone: str,
        message: str
    ) -> Dict[str, Any]:
        """Send standard text message to authorized/consented prospect."""
        pass

