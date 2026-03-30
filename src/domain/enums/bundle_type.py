from __future__ import annotations

from enum import Enum


class BundleType(str, Enum):
    HR_MANAGEMENT = "hr_management"
    TICKETING = "ticketing"
    PROJECT_MGMT = "project_mgmt"
    FINANCE = "finance"
    MARKETING = "marketing"
    SALES = "sales"
    HEALTHCARE = "healthcare"
    LEGAL_SERVICES = "legal_services"
    CONSTRUCTION_REAL_ESTATE = "construction_real_estate"
    EDUCATION = "education"
    ALL_MICROSERVICES = "all_microservices"
    GENERIC = "generic"
