"""
Checks everything a real Vobiz call needs before you place one. Places no calls.

    venv\\Scripts\\python.exe scripts\\preflight_vobiz.py

1. the .env settings are filled in (values are never printed)
2. the Sarvam key works (one tiny LLM request, a few paise)
3. the Vobiz Auth ID / Token are accepted
4. VOICE_PUBLIC_BASE_URL (the ngrok / cloudflared address) reaches this app, and the
   Answer URL returns the <Stream> XML Vobiz needs
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

REQUIRED = ["SARVAM_API_KEY", "VOBIZ_AUTH_ID", "VOBIZ_AUTH_TOKEN", "VOBIZ_CALLER_ID", "VOICE_PUBLIC_BASE_URL"]
failures = 0


def report(ok: bool, label: str, detail: str = "") -> None:
    global failures
    failures += 0 if ok else 1
    print(f"{'OK  ' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))


def check_env() -> None:
    for name in REQUIRED:
        report(bool(os.getenv(name, "").strip()), f"{name} is set")
    report(bool(os.getenv("VOBIZ_WEBHOOK_SECRET", "").strip()),
           "VOBIZ_WEBHOOK_SECRET is set (stops strangers using the public address)")
    provider = os.getenv("DIALER_PROVIDER", "")
    report(provider in ("", "vobiz"), "DIALER_PROVIDER is vobiz (or empty)", f"now: {provider or 'empty'}")
    base = os.getenv("VOICE_PUBLIC_BASE_URL", "")
    if base:
        report(base.startswith("https://"), "VOICE_PUBLIC_BASE_URL starts with https://")


def check_sarvam() -> None:
    key = os.getenv("SARVAM_API_KEY", "")
    if not key:
        return
    base = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
    try:
        resp = httpx.post(f"{base}/v1/chat/completions", timeout=30,
                          headers={"api-subscription-key": key, "Authorization": f"Bearer {key}"},
                          json={"model": "sarvam-105b-conversations", "max_tokens": 5,
                                "messages": [{"role": "user", "content": "Say hi"}]})
        detail = "no credits left: top up at dashboard.sarvam.ai" if resp.status_code == 402 else f"HTTP {resp.status_code}"
        report(resp.status_code == 200, "Sarvam key works and has credits", detail)
    except httpx.HTTPError as e:
        report(False, "Sarvam key works", type(e).__name__)


def check_vobiz() -> None:
    auth_id, token = os.getenv("VOBIZ_AUTH_ID", ""), os.getenv("VOBIZ_AUTH_TOKEN", "")
    if not (auth_id and token):
        return
    try:
        resp = httpx.get(f"https://api.vobiz.ai/api/v1/Account/{auth_id}/Call/", timeout=20,
                         headers={"X-Auth-ID": auth_id, "X-Auth-Token": token})
    except httpx.HTTPError as e:
        report(False, "Vobiz credentials accepted", type(e).__name__)
        return
    if resp.status_code in (401, 403):
        report(False, "Vobiz credentials accepted", f"HTTP {resp.status_code}: check Auth ID / Token")
    else:
        report(resp.status_code == 200, "Vobiz credentials accepted", f"HTTP {resp.status_code}")


def check_tunnel() -> None:
    base = os.getenv("VOICE_PUBLIC_BASE_URL", "").rstrip("/")
    if not base:
        return
    secret = os.getenv("VOBIZ_WEBHOOK_SECRET", "").strip()
    url = f"{base}/api/voice/vobiz/answer" + (f"?key={secret}" if secret else "")
    try:
        if secret:
            stranger = httpx.post(f"{base}/api/voice/vobiz/answer", timeout=20, data={"CallUUID": "preflight"},
                                  headers={"ngrok-skip-browser-warning": "1"})
            report(stranger.status_code == 403, "A request without the key is rejected (403)",
                   f"HTTP {stranger.status_code}: restart the app after setting the secret" if stranger.status_code != 403 else "")
        resp = httpx.post(url, timeout=20, data={"CallUUID": "preflight"},
                          headers={"ngrok-skip-browser-warning": "1"})
    except httpx.HTTPError as e:
        report(False, "Tunnel reaches the app", f"{type(e).__name__}: is the app and ngrok running?")
        return
    scheme = "wss://" if base.startswith("https://") else "ws://"
    ok = resp.status_code == 200 and "<Stream" in resp.text and scheme in resp.text
    report(ok, f"Answer URL returns <Stream> with {scheme}", f"HTTP {resp.status_code}")


if __name__ == "__main__":
    check_env()
    check_sarvam()
    check_vobiz()
    check_tunnel()
    print("\nReady for a real call." if not failures else f"\n{failures} problem(s) to fix first.")
    sys.exit(1 if failures else 0)
