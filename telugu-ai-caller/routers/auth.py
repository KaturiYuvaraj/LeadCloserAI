"""
Authentication & Team Roles Router (Phase 0).

Endpoints:
  GET    /login                Login screen HTML
  POST   /api/auth/login       Authenticate with email + password -> JWT + httpOnly cookie
  POST   /api/auth/logout      Clear session cookie
  GET    /api/auth/me          Current logged-in user + account details
  GET    /api/team             List users in the current account
  POST   /api/team             Invite/create a team member (owner/admin only)
  DELETE /api/team/{user_id}   Remove a team member (owner/admin only)
"""

import os
from datetime import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from core.auth import (
    COOKIE_NAME,
    TOKEN_TTL_SECONDS,
    create_access_token,
    get_current_user,
    get_optional_user,
    hash_password,
    login_limiter,
    require_role,
    validate_password_strength,
    verify_password,
)
from core.db import SessionLocal
from core.web import templates
from models import Account, AuditLog, User

router = APIRouter(tags=["auth"])

VALID_ROLES = {"owner", "admin", "manager", "salesperson", "member"}


@router.get("/login", response_class=HTMLResponse)
async def serve_login_page(request: Request):
    """Serve the LeadCloser AI team login page. Redirects authenticated users to CRM."""
    user = get_optional_user(request)
    if user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/crm", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"current_user": user})


@router.post("/api/auth/login")
async def api_login(payload: Dict[str, Any], request: Request, response: Response):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{email}"

    if login_limiter.is_rate_limited(rate_key) or login_limiter.is_rate_limited(email):
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Please wait 5 minutes before trying again."
        )

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email.ilike(email)).first()
        if not user or not verify_password(password, user.password_hash):
            login_limiter.record_failure(rate_key)
            login_limiter.record_failure(email)
            # Log failed login attempt
            try:
                session.add(AuditLog(
                    account_id=user.account_id if user else 1,
                    user_id=user.id if user else None,
                    action="login_failed",
                    target=f"email:{email}",
                    details={"email": email, "ip": client_ip, "reason": "invalid_credentials"},
                ))
                session.commit()
            except Exception:
                session.rollback()
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        login_limiter.reset(rate_key)
        login_limiter.reset(email)

        account = session.query(Account).filter_by(id=user.account_id).first()
        token = create_access_token(
            user_id=user.id,
            account_id=user.account_id,
            email=user.email,
            role=user.role,
        )

        session.add(AuditLog(
            account_id=user.account_id,
            user_id=user.id,
            action="user_login",
            target=f"user:{user.id}",
            details={"email": user.email, "role": user.role, "ip": client_ip},
        ))
        session.commit()

        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=TOKEN_TTL_SECONDS,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            key="lc_access_token",
            value=token,
            httponly=True,
            max_age=TOKEN_TTL_SECONDS,
            samesite="lax",
            path="/",
        )

        must_change_password = bool(user.password_hash == "pbkdf2:sha256:default_hash_for_admin")

        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "expires_in": TOKEN_TTL_SECONDS,
            "must_change_password": must_change_password,
            "user": {
                "id": user.id,
                "account_id": user.account_id,
                "account_name": account.name if account else "S P Associates",
                "email": user.email,
                "role": user.role,
                "must_change_password": must_change_password,
            },
        }
    finally:
        session.close()


@router.post("/api/auth/register")
async def api_register(payload: Dict[str, Any], request: Request, response: Response):
    """
    Self-service account registration:
    Creates an Account and the initial Owner User with validated credentials.
    """
    company_name = (payload.get("company_name") or payload.get("account_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not company_name or len(company_name) < 2:
        raise HTTPException(status_code=400, detail="Company or organization name is required (min 2 characters).")
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Valid email address is required.")

    pw_err = validate_password_strength(password)
    if pw_err:
        raise HTTPException(status_code=400, detail=pw_err)

    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.email.ilike(email)).first()
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email address already exists.")

        account = Account(name=company_name, calling_approved=True)
        session.add(account)
        session.flush()

        user = User(
            account_id=account.id,
            email=email,
            password_hash=hash_password(password),
            role="owner",
        )
        session.add(user)
        session.flush()

        token = create_access_token(
            user_id=user.id,
            account_id=account.id,
            email=user.email,
            role=user.role,
        )

        client_ip = request.client.host if request.client else "unknown"
        session.add(AuditLog(
            account_id=account.id,
            user_id=user.id,
            action="account_registered",
            target=f"account:{account.id}",
            details={"email": email, "company": company_name, "ip": client_ip},
        ))
        session.commit()

        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=TOKEN_TTL_SECONDS,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            key="lc_access_token",
            value=token,
            httponly=True,
            max_age=TOKEN_TTL_SECONDS,
            samesite="lax",
            path="/",
        )

        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "expires_in": TOKEN_TTL_SECONDS,
            "user": {
                "id": user.id,
                "account_id": account.id,
                "account_name": account.name,
                "email": user.email,
                "role": user.role,
            },
        }
    finally:
        session.close()


