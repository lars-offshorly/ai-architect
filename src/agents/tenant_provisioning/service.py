"""Tenant-provisioning orchestrator.

Top-level entry point that wires the four components together:

    bundle_key + user_message
            |
            v
    RegistryFacade.get_raw_manifest  ->  CatalogView.from_manifest
            |                                   |
            +-----------------------------------+
            v
    BundleSelector.select  ->  SelectionResult
            |
            v
    emit_tenant_provisioning  ->  final v2 manifest JSON

The service does not perform request-routing (that is the resolver's job upstream)
and does not own the LLM call (that lives behind the ``BundleSelector`` protocol).
It is intentionally thin so it can be wired into ``preview_flow`` later without
restructuring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from domain.services.registry_facade import RegistryFacade

from .catalog_view import CatalogView
from .emitter import emit_tenant_provisioning
from .selector import BaselineSelector, BundleSelector


class TenantProvisioningError(RuntimeError):
    """Raised when the orchestrator cannot produce a manifest."""


@dataclass(slots=True)
class TenantProvisioningService:
    registry_facade: RegistryFacade
    selector: BundleSelector

    @classmethod
    def with_baseline(
        cls, registry_facade: RegistryFacade
    ) -> TenantProvisioningService:
        """Convenience builder using the deterministic baseline selector."""
        return cls(registry_facade=registry_facade, selector=BaselineSelector())

    def provision(
        self,
        bundle_key: str,
        user_message: str,
        *,
        session_id: str,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        manifest = self.registry_facade.get_raw_manifest(bundle_key)
        if manifest is None:
            raise TenantProvisioningError(
                f"No canonical manifest registered for bundle '{bundle_key}'"
            )

        catalog_view = CatalogView.from_manifest(manifest)
        selection = self.selector.select(  # pylint: disable=assignment-from-no-return
            catalog_view, user_message
        )
        return emit_tenant_provisioning(
            manifest,
            selection,
            session_id=session_id,
            generated_at=generated_at,
        )
