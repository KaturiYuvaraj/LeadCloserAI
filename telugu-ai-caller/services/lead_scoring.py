"""
Explainable Lead Scoring Engine (Phase 7).

Computes a deterministic, explainable 0–100 qualification score across 5 transparent factors:
  1. Budget & Commercial Viability (0–25 pts)
  2. Need & Timeline Urgency (0–20 pts)
  3. Service & Solution Alignment (0–20 pts)
  4. Engagement & Call Outcome (0–25 pts)
  5. Decision Maker & Company Fit (0–10 pts)

Categorization:
  - HOT  (80–100): High priority sales closing, assign to human rep immediately
  - WARM (50–79):  Automated AI follow-up & nurturing sequence
  - COLD (<50):    Low priority or educational re-targeting
"""

from typing import Any, Dict, List, Optional


DEFAULT_WEIGHTS = {
    "budget": 25.0,
    "timeline": 20.0,
    "service_alignment": 20.0,
    "engagement": 25.0,
    "decision_maker_fit": 10.0,
}


def _score_budget(lead: Dict[str, Any], max_pts: float) -> Dict[str, Any]:
    budget_raw = str(
        lead.get("budget")
        or (lead.get("variables") or {}).get("budget")
        or lead.get("annual_revenue")
        or ""
    ).lower()
    notes = str(lead.get("notes") or "").lower()

    if any(k in budget_raw or k in notes for k in ["2l", "5l", "10l", "lakh", "crore", ">1l", "100000", "50000"]):
        pts = max_pts
        reason = "High verified budget (₹50k – ₹2L+)"
    elif any(k in budget_raw or k in notes for k in ["25k", "30k", "40k", "25000", "medium"]):
        pts = round(max_pts * 0.72)
        reason = "Moderate budget (₹25k – ₹50k)"
    elif any(k in budget_raw or k in notes for k in ["10k", "15k", "10000", "small", "low"]):
        pts = round(max_pts * 0.40)
        reason = "Entry-level budget (< ₹25k)"
    elif budget_raw:
        pts = round(max_pts * 0.35)
        reason = f"Unquantified budget stated: '{budget_raw[:30]}'"
    else:
        pts = round(max_pts * 0.20)
        reason = "Budget not yet discussed"

    return {"score": int(pts), "max": int(max_pts), "reason": reason}


def _score_timeline(lead: Dict[str, Any], max_pts: float) -> Dict[str, Any]:
    timeline_raw = str(
        lead.get("timeline")
        or (lead.get("variables") or {}).get("timeline")
        or ""
    ).lower()
    notes = str(lead.get("notes") or "").lower()

    if any(k in timeline_raw or k in notes for k in ["immediate", "today", "tomorrow", "urgent", "1 week", "7 days", "asap"]):
        pts = max_pts
        reason = "Immediate rollout (< 7 days)"
    elif any(k in timeline_raw or k in notes for k in ["2 weeks", "3 weeks", "month", "30 days", "soon"]):
        pts = round(max_pts * 0.75)
        reason = "Near-term rollout (1–4 weeks)"
    elif any(k in timeline_raw or k in notes for k in ["quarter", "3 months", "2 months", "planning"]):
        pts = round(max_pts * 0.50)
        reason = "Medium-term rollout (1–3 months)"
    elif any(k in timeline_raw or k in notes for k in ["exploring", "just looking", "no rush", "later"]):
        pts = round(max_pts * 0.20)
        reason = "Long-term or casual exploratory interest"
    else:
        pts = round(max_pts * 0.25)
        reason = "Timeline unverified"

    return {"score": int(pts), "max": int(max_pts), "reason": reason}


def _score_service_alignment(lead: Dict[str, Any], max_pts: float) -> Dict[str, Any]:
    service = str(
        lead.get("service")
        or (lead.get("variables") or {}).get("service")
        or lead.get("source")
        or ""
    ).lower()
    notes = str(lead.get("notes") or "").lower()

    strong_matches = ["voice", "call", "caller", "ai calling", "telugu", "hindi", "crm", "sales agent", "outbound", "telecalling"]
    moderate_matches = ["lead", "automation", "marketing", "website", "software", "support"]

    if any(k in service or k in notes for k in strong_matches):
        pts = max_pts
        reason = "Direct match for core multilingual AI voice & sales closing"
    elif any(k in service or k in notes for k in moderate_matches):
        pts = round(max_pts * 0.60)
        reason = "Moderate match for sales automation & CRM capabilities"
    else:
        pts = round(max_pts * 0.30)
        reason = "General business interest"

    return {"score": int(pts), "max": int(max_pts), "reason": reason}


