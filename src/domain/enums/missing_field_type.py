from __future__ import annotations

from enum import Enum


class MissingFieldType(str, Enum):
    COMPANY_NAME = "company_name"
    PRIMARY_USE_CASE = "primary_use_case"
    ENTITY_TYPE = "entity_type"
    WORKFLOW_TYPE = "workflow_type"
    TEAM_SIZE = "team_size"
    INDUSTRY_HINT = "industry_hint"
    PROJECT_COUNT = "project_count"
    ASSET_TYPES = "asset_types"
    LOCATION_COUNT = "location_count"
    SERVICE_ZONES = "service_zones"
    TECHNICIAN_COUNT = "technician_count"
    BUNDLE_VARIANT = "bundle_variant"
