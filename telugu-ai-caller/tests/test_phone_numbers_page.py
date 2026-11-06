"""
Unit and integration tests for Task Y8:
Phone Numbers Page showing verified Vobiz carrier trunk (+917965482229),
Active status, Linked App: Yes, Monthly rent: ₹600, Next bill: 5 Dec.
No fake carrier lines, no Twilio/Exotel.
"""

import pytest
from starlette.testclient import TestClient

from core.auth import create_access_token
from core.db import SessionLocal
from models import Number, Employee, Account
from database import get_phone_numbers, init_db


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    return {"Authorization": f"Bearer {token}"}


def test_get_phone_numbers_endpoint(client, auth_headers):
    """GET /api/phone-numbers returns verified Vobiz trunk with all required billing and rep metadata."""
    resp = client.get("/api/phone-numbers", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "numbers" in data
    assert len(data["numbers"]) >= 1

    primary = data["numbers"][0]
    assert primary["e164"] == "+917965482229"
    assert primary["provider"] == "Vobiz"
    assert primary["status"] == "Active"
    assert primary["linked_app"] == "Yes"
    assert "600" in primary["monthly_rent"]
    assert "5 Dec" in primary["next_bill"]
    assert primary["assigned_rep"] == "S P Senior Closer (Default)"


def test_database_get_phone_numbers_helper():
    """Direct database helper returns verified Vobiz trunk formatted correctly."""
    numbers = get_phone_numbers(account_id=1)
    assert len(numbers) >= 1
    found_vobiz = any(n["e164"] == "+917965482229" and n["provider"] == "Vobiz" for n in numbers)
    assert found_vobiz, f"Expected verified Vobiz trunk +917965482229, got {numbers}"

    trunk = next(n for n in numbers if n["e164"] == "+917965482229")
    assert trunk["linked_app"] == "Yes"
    assert trunk["monthly_rent"] == "₹600"
    assert trunk["next_bill"] == "5 Dec"
    assert trunk["status"] == "Active"


def test_crm_html_phone_numbers_table(client, auth_headers):
    """The CRM page renders the verified Vobiz trunk and contains no fake carrier lines or Twilio/Exotel in phone table."""
    resp = client.get("/crm", headers=auth_headers)
    assert resp.status_code == 200
    html = resp.text

    assert "crmViewPhoneNumbers" in html
    assert "crmPhoneNumbersTableBody" in html
    assert "7965482229" in html
    assert "Vobiz" in html
    assert "₹600" in html
    assert "5 Dec" in html

    # Verify that the phone numbers table does NOT contain Exotel or Twilio
    table_start = html.find('id="crmPhoneNumbersTableBody"')
    table_end = html.find('</table>', table_start)
    table_snippet = html[table_start:table_end]

    assert "Exotel" not in table_snippet
    assert "Twilio" not in table_snippet

