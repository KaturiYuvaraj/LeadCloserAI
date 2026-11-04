"""
Authentication, JWT Session Management, Role Guards & Account Separation (Phase 0).

Supports:
  - HTTP-only cookie (`lc_token`) for browser sessions
  - `Authorization: Bearer <jwt>` header for API clients
  - Roles: `owner` | `admin` | `member`
  - Account-scoped data isolation (`user.account_id`)
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Callable, Dict, Optional

from fastapi import Depends, HTTPException, Request

from core.db import SessionLocal
from models import Account, User

SECRET_KEY = os.getenv("SECRET_KEY", "lc-phase0-super-secret-signing-key-2026-sp-associates")
if os.getenv("APP_ENV", "").lower() in {"production", "prod"}:
    if not os.getenv("SECRET_KEY") or SECRET_KEY == "lc-phase0-super-secret-signing-key-2026-sp-associates":
        raise RuntimeError("FATAL: Production environment requires a strong SECRET_KEY set in environment variables.")
COOKIE_NAME = "lc_token"
TOKEN_TTL_SECONDS = 12 * 3600  # 12 hours


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode((segment + padding).encode("ascii"))


def hash_password(password: str, iterations: int = 120_000) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a cryptographic random salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2:sha256:{iterations}${salt}${dk.hex()}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify a plain password against a stored PBKDF2 hash (plus seeded admin fallback)."""
    if not plain_password or not stored_hash:
        return False
    # Support default seeded admin row before password reset
    if stored_hash == "pbkdf2:sha256:default_hash_for_admin":
        if os.getenv("APP_ENV", "").lower() in {"production", "prod"}:
            return False
        return plain_password in {"admin123", "admin@123", "password", "spassociates"}
    if stored_hash.startswith("pbkdf2:sha256:"):
        try:
            rest = stored_hash.split("pbkdf2:sha256:", 1)[1]
            iter_str, salt, hex_digest = rest.split("$", 2)
            iterations = int(iter_str)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            return hmac.compare_digest(dk.hex(), hex_digest)
        except Exception:
            return False
    return hmac.compare_digest(plain_password, stored_hash)


def create_access_token(
    user_id: int,
    account_id: int,
    email: str,
    role: str,
    expires_seconds: int = TOKEN_TTL_SECONDS,
) -> str:
    """Create an HS256 JWT token with `sub`, `acc`, `email`, `role`, and `exp`."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {
        "sub": int(user_id),
        "acc": int(account_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + int(expires_seconds),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode an HS256 JWT token. Returns None if invalid or expired."""
    if not token or token.count(".") != 2:
        return None
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def _extract_raw_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get(COOKIE_NAME) or request.cookies.get("lc_access_token")
    if cookie_token:
        return cookie_token.strip()
    return None


def _load_user_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    user_id = payload.get("sub")
    if not user_id:
        return None
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(id=int(user_id)).first()
        if not user:
            return None
        account = session.query(Account).filter_by(id=user.account_id).first()
        return {
            "id": user.id,
            "account_id": user.account_id,
            "account_name": account.name if account else "S P Associates",
            "email": user.email,
            "role": user.role,
            "calling_approved": bool(account.calling_approved) if account else True,
        }
    finally:
        session.close()


def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Strict authentication dependency: requires a valid JWT in `Authorization: Bearer`
    or the `lc_token` httpOnly cookie. Raises 401 if missing or invalid.
    """
    token = _extract_raw_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")
    user = _load_user_from_payload(payload)
    if not user:
        raise HTTPException(status_code=401, detail="User account no longer exists.")
    return user


def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Returns the authenticated user if a token/cookie is present.
    If an Authorization header is explicitly provided with an invalid token, raises 401.
    If no token is provided, raises 401 only when `AUTH_STRICT=true` or `X-Require-Auth: 1` is set.
    """
    auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
    cookie_token = request.cookies.get(COOKIE_NAME) or request.cookies.get("lc_access_token")
    strict_mode = (
        os.getenv("AUTH_STRICT", "false").lower() == "true"
        or request.headers.get("X-Require-Auth") == "1"
    )

    if auth_header and auth_header.lower().startswith("bearer "):
        raw = auth_header.split(" ", 1)[1].strip()
        # Allow developer API keys (lc_live_*) to pass through on developer routes
        if raw.startswith("lc_live_"):
            return None
        payload = decode_access_token(raw)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired Bearer token.")
        user = _load_user_from_payload(payload)
        if not user:
            raise HTTPException(status_code=401, detail="User not found.")
        return user

    if cookie_token:
        payload = decode_access_token(cookie_token.strip())
        if payload:
            user = _load_user_from_payload(payload)
            if user:
                return user
        if strict_mode:
            raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    if strict_mode:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return None


def get_request_account_id(request: Request) -> Optional[int]:
    """
    Returns the authenticated user's `account_id` for strict multi-account isolation.
    Returns `None` only for unauthenticated local test calls when `AUTH_STRICT` is off.
    """
    user = get_optional_user(request)
    return int(user["account_id"]) if user else None


def require_role(*allowed_roles: str) -> Callable:
    """
    Dependency factory that enforces `user.role` is one of `allowed_roles`
    or satisfies the hierarchical role rank (owner > admin > manager > salesperson > member).
    """
    explicit_allowed = {r.lower() for r in allowed_roles}
    # Hierarchically expand allowed roles so higher roles always qualify
    expanded_allowed = set(explicit_allowed)
    for r in explicit_allowed:
        r_level = ROLE_LEVELS.get(r, 1)
        for candidate_role, c_level in ROLE_LEVELS.items():
            if c_level >= r_level:
                expanded_allowed.add(candidate_role)

    def _checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = (user.get("role") or "").lower()
        if user_role not in expanded_allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required role: {', '.join(sorted(explicit_allowed))}.",
            )
        return user

    return _checker


ROLE_LEVELS: Dict[str, int] = {
    "owner": 5,
    "admin": 4,
    "manager": 3,
    "salesperson": 2,
    "member": 1,
}


def validate_password_strength(password: str) -> Optional[str]:
    """Validate password length (>=8) and complexity (letters + digits)."""
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long."
    if not any(c.isalpha() for c in password):
        return "Password must contain at least one letter."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one digit."
    return None


class LoginRateLimiter:
    """Thread-safe in-memory sliding window rate limiter (max 5 failed attempts in 5 minutes)."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: Dict[str, list] = {}
        import threading
        self._lock = threading.Lock()

    def is_rate_limited(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            attempts = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
            self._failures[key] = attempts
            return len(attempts) >= self.max_attempts

    def record_failure(self, key: str):
        now = time.time()
        with self._lock:
            attempts = [t for t in self._failures.get(key, []) if now - t < self.window_seconds]
            attempts.append(now)
            self._failures[key] = attempts

    def reset(self, key: str):
        with self._lock:
            self._failures.pop(key, None)


login_limiter = LoginRateLimiter(max_attempts=5, window_seconds=300)
