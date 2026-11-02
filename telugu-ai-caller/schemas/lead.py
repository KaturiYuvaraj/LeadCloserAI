"""
Unified Lead Schema for AI Sales Automation Platform.
Standardizes prospect data across Apollo.io, Apify, Excel, CSV, Manual Entry, and API Dispatch.
"""

import re
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class LeadSource(str, Enum):
    EXCEL = "EXCEL"
    CSV = "CSV"
    APOLLO = "APOLLO"
    APIFY = "APIFY"
    MANUAL = "MANUAL"
    API_DISPATCH = "API_DISPATCH"


class LeadStatus(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    DEMO_SCHEDULED = "DEMO_SCHEDULED"
    CLOSED_WON = "CLOSED_WON"
    LOST = "LOST"


class LeadPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class LeadEnrichmentData(BaseModel):
    """Firmographic and opportunity intelligence extracted before calling."""
    company_name: Optional[str] = None
    website_url: Optional[str] = None
    industry: Optional[str] = None
    employee_count_range: Optional[str] = None
    estimated_revenue: Optional[str] = None
    technologies_detected: List[str] = Field(default_factory=list)
    expansion_signals: List[str] = Field(default_factory=list)
    digital_presence_score: Optional[int] = None  # 0 to 100
    opportunity_summary: Optional[str] = None
    confidence_level: str = "INFERRED"  # VERIFIED, INFERRED, UNKNOWN
    enriched_at: Optional[datetime] = None


class UnifiedLead(BaseModel):
    """Standardized Lead model used across all services and providers."""
    id: Optional[int] = None
    name: str = Field(..., min_length=1, description="Prospect contact or business owner name")
    phone: str = Field(..., min_length=5, description="Contact phone or mobile number")
    email: Optional[str] = None
    company: Optional[str] = None
    designation: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None

    service_needed: str = Field(default="Custom Software", description="Requested software or AI solution")
    budget: str = Field(default="Flexible", description="Estimated budget or price expectation")
    timeline: str = Field(default="Immediate", description="Project deployment timeline")

    status: LeadStatus = Field(default=LeadStatus.NEW)
    priority: LeadPriority = Field(default=LeadPriority.MEDIUM)
    preferred_language: str = Field(default="te-IN", description="Preferred call language: te-IN, hi-IN, en-IN")
    source: LeadSource = Field(default=LeadSource.MANUAL)

    lead_score: Optional[int] = Field(default=50, ge=0, le=100, description="AI calculated lead score 0-100")
    score_breakdown: Optional[Dict[str, Any]] = None

    notes: Optional[str] = None
    last_call_summary: Optional[str] = None
    last_call_stage: Optional[str] = None
    last_call_sentiment: Optional[str] = None
    objections_noted: Optional[str] = None
    action_items: Optional[str] = None
    last_called_at: Optional[datetime] = None

    enrichment: Optional[LeadEnrichmentData] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("phone")
    @classmethod
    def clean_phone_number(cls, v: str) -> str:
        cleaned = re.sub(r"[^\d+]", "", str(v or "").strip())
        if not cleaned:
            return ""
        # If 10 digits without country code, default to Indian (+91)
        if len(cleaned) == 10 and not cleaned.startswith("+"):
            return f"+91 {cleaned}"
        elif len(cleaned) == 12 and cleaned.startswith("91"):
            return f"+{cleaned[:2]} {cleaned[2:]}"
        return v.strip()

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to SQLite/Postgres compatible dictionary format."""
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.email or "",
            "company": self.company or "",
            "service_needed": self.service_needed,
            "budget": self.budget,
            "timeline": self.timeline,
            "status": self.status.value if isinstance(self.status, LeadStatus) else str(self.status),
            "priority": self.priority.value if isinstance(self.priority, LeadPriority) else str(self.priority),
            "preferred_language": self.preferred_language,
            "notes": self.notes or ""
        }
