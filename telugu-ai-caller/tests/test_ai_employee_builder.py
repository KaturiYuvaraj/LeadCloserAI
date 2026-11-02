"""
Test Suite for Phase 6: AI Employee Builder & Orchestration Integration.
"""

import os
import sys
import json
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import get_all_ai_employees, get_active_ai_employee, set_active_ai_employee


class AiEmployeeBuilderTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_seeded_employees_exist(self):
        """
        Verify that 5 specialized AI sales employees are seeded in SQLite and one is active.
        """
        resp = self.client.get("/api/employees")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        employees = data["employees"]
        self.assertTrue(len(employees) >= 5)

        active = data["active_employee"]
        self.assertIsNotNone(active)
        self.assertTrue(active["is_active"])

    def test_generate_employee_draft_from_instruction(self):
        """
        Verify the AI Employee Creation Assistant generates a structured draft from user instructions.
        """
        prompt = "Create a Telugu-speaking sales employee who calls clinic owners to pitch dental appointment booking software."
        resp = self.client.post("/api/employees/generate", json={"instruction": prompt, "language": "te-IN"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        draft = data["draft"]
        self.assertIn("name", draft)
        self.assertIn("greeting", draft)
        self.assertEqual(draft["status"], "draft")
        self.assertFalse(draft["is_active"])

    def test_draft_activation_blocked_without_approval(self):
        """
        Verify security/governance rule: Draft employees CANNOT be activated without administrator approval.
        """
        # Create a draft employee
        create_resp = self.client.post("/api/employees", json={
            "name": "Draft Tester Agent",
            "role": "Testing Sales",
            "language": "te-IN",
            "greeting": "హలో అండి!",
            "system_prompt": "You are a test closer.",
            "status": "draft",
            "is_active": False
        })
        self.assertEqual(create_resp.status_code, 200)
        emp_id = create_resp.json()["employee_id"]

        # Attempt to activate without approval -> must return HTTP 400
        act_resp = self.client.post(f"/api/employees/{emp_id}/activate")
        self.assertEqual(act_resp.status_code, 400)
        self.assertIn("must be reviewed and approved", act_resp.json()["detail"])

        # Approve employee
        app_resp = self.client.post(f"/api/employees/{emp_id}/approve")
        self.assertEqual(app_resp.status_code, 200)
        self.assertEqual(app_resp.json()["employee"]["status"], "approved")

        # Now activation must succeed
        act_resp2 = self.client.post(f"/api/employees/{emp_id}/activate")
        self.assertEqual(act_resp2.status_code, 200)
        self.assertTrue(act_resp2.json()["success"])

        # Clean up by switching back to default
        set_active_ai_employee(1)

    def test_update_and_delete_employee(self):
        """
        Verify employee attributes can be modified and deleted when not active.
        """
        create_resp = self.client.post("/api/employees", json={
            "name": "Temporary Consultant",
            "role": "Temporary Consultant",
            "greeting": "Hello!",
            "status": "draft"
        })
        emp_id = create_resp.json()["employee_id"]

        # Update role
        put_resp = self.client.put(f"/api/employees/{emp_id}", json={
            "role": "Senior Cloud Solutions Architect"
        })
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.json()["employee"]["role"], "Senior Cloud Solutions Architect")

        # Delete
        del_resp = self.client.delete(f"/api/employees/{emp_id}")
        self.assertEqual(del_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
