from services.lead_scoring import score_lead, score_leads_batch
"""
Leads Router - Lead Management, Ingestion (Excel/CSV/Paste), DND/Opt-Out & Plan v2 (§3) Outcomes
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Form, HTTPException, UploadFile, File, Response, Request
from fastapi.responses import JSONResponse
from loguru import logger

from core.auth import get_optional_user, get_request_account_id
from database import (
    get_all_leads,
    get_lead_by_id,
    create_lead,
    batch_create_leads,
    import_leads_with_report,
    update_lead,
    delete_lead,
    get_calls_for_lead,
    update_lead_enrichment,
    override_lead_outcome,
    get_outcome_bucket_summary,
    get_opt_outs,
    add_opt_out,
    remove_opt_out,
)
from services.excel_service import (
    parse_excel_or_csv,
    parse_pasted_leads,
    generate_sample_excel_template,
    generate_leads_export_excel,
    generate_rejected_rows_csv,
)
from services.outcomes import OUTCOME_BUCKETS, OUTCOME_CATALOG
from providers import registry, ProviderType
from schemas.lead import UnifiedLead

router = APIRouter(tags=["leads"])

# Store latest import rejected rows per account for instant CSV download
_LAST_REJECTED_BY_ACCOUNT: Dict[int, List[Dict[str, Any]]] = {}


@router.get("/api/leads/outcomes/summary")
async def api_get_outcome_summary(request: Request):
    """Return 4-bucket (Hot, Follow-up, Closed, Not reachable) & 13-label counts + human review list."""
    account_id = get_request_account_id(request)
    return get_outcome_bucket_summary(account_id=account_id)


@router.get("/api/leads/outcomes/catalog")
async def api_get_outcome_catalog():
    """Return the official Plan v2 (§3) 4 buckets and 13 outcome labels."""
    return {"buckets": OUTCOME_BUCKETS, "outcomes": OUTCOME_CATALOG}


@router.get("/api/leads/human-review")
async def api_get_human_review_leads(request: Request):
    """Return leads flagged with low-confidence outcome labels for human review (§3 & §7)."""
    account_id = get_request_account_id(request)
    summary = get_outcome_bucket_summary(account_id=account_id)
    return {
        "count": summary["human_review_count"],
        "leads": summary["human_review_leads"],
    }


@router.get("/api/leads/template")
async def api_download_template():
    """Download a formatted Excel template for easy lead upload."""
    excel_bytes = generate_sample_excel_template()
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads_template.xlsx"}
    )


@router.get("/api/leads/export-excel")
async def api_export_leads_excel(request: Request):
    """
    Download all leads with their AI conversation summaries, deal stages,
    sentiments, objections, and action items in an Excel report.
    """
    account_id = get_request_account_id(request)
    leads = get_all_leads(account_id=account_id)
    excel_bytes = generate_leads_export_excel(leads)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leads_with_call_summaries.xlsx"}
    )


@router.post("/api/leads/upload-excel")
async def api_upload_excel_leads(
    request: Request,
    file: UploadFile = File(...),
    source_tag: str = Form("csv"),
    campaign_tag: str = Form(""),
    marketer_tag: str = Form(""),
    consent_confirmed: bool = Form(True),
    strict_phone: bool = Form(False),
):
    """
    Upload Excel (.xlsx) or CSV file with lead details (Phase A / Y6).
    Cleans +91 numbers, merges duplicates, checks Do-Not-Call / Opt-Out list,
    tags source/campaign/marketer, and returns an import report + rejected rows.
    """
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, and .csv files are supported.")

    account_id = get_request_account_id(request) or 1
    file_bytes = await file.read()
    leads, errors = parse_excel_or_csv(file_bytes, file.filename)

    if not leads and errors:
        return JSONResponse(status_code=400, content={"success": False, "errors": errors})

    consent_src = "import_confirmed" if consent_confirmed else ""
    report = import_leads_with_report(
        leads=leads,
        account_id=account_id,
        source_tag=source_tag or "csv",
        campaign_tag=campaign_tag,
        marketer_tag=marketer_tag,
        consent_source=consent_src,
        strict_phone=strict_phone,
    )
    _LAST_REJECTED_BY_ACCOUNT[account_id] = report.get("rejected_rows", [])

    logger.info(
        f"Ingested {len(leads)} rows from {file.filename}: "
        f"{report['inserted']} inserted, {report['updated']} updated, {report['rejected_count']} rejected."
    )

    return {
        "success": True,
        "total_parsed": len(leads),
        "inserted": report["inserted"],
        "updated": report["updated"],
        "merged_existing": report["updated"],
        "rejected_count": report["rejected_count"],
        "rejected_rows": report["rejected_rows"],
        "rejected_csv_url": "/api/leads/import-report/rejected.csv" if report["rejected_count"] else None,
        "source_tag": report["source_tag"],
        "campaign_tag": report["campaign_tag"],
        "marketer_tag": report["marketer_tag"],
        "errors": errors,
    }


@router.post("/api/leads/import-paste")
async def api_import_pasted_leads(payload: Dict[str, Any], request: Request):
    """
    Import leads pasted from Excel, Google Sheets, or CSV text (Phase A).
    """
    raw_text = str(payload.get("raw_text") or payload.get("text") or "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="No text provided to import.")

    account_id = get_request_account_id(request) or 1
    leads, errors = parse_pasted_leads(raw_text)
    if not leads and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    consent_confirmed = bool(payload.get("consent_confirmed", True))
    report = import_leads_with_report(
        leads=leads,
        account_id=account_id,
        source_tag=str(payload.get("source_tag") or "paste"),
        campaign_tag=str(payload.get("campaign_tag") or ""),
        marketer_tag=str(payload.get("marketer_tag") or ""),
        consent_source=str(payload.get("consent_source") or ("import_confirmed" if consent_confirmed else "")),
        strict_phone=bool(payload.get("strict_phone", True)),
    )
    _LAST_REJECTED_BY_ACCOUNT[account_id] = report.get("rejected_rows", [])

    return {
        "success": True,
        "total_parsed": len(leads),
        "inserted": report["inserted"],
        "updated": report["updated"],
        "merged_existing": report["updated"],
        "rejected_count": report["rejected_count"],
        "rejected_rows": report["rejected_rows"],
        "rejected_csv_url": "/api/leads/import-report/rejected.csv" if report["rejected_count"] else None,
        "errors": errors,
    }


@router.get("/api/leads/import-report/rejected.csv")
async def api_download_rejected_rows_csv(request: Request):
    """Download the rejected rows and reasons from the most recent import as a CSV file."""
    account_id = get_request_account_id(request) or 1
    rejected = _LAST_REJECTED_BY_ACCOUNT.get(account_id, [])
    csv_bytes = generate_rejected_rows_csv(rejected)
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=rejected_leads_report.csv"},
    )


# ---------------- DO-NOT-CALL / OPT-OUT LIST (Phase A & Y7) ----------------

@router.get("/api/opt-outs")
async def api_list_opt_outs(request: Request):
    account_id = get_request_account_id(request) or 1
    return {"opt_outs": get_opt_outs(account_id=account_id)}


@router.post("/api/opt-outs")
async def api_create_opt_out(payload: Dict[str, Any], request: Request):
    phone = str(payload.get("phone") or payload.get("phone_e164") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    reason = str(payload.get("reason") or "manual_dnd")
    account_id = get_request_account_id(request) or 1
    row = add_opt_out(phone=phone, reason=reason, account_id=account_id)
    return {"success": True, "opt_out": row}


@router.delete("/api/opt-outs/{item}")
async def api_delete_opt_out(item: str, request: Request):
    account_id = get_request_account_id(request) or 1
    ok = remove_opt_out(item=item, account_id=account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Opt-out entry not found")
    return {"success": True}


# ---------------- LEADS CRUD & FILTERS ----------------

@router.get("/api/leads")
async def api_get_leads(
    request: Request,
    bucket: Optional[str] = None,
    outcome: Optional[str] = None,
    source: Optional[str] = None,
    campaign: Optional[str] = None,
    marketer: Optional[str] = None,
    search: Optional[str] = None,
    score_category: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    sort_by: str = "id",
    order: str = "desc",
):
    account_id = get_request_account_id(request)
    leads = get_all_leads(account_id=account_id)

    # 1. Bucket & Outcome filters
    if bucket:
        b = bucket.strip().lower()
        leads = [l for l in leads if (l.get("outcome_bucket") or "").lower() == b]
    if outcome:
        o = outcome.strip().lower()
        leads = [
            l for l in leads
            if (l.get("outcome_label") or "").lower() == o
            or (l.get("last_outcome") or "").lower() == o
        ]
    if source:
        s = source.strip().lower()
        leads = [l for l in leads if (l.get("source") or "").lower() == s]
    if campaign:
        c = campaign.strip().lower()
        leads = [l for l in leads if (l.get("campaign_tag") or "").lower() == c]
    if marketer:
        m = marketer.strip().lower()
        leads = [l for l in leads if (l.get("marketer_tag") or "").lower() == m]

    # 2. Text search across name, company, phone, notes
    if search:
        q = search.strip().lower()
        leads = [
            l for l in leads
            if q in (l.get("name") or "").lower()
            or q in (l.get("company") or "").lower()
            or q in (l.get("phone") or "").lower()
            or q in (l.get("notes") or "").lower()
        ]

    # 3. Score Category filter (HOT, WARM, COLD)
    if score_category:
        cat = score_category.strip().upper()
        if cat == "HOT":
            leads = [l for l in leads if (float(l.get("score") or 0) >= 80)]
        elif cat == "WARM":
            leads = [l for l in leads if (50 <= float(l.get("score") or 0) < 80)]
        elif cat == "COLD":
            leads = [l for l in leads if (float(l.get("score") or 0) < 50)]

    # 4. Sorting
    reverse = (order.lower() == "desc")
    try:
        if sort_by in {"id", "score"}:
            leads.sort(key=lambda x: float(x.get(sort_by) or 0), reverse=reverse)
        else:
            leads.sort(key=lambda x: str(x.get(sort_by) or "").lower(), reverse=reverse)
    except Exception:
        pass

    total = len(leads)

    # 5. Pagination
    if limit is not None and limit > 0:
        paginated_leads = leads[offset: offset + limit]
    else:
        paginated_leads = leads[offset:] if offset > 0 else leads

    return {
        "leads": paginated_leads,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/leads/{lead_id}")
async def api_get_lead(lead_id: int, request: Request):
    account_id = get_request_account_id(request)
    lead = get_lead_by_id(lead_id, account_id=account_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead": lead}


@router.post("/api/leads")
async def api_create_lead(lead_data: Dict[str, Any], request: Request):
    account_id = get_request_account_id(request) or 1
    lead_id = create_lead(lead_data, account_id=account_id)
    return {"success": True, "lead_id": lead_id}


@router.post("/api/leads/{lead_id}/outcome")
async def api_override_lead_outcome(lead_id: int, payload: Dict[str, Any], request: Request):
    """
    Rep override of a lead's call outcome (§3 & §7).
    Saves the corrected outcome_label, outcome_bucket, reason, callback_at,
    honors do_not_call -> opt_outs, and logs an AuditLog row.
    """
    user = get_optional_user(request)
    account_id = int(user["account_id"]) if user else 1
    user_id = int(user["id"]) if user else None

    existing = get_lead_by_id(lead_id, account_id=account_id if user else None)
    if not existing:
        raise HTTPException(status_code=404, detail="Lead not found")

    outcome_label = (payload.get("outcome_label") or payload.get("outcome") or "").strip()
    if not outcome_label:
        raise HTTPException(status_code=400, detail="outcome_label is required")

    updated = override_lead_outcome(
        lead_id=lead_id,
        outcome_label=outcome_label,
        reason=str(payload.get("reason") or ""),
        callback_at=payload.get("callback_at"),
        user_id=user_id,
        account_id=account_id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Failed to update lead outcome")
    return {"success": True, "lead": updated}


@router.post("/api/leads/discover")
async def api_discover_leads(payload: Dict[str, Any]):
    """Discover prospective leads via Apollo.io B2B search or Apify web scraping."""
    provider_name = payload.get("provider", "apollo").lower()
    filters = payload.get("filters", {})
    limit = int(payload.get("limit", 15))

    provider = registry.get(ProviderType.LEAD_DISCOVERY, provider_name)
    if not provider:
        raise HTTPException(status_code=400, detail=f"Lead discovery provider '{provider_name}' not found.")

    if not provider.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": f"Provider '{provider_name.upper()}' is not configured with an API credential. Please configure it in Integrations > Settings or set the environment variable.",
                "provider": provider_name,
                "leads": []
            }
        )

    try:
        leads = await provider.search_leads(filters, limit=limit)
        leads_dict = [l.to_dict() for l in leads]
        return {
            "success": True,
            "provider": provider_name,
            "count": len(leads_dict),
            "leads": leads_dict
        }
    except Exception as e:
        logger.error(f"Lead discovery failed for {provider_name}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "provider": provider_name,
                "leads": []
            }
        )


@router.post("/api/leads/discover/import")
async def api_import_discovered_leads(payload: Dict[str, Any], request: Request):
    """Import selected discovered leads into the CRM database pipeline."""
    leads_data = payload.get("leads", [])
    if not leads_data:
        raise HTTPException(status_code=400, detail="No leads provided for import.")

    account_id = get_request_account_id(request) or 1
    inserted = 0
    for l_data in leads_data:
        try:
            create_lead(l_data, account_id=account_id)
            inserted += 1
        except Exception as e:
            logger.warning(f"Error importing discovered lead {l_data.get('name')}: {e}")

    return {
        "success": True,
        "imported_count": inserted,
        "message": f"Successfully imported {inserted} discovered leads into CRM station."
    }


@router.post("/api/leads/{lead_id}/enrich")
async def api_enrich_lead(lead_id: int, request: Request, payload: Optional[Dict[str, Any]] = None):
    """
    Enrich an existing CRM lead with organization intelligence, tech stack, and digital footprint
    via active Apollo or Apify providers.
    """
    account_id = get_request_account_id(request)
    lead = get_lead_by_id(lead_id, account_id=account_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    provider_name = (payload or {}).get("provider", "apollo").lower()
    provider = registry.get(ProviderType.LEAD_DISCOVERY, provider_name)
    if not provider or not provider.is_configured():
        alt_name = "apify" if provider_name == "apollo" else "apollo"
        alt_provider = registry.get(ProviderType.LEAD_DISCOVERY, alt_name)
        if alt_provider and alt_provider.is_configured():
            provider = alt_provider
            provider_name = alt_name

    if not provider or not provider.is_configured():
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Neither Apollo nor Apify is configured with valid credentials in Integrations Settings.",
                "lead_id": lead_id
            }
        )

    unified_lead = UnifiedLead.from_db_row(lead)
    try:
        enriched_lead = await provider.enrich_lead(unified_lead)
        enrichment_dict = enriched_lead.enrichment.to_dict() if enriched_lead.enrichment else {}

        extra = {
            "industry": enriched_lead.industry,
            "website": enriched_lead.website,
            "designation": enriched_lead.designation,
            "location": enriched_lead.location,
            "company": enriched_lead.company
        }
        update_lead_enrichment(lead_id, enrichment_dict, extra=extra)

        updated_lead = get_lead_by_id(lead_id, account_id=account_id)
        return {
            "success": True,
            "provider": provider_name,
            "lead": updated_lead,
            "enrichment": enrichment_dict
        }
    except Exception as e:
        logger.error(f"Enrichment error for lead {lead_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "lead_id": lead_id}
        )


@router.get("/api/leads/{lead_id}/calls")
async def api_get_lead_calls(lead_id: int, request: Request):
    account_id = get_request_account_id(request)
    return {"calls": get_calls_for_lead(lead_id, account_id=account_id)}


@router.put("/api/leads/{lead_id}")
async def api_update_lead(lead_id: int, updates: Dict[str, Any], request: Request):
    account_id = get_request_account_id(request)
    ok = update_lead(lead_id, updates, account_id=account_id)
    if not ok and account_id is not None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": ok}


@router.delete("/api/leads/{lead_id}")
async def api_delete_lead(lead_id: int, request: Request):
    account_id = get_request_account_id(request)
    ok = delete_lead(lead_id, account_id=account_id)
    if not ok and account_id is not None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"success": ok}


# ---------------- EXPLAINABLE SCORING & BULK ACTIONS ----------------

@router.post("/api/leads/{lead_id}/score")
async def api_score_single_lead(lead_id: int, request: Request, payload: Optional[Dict[str, Any]] = None):
    """
    Compute an explainable 0–100 score for a lead across the 5 transparent factors,
    store the score and factor breakdown on the lead, and return the report.
    """
    account_id = get_request_account_id(request)
    lead = get_lead_by_id(lead_id, account_id=account_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    weights = (payload or {}).get("weights")
    scoring_result = score_lead(lead, weights=weights)

    # Persist score and scoring breakdown in variables
    variables = lead.get("variables") or {}
    variables["scoring"] = scoring_result
    update_lead(lead_id, {"score": scoring_result["total_score"], "variables": variables}, account_id=account_id)

    return {"success": True, "lead_id": lead_id, "score": scoring_result}


@router.post("/api/leads/score-all")
async def api_score_all_leads(request: Request, payload: Optional[Dict[str, Any]] = None):
    """
    Batch-score all leads for the account and update their qualification scores.
    """
    account_id = get_request_account_id(request)
    leads = get_all_leads(account_id=account_id)
    weights = (payload or {}).get("weights")

    results = []
    hot = warm = cold = 0

    for l in leads:
        sc = score_lead(l, weights=weights)
        variables = l.get("variables") or {}
        variables["scoring"] = sc
        update_lead(l["id"], {"score": sc["total_score"], "variables": variables}, account_id=account_id)

        cat = sc["category"]
        if cat == "HOT":
            hot += 1
        elif cat == "WARM":
            warm += 1
        else:
            cold += 1

        results.append({"id": l["id"], "score": sc["total_score"], "category": cat})

    return {
        "success": True,
        "scored_count": len(leads),
        "hot_count": hot,
        "warm_count": warm,
        "cold_count": cold,
        "results": results,
    }


@router.post("/api/leads/bulk-delete")
async def api_bulk_delete_leads(payload: Dict[str, Any], request: Request):
    """Delete multiple leads safely within tenant scope."""
    lead_ids = payload.get("lead_ids", [])
    if not lead_ids or not isinstance(lead_ids, list):
        raise HTTPException(status_code=400, detail="lead_ids array is required")

    account_id = get_request_account_id(request)
    deleted = 0
    for lid in lead_ids:
        try:
            ok = delete_lead(int(lid), account_id=account_id)
            if ok:
                deleted += 1
        except Exception as e:
            logger.warning(f"Failed deleting lead {lid}: {e}")

    return {"success": True, "deleted_count": deleted}


@router.post("/api/leads/bulk-assign")
async def api_bulk_assign_leads(payload: Dict[str, Any], request: Request):
    """Assign multiple leads to a team member or salesperson."""
    lead_ids = payload.get("lead_ids", [])
    assigned_to = (payload.get("assigned_to") or "").strip()
    if not lead_ids or not isinstance(lead_ids, list):
        raise HTTPException(status_code=400, detail="lead_ids array is required")
    if not assigned_to:
        raise HTTPException(status_code=400, detail="assigned_to name or email is required")

    account_id = get_request_account_id(request)
    assigned = 0
    for lid in lead_ids:
        try:
            ok = update_lead(int(lid), {"assigned_to": assigned_to}, account_id=account_id)
            if ok:
                assigned += 1
        except Exception as e:
            logger.warning(f"Failed assigning lead {lid}: {e}")

    return {"success": True, "assigned_count": assigned, "assigned_to": assigned_to}
