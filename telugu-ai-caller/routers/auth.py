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
    require_role,
    verify_password,
)
from core.db import SessionLocal
from core.web import templates
from models import Account, AuditLog, User

router = APIRouter(tags=["auth"])

VALID_ROLES = {"owner", "admin", "member"}


@router.get("/login", response_class=HTMLResponse)
async def serve_login_page(request: Request):
    """Serve the LeadCloser AI team login page."""
    user = get_optional_user(request)
    return templates.TemplateResponse(request, "login.html", {"current_user": user})


@router.post("/api/auth/login")
async def api_login(payload: Dict[str, Any], response: Response):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.email.ilike(email)).first()
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password.")

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
            details={"email": user.email, "role": user.role},
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


@router.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
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
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
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

