"""
Excel & CSV Lead Ingestion Service.
Parses uploaded .xlsx, .xls, and .csv files with intelligent column header matching.
Generates downloadable Excel template for admin.
"""

import io
import csv
import re
import openpyxl
from typing import List, Dict, Any, Tuple
from loguru import logger


HEADER_MAPPINGS = {
    "name": ["name", "customer name", "client name", "lead name", "full name", "contact name", "organization", "సంస్థ", "పేరు"],
    "phone": ["phone", "phone number", "mobile", "mobile number", "contact", "cell", "telephone", "ఫోన్ నంబర్"],
    "email": ["email", "e-mail", "mail", "email address", "ఈమెయిల్"],
    "company": ["company", "company name", "business", "business name", "shop", "organization name", "సంస్థ పేరు"],
    "owner_name": ["owner", "business owner", "owner name", "founder", "trustee", "director", "contact person", "decision maker", "doctor", "యాజమాని"],
    "website": ["website", "site", "web", "url", "domain", "వెబ్‌సైట్"],
    "has_website": ["has website", "has_website", "has web", "website available", "web status"],
    "reviews": ["reviews", "review", "review count", "rating", "ratings", "stars"],
    "score": ["score", "lead score", "priority score", "points", "rank"],
    "pitch": ["pitch", "sales pitch", "pitch angle", "strategy", "talking points", "script", "pitch idea"],
    "service_needed": ["service", "service needed", "requirement", "project", "interested in", "product", "అవసరం"],
    "budget": ["budget", "estimated budget", "price", "cost", "amount", "బడ్జెట్"],
    "timeline": ["timeline", "timeframe", "target date", "deadline", "duration", "సమయం"],
    "preferred_language": ["language", "preferred language", "customer language", "lang", "భాష"],
    "notes": ["notes", "notes/details", "remarks", "comments", "details", "description", "వివరాలు"]
}


def extract_business_and_owner(raw_name: str, raw_company: str = "", raw_owner: str = "") -> Tuple[str, str]:
    """
    Intelligently deduce the clean business name and business owner/key decision maker
    from organizational names, healthcare entities, trusts, or individual practitioner records.
    """
    raw_name = str(raw_name or "").strip()
    # Strip emojis and marketing superlatives for clean voice & display
    clean_biz = re.sub(r'[\U00010000-\U0010ffff]', '', raw_name).strip()
    clean_biz = re.sub(r'\s*-\s*Best NGO in.*', '', clean_biz, flags=re.IGNORECASE).strip()
    clean_biz = clean_biz.strip('"\' ')

    owner_name = raw_owner.strip()
    company_name = raw_company.strip() or clean_biz

    if not owner_name:
        # Check if raw_name starts with a person honorific (Dr. / Mr. / Mrs. / Sri) without being a facility
        if re.match(r'^(dr\.|mr\.|mrs\.|sri\b)', raw_name, re.IGNORECASE) and not any(w in raw_name.lower() for w in ["hospital", "clinic", "trust", "foundation"]):
            owner_name = clean_biz
            company_name = f"{clean_biz} Professional Practice"
        else:
            m_dr = re.search(r'\b(dr\s+[a-z\s\.]+?)\s+(?:bharathi\s+)?charitable\s+trust', clean_biz, re.IGNORECASE)
            if m_dr:
                owner_name = m_dr.group(1).title() + " (Founder & Trustee)"
            elif "jaireddy" in clean_biz.lower():
                owner_name = "Jaireddy (Founder & Trustee)"
            elif "chiranjeevi" in clean_biz.lower():
                owner_name = "Chiranjeevi (Founder)"
            elif "brahmaji" in clean_biz.lower():
                owner_name = "Brahmaji Nelluri (Managing Trustee)"
            elif "venkat" in clean_biz.lower():
                owner_name = "Venkat (Managing Trustee)"
            elif "perali narasaiah" in clean_biz.lower():
                owner_name = "Perali Narasaiah Family Trustee"
            elif any(w in clean_biz.lower() for w in ["trust", "foundation", "society", "association", "samithi", "ngo", "welfare"]):
                owner_name = "Founder & Managing Trustee"
            elif "hospital" in clean_biz.lower() or "clinic" in clean_biz.lower():
                owner_name = "Medical Director & Administrator"
            elif any(w in clean_biz.lower() for w in ["office", "department", "govt", "government"]):
                owner_name = "District Officer / In-Charge"
            elif any(w in clean_biz.lower() for w in ["hall", "colony"]):
                owner_name = "Community President / Secretary"
            else:
                owner_name = "Business Owner / Managing Director"

    return company_name, owner_name


