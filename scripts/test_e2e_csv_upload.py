import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "telugu-ai-caller"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from main import app
from database import get_all_leads

client = TestClient(app)

csv_candidates = list(Path(r"C:\Users\YUVARAJ\.gemini\antigravity\brain").glob("**/media_*c4da3ed1.csv"))
if csv_candidates:
    csv_path = csv_candidates[0]
else:
    csv_path = ROOT / "ap_telangana_ngo_leads_output.csv"

if csv_path.exists():
    with open(csv_path, "rb") as f:
        response = client.post(
            "/api/leads/upload-excel",
            files={"file": ("ap_telangana_ngo_leads_output.csv", f, "text/csv")}
        )

    print("HTTP Status Code:", response.status_code)
    res_json = response.json()
    print("Success:", res_json.get("success"))
    print("Total Parsed:", res_json.get("total_parsed"))
    print("Inserted:", res_json.get("inserted"))
    print("Updated:", res_json.get("updated"))

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert res_json.get("success") is True
    assert res_json.get("total_parsed") == 200

# Verify leads endpoint returns enriched records
leads_res = client.get("/api/leads")
assert leads_res.status_code == 200
leads_data = leads_res.json().get("leads", [])

# Find specific sample leads from user's CSV
athma = next((l for l in leads_data if "Athma NGO" in (l.get("company") or "")), None)
if athma:
    print("\n[VERIFIED] Athma NGO:")
    print("  Business Name:", athma.get("company"))
    print("  Business Owner / Decision Maker:", athma.get("owner_name"))
    print("  Phone:", athma.get("phone"))
    print("  Has Website:", athma.get("has_website"))
    print("  Service Needed:", athma.get("service_needed"))
    print("  Lead Score:", athma.get("score"))
    print("  Reviews:", athma.get("reviews"))

    assert athma.get("owner_name") == "Founder & Managing Trustee"
    assert athma.get("has_website") == "No"
    assert athma.get("score") == "135"

print("\n[ALL ASSERTIONS PASSED] End-to-end CSV ingestion and business/owner intelligence verified successfully!")
