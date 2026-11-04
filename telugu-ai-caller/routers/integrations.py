"""
Integrations Router - Third-Party Providers, Company Profile & Voice Testing
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Response, Request
from core.auth import get_request_account_id
from loguru import logger

from config import DEFAULT_TTS_SPEAKER, DEFAULT_TTS_MODEL
from database import (
    get_company_profile,
    update_company_profile,
    get_all_provider_settings,
    upsert_provider_setting,
    record_provider_test_result,
)
from services.sarvam_service import sarvam_client
from providers import registry, ProviderType

router = APIRouter(tags=["integrations"])


@router.get("/api/profile")
async def api_get_profile(request: Request):
    acc_id = get_request_account_id(request) or 1
    return {"profile": get_company_profile(account_id=acc_id)}


@router.post("/api/profile")
async def api_update_profile(data: Dict[str, Any], request: Request):
    acc_id = get_request_account_id(request) or 1
    ok = update_company_profile(data, account_id=acc_id)
    return {"success": ok}


@router.post("/api/tts/test")
async def api_test_tts(payload: Dict[str, Any]):
    text = payload.get("text", "నమస్కారం! మేము మీ వ్యాపారం కోసం అధునాతన సాఫ్ట్‌వేర్ మరియు AI సేవలను అందిస్తున్నాము.")
    speaker = payload.get("speaker", DEFAULT_TTS_SPEAKER)
    model = payload.get("model", DEFAULT_TTS_MODEL)
    language_code = payload.get("language_code")

    try:
        audio_bytes = await sarvam_client.text_to_speech(
            text=text,
            language_code=language_code,
            speaker=speaker,
            model=model
        )
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        logger.error(f"TTS Test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/integrations/providers")
async def api_list_providers():
    """
    List all third-party providers with configuration status, activation, and recent test results.
    """
    providers_list = registry.list_all()
    db_settings = {f"{s['provider_type']}:{s['provider_name']}": s for s in get_all_provider_settings()}
    for p in providers_list:
        key = f"{p['type']}:{p['name']}"
        rec = db_settings.get(key, {})
        p["last_tested_at"] = rec.get("last_tested_at")
        p["test_status"] = rec.get("test_status", "untested")
        p["test_message"] = rec.get("test_message", "")
    return {"providers": providers_list}


def _resolve_provider_type(pt_str: str) -> ProviderType:
    s = pt_str.strip().lower()
    if s in ["leads", "lead", "discovery", "lead_discovery"]:
        return ProviderType.LEAD_DISCOVERY
    if s in ["voice", "tts", "voice_tts"]:
        return ProviderType.VOICE_TTS
    if s in ["stt", "voice_stt"]:
        return ProviderType.VOICE_STT
    return ProviderType(s)


@router.post("/api/integrations/providers/{provider_type}/{provider_name}")
async def api_update_provider(
    provider_type: str,
    provider_name: str,
    payload: Dict[str, Any]
):
    """Update configuration settings or enable/disable a specific provider."""
    try:
        p_type = _resolve_provider_type(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    provider = registry.get(p_type, provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found under '{provider_type}'")

    is_enabled = payload.get("is_enabled", provider.enabled)
    is_active = payload.get("is_active", False)
    config = payload.get("config", {})

    provider.enabled = bool(is_enabled)
    if config:
        provider.update_config(config)

    if is_active:
        registry.set_active(p_type, provider_name)

    upsert_provider_setting(
        provider_type=provider_type,
        provider_name=provider_name,
        is_enabled=provider.enabled,
        is_configured=provider.is_configured(),
        config=provider.get_masked_config()
    )

    return {
        "success": True,
        "provider": {
            "type": provider_type,
            "name": provider_name,
            "is_enabled": provider.enabled,
            "is_configured": provider.is_configured(),
            "config": provider.get_masked_config()
        }
    }


@router.post("/api/integrations/providers/{provider_type}/{provider_name}/test")
async def api_test_provider_connection(provider_type: str, provider_name: str):
    """Execute a live diagnostic connection test against the third-party provider API."""
    try:
        p_type = _resolve_provider_type(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    provider = registry.get(p_type, provider_name)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found under '{provider_type}'")

    test_result = await provider.test_connection()
    status_str = "success" if test_result.get("success") else "failed"
    message_str = test_result.get("message", "")

    record_provider_test_result(
        provider_type=provider_type,
        provider_name=provider_name,
        status=status_str,
        message=message_str
    )

    return {
        "provider_type": provider_type,
        "provider_name": provider_name,
        "result": test_result
    }

