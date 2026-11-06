"""
Unit and integration tests for Task Y6:
Admin password change, default password revocation, and team management.
"""

import pytest
from starlette.testclient import TestClient

from core.auth import create_access_token, hash_password
from core.db import SessionLocal
from models import User, Account


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_login_returns_must_change_password_when_default_hash(client):
    """Seeded admin using placeholder hash returns must_change_password=True on login."""
    resp = client.post("/api/auth/login", json={
        "email": "admin@leadcloser.ai",
        "password": "admin123"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["must_change_password"] is True
    assert "access_token" in data


def test_set_password_page_route(client):
    """Unauthenticated users are redirected; authenticated users get the set-password page."""
    # Unauthenticated
    resp_unauth = client.get("/set-password", follow_redirects=False)
    assert resp_unauth.status_code == 302
    assert "/login" in resp_unauth.headers["location"]

    # Authenticated with placeholder hash
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    resp_auth = client.get("/set-password", cookies={"lc_access_token": token})
    assert resp_auth.status_code == 200
    assert "Set Your Secure Password" in resp_auth.text
    assert "changePasswordForm" in resp_auth.text


def test_change_password_validations(client):
    """Validation guards on current password, length, and presence."""
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    # Missing fields
    resp = client.post("/api/auth/change-password", json={}, headers=headers)
    assert resp.status_code == 400
    assert "required" in resp.json()["detail"].lower()

    # Password too short (< 8 chars)
    resp = client.post("/api/auth/change-password", json={
        "current_password": "admin123",
        "new_password": "short"
    }, headers=headers)
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]

    # Wrong current password
    resp = client.post("/api/auth/change-password", json={
        "current_password": "completely_wrong_pass",
        "new_password": "ValidNewPassword123"
    }, headers=headers)
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


def test_change_password_success_revokes_default_passwords(client):
    """Once a real password is set, fallback passwords stop working immediately."""
    session = SessionLocal()
    try:
        user = session.query(User).filter_by(id=1).first()
        # Ensure user 1 has default hash initially
        user.password_hash = "pbkdf2:sha256:default_hash_for_admin"
        session.commit()
    finally:
        session.close()

    try:
        # Verify default password works before change
        resp_before = client.post("/api/auth/login", json={
            "email": "admin@leadcloser.ai",
            "password": "admin123"
        })
        assert resp_before.status_code == 200
        token = resp_before.json()["access_token"]

        # Change password to a strong new password
        new_secret = "LeadCloser2026Secure!"
        change_resp = client.post("/api/auth/change-password", json={
            "current_password": "admin123",
            "new_password": new_secret
        }, headers={"Authorization": f"Bearer {token}"})
        assert change_resp.status_code == 200
        assert change_resp.json()["success"] is True

        # Try default passwords -> all must fail with 401
        for default_pw in ["admin123", "admin@123", "password", "spassociates"]:
            failed_resp = client.post("/api/auth/login", json={
                "email": "admin@leadcloser.ai",
                "password": default_pw
            })
            assert failed_resp.status_code == 401, f"Default password {default_pw} should be revoked!"

        # Login with the new password -> must succeed with must_change_password=False
        success_resp = client.post("/api/auth/login", json={
            "email": "admin@leadcloser.ai",
            "password": new_secret
        })
        assert success_resp.status_code == 200
        assert success_resp.json()["must_change_password"] is False
    finally:
        # Restore default hash so subsequent tests in the session are not affected
        restore_session = SessionLocal()
        try:
            u = restore_session.query(User).filter_by(id=1).first()
            if u:
                u.password_hash = "pbkdf2:sha256:default_hash_for_admin"
                restore_session.commit()
        finally:
            restore_session.close()


def test_team_crud_for_settings_ui(client):
    """List team members, invite new colleague, and remove team member."""
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List team
    list_resp = client.get("/api/team", headers=headers)
    assert list_resp.status_code == 200
    assert "team" in list_resp.json()
    initial_count = len(list_resp.json()["team"])

    # 2. Add team member
    new_rep_email = "new_sales_rep@leadcloser.ai"
    add_resp = client.post("/api/team", json={
        "email": new_rep_email,
        "password": "TemporaryPass123",
        "role": "salesperson"
    }, headers=headers)
    assert add_resp.status_code == 200
    new_member_id = add_resp.json()["user"]["id"]
    assert add_resp.json()["user"]["role"] == "salesperson"

    # List again -> count increased by 1
    list_resp2 = client.get("/api/team", headers=headers)
    assert len(list_resp2.json()["team"]) == initial_count + 1

    # 3. Cannot delete own account
    self_delete_resp = client.delete("/api/team/1", headers=headers)
    assert self_delete_resp.status_code == 400

    # 4. Remove newly added member
    del_resp = client.delete(f"/api/team/{new_member_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # List again -> count back to initial
    list_resp3 = client.get("/api/team", headers=headers)
    assert len(list_resp3.json()["team"]) == initial_count
