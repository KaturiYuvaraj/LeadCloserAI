"""
Unit and integration tests for Task Y5:
Account Settings for calling hours, days, redial gap, and max duration.
"""

from datetime import datetime, time, timezone
import pytest
from starlette.testclient import TestClient

from core.auth import create_access_token
from core.db import SessionLocal
from models import Account, User, Lead
from voice_agent.rules import check_can_call, in_calling_window, IST


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def owner_headers():
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def salesperson_headers():
    session = SessionLocal()
    try:
        user2 = session.query(User).filter_by(id=2).first()
        if not user2:
            user2 = User(
                id=2,
                account_id=1,
                email="sales@leadcloser.ai",
                password_hash="pbkdf2:sha256:somehash",
                role="salesperson"
            )
            session.add(user2)
            session.commit()
    finally:
        session.close()
    token = create_access_token(user_id=2, email="sales@leadcloser.ai", role="salesperson", account_id=1)
    return {"Authorization": f"Bearer {token}"}


def test_get_account_settings_owner_only(client, owner_headers, salesperson_headers):
    """GET /api/account/settings is accessible by owner, blocked for salesperson, 401 for unauth."""
    # Owner succeeds
    resp_owner = client.get("/api/account/settings", headers=owner_headers)
    assert resp_owner.status_code == 200
    data = resp_owner.json()
    assert "calling_start" in data
    assert "calling_end" in data
    assert "calling_days" in data
    assert "recent_call_hours" in data
    assert "max_call_seconds" in data
    assert "weekly_call_limit" in data

    # Salesperson gets 403 Forbidden
    resp_sales = client.get("/api/account/settings", headers=salesperson_headers)
    assert resp_sales.status_code == 403

    # Unauthenticated gets 401
    resp_unauth = client.get("/api/account/settings")
    assert resp_unauth.status_code == 401


def test_update_account_settings_success(client, owner_headers):
    """PUT /api/account/settings successfully saves valid settings."""
    payload = {
        "calling_start": "10:00",
        "calling_end": "18:00",
        "calling_days": [0, 1, 2, 3, 4],  # Mon-Fri
        "recent_call_hours": 48,
        "max_call_seconds": 900
    }
    resp = client.put("/api/account/settings", json=payload, headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["calling_start"] == "10:00"
    assert data["calling_end"] == "18:00"
    assert data["calling_days"] == [0, 1, 2, 3, 4]
    assert data["recent_call_hours"] == 48
    assert data["max_call_seconds"] == 900

    # Verify persisted in database
    session = SessionLocal()
    try:
        acc = session.query(Account).filter_by(id=1).first()
        assert acc.calling_start == time(10, 0)
        assert acc.calling_end == time(18, 0)
        assert acc.calling_days == [0, 1, 2, 3, 4]
        assert acc.recent_call_hours == 48
        assert acc.max_call_seconds == 900
    finally:
        session.close()


def test_update_account_settings_legal_hours_guards(client, owner_headers):
    """Calling hours must be strictly 09:00 to 21:00 IST and start < end."""
    # Start before 09:00
    resp_early = client.put("/api/account/settings", json={
        "calling_start": "08:30",
        "calling_end": "18:00",
        "calling_days": [0, 1, 2, 3, 4]
    }, headers=owner_headers)
    assert resp_early.status_code == 400
    assert "09:00 and 21:00" in resp_early.json()["detail"]

    # End after 21:00
    resp_late = client.put("/api/account/settings", json={
        "calling_start": "10:00",
        "calling_end": "21:30",
        "calling_days": [0, 1, 2, 3, 4]
    }, headers=owner_headers)
    assert resp_late.status_code == 400
    assert "09:00 and 21:00" in resp_late.json()["detail"]

    # Start >= End
    resp_inverted = client.put("/api/account/settings", json={
        "calling_start": "19:00",
        "calling_end": "10:00",
        "calling_days": [0, 1, 2, 3, 4]
    }, headers=owner_headers)
    assert resp_inverted.status_code == 400
    assert "precede" in resp_inverted.json()["detail"].lower()


def test_update_account_settings_days_and_limits_guards(client, owner_headers):
    """Validation for calling days list, redial gap (0-168h), and max duration (60-1800s)."""
    # Empty days
    resp_empty_days = client.put("/api/account/settings", json={
        "calling_start": "09:00",
        "calling_end": "19:00",
        "calling_days": []
    }, headers=owner_headers)
    assert resp_empty_days.status_code == 400
    assert "at least one" in resp_empty_days.json()["detail"].lower()

    # Invalid day index (7)
    resp_bad_day = client.put("/api/account/settings", json={
        "calling_start": "09:00",
        "calling_end": "19:00",
        "calling_days": [0, 7]
    }, headers=owner_headers)
    assert resp_bad_day.status_code == 400

    # Negative recent_call_hours
    resp_neg_gap = client.put("/api/account/settings", json={
        "calling_start": "09:00",
        "calling_end": "19:00",
        "calling_days": [0, 1],
        "recent_call_hours": -5
    }, headers=owner_headers)
    assert resp_neg_gap.status_code == 400

    # Max seconds too short (< 60s)
    resp_short = client.put("/api/account/settings", json={
        "calling_start": "09:00",
        "calling_end": "19:00",
        "calling_days": [0, 1],
        "max_call_seconds": 30
    }, headers=owner_headers)
    assert resp_short.status_code == 400


def test_dialer_rules_respect_account_settings():
    """Dialer rules directly evaluate the account's configured window and days."""
    session = SessionLocal()
    try:
        acc = session.query(Account).filter_by(id=1).first()
        acc.calling_start = time(10, 0)
        acc.calling_end = time(17, 0)
        acc.calling_days = [0]  # Only Mondays (0)
        acc.calling_approved = True
        session.commit()

        # At Tuesday 11:00 AM IST (weekday 1) -> outside window because only Monday is allowed
        tuesday_utc = datetime(2026, 11, 10, 5, 30, tzinfo=timezone.utc)  # 11:00 IST
        assert not in_calling_window(tuesday_utc, acc)

        # Restore default days
        acc.calling_days = list(range(7))
        acc.calling_start = time(9, 0)
        acc.calling_end = time(19, 0)
        session.commit()
    finally:
        session.close()


def test_crm_settings_template_contains_form(client, owner_headers):
    """Settings view contains the calling hours form and controls."""
    resp = client.get("/crm", headers=owner_headers)
    assert resp.status_code == 200
    html = resp.text

    assert "callingSettingsCard" in html
    assert "crmCallingSettingsForm" in html
    assert "settingCallingStart" in html
    assert "settingCallingEnd" in html
    assert "settingRecentHours" in html
    assert "settingMaxCallSeconds" in html
    assert "callingDaysCheckboxes" in html
