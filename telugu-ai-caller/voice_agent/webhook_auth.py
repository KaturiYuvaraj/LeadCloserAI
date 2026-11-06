"""
Vobiz webhook security.

Vobiz doesn't document a signature on the requests it sends us (Answer URL, Hangup URL, audio
stream), and the IPs it calls from change, so we use a secret that only Vobiz and we know: it is
part of the URLs we give Vobiz (`?key=<secret>`), and every Vobiz route rejects a request without it.
Without this anyone who finds the public address could start calls on our engine (using our Sarvam
credits) or fake call results.

Set VOBIZ_WEBHOOK_SECRET in .env (a long random string, e.g. `python -c "import secrets;print(secrets.token_urlsafe(32))"`)
and put `?key=<same secret>` on the Answer and Hangup URLs of the Vobiz Application (inbound calls).
Calls we place ourselves get the key automatically. With no secret set the routes stay open (as in
local development) and the app logs a warning at start-up.
"""

import hmac
import os
from typing import Mapping, Optional


def secret() -> str:
    return os.getenv("VOBIZ_WEBHOOK_SECRET", "").strip()


def enabled() -> bool:
    return bool(secret())


def is_valid(provided: Optional[str]) -> bool:
    """True when no secret is configured, or `provided` equals it (constant-time comparison)."""
    expected = secret()
    if not expected:
        return True
    return hmac.compare_digest(str(provided or "").encode("utf-8"), expected.encode("utf-8"))


def allowed(params: Mapping[str, str]) -> bool:
    return is_valid(params.get("key"))
