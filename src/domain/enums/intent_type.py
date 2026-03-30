from __future__ import annotations

from enum import Enum


class IntentType(str, Enum):
    TRACK = "track"
    APPROVE = "approve"
    ASSIGN = "assign"
    REPORT = "report"
    MANAGE = "manage"
    SCHEDULE = "schedule"
    UNKNOWN = "unknown"
