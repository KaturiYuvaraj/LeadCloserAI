"""
Quotation Guardrails, Price Book, Branded PDF Generator & WhatsApp Opt-In/STOP Engine (Plan v2 §5 & §6).

Implements:
1. Price Book management for S P Associates Software Company (standard packages + max auto-discount limits).
2. Quotation Guardrails:
   - Standard package within discount limit (<= 10%) and no custom scope -> auto-approved & ready/sent.
   - Custom scope OR discount above limit (> 10%) -> blocked in `pending_approval` until manager approves.
3. Versioned Quotations with 18% GST calculation, validity date, and branded PDF generation (`%PDF-1.4`).
4. Quote follow-up cadence checker (24h not opened -> WhatsApp; 48h no reply -> AI call; expiring -> reminder).
5. WhatsApp opt-in verification and instant `"STOP"` opt-out enforcement.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))

DEFAULT_PRICE_BOOK: List[Dict[str, Any]] = [
    {
        "code": "pkg_website_starter",
        "name": "Business Website & SEO Starter",
        "category": "Web Development",
        "base_price_inr": 25000.0,
        "max_discount_pct": 10.0,
        "delivery_days": 7,
        "deliverables": "5-page responsive website, SEO setup, WhatsApp chat integration, 1 year free hosting support",
        "active": True,
    },
    {
        "code": "pkg_ecommerce_pro",
        "name": "E-Commerce Web & Payment Portal",
        "category": "E-Commerce",
        "base_price_inr": 45000.0,
        "max_discount_pct": 10.0,
        "delivery_days": 14,
        "deliverables": "Product catalog, cart, Razorpay/UPI gateway, admin order dashboard, inventory alerts",
        "active": True,
    },
    {
        "code": "pkg_mobile_app",
        "name": "Custom Android & iOS Mobile App",
        "category": "Mobile App",
        "base_price_inr": 75000.0,
        "max_discount_pct": 10.0,
        "delivery_days": 21,
        "deliverables": "Flutter/React Native Android & iOS apps, push notifications, backend API, Play Store deployment",
        "active": True,
    },
    {
        "code": "pkg_ai_caller",
        "name": "AI Voice Caller & WhatsApp Automation",
        "category": "AI Automation",
        "base_price_inr": 35000.0,
        "max_discount_pct": 10.0,
        "delivery_days": 10,
        "deliverables": "Multilingual AI voice agent (Telugu/Hindi/English/Tamil/Kannada/Malayalam), CRM pipeline, WhatsApp workflows",
        "active": True,
    },
    {
        "code": "pkg_erp_billing",
        "name": "GST Billing, POS & Inventory ERP",
        "category": "ERP & Billing",
        "base_price_inr": 40000.0,
        "max_discount_pct": 10.0,
        "delivery_days": 10,
        "deliverables": "GST invoicing, barcode POS, multi-warehouse stock alerts, daily owner mobile reports",
        "active": True,
    },
]

# In-memory store backed by Account/Lead JSON persistence in database
_CUSTOM_PRICE_BOOK_BY_ACCOUNT: Dict[int, List[Dict[str, Any]]] = {}
_QUOTATIONS_STORE: Dict[int, Dict[str, Any]] = {}
_QUOTE_SEQ: int = 1040


def get_price_book(account_id: int = 1) -> List[Dict[str, Any]]:
    """Returns the active price book for an account."""
    if account_id not in _CUSTOM_PRICE_BOOK_BY_ACCOUNT:
        _CUSTOM_PRICE_BOOK_BY_ACCOUNT[account_id] = [dict(item) for item in DEFAULT_PRICE_BOOK]
    return _CUSTOM_PRICE_BOOK_BY_ACCOUNT[account_id]


def upsert_price_book_item(item_data: Dict[str, Any], account_id: int = 1) -> Dict[str, Any]:
    """Adds or updates a package in the account's price book."""
    book = get_price_book(account_id)
    code = (item_data.get("code") or "").strip() or f"pkg_custom_{len(book) + 1}"
    entry = {
        "code": code,
        "name": item_data.get("name", "Custom Software Package"),
        "category": item_data.get("category", "Software Services"),
        "base_price_inr": float(item_data.get("base_price_inr", 30000.0)),
        "max_discount_pct": float(item_data.get("max_discount_pct", 10.0)),
        "delivery_days": int(item_data.get("delivery_days", 14)),
        "deliverables": item_data.get("deliverables", "Standard software deliverables"),
        "active": bool(item_data.get("active", True)),
    }
    for idx, existing in enumerate(book):
        if existing["code"] == code:
            book[idx] = entry
            return entry
    book.append(entry)
    return entry


