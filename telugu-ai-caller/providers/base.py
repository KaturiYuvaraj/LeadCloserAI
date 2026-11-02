"""
Base Provider Interfaces & Provider Registry for AI Sales Automation Platform.
Guarantees decoupling between application business logic and specific third-party APIs.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List, Type


class ProviderType(str, Enum):
    VOICE_STT = "voice_stt"
    VOICE_TTS = "voice_tts"
    LLM = "llm"
    TELEPHONY = "telephony"
    LEAD_DISCOVERY = "lead_discovery"
    MESSAGING = "messaging"
    CALENDAR = "calendar"
    STORAGE = "storage"


class ProviderStatus(str, Enum):
    ACTIVE = "active"
    CONFIGURED = "configured"
    UNCONFIGURED = "unconfigured"
    DISABLED = "disabled"
    ERROR = "error"


class BaseProvider(ABC):
    """Abstract base class for all third-party service providers."""

    def __init__(self, provider_name: str, provider_type: ProviderType):
        self.provider_name = provider_name
        self.provider_type = provider_type
        self.enabled = True
        self._config: Dict[str, Any] = {}

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if all mandatory credentials and configurations are set."""
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Execute an actual lightweight test call against the external API.
        Returns:
            {
                "success": bool,
                "latency_ms": float,
                "message": str,
                "details": dict
            }
        """
        pass

    @abstractmethod
    def get_masked_config(self) -> Dict[str, Any]:
        """Return configuration dictionary with sensitive API keys and tokens masked."""
        pass

    def update_config(self, new_config: Dict[str, Any]):
        """Update internal configuration with new values."""
        self._config.update(new_config)

    def mask_secret(self, secret: Optional[str], visible_chars: int = 4) -> str:
        """Helper to mask sensitive credentials."""
        if not secret:
            return ""
        s = str(secret).strip()
        if len(s) <= visible_chars * 2:
            return "********"
        return f"{s[:visible_chars]}****{s[-visible_chars:]}"


class ProviderRegistry:
    """Central registry and factory for all third-party integration providers."""

    def __init__(self):
        self._providers: Dict[ProviderType, Dict[str, BaseProvider]] = {
            pt: {} for pt in ProviderType
        }
        self._active_provider: Dict[ProviderType, Optional[str]] = {
            pt: None for pt in ProviderType
        }

    def register(self, provider: BaseProvider, is_default: bool = False):
        """Register a provider instance in the registry."""
        p_type = provider.provider_type
        p_name = provider.provider_name
        self._providers[p_type][p_name] = provider
        if is_default or self._active_provider[p_type] is None:
            self._active_provider[p_type] = p_name

    def set_active(self, provider_type: ProviderType, provider_name: str) -> bool:
        """Set the active provider for a given capability domain."""
        if provider_name in self._providers[provider_type]:
            self._active_provider[provider_type] = provider_name
            return True
        return False

    def get(self, provider_type: ProviderType, provider_name: Optional[str] = None) -> Optional[BaseProvider]:
        """Get an active or specifically named provider instance."""
        target_name = provider_name or self._active_provider[provider_type]
        if target_name:
            return self._providers[provider_type].get(target_name)
        return None

    def get_active(self, provider_type: ProviderType) -> Optional[BaseProvider]:
        """Convenience method to get the active provider for a capability domain."""
        return self.get(provider_type)

    def list_all(self) -> List[Dict[str, Any]]:
        """List metadata and status for all registered providers."""
        items = []
        for p_type, providers_dict in self._providers.items():
            active_name = self._active_provider[p_type]
            for p_name, provider in providers_dict.items():
                is_active = (p_name == active_name)
                is_conf = provider.is_configured()
                status = ProviderStatus.ACTIVE if (is_active and is_conf and provider.enabled) else (
                    ProviderStatus.CONFIGURED if is_conf else ProviderStatus.UNCONFIGURED
                )
                items.append({
                    "type": p_type.value,
                    "name": p_name,
                    "is_active": is_active,
                    "is_enabled": provider.enabled,
                    "is_configured": is_conf,
                    "status": status.value,
                    "config": provider.get_masked_config()
                })
        return items


# Global provider registry singleton
registry = ProviderRegistry()
