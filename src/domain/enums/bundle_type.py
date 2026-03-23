from __future__ import annotations

from enum import Enum


class BundleType(str, Enum):
    HR_HUB = "hr_hub"
    PROJECT_OPS = "project_ops"
    ASSET_MGMT = "asset_mgmt"
    FIELD_SERVICE = "field_service"
    GENERIC = "generic"
