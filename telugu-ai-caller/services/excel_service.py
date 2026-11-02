"""
Excel & CSV Lead Ingestion Service.
Parses uploaded .xlsx, .xls, and .csv files with intelligent column header matching.
Generates downloadable Excel template for admin.
"""

import io
import csv
import openpyxl
from typing import List, Dict, Any, Tuple
from loguru import logger


HEADER_MAPPINGS = {
    "name": ["name", "customer name", "client name", "lead name", "full name", "contact name", "పేరు"],
    "phone": ["phone", "phone number", "mobile", "mobile number", "contact", "cell", "telephone", "ఫోన్ నంబర్"],
    "email": ["email", "e-mail", "mail", "email address", "ఈమెయిల్"],
    "company": ["company", "company name", "business", "business name", "shop", "organization", "సంస్థ"],
    "service_needed": ["service", "service needed", "requirement", "project", "interested in", "product", "అవసరం"],
    "budget": ["budget", "estimated budget", "price", "cost", "amount", "బడ్జెట్"],
    "timeline": ["timeline", "timeframe", "target date", "deadline", "duration", "సమయం"],
    "preferred_language": ["language", "preferred language", "customer language", "lang", "భాష"],
    "notes": ["notes", "notes/details", "remarks", "comments", "details", "description", "వివరాలు"]
}


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

                if lead.get("phone") or lead.get("name"):
                    lead.setdefault("name", "Unknown Lead")
                    lead.setdefault("phone", "")
                    lead.setdefault("service_needed", "Software Services")
                    lead.setdefault("budget", "Flexible")
                    lead.setdefault("status", "NEW")
                    lead["preferred_language"] = _clean_language(lead.get("preferred_language"))
                    leads.append(lead)
                else:
                    errors.append(f"Row {row_idx}: Missing required name or phone number.")

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

                if lead.get("phone") or lead.get("name"):
                    lead.setdefault("name", "Unknown Lead")
                    lead.setdefault("phone", "")
                    lead.setdefault("service_needed", "Software Services")
                    lead.setdefault("budget", "Flexible")
                    lead.setdefault("status", "NEW")
                    lead["preferred_language"] = _clean_language(lead.get("preferred_language"))
                    leads.append(lead)
                else:
                    errors.append(f"Row {row_idx}: Missing required name or phone number.")

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
    deal closing stages, customer sentiments, and next action items.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads_Call_Summaries"

    headers = [
        "Lead ID",
        "Customer Name",
        "Phone Number",
        "Company",
        "Service Needed",
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
            lead.get("name", ""),
            lead.get("phone", ""),
            lead.get("company", ""),
            lead.get("service_needed", ""),
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

