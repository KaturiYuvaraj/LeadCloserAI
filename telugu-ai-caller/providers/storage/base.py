"""
Storage Provider Base Interface.
"""

from abc import abstractmethod
from typing import Dict, Any, List, Optional
from providers.base import BaseProvider, ProviderType


class BaseStorageProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.STORAGE)

    @abstractmethod
    def get_connection(self) -> Any:
        pass
