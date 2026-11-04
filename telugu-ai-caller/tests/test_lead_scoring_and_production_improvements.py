import pytest
import secrets
from fastapi.testclient import TestClient
from main import app
from core.db import SessionLocal
from core.auth import validate_password_strength, hash_password, login_limiter
from models import User, Account, Lead, Campaign, Employee
from services.lead_scoring import score_lead, score_leads_batch


client = TestClient(app)


def test_explainable_lead_scoring_hot_prospect():
    lead = {
        "id": 101,
        "name": "Vikram Patel",
        "company": "Patel Real Estate Developers",
        "title": "Managing Director",
        "budget": "2 Lakhs",
        "timeline": "immediate within 1 week",
        "service": "AI Calling Telugu and Hindi Voice Agents",
        "status": "demo_requested",
        "notes": "Requested urgent demonstration for 10,000 monthly buyers.",
    }

    scored = score_lead(lead)
    assert scored["total_score"] >= 80, f"Expected HOT score >= 80, got {scored['total_score']}"
    assert scored["category"] == "HOT"
    assert "budget" in scored["factors"]
    assert scored["factors"]["budget"]["score"] == 25
    assert scored["factors"]["decision_maker_fit"]["score"] == 10
    assert len(scored["summary_reasons"]) >= 3
    assert "demo" in scored["recommended_action"].lower()


def test_explainable_lead_scoring_cold_disqualified():
    lead = {
        "id": 102,
        "name": "Casual Visitor",
        "status": "not interested",
        "notes": "DND, requested not to call back",
    }

    scored = score_lead(lead)
    assert scored["total_score"] < 50
    assert scored["category"] == "COLD"
    assert scored["factors"]["engagement"]["score"] == 0


def test_explainable_lead_scoring_custom_weights():
    lead = {
        "id": 103,
        "budget": "50000",
        "timeline": "soon",
    }
    # Double the budget weight
    weights = {"budget": 50.0}
    scored = score_lead(lead, weights=weights)
    assert scored["factors"]["budget"]["max"] == 50
    assert scored["factors"]["budget"]["score"] == 50


def test_password_strength_validation():
    assert validate_password_strength("short") is not None
    assert validate_password_strength("alllettersonly") is not None
    assert validate_password_strength("1234567890") is not None
    assert validate_password_strength("ValidPassword123") is None


def test_self_service_account_registration():
    unique_email = f"leadcloser_owner_{secrets.token_hex(4)}@example.com"
    payload = {
        "company_name": "Apex Sales Corp",
        "email": unique_email,
        "password": "SecurePassword2026!",
    }

    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert "access_token" in data
    assert data["user"]["role"] == "owner"
    assert data["user"]["account_name"] == "Apex Sales Corp"

    # Duplicate registration should fail with 409
    res_dup = client.post("/api/auth/register", json=payload)
    assert res_dup.status_code == 409


def test_login_rate_limiting():
    fake_email = f"ratelimit_test_{secrets.token_hex(4)}@example.com"
    # Reset limiter for this email
    login_limiter.reset(fake_email)

    for i in range(5):
        res = client.post("/api/auth/login", json={"email": fake_email, "password": f"wrong_{i}"})
        assert res.status_code == 401

    # 6th attempt should be blocked with 429
    res_blocked = client.post("/api/auth/login", json={"email": fake_email, "password": "wrong"})
    assert res_blocked.status_code == 429
    assert "Too many failed login attempts" in res_blocked.json()["detail"]

    login_limiter.reset(fake_email)


def test_persistent_campaign_crud():
    payload = {
        "name": f"Q4 Real Estate Blitz {secrets.token_hex(3)}",
        "description": "High intent buyer outreach",
        "lead_ids": [1, 2, 3],
        "max_concurrency": 4,
        "retry_attempts": 3,
    }

    create_res = client.post("/api/campaigns", json=payload)
    assert create_res.status_code == 200, create_res.text
    camp_id = create_res.json()["campaign_id"]

    get_res = client.get(f"/api/campaigns/{camp_id}")
    assert get_res.status_code == 200
    camp = get_res.json()["campaign"]
    assert camp["name"] == payload["name"]
    assert camp["total_leads"] == 3
    assert camp["max_concurrency"] == 4

    list_res = client.get("/api/campaigns")
    assert list_res.status_code == 200
    assert any(c["id"] == camp_id for c in list_res.json()["campaigns"])


def test_ai_employee_duplicate():
    # Fetch existing employees or create a test one
    emp_res = client.get("/api/employees")
    assert emp_res.status_code == 200
    employees = emp_res.json()["employees"]
    if not employees:
        create_res = client.post("/api/employees", json={
            "name": "Priya Telugu Sales",
            "greeting": "Namaskaram! LeadCloser AI nundi matladuthunnanu.",
            "primary_language": "te-IN",
        })
        assert create_res.status_code == 200
        emp_id = create_res.json()["employee_id"]
    else:
        emp_id = employees[0]["id"]

    dup_res = client.post(f"/api/employees/{emp_id}/duplicate")
    assert dup_res.status_code == 200, dup_res.text
    dup_data = dup_res.json()
    assert dup_data["success"] is True
    assert "(Copy)" in dup_data["employee"]["name"]
    assert dup_data["employee"]["status"] == "draft"
    assert bool(dup_data["employee"]["is_active"]) is False


def test_leads_scoring_and_bulk_operations():
    # 1. Fetch leads
    leads_res = client.get("/api/leads?limit=5")
    assert leads_res.status_code == 200
    data = leads_res.json()
    assert "leads" in data
    assert "total" in data

    if data["leads"]:
        lead_id = data["leads"][0]["id"]
        # Score single lead
        score_res = client.post(f"/api/leads/{lead_id}/score")
        assert score_res.status_code == 200
        assert "score" in score_res.json()
        assert 0 <= score_res.json()["score"]["total_score"] <= 100

        # Score all
        score_all_res = client.post("/api/leads/score-all")
        assert score_all_res.status_code == 200
        assert "scored_count" in score_all_res.json()
