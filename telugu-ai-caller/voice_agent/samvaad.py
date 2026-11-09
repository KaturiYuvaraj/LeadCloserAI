"""
Sarvam's own voice agent (Samvaad, "Shriya") as a second calling engine, for side-by-side tests.

With the engine set to "samvaad" the dialer still runs every calling rule (consent, Do-Not-Call,
calling hours), then asks Sarvam to place the call through its Instant Outbound API instead of
connecting the call to our Pipecat engine:

  POST https://apps.sarvam.ai/api/outbounds/v1/orgs/{org}/workspaces/{ws}/outbounds   (X-API-Key)

Sarvam talks to the customer over the same Vobiz number and, after the call, POSTs the result to
/api/voice/samvaad/webhook (status, duration, English transcript, the agent's variables), which is
saved like any other call. Sarvam bills these calls itself: about ₹3.50 a minute, rounded up per call.

Sarvam Agent calls are tests: they never schedule automatic follow-up calls, and a call Sarvam never
reports on is closed without dialling again (so nobody is charged twice).

.env: SAMVAAD_API_KEY, SAMVAAD_ORG_ID, SAMVAAD_WORKSPACE_ID, SAMVAAD_APP_ID, SAMVAAD_APP_VERSION,
SAMVAAD_CONNECTION_ID, SAMVAAD_AGENT_NUMBER (defaults to VOBIZ_CALLER_ID).
The engine choice is kept in call_engine.json so it survives a restart.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from voice_agent.outbound import BaseDialer, DialError, DialRequest, _callback_query, public_base_url

BASE_DIR = Path(__file__).resolve().parent.parent
API_BASE = "https://apps.sarvam.ai/api/outbounds/v1"

ENGINES = {"pipecat": "Our engine (Shreya)", "samvaad": "Sarvam Agent (Shriya)"}
DEFAULT_ENGINE = "pipecat"

LANGUAGE_NAMES = {"te-IN": "Telugu", "hi-IN": "Hindi", "en-IN": "English",
                  "ta-IN": "Tamil", "kn-IN": "Kannada", "ml-IN": "Malayalam"}

SETTINGS = {
    "SAMVAAD_API_KEY": "API key (Settings → API Key)",
    "SAMVAAD_ORG_ID": "Org ID",
    "SAMVAAD_WORKSPACE_ID": "Workspace ID",
    "SAMVAAD_APP_ID": "Agent ID",
    "SAMVAAD_APP_VERSION": "committed agent version",
    "SAMVAAD_CONNECTION_ID": "telephony connection ID",
}


def _engine_file() -> Path:
    return Path(os.getenv("CALL_ENGINE_FILE") or BASE_DIR / "call_engine.json")


def _env(name: str) -> str:
    return os.getenv(name, "").strip()


def agent_number() -> str:
    return _env("SAMVAAD_AGENT_NUMBER") or _env("VOBIZ_CALLER_ID")


def missing_settings() -> List[str]:
    missing = [label for name, label in SETTINGS.items() if not _env(name)]
    if _env("SAMVAAD_APP_VERSION") and not _env("SAMVAAD_APP_VERSION").isdigit():
        missing.append("agent version as a number (e.g. 2)")
    if not agent_number():
        missing.append("agent phone number")
    return missing


def is_configured() -> bool:
    return not missing_settings()


def current_engine() -> str:
    try:
        engine = json.loads(_engine_file().read_text(encoding="utf-8")).get("engine")
    except (OSError, ValueError, AttributeError):
        engine = None
    return engine if engine in ENGINES else DEFAULT_ENGINE


def set_engine(engine: str) -> str:
    """Choose the engine for the next calls. Sarvam Agent needs its settings in .env first."""
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine {engine!r}")
    if engine == "samvaad" and not is_configured():
        raise ValueError("Sarvam Agent is not set up yet. Missing in .env: " + ", ".join(missing_settings()))
    _engine_file().write_text(json.dumps({"engine": engine}), encoding="utf-8")
    return engine


def engine_options() -> Dict[str, Any]:
    return {
        "engine": current_engine(),
        "options": [
            {"id": "pipecat", "label": ENGINES["pipecat"], "ready": True, "missing": []},
            {"id": "samvaad", "label": ENGINES["samvaad"], "ready": is_configured(), "missing": missing_settings()},
        ],
    }


def _real_name(name: Optional[str]) -> str:
    name = (name or "").strip()
    return "" if not name or name.startswith(("Manual call", "Inbound caller")) else name


def build_request(req: DialRequest) -> Dict[str, Any]:
    app_config: Dict[str, Any] = {
        "app_id": _env("SAMVAAD_APP_ID"),
        "app_version": int(_env("SAMVAAD_APP_VERSION") or 0),
        "connection_config": {"connection_id": _env("SAMVAAD_CONNECTION_ID"), "agent_phone_number": agent_number()},
    }
    if _real_name(req.lead_name):
        app_config["agent_variables"] = {"user_name": _real_name(req.lead_name)}
    if LANGUAGE_NAMES.get(req.language or ""):
        app_config["app_overrides"] = {"initial_language_name": LANGUAGE_NAMES[req.language]}
    return {
        "app_config": app_config,
        "user_config": {"user_phone_number": req.to_number},
        "webhook_config": {
            "url": f"{public_base_url()}/api/voice/samvaad/webhook?{_callback_query(req)}",
            "metadata": {"job_id": req.job_id, "lead_id": req.lead_id},
        },
    }


class SamvaadDialer(BaseDialer):
    name = "samvaad"

    def is_configured(self) -> bool:
        return is_configured()

    async def dial(self, req: DialRequest) -> str:
        if not is_configured():
            raise DialError("Sarvam Agent is not configured. Missing in .env: " + ", ".join(missing_settings()))
        url = f"{API_BASE}/orgs/{_env('SAMVAAD_ORG_ID')}/workspaces/{_env('SAMVAAD_WORKSPACE_ID')}/outbounds"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=build_request(req),
                                     headers={"X-API-Key": _env("SAMVAAD_API_KEY"), "Content-Type": "application/json"})
        if resp.status_code >= 300:
            raise DialError(f"Sarvam Agent {resp.status_code}: {resp.text[:600]}")
        data = resp.json() if resp.content else {}
        return str(data.get("attempt_id") or "")


def _outcome(variables: Dict[str, Any]) -> str:
    for key in ("call_outcome", "outcome", "call_status", "lead_status", "status"):
        value = variables.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "completed"


def result_to_call(payload: Dict[str, Any], lead_id: int, phone: str) -> Dict[str, Any]:
    """A connected call's webhook payload, as the call record save_call_record expects."""
    turns = payload.get("interaction_transcript") or []
    transcript = [{"role": "assistant" if t.get("role") == "agent" else "user", "content": t.get("en_text") or ""}
                  for t in turns if isinstance(t, dict)]
    variables = payload.get("final_agent_variables") or {}
    duration = int(payload.get("duration") or 0)
    summary = f"Sarvam Agent (Shriya) call, {duration} s. Transcript is Sarvam's English translation."
    if payload.get("interaction_id"):
        summary += f" Sarvam interaction {payload['interaction_id']} has the recording."
    return {
        "lead_id": lead_id, "call_type": "phone", "phone_number": phone, "status": "completed",
        "duration_seconds": duration, "transcript": transcript, "summary": summary,
        "outcome_label": _outcome(variables), "call_sid": payload.get("attempt_id"),
        "extracted_requirements": json.dumps(variables, ensure_ascii=False) if variables else "",
    }
