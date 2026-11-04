"""
Quotation Guardrails, Price Book, Branded PDF Generator & WhatsApp Opt-In/STOP Engine (Plan v2 §5 & §6).

Implements:
1. Database-persisted Price Book management for S P Associates Software Company
   (standard packages + max auto-discount limits).
2. Quotation Guardrails:
   - Standard package within discount limit (<= 10%) and no custom scope -> auto-approved & ready/sent.
   - Custom scope OR discount above limit (> 10%) -> blocked in `pending_approval` until manager approves.
3. Versioned Quotations (auto-superseding prior drafts) with 18% GST calculation,
   validity date, and line-wrapped branded PDF generation (`%PDF-1.4`).
4. Quote follow-up cadence checker (24h not opened -> WhatsApp; 48h no reply -> AI call; expiring -> reminder).
5. WhatsApp opt-in verification and instant `"STOP"` opt-out enforcement.
"""

import json
import re
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from loguru import logger
from sqlalchemy import text

from core.db import engine

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

_CUSTOM_PRICE_BOOK_BY_ACCOUNT: Dict[int, List[Dict[str, Any]]] = {}
_QUOTATIONS_STORE: Dict[int, Dict[str, Any]] = {}
_QUOTE_SEQ: int = 1040
_DB_TABLES_READY: bool = False


def _ensure_tables() -> None:
    """Ensures SQLite/PostgreSQL persistence tables exist and loads stored rows into memory."""
    global _DB_TABLES_READY, _QUOTE_SEQ
    if _DB_TABLES_READY:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS price_book_store (
                        account_id INTEGER NOT NULL,
                        code VARCHAR(128) NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at VARCHAR(64),
                        PRIMARY KEY (account_id, code)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS quotations_store (
                        id INTEGER PRIMARY KEY,
                        account_id INTEGER NOT NULL,
                        lead_id INTEGER NOT NULL,
                        status VARCHAR(64) NOT NULL,
                        payload_json TEXT NOT NULL,
                        updated_at VARCHAR(64)
                    )
                    """
                )
            )
            pb_rows = conn.execute(text("SELECT account_id, payload_json FROM price_book_store")).fetchall()
            for acc_id, payload_str in pb_rows:
                try:
                    item = json.loads(payload_str)
                    acc_int = int(acc_id)
                    if acc_int not in _CUSTOM_PRICE_BOOK_BY_ACCOUNT:
                        _CUSTOM_PRICE_BOOK_BY_ACCOUNT[acc_int] = [dict(x) for x in DEFAULT_PRICE_BOOK]
                    book = _CUSTOM_PRICE_BOOK_BY_ACCOUNT[acc_int]
                    replaced = False
                    for idx, ex in enumerate(book):
                        if ex.get("code") == item.get("code"):
                            book[idx] = item
                            replaced = True
                            break
                    if not replaced:
                        book.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse price_book_store row: {e}")

            q_rows = conn.execute(text("SELECT id, payload_json FROM quotations_store")).fetchall()
            for qid, payload_str in q_rows:
                try:
                    q_obj = json.loads(payload_str)
                    qid_int = int(qid)
                    _QUOTATIONS_STORE[qid_int] = q_obj
                    if qid_int > _QUOTE_SEQ:
                        _QUOTE_SEQ = qid_int
                except Exception as e:
                    logger.warning(f"Failed to parse quotations_store row: {e}")

        _DB_TABLES_READY = True
    except Exception as e:
        logger.warning(f"Quotation persistence table init warning: {e}")


def _persist_quotation(quote: Dict[str, Any]) -> None:
    """Persists a quotation dictionary into `quotations_store`."""
    _ensure_tables()
    try:
        payload_str = json.dumps(quote, ensure_ascii=False)
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM quotations_store WHERE id = :id"),
                {"id": int(quote["id"])},
            ).fetchone()
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE quotations_store
                        SET status = :status, payload_json = :payload, updated_at = :updated_at
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": int(quote["id"]),
                        "status": str(quote.get("status", "draft")),
                        "payload": payload_str,
                        "updated_at": str(quote.get("updated_at", "")),
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO quotations_store (id, account_id, lead_id, status, payload_json, updated_at)
                        VALUES (:id, :account_id, :lead_id, :status, :payload, :updated_at)
                        """
                    ),
                    {
                        "id": int(quote["id"]),
                        "account_id": int(quote.get("account_id", 1)),
                        "lead_id": int(quote.get("lead_id", 0)),
                        "status": str(quote.get("status", "draft")),
                        "payload": payload_str,
                        "updated_at": str(quote.get("updated_at", "")),
                    },
                )
    except Exception as e:
        logger.warning(f"Failed to persist quotation {quote.get('id')}: {e}")