def _score_engagement(lead: Dict[str, Any], max_pts: float) -> Dict[str, Any]:
    status = str(lead.get("status") or "").lower()
    call_outcome = str(lead.get("call_outcome") or (lead.get("variables") or {}).get("outcome") or "").lower()
    notes = str(lead.get("notes") or "").lower()

    if any(k in status or k in call_outcome for k in ["dnd", "not interested", "wrong number", "unsubscribed"]):
        pts = 0
        reason = "Explicitly opted out or disqualified"
    elif any(k in status or k in call_outcome or k in notes for k in ["demo", "closed", "won", "callback", "highly interested", "meeting scheduled"]):
        pts = max_pts
        reason = "High engagement: demo requested, callback scheduled, or deal stage"
    elif any(k in status or k in call_outcome or k in notes for k in ["interested", "qualified", "in discussion", "positive"]):
        pts = round(max_pts * 0.72)
        reason = "Engaged prospect: asked questions and discussed requirements"
    elif any(k in status or k in call_outcome for k in ["contacted", "answered", "completed"]):
        pts = round(max_pts * 0.44)
        reason = "Call connected; basic conversation completed"
    elif any(k in status or k in call_outcome for k in ["busy", "no answer", "voicemail"]):
        pts = round(max_pts * 0.16)
        reason = "Attempted contact; awaiting response"
    else:
        pts = round(max_pts * 0.20)
        reason = "New uncontacted lead"

    return {"score": int(pts), "max": int(max_pts), "reason": reason}


def _score_decision_maker_fit(lead: Dict[str, Any], max_pts: float) -> Dict[str, Any]:
    title = str(
        lead.get("title")
        or lead.get("role")
        or (lead.get("variables") or {}).get("title")
        or (lead.get("variables") or {}).get("designation")
        or ""
    ).lower()

    cxo_keywords = ["founder", "co-founder", "ceo", "cto", "md", "managing director", "director", "owner", "partner", "vp", "president"]
    mgr_keywords = ["manager", "lead", "head", "gm", "general manager", "supervisor", "vp"]

    if any(k in title for k in cxo_keywords):
        pts = max_pts
        reason = f"Primary decision maker ({title.title() if title else 'Executive'})"
    elif any(k in title for k in mgr_keywords):
        pts = round(max_pts * 0.70)
        reason = f"Senior manager / influencer ({title.title() if title else 'Manager'})"
    elif title:
        pts = round(max_pts * 0.40)
        reason = f"Operational contact ({title.title()})"
    else:
        pts = round(max_pts * 0.30)
        reason = "Decision-maker role unverified"

    return {"score": int(pts), "max": int(max_pts), "reason": reason}


def score_lead(lead_data: Dict[str, Any], weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Compute a 0–100 qualification score for a lead record with full explainability.
    """
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    f_budget = _score_budget(lead_data, w.get("budget", 25.0))
    f_timeline = _score_timeline(lead_data, w.get("timeline", 20.0))
    f_alignment = _score_service_alignment(lead_data, w.get("service_alignment", 20.0))
    f_engagement = _score_engagement(lead_data, w.get("engagement", 25.0))
    f_fit = _score_decision_maker_fit(lead_data, w.get("decision_maker_fit", 10.0))

    total = min(100, max(0, (
        f_budget["score"]
        + f_timeline["score"]
        + f_alignment["score"]
        + f_engagement["score"]
        + f_fit["score"]
    )))

    if total >= 80:
        category = "HOT"
        action = "Schedule immediate human executive demo and prioritize closing sequence."
    elif total >= 50:
        category = "WARM"
        action = "Enroll in multilingual AI voice nurturing follow-up sequence."
    else:
        category = "COLD"
        action = "Low priority. Retain for drip educational messaging."

    summary_reasons = []
    if f_budget["score"] >= round(w.get("budget", 25.0) * 0.7):
        summary_reasons.append(f_budget["reason"])
    if f_timeline["score"] >= round(w.get("timeline", 20.0) * 0.7):
        summary_reasons.append(f_timeline["reason"])
    if f_alignment["score"] >= round(w.get("service_alignment", 20.0) * 0.7):
        summary_reasons.append(f_alignment["reason"])
    if f_engagement["score"] >= round(w.get("engagement", 25.0) * 0.7):
        summary_reasons.append(f_engagement["reason"])
    if f_fit["score"] >= round(w.get("decision_maker_fit", 10.0) * 0.7):
        summary_reasons.append(f_fit["reason"])

    if not summary_reasons:
        summary_reasons.append("Early stage lead awaiting discovery and commercial qualification.")

    return {
        "lead_id": lead_data.get("id"),
        "total_score": total,
        "category": category,
        "factors": {
            "budget": f_budget,
            "timeline": f_timeline,
            "service_alignment": f_alignment,
            "engagement": f_engagement,
            "decision_maker_fit": f_fit,
        },
        "summary_reasons": summary_reasons,
        "recommended_action": action,
    }


def score_leads_batch(leads: List[Dict[str, Any]], weights: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """Batch compute qualification scores for a collection of leads."""
    return [score_lead(lead, weights=weights) for lead in leads]
