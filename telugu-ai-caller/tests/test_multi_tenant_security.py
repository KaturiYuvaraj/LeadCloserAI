"""
Multi-Tenant Account Isolation & Production Security Hardening Verification Tests
"""
import os
import unittest
from database import (
    create_lead,
    get_lead_by_id,
    get_all_leads,
    create_campaign,
    get_campaign_by_id,
    get_all_campaigns,
    create_ai_employee,
    get_ai_employee_by_id,
    get_all_ai_employees,
    create_api_key,
    get_all_api_keys,
    create_billing_order,
    get_billing_orders,
    get_analytics_summary,
)
from services.excel_service import sanitize_for_spreadsheet
from core.auth import verify_password


class MultiTenantSecurityTests(unittest.TestCase):

    def test_formula_injection_sanitization(self):
        """Spreadsheet export disarms dangerous formula injection strings."""
        self.assertEqual(sanitize_for_spreadsheet("=SUM(A1:A10)"), "'=SUM(A1:A10)")
        self.assertEqual(sanitize_for_spreadsheet("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(sanitize_for_spreadsheet("-123+456"), "'-123+456")
        self.assertEqual(sanitize_for_spreadsheet("@evil_site"), "'@evil_site")
        self.assertEqual(sanitize_for_spreadsheet("\tTAB_INJECT"), "'\tTAB_INJECT")
        self.assertEqual(sanitize_for_spreadsheet("Normal Text"), "Normal Text")
        self.assertEqual(sanitize_for_spreadsheet(12345), 12345)
        self.assertEqual(sanitize_for_spreadsheet(None), "")

    def test_lead_cross_account_isolation(self):
        """Lead created under Account 1 cannot be accessed by Account 2."""
        lead_id = create_lead({
            "name": "Secret Enterprise Prospect",
            "phone": "+919999900001",
            "company": "Tenancy Corp A",
        }, account_id=1)

        # Querying under Account 1 succeeds
        lead_acc1 = get_lead_by_id(lead_id, account_id=1)
        self.assertIsNotNone(lead_acc1)
        self.assertEqual(lead_acc1["id"], lead_id)

        # Querying under Account 2 fails (returns None)
        lead_acc2 = get_lead_by_id(lead_id, account_id=2)
        self.assertIsNone(lead_acc2)

        # Querying all leads for Account 2 does not include lead_id
        all_acc2 = get_all_leads(account_id=2)
        self.assertFalse(any(l["id"] == lead_id for l in all_acc2))

    def test_campaign_cross_account_isolation(self):
        """Campaign created under Account 1 cannot be accessed by Account 2."""
        camp_id = create_campaign({
            "name": "Outbound VIP Run",
            "lead_ids": [10, 11, 12],
        }, account_id=1)

        camp_acc1 = get_campaign_by_id(camp_id, account_id=1)
        self.assertIsNotNone(camp_acc1)

        camp_acc2 = get_campaign_by_id(camp_id, account_id=2)
        self.assertIsNone(camp_acc2)

        all_acc2 = get_all_campaigns(account_id=2)
        self.assertFalse(any(c["id"] == camp_id for c in all_acc2))

    def test_ai_employee_cross_account_isolation(self):
        """AI employee created under Account 1 cannot be retrieved by Account 2."""
        emp_id = create_ai_employee({
            "name": "Custom Private Agent",
            "role": "Confidential Closer",
        }, account_id=1)

        emp_acc1 = get_ai_employee_by_id(emp_id, account_id=1)
        self.assertIsNotNone(emp_acc1)

        emp_acc2 = get_ai_employee_by_id(emp_id, account_id=2)
        self.assertIsNone(emp_acc2)

        all_acc2 = get_all_ai_employees(account_id=2)
        self.assertFalse(any(e["id"] == emp_id for e in all_acc2))

    def test_api_key_cross_account_isolation(self):
        """API key created under Account 1 is isolated from Account 2."""
        key_res = create_api_key({
            "key_name": "Tenant 1 Master Key",
        }, account_id=1)

        all_acc2 = get_all_api_keys(account_id=2)
        self.assertFalse(any(k.get("key_name") == "Tenant 1 Master Key" for k in all_acc2))

    def test_billing_order_cross_account_isolation(self):
        """Billing order created under Account 1 is isolated from Account 2."""
        import secrets
        order_id = create_billing_order({
            "order_id": f"ORD-TEST-{secrets.token_hex(6)}",
            "plan_name": "VIP Recharge",
            "amount_inr": 4999.0,
            "minutes_credited": 1000.0,
        }, account_id=1)

        all_acc2 = get_billing_orders(account_id=2)
        self.assertFalse(any(o["id"] == order_id for o in all_acc2))

    def test_analytics_summary_zero_fake_data(self):
        """Analytics summary produces strictly factual numbers without mock fallbacks."""
        # Querying an empty account (Account 999999) must return 0 leads, 0 calls, and true empty metrics
        summary = get_analytics_summary(account_id=999999)
        self.assertEqual(summary["total_leads"], 0)
        self.assertEqual(summary["total_calls"], 0)
        self.assertEqual(summary["total_duration_sec"], 0)
        self.assertEqual(summary["conversion_rate"], 0.0)
        self.assertEqual(summary["cpql_inr"], 0.0)
        # Verify no fake numbers in objections
        self.assertEqual(summary["objections"]["pricing"], 0)
        self.assertEqual(summary["objections"]["existing_solution"], 0)
        # Verify no fake numbers in languages
        self.assertEqual(summary["languages"]["te-IN"], 0)
        self.assertEqual(summary["languages"]["hi-IN"], 0)

    def test_production_admin_password_bypass_disabled(self):
        """Default admin hash cannot be bypassed with default passwords in production."""
        os.environ["APP_ENV"] = "production"
        try:
            is_valid = verify_password("admin123", "pbkdf2:sha256:default_hash_for_admin")
            self.assertFalse(is_valid)
            is_valid_sp = verify_password("spassociates", "pbkdf2:sha256:default_hash_for_admin")
            self.assertFalse(is_valid_sp)
        finally:
            os.environ.pop("APP_ENV", None)


if __name__ == "__main__":
    unittest.main()
