"""
Unit and integration tests for Task Y2:
Knowledge-base upload, listing, replacing, deleting, and prompt injection for AI employees.
"""

import io
import pytest
from starlette.testclient import TestClient

from core.auth import create_access_token
from core.db import SessionLocal
from models import Employee, User, Account
from voice_agent.knowledge import KnowledgeBase, list_docs, add_doc, delete_doc


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(user_id=1, email="admin@leadcloser.ai", role="owner", account_id=1)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_employee():
    session = SessionLocal()
    try:
        # Get or create an employee for account 1
        emp = session.query(Employee).filter_by(account_id=1).first()
        if not emp:
            emp = Employee(
                name="Knowledge Test Closer",
                account_id=1,
                role="Software Sales Specialist",
                system_prompt="You are an AI sales closer.",
                variables={"knowledge_docs": []}
            )
            session.add(emp)
            session.commit()
            session.refresh(emp)
        else:
            # Clean docs before test
            vars_dict = dict(emp.variables or {})
            vars_dict["knowledge_docs"] = []
            emp.variables = vars_dict
            session.commit()
            session.refresh(emp)
        emp_id = emp.id
    finally:
        session.close()
    return emp_id


def test_list_knowledge_empty(client, auth_headers, test_employee):
    """GET /api/employees/{id}/knowledge returns empty list and accepted formats."""
    resp = client.get(f"/api/employees/{test_employee}/knowledge", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "documents" in data
    assert isinstance(data["documents"], list)
    assert ".pdf" in data["accepted"]
    assert ".docx" in data["accepted"]
    assert ".xlsx" in data["accepted"]
    assert ".csv" in data["accepted"]
    assert ".txt" in data["accepted"]


def test_upload_and_replace_knowledge_document(client, auth_headers, test_employee):
    """Uploading a document indexes it; re-uploading same name replaces it."""
    # 1. Upload text doc
    file_content = b"Enterprise Plan: Rs 49,999/month. Includes unlimited AI sales calls and CRM sync."
    files = {"file": ("pricing_catalog.txt", io.BytesIO(file_content), "text/plain")}
    resp = client.post(f"/api/employees/{test_employee}/knowledge", files=files, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["name"] == "pricing_catalog.txt"
    assert data["chars"] == len(file_content)

    # Verify in list
    list_resp = client.get(f"/api/employees/{test_employee}/knowledge", headers=auth_headers)
    assert list_resp.status_code == 200
    docs = list_resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["name"] == "pricing_catalog.txt"

    # 2. Re-upload with same filename replaces old entry
    updated_content = b"Enterprise Plan Updated: Rs 39,999/month promotional discount."
    files_updated = {"file": ("pricing_catalog.txt", io.BytesIO(updated_content), "text/plain")}
    resp_updated = client.post(f"/api/employees/{test_employee}/knowledge", files=files_updated, headers=auth_headers)
    assert resp_updated.status_code == 200
    assert resp_updated.json()["chars"] == len(updated_content)

    # List should still have exactly 1 document, with the updated character count
    list_resp2 = client.get(f"/api/employees/{test_employee}/knowledge", headers=auth_headers)
    docs2 = list_resp2.json()["documents"]
    assert len(docs2) == 1
    assert docs2[0]["chars"] == len(updated_content)


def test_upload_knowledge_validation_errors(client, auth_headers, test_employee):
    """Validation for empty files, unsupported types, and oversized files."""
    # Empty file
    empty_file = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    resp_empty = client.post(f"/api/employees/{test_employee}/knowledge", files=empty_file, headers=auth_headers)
    assert resp_empty.status_code == 400
    assert "empty" in resp_empty.json()["detail"].lower()

    # Unsupported format (.exe)
    bad_type = {"file": ("malicious.exe", io.BytesIO(b"executable content"), "application/octet-stream")}
    resp_bad = client.post(f"/api/employees/{test_employee}/knowledge", files=bad_type, headers=auth_headers)
    assert resp_bad.status_code == 400
    assert "unsupported" in resp_bad.json()["detail"].lower()

    # Oversized file (> 15 MB)
    large_payload = b"X" * (15 * 1024 * 1024 + 10)
    oversized = {"file": ("huge.txt", io.BytesIO(large_payload), "text/plain")}
    resp_large = client.post(f"/api/employees/{test_employee}/knowledge", files=oversized, headers=auth_headers)
    assert resp_large.status_code == 413
    assert "15 mb" in resp_large.json()["detail"].lower()


def test_delete_knowledge_document(client, auth_headers, test_employee):
    """DELETE /api/employees/{id}/knowledge/{index} removes the doc."""
    # Upload 2 docs
    client.post(
        f"/api/employees/{test_employee}/knowledge",
        files={"file": ("doc1.txt", io.BytesIO(b"Content one"), "text/plain")},
        headers=auth_headers
    )
    client.post(
        f"/api/employees/{test_employee}/knowledge",
        files={"file": ("doc2.txt", io.BytesIO(b"Content two"), "text/plain")},
        headers=auth_headers
    )

    docs_before = client.get(f"/api/employees/{test_employee}/knowledge", headers=auth_headers).json()["documents"]
    assert len(docs_before) == 2

    # Delete index 0
    resp_del = client.delete(f"/api/employees/{test_employee}/knowledge/0", headers=auth_headers)
    assert resp_del.status_code == 200
    assert resp_del.json()["success"] is True

    # Docs should now only have 1 item (doc2)
    docs_after = client.get(f"/api/employees/{test_employee}/knowledge", headers=auth_headers).json()["documents"]
    assert len(docs_after) == 1
    assert docs_after[0]["name"] == "doc2.txt"

    # Out of range index -> 404
    resp_del_invalid = client.delete(f"/api/employees/{test_employee}/knowledge/99", headers=auth_headers)
    assert resp_del_invalid.status_code == 404


def test_live_calls_prompt_uses_uploaded_knowledge(test_employee):
    """KnowledgeBase.for_employee generates prompt with uploaded knowledge docs."""
    add_doc(test_employee, "PricingSheet.txt", "Standard plan is Rs 15,000. Premium plan is Rs 35,000.")
    docs = list_docs(test_employee, with_text=True)

    kb = KnowledgeBase.for_employee(
        employee={"name": "Closer", "knowledge_base": "We sell B2B software."},
        docs=docs
    )

    prompt = kb.prompt_section()
    assert "COMPANY KNOWLEDGE" in prompt
    assert "Standard plan is Rs 15,000" in prompt
    assert "We sell B2B software" in prompt


def test_crm_html_contains_knowledge_section(client, auth_headers):
    """CRM view contains the knowledge base UI elements in #crmViewEmployees."""
    resp = client.get("/crm", headers=auth_headers)
    assert resp.status_code == 200
    assert "crmEmployeeKnowledgeSection" in resp.text
    assert "kbEmployeeSelect" in resp.text
    assert "kbEmployeeFileInput" in resp.text
    assert "crmEmployeeKnowledgeTableBody" in resp.text
    assert "kbDropZone" in resp.text
