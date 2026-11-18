"""
Services subpackage: Calendar, Schedule, and Music streaming
"""

from .calendar_service import CalendarService, get_calendar_service

__all__ = [
    "CalendarService",
    "get_calendar_service"
]