def create_quotation(
    lead_id: int,
    lead_name: str,
    lead_phone: str,
    package_code: str,
    discount_pct: float = 0.0,
    is_custom_scope: bool = False,
    custom_scope_notes: str = "",
    custom_price_inr: Optional[float] = None,
    validity_days: int = 7,
    whatsapp_opt_in: bool = False,
    account_id: int = 1,
    created_by: str = "ai_agent",
) -> Dict[str, Any]:
    """
    Creates a versioned quotation enforcing Plan v2 §5 guardrails:
    - Price comes from the price book unless custom scope is flagged.
    - If `is_custom_scope` is True OR `discount_pct > max_discount_pct`:
      status is set to `pending_approval` and `requires_manager_approval = True`.
    - Otherwise, status is `sent` (auto-approved) if `whatsapp_opt_in` is True, or `approved_ready`.
    """
    global _QUOTE_SEQ
    book = get_price_book(account_id)
    pkg = next((p for p in book if p["code"] == package_code), None)
    if not pkg:
        pkg = book[0]

    max_disc = float(pkg.get("max_discount_pct", 10.0))
    req_disc = max(0.0, min(90.0, float(discount_pct or 0.0)))

    # Determine version for this lead
    existing_for_lead = [
        q for q in _QUOTATIONS_STORE.values()
        if q.get("lead_id") == lead_id and q.get("account_id") == account_id
    ]
    version = len(existing_for_lead) + 1

    base_price = float(custom_price_inr) if (is_custom_scope and custom_price_inr is not None) else float(pkg["base_price_inr"])
    discount_amount = round(base_price * (req_disc / 100.0), 2)
    taxable_amount = round(base_price - discount_amount, 2)
    gst_amount = round(taxable_amount * 0.18, 2)  # 18% GST
    total_inr = round(taxable_amount + gst_amount, 2)

    requires_approval = bool(is_custom_scope or (req_disc > max_disc))
    approval_reason = []
    if is_custom_scope:
        approval_reason.append("Custom scope outside standard price book")
    if req_disc > max_disc:
        approval_reason.append(f"Requested discount {req_disc}% exceeds limit of {max_disc}%")

    now_ist = datetime.now(IST)
    valid_until = (now_ist + timedelta(days=max(1, validity_days))).strftime("%Y-%m-%d")

    _QUOTE_SEQ += 1
    quote_id = _QUOTE_SEQ
    quote_number = f"Q-{quote_id}"

    if requires_approval:
        status = "pending_approval"
    else:
        status = "sent" if whatsapp_opt_in else "approved_ready"

    quote = {
        "id": quote_id,
        "quote_number": quote_number,
        "version": version,
        "account_id": account_id,
        "lead_id": lead_id,
        "lead_name": lead_name,
        "lead_phone": lead_phone,
        "package_code": pkg["code"],
        "package_name": pkg["name"],
        "deliverables": custom_scope_notes if (is_custom_scope and custom_scope_notes) else pkg["deliverables"],
        "is_custom_scope": bool(is_custom_scope),
        "custom_scope_notes": custom_scope_notes,
        "base_price_inr": base_price,
        "discount_pct": req_disc,
        "max_discount_pct": max_disc,
        "discount_amount_inr": discount_amount,
        "taxable_amount_inr": taxable_amount,
        "gst_pct": 18.0,
        "gst_amount_inr": gst_amount,
        "total_inr": total_inr,
        "requires_manager_approval": requires_approval,
        "approval_reason": "; ".join(approval_reason) if approval_reason else "Within standard price book guardrails",
        "approved_by": "system_auto" if not requires_approval else None,
        "approved_at": now_ist.isoformat() if not requires_approval else None,
        "status": status,
        "whatsapp_opt_in": bool(whatsapp_opt_in),
        "whatsapp_sent": bool(status == "sent" and whatsapp_opt_in),
        "opened_at": None,
        "replied_at": None,
        "valid_until": valid_until,
        "terms": "50% advance on kick-off, 30% on UAT preview, 20% on final deployment. GST 18% included.",
        "created_by": created_by,
        "created_at": now_ist.isoformat(),
        "updated_at": now_ist.isoformat(),
    }
    _QUOTATIONS_STORE[quote_id] = quote
    return quote


