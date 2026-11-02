"""
Calendar & Scheduling Provider Base Interface.
"""

from abc import abstractmethod
from typing import List, Dict, Any, Optional
from providers.base import BaseProvider, ProviderType


class BaseCalendarProvider(BaseProvider):
    def __init__(self, provider_name: str):
        super().__init__(provider_name=provider_name, provider_type=ProviderType.CALENDAR)

    @abstractmethod
    async def check_availability(
        self,
        start_time: str,
        end_time: str,
        timezone: str = "Asia/Kolkata"
    ) -> List[Dict[str, Any]]:
        """Query availability for the target time window."""
        pass

    @abstractmethod
    async def book_meeting(
        self,
        title: str,
        start_time: str,
        duration_minutes: int = 15,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Book a live sales demo / kickoff meeting on the calendar."""
        pass
