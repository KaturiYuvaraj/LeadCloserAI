"""
Provider Package Initializer and Registry Bootstrapper.
"""

import os
from providers.base import registry, ProviderType, ProviderStatus, BaseProvider
from providers.voice.sarvam_stt import SarvamSTTProvider
from providers.voice.sarvam_tts import SarvamTTSProvider
from providers.llm.sarvam_llm import SarvamLLMProvider
from providers.telephony.vobiz import VobizTelephonyProvider
from providers.telephony.exotel import ExotelTelephonyProvider
from providers.telephony.twilio_legacy import TwilioTelephonyProvider
from providers.leads.apollo import ApolloLeadProvider
from providers.leads.apify import ApifyLeadProvider
from providers.messaging.meta_whatsapp import MetaWhatsAppProvider
from providers.calendar.google_calendar import GoogleCalendarProvider
from providers.storage.sqlite_storage import SQLiteStorageProvider


def initialize_providers():
    """Register all available third-party providers with their default activations."""
    # Voice STT & TTS (Sarvam AI is the active native Indic voice engine)
    sarvam_stt = SarvamSTTProvider()
    sarvam_tts = SarvamTTSProvider()
    registry.register(sarvam_stt, is_default=True)
    registry.register(sarvam_tts, is_default=True)

    # LLM (Sarvam 105B Conversational)
    sarvam_llm = SarvamLLMProvider()
    registry.register(sarvam_llm, is_default=True)

    # Telephony (Vobiz is the active carrier; Exotel/Twilio are legacy/optional)
    vobiz = VobizTelephonyProvider()
    exotel = ExotelTelephonyProvider()
    twilio = TwilioTelephonyProvider()
    is_vobiz_active = vobiz.is_configured() or os.getenv("DIALER_PROVIDER", "").lower() == "vobiz"
    registry.register(vobiz, is_default=is_vobiz_active)
    registry.register(exotel, is_default=not is_vobiz_active)
    registry.register(twilio, is_default=False)

    # Lead Discovery
    apollo = ApolloLeadProvider()
    apify = ApifyLeadProvider()
    registry.register(apollo, is_default=True)
    registry.register(apify, is_default=False)

    # Messaging
    whatsapp = MetaWhatsAppProvider()
    registry.register(whatsapp, is_default=True)

    # Calendar
    gcal = GoogleCalendarProvider()
    registry.register(gcal, is_default=True)

    # Storage
    sqlite_storage = SQLiteStorageProvider()
    registry.register(sqlite_storage, is_default=True)


def sync_providers_with_db():
    """Sync registered provider statuses with database settings."""
    try:
        from database import get_all_provider_settings, upsert_provider_setting
        db_settings = {f"{s['provider_type']}:{s['provider_name']}": s for s in get_all_provider_settings()}

        for item in registry.list_all():
            key = f"{item['type']}:{item['name']}"
            if key in db_settings:
                # Load enabled state from DB
                provider = registry.get(ProviderType(item['type']), item['name'])
                if provider:
                    provider.enabled = bool(db_settings[key]['is_enabled'])
            else:
                # Seed default entry in DB
                upsert_provider_setting(
                    provider_type=item['type'],
                    provider_name=item['name'],
                    is_enabled=item['is_enabled'],
                    is_configured=item['is_configured'],
                    config=item['config']
                )
    except Exception:
        pass


# Initialize on import
initialize_providers()

__all__ = [
    "registry",
    "ProviderType",
    "ProviderStatus",
    "BaseProvider",
    "initialize_providers",
    "sync_providers_with_db"
]