def list_quotations(account_id: int = 1, lead_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists quotations for an account with optional filters."""
    results = [q for q in _QUOTATIONS_STORE.values() if q.get("account_id") == account_id]
    if lead_id is not None:
        results = [q for q in results if q.get("lead_id") == lead_id]
    if status:
        results = [q for q in results if q.get("status") == status]
    return sorted(results, key=lambda x: x["id"], reverse=True)


def get_quotation(quote_id: int, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single quotation by ID."""
    q = _QUOTATIONS_STORE.get(quote_id)
    if not q:
        return None
    if account_id is not None and q.get("account_id") != account_id:
        return None
    return q


def approve_quotation(quote_id: int, manager_email: str = "owner@spassociates.com", account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Manager one-tap approval for custom scope or high-discount quotations (§5)."""
    q = get_quotation(quote_id, account_id=account_id)
    if not q:
        return None
    now_ist = datetime.now(IST).isoformat()
    q["requires_manager_approval"] = False
    q["approved_by"] = manager_email
    q["approved_at"] = now_ist
    q["status"] = "sent" if q.get("whatsapp_opt_in") else "approved_ready"
    q["whatsapp_sent"] = bool(q.get("whatsapp_opt_in"))
    q["updated_at"] = now_ist
    return q


def update_quotation_status(
    quote_id: int,
    new_status: str,
    lost_reason: Optional[str] = None,
    won_amount_inr: Optional[float] = None,
    account_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Updates quotation lifecycle status (`sent`, `opened`, `won`, `lost`, `rejected`)."""
    q = get_quotation(quote_id, account_id=account_id)
    if not q:
        return None
    now_ist = datetime.now(IST).isoformat()
    q["status"] = new_status
    if new_status == "opened" and not q.get("opened_at"):
        q["opened_at"] = now_ist
    if new_status == "won" and won_amount_inr is not None:
        q["won_amount_inr"] = float(won_amount_inr)
    if new_status == "lost" and lost_reason:
        q["lost_reason"] = lost_reason
    q["updated_at"] = now_ist
    return q


def evaluate_quote_followup_needed(quote: Dict[str, Any], now_ist: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Evaluates Plan v2 §5 item 6 quote follow-up rules:
    - Not opened in 24 h -> WhatsApp reminder
    - No reply in 48 h -> AI follow-up call
    - Expiring within 24 h -> Expiry reminder
    """
    now = now_ist or datetime.now(IST)
    if quote.get("status") in {"won", "lost", "pending_approval", "rejected"}:
        return {"action": "none", "reason": f"Quote status is {quote.get('status')}"}

    created_dt = datetime.fromisoformat(quote["created_at"])
    hours_elapsed = (now - created_dt).total_seconds() / 3600.0

    valid_until_str = quote.get("valid_until")
    if valid_until_str:
        valid_dt = datetime.strptime(valid_until_str, "%Y-%m-%d").replace(tzinfo=IST)
        hours_to_expiry = (valid_dt - now).total_seconds() / 3600.0
        if 0 <= hours_to_expiry <= 24:
            return {
                "action": "send_expiry_reminder",
                "channel": "whatsapp",
                "reason": "Quote is expiring within 24 hours",
            }

    if hours_elapsed >= 48 and not quote.get("replied_at"):
        return {
            "action": "ai_followup_call",
            "channel": "ai_call",
            "reason": "No reply within 48 hours of sending quotation",
        }

    if hours_elapsed >= 24 and not quote.get("opened_at"):
        return {
            "action": "whatsapp_quote_nudge",
            "channel": "whatsapp",
            "reason": "Quotation not opened within 24 hours",
        }

    return {"action": "none", "reason": "Within normal wait window"}


def generate_quotation_pdf_bytes(quote: Dict[str, Any]) -> bytes:
    """
    Generates a valid, standalone branded PDF document (`%PDF-1.4`) containing:
    - S P Associates Software Company header
    - Quote Number, Version, Validity Date
    - Client Name & Phone
    - Package Name, Deliverables, Base Price, Discount, 18% GST, Grand Total
    - Terms & Conditions
    """
    lines = [
        "S P ASSOCIATES SOFTWARE COMPANY - OFFICIAL QUOTATION",
        f"Quote No: {quote.get('quote_number')} (v{quote.get('version', 1)})   |   Valid Until: {quote.get('valid_until')}",
        "------------------------------------------------------------------------",
        f"Prepared For : {quote.get('lead_name')} ({quote.get('lead_phone')})",
        f"Package      : {quote.get('package_name')} [{quote.get('package_code')}]",
        f"Scope        : {quote.get('deliverables')}",
        "------------------------------------------------------------------------",
        f"Base Price                 : INR {quote.get('base_price_inr', 0):,.2f}",
        f"Discount ({quote.get('discount_pct', 0)}%)            : -INR {quote.get('discount_amount_inr', 0):,.2f}",
        f"Taxable Amount             : INR {quote.get('taxable_amount_inr', 0):,.2f}",
        f"GST (18% CGST+SGST)        : INR {quote.get('gst_amount_inr', 0):,.2f}",
        f"GRAND TOTAL (Incl. GST)    : INR {quote.get('total_inr', 0):,.2f}",
        "------------------------------------------------------------------------",
        f"Status : {str(quote.get('status', '')).upper()}",
        f"Terms  : {quote.get('terms')}",
    ]

    # Build valid PDF content stream using standard Helvetica Type1 font
    content_ops = ["BT", "/F1 11 Tf", "50 760 Td", "16 TL"]
    for line in lines:
        safe_line = (
            str(line)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        content_ops.append(f"({safe_line}) Tj T*")
    content_ops.append("ET")
    stream_data = "\n".join(content_ops).encode("latin-1", errors="replace")

    objs: List[bytes] = []
    objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objs.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objs.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objs.append(
        f"5 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("ascii")
        + stream_data
        + b"\nendstream\nendobj\n"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for obj in objs:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


STOP_KEYWORDS = {"stop", "unsubscribe", "dnd", "dont message", "don't message", "stop messaging", "opt out", "opt-out"}


def is_whatsapp_stop_message(text: str) -> bool:
    """Checks if an incoming WhatsApp message is a STOP / opt-out request (§6)."""
    cleaned = (text or "").strip().lower()
    if cleaned in STOP_KEYWORDS:
        return True
    return any(cleaned.startswith(k + " ") or cleaned == k for k in STOP_KEYWORDS)
