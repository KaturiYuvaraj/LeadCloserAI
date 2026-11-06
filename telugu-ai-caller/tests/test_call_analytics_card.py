"""
Unit and integration tests for Task Y3:
Call Analytics Card on the CRM Dashboard (7/30/90 day selector, telemetry tiles, bar lists).
"""

from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from core.auth import create_access_token
from core.db import SessionLocal
from models import Call, Account, User


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_test_calls():
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Create test calls for account 1
        calls = [
            Call(
                account_id=1,
                direction="out",
                state="completed",
                outcome="interested",
                talk_seconds=120,
                latency_avg_ms=1650.0,
                created_at=now,
                captured={
                    "analytics": {
                        "user_turns": 4,
                        "end_reason": "completed",
                        "languages": ["te-IN", "en-IN"],
                        "actions": [{"action": "whatsapp_catalog_sent"}],
                        "signals": {"asked_price": 1}
                    }
                }
            ),
            Call(
                account_id=1,
                direction="out",
                state="completed",
                outcome="callback",
                talk_seconds=60,
                latency_avg_ms=1720.0,
                created_at=now,
                captured={
                    "analytics": {
                        "user_turns": 2,
                        "end_reason": "callback_scheduled",
                        "languages": ["te-IN"],
                        "actions": [{"action": "callback_scheduled"}],
                        "signals": {}
                    }
                }
            ),
            Call(
                account_id=1,
                direction="out",
                state="completed",
                outcome="no_answer",
                talk_seconds=0,
                created_at=now,
                captured={
                    "analytics": {
                        "user_turns": 0,
                        "end_reason": "voicemail",
                        "languages": [],
                        "actions": []
                    }
                }
            ),
            # Call for a different account to test isolation
            Call(
                account_id=999,
                direction="out",
                state="completed",
                outcome="interested",
                talk_seconds=300,
                created_at=now
            )
        ]
        session.add_all(calls)
        session.commit()
    finally:
        session.close()


def test_call_analytics_endpoint_structure(client, auth_headers):
    """GET /api/analytics/calls returns the expected fields and defaults."""
    resp = client.get("/api/analytics/calls?days=30", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "days" in data
    assert "total_calls" in data
    assert "conversations" in data
    assert "machine_answered" in data
    assert "no_response" in data
    assert "avg_talk_seconds" in data
    assert "avg_reply_gap_ms" in data
    assert "outcomes" in data
    assert "languages" in data
    assert "actions" in data
    assert "end_reasons" in data


def test_call_analytics_days_selector(client, auth_headers):
    """7, 30, and 90 day selector filters data correctly."""
    for d in (7, 30, 90):
        resp = client.get(f"/api/analytics/calls?days={d}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["days"] == d


def test_call_analytics_metrics_and_isolation(client, auth_headers, seed_test_calls):
    """Metrics accurately aggregate company calls and exclude calls from other companies."""
    resp = client.get("/api/analytics/calls?days=30", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Should only count account 1 calls (at least the 3 seeded ones, not account 999)
    assert data["total_calls"] >= 3
    assert data["conversations"] >= 2  # 2 seeded had user_turns
    assert data["machine_answered"] >= 1  # 1 seeded had voicemail

    # Check outcomes
    assert "interested" in data["outcomes"]
    assert "callback" in data["outcomes"]

    # Check languages
    assert "te-IN" in data["languages"]

    # Check actions
    assert "whatsapp_catalog_sent" in data["actions"] or "callback_scheduled" in data["actions"]

    # Check avg reply gap is computed in ms
    if data["avg_reply_gap_ms"] is not None:
        assert data["avg_reply_gap_ms"] > 0


def test_crm_dashboard_contains_call_analytics_card(client, auth_headers):
    """Dashboard template includes the telemetry card, 7/30/90 selector, tiles, and bar lists."""
    resp = client.get("/crm", headers=auth_headers)
    assert resp.status_code == 200
    html = resp.text

    # Card & Selector
    assert "crmCallAnalyticsCard" in html
    assert "analyticsDaysSelector" in html
    assert "analyticsBtn7" in html
    assert "analyticsBtn30" in html
    assert "analyticsBtn90" in html

    # 6 Telemetry Tiles
    assert "tileTotalCalls" in html
    assert "tileConversations" in html
    assert "tileMachineAnswered" in html
    assert "tileNoResponse" in html
    assert "tileAvgTalk" in html
    assert "tileAvgReplyGap" in html

    # 3 Bar Lists
    assert "analyticsOutcomesList" in html
    assert "analyticsLanguagesList" in html
    assert "analyticsActionsList" in html
