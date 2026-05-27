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

from langchain_openai import ChatOpenAI

from domain.services.registry_facade import RegistryFacade

from .catalog_view import CatalogView
from .emitter import emit_tenant_provisioning
from .selector import BaselineSelector, BundleSelector, LLMSelector


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

    @classmethod
    def with_llm(
        cls, model: ChatOpenAI, registry_facade: RegistryFacade
    ) -> TenantProvisioningService:
        """Convenience builder using the LLM selector with a baseline fallback."""
        return cls(
            registry_facade=registry_facade,
            selector=LLMSelector(model=model, fallback_selector=BaselineSelector()),
        )

    def provision(
        self,
        bundle_key: str,
        user_message: str,
        *,
        session_id: str,
        generated_at: datetime | None = None,
        tenant_overrides: dict[str, str] | None = None,
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
        if tenant_overrides:
            selection = _apply_tenant_overrides(
                selection, tenant_overrides, catalog_view.bundle_industry
            )
        return emit_tenant_provisioning(
            manifest,
            selection,
            session_id=session_id,
            generated_at=generated_at,
        )

    async def provision_async(
        self,
        bundle_key: str,
        user_message: str,
        *,
        session_id: str,
        generated_at: datetime | None = None,
        tenant_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        manifest = self.registry_facade.get_raw_manifest(bundle_key)
        if manifest is None:
            raise TenantProvisioningError(
                f"No canonical manifest registered for bundle '{bundle_key}'"
            )
        catalog_view = CatalogView.from_manifest(manifest)
        selection = await self.selector.select_async(catalog_view, user_message)
        if tenant_overrides:
            selection = _apply_tenant_overrides(
                selection, tenant_overrides, catalog_view.bundle_industry
            )
        return emit_tenant_provisioning(
            manifest,
            selection,
            session_id=session_id,
            generated_at=generated_at,
        )


def _apply_tenant_overrides(
    selection: Any,
    overrides: dict[str, str],
    bundle_industry: str,
) -> Any:
    """Apply user-derived overrides to the selection's tenant block.

    ``industry`` is silently locked to ``bundle_industry`` to keep the emitter
    happy regardless of what an override might try to set.
    """
    cleaned = {
        key: value
        for key, value in overrides.items()
        if isinstance(value, str) and value.strip()
    }
    if not cleaned:
        return selection
    cleaned["industry"] = bundle_industry
    new_tenant = selection.tenant.model_copy(update=cleaned)
    return selection.model_copy(update={"tenant": new_tenant})
