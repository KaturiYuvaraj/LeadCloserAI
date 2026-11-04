"""
Leads Router - Lead Management, Ingestion, Discovery, Enrichment & Plan v2 (§3) Outcomes
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Response, Request
from fastapi.responses import JSONResponse
from loguru import logger

from core.auth import get_optional_user, get_request_account_id
from database import (
    get_all_leads,
    get_lead_by_id,
    create_lead,
    batch_create_leads,
    update_lead,
    delete_lead,
    get_calls_for_lead,
    update_lead_enrichment,
    override_lead_outcome,
    get_outcome_bucket_summary,
)
from services.excel_service import parse_excel_or_csv, generate_sample_excel_template, generate_leads_export_excel
from services.outcomes import OUTCOME_BUCKETS, OUTCOME_CATALOG
from providers import registry, ProviderType
from schemas.lead import UnifiedLead

router = APIRouter(tags=["leads"])


@router.get("/api/leads/outcomes/summary")
async def api_get_outcome_summary(request: Request):
    """Return 4-bucket (Hot, Follow-up, Closed, Not reachable) & 13-label counts + human review list."""
    account_id = get_request_account_id(request)
    return get_outcome_bucket_summary(account_id=account_id)


@router.get("/api/leads/outcomes/catalog")
async def api_get_outcome_catalog():
    """Return the official Plan v2 (§3) 4 buckets and 13 outcome labels."""
    return {"buckets": OUTCOME_BUCKETS, "outcomes": OUTCOME_CATALOG}


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
async def api_upload_excel_leads(request: Request, file: UploadFile = File(...)):
    """
    Upload Excel (.xlsx) or CSV file with lead details.
    Parses customer name, phone, service needed, budget, notes, etc.
    """
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, and .csv files are supported.")

    account_id = get_request_account_id(request) or 1
    file_bytes = await file.read()
    leads, errors = parse_excel_or_csv(file_bytes, file.filename)

    if not leads and errors:
        return JSONResponse(status_code=400, content={"success": False, "errors": errors})

    inserted, updated = batch_create_leads(leads, account_id=account_id)
    logger.info(f"Ingested {len(leads)} leads from {file.filename}: {inserted} inserted, {updated} updated.")

    return {
        "success": True,
        "total_parsed": len(leads),
        "inserted": inserted,
        "updated": updated,
        "errors": errors
    }


@router.get("/api/leads")
async def api_get_leads(
    request: Request,
    bucket: Optional[str] = None,
    outcome: Optional[str] = None,
):
    account_id = get_request_account_id(request)
    leads = get_all_leads(account_id=account_id)
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
    return {"leads": leads}


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
