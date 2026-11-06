"""
Unit tests for Task Y1:
Ensures empty or partial call records render neutral '—' or 'No summary yet',
and never display fake or invented data.
"""

import pytest
from starlette.testclient import TestClient
from core.auth import create_access_token


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def test_empty_call_fields_render_neutral_placeholders(client, monkeypatch):
    """A call with empty fields shows '—' and 'No summary yet', never fake text/durations."""
    # Mock get_call_history to return an empty-field call
    import routers.pages as pages_mod

    mock_calls = [
        {
            "id": 999,
            "lead_name": None,
            "phone": None,
            "disposition": None,
            "summary": None,
            "duration_seconds": None,
            "created_at": None,
            "recording_url": None,
        }
    ]
    monkeypatch.setattr(pages_mod, "get_call_history", lambda *args, **kwargs: mock_calls)

    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    resp = client.get("/crm", cookies={"lc_access_token": token})
    assert resp.status_code == 200
    html = resp.text

    # Must NOT contain fake data
    assert "+91 98765 43210" not in html
    assert "Duration: 74s" not in html
    assert "Lead inquired about AI automated sales dialer" not in html
    assert "Agreed to a demo scheduled for tomorrow" not in html
    assert "Discussed service packages and sent WhatsApp brochure" not in html

    # Must contain neutral indicators
    assert "No summary yet" in html
    assert "Duration: 0s" in html
