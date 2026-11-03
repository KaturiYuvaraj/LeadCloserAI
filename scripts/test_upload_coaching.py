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

csv_path = Path(r"C:\Users\YUVARAJ\Downloads\hyderabad_graphic_design_coaching_centers_leads_output.csv")
if not csv_path.exists():
    candidates = list(ROOT.glob("**/*coaching*.csv"))
    if candidates:
        csv_path = candidates[0]

if csv_path.exists():
    with open(csv_path, "rb") as f:
        resp = client.post(
            "/api/leads/upload-excel",
            files={"file": ("ap_telangana_coaching_centers_leads_output.csv", f, "text/csv")}
        )

    print("HTTP Status:", resp.status_code)
    data = resp.json()
    print("Success:", data.get("success"))
    print("Parsed:", data.get("total_parsed"))
    print("Inserted:", data.get("inserted"))
    print("Updated:", data.get("updated"))

leads = get_all_leads()
print(f"Total leads in canonical DB: {len(leads)}")

print("\nTop 5 Leads (Newest First):")
for i, l in enumerate(leads[:5]):
    company = str(l.get('company') or '').encode('ascii', 'replace').decode()
    owner = str(l.get('owner_name') or '').encode('ascii', 'replace').decode()
    service = str(l.get('service_needed') or '').encode('ascii', 'replace').decode()
    phone = str(l.get('phone') or '')
    print(f"#{i+1}: Company: {company} | Owner: {owner} | Service: {service} | Phone: {phone}")
