"""Tenant-provisioning emitter (schema_version 2.0).

This package owns the LLM-driven path that turns a canonical JSONC manifest
into the final tenant-provisioning JSON the BE consumes.

Components (built top-down):

* schemas       Pydantic models defining the LLM structured-output contract.
* catalog_view  Deterministic manifest->prompt summariser.
* selector      LLM call producing a SelectionResult.
* emitter       Deterministic SelectionResult + manifest -> final JSON.
* service       Orchestrator wired into preview_flow.

Only schemas and catalog_view exist initially; the rest land once the
contract surface has been reviewed.
"""

from __future__ import annotations

from .catalog_view import CatalogEmployee, CatalogItem, CatalogView
from .emitter import EmitterError, emit_tenant_provisioning
from .schemas import EmployeeOverride, SelectionResult, TenantSelection
from .selector import BaselineSelector, BundleSelector
from .service import TenantProvisioningError, TenantProvisioningService

__all__ = [
    "BaselineSelector",
    "BundleSelector",
    "CatalogEmployee",
    "CatalogItem",
    "CatalogView",
    "EmitterError",
    "EmployeeOverride",
    "SelectionResult",
    "TenantProvisioningError",
    "TenantProvisioningService",
    "TenantSelection",
    "emit_tenant_provisioning",
]