@router.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    response.delete_cookie(key="lc_access_token", path="/")
    return {"success": True, "message": "Logged out successfully."}


@router.get("/api/auth/me")
async def api_me(user: Dict[str, Any] = Depends(get_current_user)):
    return {"authenticated": True, "user": user}


@router.post("/api/auth/change-password")
async def api_change_password(
    payload: Dict[str, Any],
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    current_password = (payload.get("current_password") or "").strip()
    new_password = (payload.get("new_password") or "").strip()

    if not current_password or not new_password:
        raise HTTPException(status_code=400, detail="Current password and new password are required.")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long.")

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.id == current_user["id"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User account not found.")

        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")

        user.password_hash = hash_password(new_password)
        client_ip = request.client.host if request.client else "unknown"
        session.add(AuditLog(
            account_id=user.account_id,
            user_id=user.id,
            action="password_changed",
            target=f"user:{user.id}",
            details={"email": user.email, "ip": client_ip},
        ))
        session.commit()
        return {"success": True, "message": "Password updated successfully."}
    finally:
        session.close()


@router.get("/api/team")
async def api_list_team(user: Dict[str, Any] = Depends(get_current_user)):
    session = SessionLocal()
    try:
        users = (
            session.query(User)
            .filter(User.account_id == user["account_id"])
            .order_by(User.id.asc())
            .all()
        )
        return {
            "team": [
                {
                    "id": u.id,
                    "account_id": u.account_id,
                    "email": u.email,
                    "role": u.role,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ]
        }
    finally:
        session.close()


@router.post("/api/team")
async def api_invite_team_member(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_role("owner", "admin")),
):
    email = (payload.get("email") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    role = (payload.get("role") or "member").strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email address is required.")
    pw_err = validate_password_strength(password)
    if pw_err:
        raise HTTPException(status_code=400, detail=pw_err)
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")

    session = SessionLocal()
    try:
        existing = session.query(User).filter(User.email.ilike(email)).first()
        if existing:
            raise HTTPException(status_code=409, detail="A user with this email already exists.")

        new_user = User(
            account_id=current_user["account_id"],
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        session.add(new_user)
        session.flush()

        session.add(AuditLog(
            account_id=current_user["account_id"],
            user_id=current_user["id"],
            action="team_invite",
            target=f"user:{new_user.id}",
            details={"email": email, "role": role},
        ))
        session.commit()

        return {
            "success": True,
            "user": {
                "id": new_user.id,
                "account_id": new_user.account_id,
                "email": new_user.email,
                "role": new_user.role,
            },
        }
    finally:
        session.close()


@router.delete("/api/team/{member_id}")
async def api_remove_team_member(
    member_id: int,
    current_user: Dict[str, Any] = Depends(require_role("owner", "admin")),
):
    if int(member_id) == int(current_user["id"]):
        raise HTTPException(status_code=400, detail="You cannot remove your own active user account.")

    session = SessionLocal()
    try:
        target = (
            session.query(User)
            .filter(User.id == member_id, User.account_id == current_user["account_id"])
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail="Team member not found in your account.")

        email_removed = target.email
        session.delete(target)
        session.add(AuditLog(
            account_id=current_user["account_id"],
            user_id=current_user["id"],
            action="team_remove",
            target=f"user:{member_id}",
            details={"email": email_removed},
        ))
        session.commit()
        return {"success": True, "removed_id": member_id}
    finally:
        session.close()


@router.get("/api/account/settings")
async def api_get_account_settings(
    current_user: Dict[str, Any] = Depends(require_role("owner")),
):
    """Retrieve operational calling hours, day schedules, and limits (owner only)."""
    session = SessionLocal()
    try:
        account = session.query(Account).filter(Account.id == current_user["account_id"]).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found.")

        start_str = account.calling_start.strftime("%H:%M") if account.calling_start else "09:00"
        end_str = account.calling_end.strftime("%H:%M") if account.calling_end else "19:00"
        days = account.calling_days if isinstance(account.calling_days, list) and account.calling_days else list(range(7))
        weekly_limit = int(os.getenv("DIALER_WEEKLY_CALL_LIMIT", 4))

        return {
            "account_id": account.id,
            "name": account.name,
            "calling_start": start_str,
            "calling_end": end_str,
            "calling_days": [int(d) for d in days],
            "recent_call_hours": int(account.recent_call_hours if account.recent_call_hours is not None else 24),
            "max_call_seconds": int(account.max_call_seconds if account.max_call_seconds is not None else 600),
            "weekly_call_limit": weekly_limit,
            "calling_approved": bool(account.calling_approved),
            "rate_per_min": float(account.rate_per_min or 5.0),
        }
    finally:
        session.close()


@router.put("/api/account/settings")
async def api_update_account_settings(
    payload: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_role("owner")),
):
    """Update operational calling hours, days, and safety limits (owner only)."""
    LEGAL_START = time(9, 0)
    LEGAL_END = time(21, 0)

    # 1. Validate calling_start and calling_end
    start_raw = payload.get("calling_start")
    end_raw = payload.get("calling_end")

    if not start_raw or not end_raw:
        raise HTTPException(status_code=400, detail="Both calling_start and calling_end are required (format HH:MM).")

    try:
        sp = [int(p) for p in str(start_raw).strip().split(":")]
        ep = [int(p) for p in str(end_raw).strip().split(":")]
        start_t = time(sp[0], sp[1])
        end_t = time(ep[0], ep[1])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM (e.g. 09:00).")

    if start_t < LEGAL_START or end_t > LEGAL_END:
        raise HTTPException(
            status_code=400,
            detail="Calling hours must be strictly between 09:00 and 21:00 IST according to regulatory compliance.",
        )
    if start_t >= end_t:
        raise HTTPException(status_code=400, detail="Calling start time must precede end time.")

    # 2. Validate calling_days
    days_raw = payload.get("calling_days")
    if days_raw is None or not isinstance(days_raw, list) or len(days_raw) == 0:
        raise HTTPException(status_code=400, detail="At least one operational calling day must be selected (Mon–Sun).")
    try:
        days = sorted(list({int(d) for d in days_raw}))
        if any(d < 0 or d > 6 for d in days):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Calling days must be integers from 0 (Monday) to 6 (Sunday).")

    # 3. Validate recent_call_hours (0 to 168)
    try:
        recent_hours = int(payload.get("recent_call_hours", 24))
        if not (0 <= recent_hours <= 168):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Minimum redial gap must be between 0 and 168 hours.")

    # 4. Validate max_call_seconds (60 to 1800)
    try:
        max_sec = int(payload.get("max_call_seconds", 600))
        if not (60 <= max_sec <= 1800):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Maximum call duration must be between 60 and 1800 seconds.")

    session = SessionLocal()
    try:
        account = session.query(Account).filter(Account.id == current_user["account_id"]).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found.")

        account.calling_start = start_t
        account.calling_end = end_t
        account.calling_days = days
        account.recent_call_hours = recent_hours
        account.max_call_seconds = max_sec

        session.add(AuditLog(
            account_id=account.id,
            user_id=current_user["id"],
            action="account_settings_update",
            target=f"account:{account.id}",
            details={
                "calling_start": start_t.strftime("%H:%M"),
                "calling_end": end_t.strftime("%H:%M"),
                "calling_days": days,
                "recent_call_hours": recent_hours,
                "max_call_seconds": max_sec,
            },
        ))
        session.commit()
        session.refresh(account)

        return {
            "success": True,
            "calling_start": account.calling_start.strftime("%H:%M"),
            "calling_end": account.calling_end.strftime("%H:%M"),
            "calling_days": account.calling_days,
            "recent_call_hours": account.recent_call_hours,
            "max_call_seconds": account.max_call_seconds,
            "weekly_call_limit": int(os.getenv("DIALER_WEEKLY_CALL_LIMIT", 4)),
        }
    finally:
        session.close()

