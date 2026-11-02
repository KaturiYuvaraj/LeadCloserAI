"""
Lead Discovery & Enrichment Provider Base Interface.
"""

from abc import abstractmethod
from typing import List, Dict, Any
from providers.base import BaseProvider, ProviderType
from schemas.lead import UnifiedLead


class BaseLeadDiscoveryProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.LEAD_DISCOVERY)

    @abstractmethod
    async def search_leads(
        self,
        filters: Dict[str, Any],
        limit: int = 25
    ) -> List[UnifiedLead]:
        """Search and discover prospects matching industry/location/title criteria."""
        pass

    @abstractmethod
    async def enrich_lead(
        self,
        lead: UnifiedLead
    ) -> UnifiedLead:
        """Enrich existing lead with deep company, contact, and tech stack intelligence."""
        pass