def enrich_lead_record(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich a parsed lead dictionary with inferred business profile, owner details,
    website audit, and targeted sales pitch angle.
    """
    raw_name = lead.get("name", "")
    raw_company = lead.get("company", "")
    raw_owner = lead.get("owner_name", "")

    company_name, owner_name = extract_business_and_owner(raw_name, raw_company, raw_owner)
    lead["company"] = company_name
    lead["owner_name"] = owner_name

    # Website and digital presence classification
    has_web_raw = str(lead.get("has_website", "")).strip().lower()
    website = str(lead.get("website", "")).strip()
    if website.lower() in ["n/a", "none", "null", "no", ""]:
        website = ""
        lead["website"] = ""

    if has_web_raw in ["yes", "y", "true", "1"] or website:
        lead["has_website"] = "Yes"
    else:
        lead["has_website"] = "No"

    # Tailored requirement based on digital footprint audit and industry type
    cur_service = lead.get("service_needed", "").strip()
    if not cur_service or cur_service.lower() in ["software services", "software"]:
        name_lower = (company_name + " " + raw_name).lower()
        if any(w in name_lower for w in ["academy", "institute", "coaching", "classes", "training", "tuition", "school", "college", "graphics", "design"]):
            lead["service_needed"] = "Student Enrollment & Online Course Portal" if lead["has_website"] == "No" else "Student Review Booster & Lead Capture Engine"
        elif any(w in name_lower for w in ["hospital", "clinic", "health", "dental", "care", "diagnostic", "dr."]):
            lead["service_needed"] = "Doctor Appointment & Patient Booking Portal" if lead["has_website"] == "No" else "Patient Reviews & Healthcare SEO Engine"
        elif any(w in name_lower for w in ["ngo", "trust", "foundation", "charitable", "samithi", "society", "welfare"]):
            lead["service_needed"] = "Custom NGO Website & Donation Portal" if lead["has_website"] == "No" else "Online Reputation & Donor Growth"
        elif any(w in name_lower for w in ["mart", "store", "shop", "supermarket", "retail"]):
            lead["service_needed"] = "E-Commerce Catalog & Online Ordering App" if lead["has_website"] == "No" else "Local Google Reviews & Delivery App"
        else:
            lead["service_needed"] = "Custom Business Website & Lead Gen Engine" if lead["has_website"] == "No" else "Online Review Booster & SEO Optimization"

    # Clean reviews and score
    if "reviews" in lead and lead["reviews"]:
        try:
            lead["reviews"] = str(int(float(lead["reviews"])))
        except Exception:
            pass
    if "score" in lead and lead["score"]:
        try:
            lead["score"] = str(int(float(lead["score"])))
        except Exception:
            pass

    # Sales pitch talking points
    if not lead.get("pitch"):
        if lead["has_website"] == "No":
            lead["pitch"] = "No website found. Pitch a modern, mobile-responsive NGO website with donation portal, mission showcase, and 80G tax exemption info."
        else:
            lead["pitch"] = "Website active. Pitch Google review boosting, donor testimonials showcase, and volunteer enrollment automations."

    return lead


def _match_header(col_name: str) -> str:
    cleaned = col_name.strip().lower()
    # 1. Exact match
    for standard_field, aliases in HEADER_MAPPINGS.items():
        if cleaned in aliases:
            return standard_field
    # 2. Substring match (check longer aliases first, requiring min 4 chars)
    for standard_field, aliases in HEADER_MAPPINGS.items():
        for alias in sorted(aliases, key=len, reverse=True):
            if len(alias) >= 4 and alias in cleaned:
                return standard_field
    return cleaned


def _clean_language(lang_val: str) -> str:
    cleaned = str(lang_val or "").strip().lower()
    if any(h in cleaned for h in ["hi", "hindi", "हिंदी"]):
        return "hi-IN"
    if any(e in cleaned for e in ["en", "english", "eng"]):
        return "en-IN"
    if any(t in cleaned for t in ["ta", "tamil", "தமிழ்"]):
        return "ta-IN"
    if any(k in cleaned for k in ["kn", "kannada", "ಕನ್ನಡ"]):
        return "kn-IN"
    if any(m in cleaned for m in ["ml", "malayalam", "മലയാളം"]):
        return "ml-IN"
    return "te-IN"


def parse_excel_or_csv(file_bytes: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse an uploaded Excel (.xlsx) or CSV file into a list of standardized lead dictionaries.
    Returns: (leads_list, errors_list)
    """
    leads = []
    errors = []

    if filename.endswith(".csv"):
        # CSV parsing
        try:
            content = file_bytes.decode("utf-8-sig", errors="replace")
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            if not rows:
                return [], ["CSV file is empty."]

            raw_headers = rows[0]
            field_map = {idx: _match_header(h) for idx, h in enumerate(raw_headers)}

            for row_idx, row in enumerate(rows[1:], start=2):
                if not any(row):  # skip blank lines
                    continue
                lead = {}
                for idx, val in enumerate(row):
                    field_name = field_map.get(idx)
                    if field_name:
                        lead[field_name] = val.strip()

                if lead.get("phone") or lead.get("name") or lead.get("company"):
                    lead.setdefault("name", lead.get("company") or "Unknown Lead")
                    lead.setdefault("phone", "")
                    lead.setdefault("budget", "Flexible")
                    lead.setdefault("status", "NEW")
                    lead["preferred_language"] = _clean_language(lead.get("preferred_language"))
                    lead = enrich_lead_record(lead)
                    leads.append(lead)
                else:
                    errors.append(f"Row {row_idx}: Missing required name, organization, or phone number.")

        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            errors.append(f"Failed to parse CSV: {str(e)}")

    else:
        # Excel (.xlsx) parsing using openpyxl
        try:
            workbook = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
            sheet = workbook.active
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return [], ["Excel worksheet is empty."]

            raw_headers = [str(c or "").strip() for c in rows[0]]
            field_map = {idx: _match_header(h) for idx, h in enumerate(raw_headers) if h}

            for row_idx, row in enumerate(rows[1:], start=2):
                if not any(row):
                    continue
                lead = {}
                for idx, val in enumerate(row):
                    field_name = field_map.get(idx)
                    if field_name and val is not None:
                        # Clean cell values (e.g. floats in phone column)
                        str_val = str(val).strip()
                        if field_name == "phone" and str_val.endswith(".0"):
                            str_val = str_val[:-2]
                        lead[field_name] = str_val

                if lead.get("phone") or lead.get("name") or lead.get("company"):
                    lead.setdefault("name", lead.get("company") or "Unknown Lead")
                    lead.setdefault("phone", "")
                    lead.setdefault("budget", "Flexible")
                    lead.setdefault("status", "NEW")
                    lead["preferred_language"] = _clean_language(lead.get("preferred_language"))
                    lead = enrich_lead_record(lead)
                    leads.append(lead)
                else:
                    errors.append(f"Row {row_idx}: Missing required name, organization, or phone number.")

        except Exception as e:
            logger.error(f"Excel parse error: {e}")
            errors.append(f"Failed to parse Excel file: {str(e)}")

    return leads, errors


def generate_sample_excel_template() -> bytes:
    """
    Generate a formatted sample Excel (.xlsx) file that the admin can download.
    Includes Language column for Telugu, Hindi, or English caller targeting.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads_Template"

    headers = [
        "Customer Name",
        "Phone Number",
        "Company Name",
        "Service Needed",
        "Estimated Budget",
        "Timeline",
        "Language (Telugu / Hindi / English)",
        "Notes/Details"
    ]
    ws.append(headers)

    sample_rows = [
        ["రమేష్ నాయుడు (Ramesh Naidu)", "+91 9848011223", "Naidu Supermarkets", "Mobile App & Billing", "₹75,000", "Immediate", "Telugu", "Looking for grocery ordering mobile app."],
        ["अमित शर्मा (Amit Sharma)", "+91 9811002233", "Sharma Logistics", "Fleet Tracking & Billing Web", "₹1,20,000", "2 Weeks", "Hindi", "Wants automated customer dispatch system."],
        ["Rajesh Nair", "+91 9895001122", "Apex Diagnostic Labs", "AI Voice Caller & Chatbot", "₹50,000", "1 Month", "English", "Needs AI phone calling agent for appointment confirmation."]
    ]

    for row in sample_rows:
        ws.append(row)

    # Style header row
    header_fill = openpyxl.styles.PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = openpyxl.styles.Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font

    # Set column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 16)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_leads_export_excel(leads: List[Dict[str, Any]]) -> bytes:
    """
    Generate an Excel (.xlsx) file containing all leads along with their call summaries,
    business profiles, decision maker details, deal closing stages, and next action items.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads_Call_Summaries"

    headers = [
        "Lead ID",
        "Business / Company",
        "Decision Maker / Owner",
        "Phone Number",
        "Email",
        "Website",
        "Has Website",
        "Service Needed",
        "Lead Score",
        "Reviews",
        "Pitch Strategy",
        "Language",
        "Budget",
        "Timeline",
        "Status",
        "Call Summary (Executive Overview)",
        "Deal Stage",
        "Sentiment",
        "Objections Raised",
        "Next Action Items",
        "Last Called At"
    ]
    ws.append(headers)

    for lead in leads:
        ws.append([
            lead.get("id", ""),
            lead.get("company", lead.get("name", "")),
            lead.get("owner_name", lead.get("name", "")),
            lead.get("phone", ""),
            lead.get("email", ""),
            lead.get("website", ""),
            lead.get("has_website", ""),
            lead.get("service_needed", ""),
            lead.get("score", ""),
            lead.get("reviews", ""),
            lead.get("pitch", ""),
            lead.get("preferred_language", "te-IN"),
            lead.get("budget", ""),
            lead.get("timeline", ""),
            lead.get("status", "NEW"),
            lead.get("last_call_summary", "No call yet"),
            lead.get("last_call_stage", ""),
            lead.get("last_call_sentiment", ""),
            lead.get("objections_noted", ""),
            lead.get("action_items", ""),
            str(lead.get("last_called_at") or "")
        ])

    # Header styling
    header_fill = openpyxl.styles.PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = openpyxl.styles.Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font

    # Set column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 14), 50)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

