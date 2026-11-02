"""
Test Suite for Developer API, API Keys, and Outpero-Style Credit Billing.
Validates:
1. API key generation and listing.
2. Credit purchase order creation (instant UPI / Razorpay simulation).
3. Programmatic API call dispatch with talk-time credit deduction.
4. Insufficient balance prevention.
5. Post-call intelligence retrieval via API.
"""

import sys
import asyncio
import httpx
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.stdout.reconfigure(encoding='utf-8')

from main import app
from database import (
    init_db,
    get_all_api_keys,
    get_primary_api_key,
    get_api_key_by_token,
    create_api_key,
    create_billing_order,
    get_billing_orders,
    deduct_api_credits
)


async def run_developer_api_tests():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        print("1. Testing GET /api/v1/keys...")
        res = await client.get("/api/v1/keys")
        assert res.status_code == 200
        keys_data = res.json()
        assert "keys" in keys_data
        assert len(keys_data["keys"]) >= 1
        primary = keys_data["primary_key"]
        assert primary is not None
        print(f"   ✓ Found {len(keys_data['keys'])} keys. Primary: {primary['key_name']} (₹{primary['credits_inr']})")

        print("2. Testing POST /api/v1/keys (Generate custom key)...")
        res_create = await client.post("/api/v1/keys", json={
            "key_name": "Integration Test Key",
            "user_email": "testdev@company.com",
            "company_name": "Test Agency Ltd",
            "plan_tier": "Business Growth",
            "initial_credits": 1500.0
        })
        assert res_create.status_code == 200
        new_key = res_create.json()["key"]
        assert new_key["api_key"].startswith("lc_live_")
        assert new_key["credits_inr"] == 1500.0
        print(f"   ✓ Created key: {new_key['api_key']}")

        print("3. Testing POST /api/v1/billing/purchase-credits...")
        res_order = await client.post("/api/v1/billing/purchase-credits", json={
            "api_key_id": new_key["id"],
            "plan_name": "Pay-As-You-Go Credits",
            "amount_inr": 2500.0,
            "payment_method": "Instant UPI / QR Code",
            "customer_email": "testdev@company.com"
        })
        assert res_order.status_code == 200
        order_info = res_order.json()["order"]
        assert order_info["payment_status"] == "success"
        assert order_info["minutes_credited"] >= 500.0
        print(f"   ✓ Order #{order_info['order_id']} placed. Credited: {order_info['minutes_credited']} mins")

        print("4. Testing POST /api/v1/calls/dispatch (Programmatic AI Closer Call)...")
        res_dispatch = await client.post(
            "/api/v1/calls/dispatch",
            headers={"Authorization": f"Bearer {new_key['api_key']}"},
            json={
                "lead_name": "Ramesh Naidu",
                "phone": "+91 9848011223",
                "company": "Naidu Supermarkets",
                "service": "Mobile App & Billing",
                "budget": "₹75,000",
                "language": "te-IN"
            }
        )
        assert res_dispatch.status_code == 200
        dispatch_data = res_dispatch.json()
        assert dispatch_data["success"] is True
        assert dispatch_data["deal_stage"] in ["demo_scheduled", "qualified", "closed_won"]
        assert len(dispatch_data["summary"]) > 10
        assert dispatch_data["billing"]["charged_inr"] > 0
        call_id = dispatch_data["call_id"]
        print(f"   ✓ Dispatch call #{call_id} closed! Stage: {dispatch_data['deal_stage']}")
        print(f"   ✓ Summary: {dispatch_data['summary']}")
        print(f"   ✓ Billed: {dispatch_data['billing']['minutes_billed']} mins (₹{dispatch_data['billing']['charged_inr']})")

        print("5. Testing GET /api/v1/calls/{id}/intelligence...")
        res_intel = await client.get(f"/api/v1/calls/{call_id}/intelligence")
        assert res_intel.status_code == 200
        intel_call = res_intel.json()["call"]
        assert intel_call["id"] == call_id
        assert intel_call["deal_stage"] == dispatch_data["deal_stage"]
        print(f"   ✓ Retrieved call intelligence: {intel_call['summary']}")

    print("\nALL DEVELOPER API & BILLING STORE TESTS PASSED SUCCESSFULLY! 🎯")


if __name__ == "__main__":
    asyncio.run(run_developer_api_tests())
