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

        return {
            "success": True,
            "access_token": token,
            "token_type": "bearer",
            "expires_in": TOKEN_TTL_SECONDS,
            "user": {
                "id": user.id,
                "account_id": user.account_id,
                "account_name": account.name if account else "S P Associates",
                "email": user.email,
                "role": user.role,
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

