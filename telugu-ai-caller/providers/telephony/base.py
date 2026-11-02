"""
Telephony Provider Base Interface.
"""

from abc import abstractmethod
from typing import Optional, Dict, Any
from providers.base import BaseProvider, ProviderType


class BaseTelephonyProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.TELEPHONY)

    @abstractmethod
    async def initiate_outbound_call(
        self,
        to_phone: str,
        lead_id: Optional[int] = None,
        callback_host: Optional[str] = None
    ) -> Dict[str, Any]:
        """Trigger an outbound PSTN telephone call."""
        pass

    @abstractmethod
    def generate_stream_instruction(
        self,
        host: str,
        lead_id: Optional[int] = None
    ) -> str:
        """Generate response payload/XML instructing the telephony gateway to stream audio."""
        pass
