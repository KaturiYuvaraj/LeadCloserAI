import sys
from pathlib import Path

# Add project root and virtual environment site-packages to sys.path
ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "telugu-ai-caller"
VENV_SITE = PROJECT / "venv" / "Lib" / "site-packages"

for p in [str(PROJECT), str(VENV_SITE), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi.testclient import TestClient  # type: ignore
from main import app  # type: ignore
from database import get_all_leads  # type: ignore

client = TestClient(app)

csv_candidates = list(Path(r"C:\Users\YUVARAJ\.gemini\antigravity\brain").glob("**/media_*c4da3ed1.csv"))
if csv_candidates:
    csv_path = csv_candidates[0]
else:
    csv_path = ROOT / "ap_telangana_ngo_leads_output.csv"

if csv_path.exists():
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/api/leads/upload-excel",
            files={"file": ("ap_telangana_ngo_leads_output.csv", f, "text/csv")}
        )

    print("NGO Upload Status:", resp.status_code)
    data = resp.json()
    print("Success:", data.get("success"), "Total:", data.get("total_parsed"), "Inserted:", data.get("inserted"), "Updated:", data.get("updated"))

leads = get_all_leads()
print(f"Total leads in canonical DB: {len(leads)}")
if leads:
    top_c = str(leads[0].get('company') or '').encode('ascii', 'replace').decode()
    top_o = str(leads[0].get('owner_name') or '').encode('ascii', 'replace').decode()
    top_s = str(leads[0].get('service_needed') or '').encode('ascii', 'replace').decode()
    print(f"Top Lead: {top_c} | Owner: {top_o} | Service: {top_s}")