def _persist_price_book_item(account_id: int, entry: Dict[str, Any]) -> None:
    """Persists a price book item into `price_book_store`."""
    _ensure_tables()
    try:
        payload_str = json.dumps(entry, ensure_ascii=False)
        now_str = datetime.now(IST).isoformat()
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT code FROM price_book_store WHERE account_id = :acc AND code = :code"),
                {"acc": account_id, "code": entry["code"]},
            ).fetchone()
            if existing:
                conn.execute(
                    text(
                        """
                        UPDATE price_book_store
                        SET payload_json = :payload, updated_at = :updated_at
                        WHERE account_id = :acc AND code = :code
                        """
                    ),
                    {"acc": account_id, "code": entry["code"], "payload": payload_str, "updated_at": now_str},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO price_book_store (account_id, code, payload_json, updated_at)
                        VALUES (:acc, :code, :payload, :updated_at)
                        """
                    ),
                    {"acc": account_id, "code": entry["code"], "payload": payload_str, "updated_at": now_str},
                )
    except Exception as e:
        logger.warning(f"Failed to persist price book item {entry.get('code')}: {e}")


def _parse_iso_ist(raw_iso: Optional[str]) -> Optional[datetime]:
    """Python 3.9+ safe ISO-8601 parser that always returns a timezone-aware IST datetime."""
    if not raw_iso or not isinstance(raw_iso, str):
        return None
    cleaned = raw_iso.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except ValueError:
        return None


def get_price_book(account_id: int = 1) -> List[Dict[str, Any]]:
    """Returns the active price book for an account."""
    _ensure_tables()
    if account_id not in _CUSTOM_PRICE_BOOK_BY_ACCOUNT:
        _CUSTOM_PRICE_BOOK_BY_ACCOUNT[account_id] = [dict(item) for item in DEFAULT_PRICE_BOOK]
    return _CUSTOM_PRICE_BOOK_BY_ACCOUNT[account_id]


def upsert_price_book_item(item_data: Dict[str, Any], account_id: int = 1) -> Dict[str, Any]:
    """Adds or updates a package in the account's price book."""
    book = get_price_book(account_id)
    code = str(item_data.get("code") or "").strip() or f"pkg_custom_{len(book) + 1}"
    base_price = max(0.0, float(item_data.get("base_price_inr", 30000.0) or 30000.0))
    max_disc = max(0.0, min(90.0, float(item_data.get("max_discount_pct", 10.0) or 10.0)))

    entry: Dict[str, Any] = {
        "code": code,
        "name": str(item_data.get("name") or "Custom Software Package"),
        "category": str(item_data.get("category") or "Software Services"),
        "base_price_inr": base_price,
        "max_discount_pct": max_disc,
        "delivery_days": max(1, int(item_data.get("delivery_days", 14) or 14)),
        "deliverables": str(item_data.get("deliverables") or "Standard software deliverables"),
        "active": bool(item_data.get("active", True)),
    }
    updated_in_list = False
    for idx, existing in enumerate(book):
        if existing["code"] == code:
            book[idx] = entry
            updated_in_list = True
            break
    if not updated_in_list:
        book.append(entry)

    _persist_price_book_item(account_id, entry)
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
    _ensure_tables()
    book = get_price_book(account_id)
    pkg: Optional[Dict[str, Any]] = next((p for p in book if p.get("code") == package_code), None)
    if not pkg:
        if is_custom_scope:
            pkg = {
                "code": package_code or "pkg_custom_scope",
                "name": "Custom Software Solution",
                "base_price_inr": float(custom_price_inr or 50000.0),
                "max_discount_pct": 10.0,
                "deliverables": custom_scope_notes or "Custom software scope as discussed",
            }
        elif book:
            pkg = book[0]
        else:
            pkg = dict(DEFAULT_PRICE_BOOK[0])

    max_disc = float(pkg.get("max_discount_pct", 10.0))
    req_disc = max(0.0, min(90.0, float(discount_pct or 0.0)))

    # Determine version for this lead and supersede previous open versions
    existing_for_lead = [
        q for q in _QUOTATIONS_STORE.values()
        if q.get("lead_id") == lead_id and q.get("account_id") == account_id
    ]
    version = len(existing_for_lead) + 1
    now_ist = datetime.now(IST)
    for prev_q in existing_for_lead:
        if prev_q.get("status") in {"pending_approval", "approved_ready", "draft"}:
            prev_q["status"] = "superseded"
            prev_q["updated_at"] = now_ist.isoformat()
            _persist_quotation(prev_q)

    raw_base = float(custom_price_inr) if (is_custom_scope and custom_price_inr is not None) else float(pkg["base_price_inr"])
    base_price = max(0.0, raw_base)
    discount_amount = round(base_price * (req_disc / 100.0), 2)
    taxable_amount = round(max(0.0, base_price - discount_amount), 2)
    gst_amount = round(taxable_amount * 0.18, 2)  # 18% GST
    total_inr = round(taxable_amount + gst_amount, 2)

    requires_approval = bool(is_custom_scope or (req_disc > max_disc))
    approval_reason: List[str] = []
    if is_custom_scope:
        approval_reason.append("Custom scope outside standard price book")
    if req_disc > max_disc:
        approval_reason.append(f"Requested discount {req_disc}% exceeds limit of {max_disc}%")

    valid_until = (now_ist + timedelta(days=max(1, int(validity_days or 7)))).strftime("%Y-%m-%d")

    _QUOTE_SEQ += 1
    quote_id = _QUOTE_SEQ
    quote_number = f"Q-{quote_id}"

    if requires_approval:
        status = "pending_approval"
    else:
        status = "sent" if whatsapp_opt_in else "approved_ready"

    quote: Dict[str, Any] = {
        "id": quote_id,
        "quote_number": quote_number,
        "version": version,
        "account_id": account_id,
        "lead_id": lead_id,
        "lead_name": str(lead_name or "Valued Client"),
        "lead_phone": str(lead_phone or "+910000000000"),
        "package_code": str(pkg["code"]),
        "package_name": str(pkg["name"]),
        "deliverables": str(custom_scope_notes if (is_custom_scope and custom_scope_notes) else pkg["deliverables"]),
        "is_custom_scope": bool(is_custom_scope),
        "custom_scope_notes": str(custom_scope_notes or ""),
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
        "created_by": str(created_by or "ai_agent"),
        "created_at": now_ist.isoformat(),
        "updated_at": now_ist.isoformat(),
    }
    _QUOTATIONS_STORE[quote_id] = quote
    _persist_quotation(quote)
    return quote


def list_quotations(account_id: int = 1, lead_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists quotations for an account with optional filters."""
    _ensure_tables()
    results = [q for q in _QUOTATIONS_STORE.values() if q.get("account_id") == account_id]
    if lead_id is not None:
        results = [q for q in results if q.get("lead_id") == lead_id]
    if status:
        results = [q for q in results if q.get("status") == status]
    return sorted(results, key=lambda x: int(x.get("id", 0)), reverse=True)


def get_quotation(quote_id: int, account_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single quotation by ID."""
    _ensure_tables()
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
    _persist_quotation(q)
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
    _persist_quotation(q)
    return q


def evaluate_quote_followup_needed(quote: Dict[str, Any], now_ist: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Evaluates Plan v2 §5 item 6 quote follow-up rules:
    - Not opened in 24 h -> WhatsApp reminder
    - No reply in 48 h -> AI follow-up call
    - Expiring within 24 h -> Expiry reminder
    """
    if now_ist is None:
        now = datetime.now(IST)
    elif now_ist.tzinfo is None:
        now = now_ist.replace(tzinfo=IST)
    else:
        now = now_ist.astimezone(IST)

    if quote.get("status") in {"won", "lost", "pending_approval", "rejected", "superseded"}:
        return {"action": "none", "reason": f"Quote status is {quote.get('status')}"}

    created_dt = _parse_iso_ist(str(quote.get("created_at") or "")) or now
    hours_elapsed = max(0.0, (now - created_dt).total_seconds() / 3600.0)

    valid_until_str = str(quote.get("valid_until") or "").strip()
    if valid_until_str:
        try:
            valid_dt = datetime.strptime(valid_until_str, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=IST
            )
            hours_to_expiry = (valid_dt - now).total_seconds() / 3600.0
            if 0.0 <= hours_to_expiry <= 24.0:
                return {
                    "action": "send_expiry_reminder",
                    "channel": "whatsapp",
                    "reason": "Quote is expiring within 24 hours",
                }
        except ValueError:
            pass

    if hours_elapsed >= 48.0 and not quote.get("replied_at"):
        return {
            "action": "ai_followup_call",
            "channel": "ai_call",
            "reason": "No reply within 48 hours of sending quotation",
        }

    if hours_elapsed >= 24.0 and not quote.get("opened_at"):
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
    - Package Name, Deliverables (auto line-wrapped), Base Price, Discount, 18% GST, Grand Total
    - Terms & Conditions
    """
    base_price = float(quote.get("base_price_inr") or 0.0)
    discount_pct = float(quote.get("discount_pct") or 0.0)
    discount_amt = float(quote.get("discount_amount_inr") or 0.0)
    taxable_amt = float(quote.get("taxable_amount_inr") or 0.0)
    gst_amt = float(quote.get("gst_amount_inr") or 0.0)
    total_inr = float(quote.get("total_inr") or 0.0)

    scope_text = str(quote.get("deliverables") or "Standard software deliverables").replace("₹", "INR ")
    wrapped_scope = textwrap.wrap(scope_text, width=68) or [scope_text]

    terms_text = str(quote.get("terms") or "").replace("₹", "INR ")
    wrapped_terms = textwrap.wrap(terms_text, width=68) or [terms_text]

    lines: List[str] = [
        "S P ASSOCIATES SOFTWARE COMPANY - OFFICIAL QUOTATION",
        f"Quote No: {quote.get('quote_number', 'Q-1000')} (v{quote.get('version', 1)})   |   Valid Until: {quote.get('valid_until', '-')}",
        "------------------------------------------------------------------------",
        f"Prepared For : {quote.get('lead_name', 'Valued Client')} ({quote.get('lead_phone', '')})",
        f"Package      : {quote.get('package_name', '')} [{quote.get('package_code', '')}]",
        f"Scope        : {wrapped_scope[0]}",
    ]
    for extra_scope_line in wrapped_scope[1:]:
        lines.append(f"               {extra_scope_line}")

    lines.extend(
        [
            "------------------------------------------------------------------------",
            f"Base Price                 : INR {base_price:,.2f}",
            f"Discount ({discount_pct:.1f}%)            : -INR {discount_amt:,.2f}",
            f"Taxable Amount             : INR {taxable_amt:,.2f}",
            f"GST (18% CGST+SGST)        : INR {gst_amt:,.2f}",
            f"GRAND TOTAL (Incl. GST)    : INR {total_inr:,.2f}",
            "------------------------------------------------------------------------",
            f"Status : {str(quote.get('status', 'draft')).upper()}",
            f"Terms  : {wrapped_terms[0]}",
        ]
    )
    for extra_term_line in wrapped_terms[1:]:
        lines.append(f"         {extra_term_line}")

    # Build valid PDF content stream using standard Helvetica Type1 font
    content_ops: List[str] = ["BT", "/F1 11 Tf", "50 760 Td", "16 TL"]
    for line in lines:
        safe_line = (
            str(line)
            .replace("₹", "INR ")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        content_ops.append(f"({safe_line}) Tj T*")
    content_ops.append("ET")
    stream_data = "\n".join(content_ops).encode("latin-1", errors="replace")

    objs: List[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("ascii")
            + stream_data
            + b"\nendstream\nendobj\n"
        ),
    ]

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


STOP_KEYWORDS: Set[str] = {
    "stop",
    "unsubscribe",
    "dnd",
    "dont message",
    "don't message",
    "stop messaging",
    "opt out",
    "opt-out",
}


def is_whatsapp_stop_message(text_msg: str) -> bool:
    """Checks if an incoming WhatsApp message is a STOP / opt-out request (§6)."""
    cleaned = re.sub(r"[.!?,;:]+$", "", (text_msg or "").strip().lower()).strip()
    if cleaned in STOP_KEYWORDS:
        return True
    return any(cleaned.startswith(k + " ") or cleaned == k for k in STOP_KEYWORDS)
