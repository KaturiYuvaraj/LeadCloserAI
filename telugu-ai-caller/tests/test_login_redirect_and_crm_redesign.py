import pytest
from fastapi.testclient import TestClient
from main import app
from core.auth import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


def test_crm_redirects_unauthenticated_to_login(client):
    """Unauthenticated access to /crm must redirect to /login with next parameter."""
    resp = client.get("/crm", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login?next=/crm" in resp.headers.get("location", "")


def test_login_page_redirects_authenticated_to_crm(client):
    """Authenticated user opening /login must be redirected directly to /crm."""
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    resp = client.get("/login", cookies={"lc_access_token": token}, follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers.get("location") == "/crm"


def test_login_api_returns_token_and_crm_access(client):
    """POST /api/auth/login validates credentials and sets session cookie."""
    resp = client.post("/api/auth/login", json={"email": "admin@leadcloser.ai", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "access_token" in data
    assert "lc_access_token" in resp.cookies


def test_crm_dashboard_renders_outpero_elements(client):
    """CRM shell renders Outpero layout: brand, sections, topbar telemetry, and account dropdown."""
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    resp = client.get("/crm", cookies={"lc_access_token": token})
    assert resp.status_code == 200
    html = resp.text

    # Sidebar Header & Brand
    assert "LeadCloser" in html
    assert "AI Voice Calling" in html
    assert "sidebarCollapseBtn" in html

    # Outpero Grouped Sections
    assert "Overview" in html
    assert "navItemDashboard" in html
    assert "navItemEmployees" in html
    assert "navItemNewEmployee" in html
    assert "navItemTalkEmployee" in html

    assert "Calling" in html
    assert "navItemCalling" in html
    assert "navItemCampaigns" in html
    assert "navItemInbound" in html

    assert "Results &amp; Setup" in html or "Results & Setup" in html
    assert "navItemLeads" in html
    assert "navItemConversations" in html
    assert "navItemTrainEmployees" in html
    assert "navItemPhoneNumbers" in html
    assert "navItemAnalytics" in html
    assert "navItemBilling" in html
    assert "navItemSettings" in html
    assert "navItemDeveloper" in html

    # Outpero Topbar Telemetry & Wallet Pills
    assert "crmLiveTelemetryPill" in html
    assert "crmTopbarMinutes" in html
    assert "crmAccountDropdown" in html

    # Optional Setup Reminder Card (non-blocking)
    assert "crmSetupReminderCard" in html
    assert "setupReminderName" in html
    assert "setupReminderBiz" in html
    assert "setupReminderPhone" in html


def test_save_quick_setup_profile(client):
    """Optional setup reminder saves business profile without mandatory blocking page."""
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    resp = client.post(
        "/api/profile",
        json={
            "company_name": "Sunrise Healthcare Clinic",
            "phone": "+91 98765 43210",
            "owner_name": "Priya Sharma"
        },
        cookies={"lc_access_token": token}
    )
    assert resp.status_code == 200
    assert resp.json().get("success") is True
