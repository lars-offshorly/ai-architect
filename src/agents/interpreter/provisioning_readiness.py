"""Provisioning-readiness evaluator.

The v2 canonical manifest gives the AI a very small mutable surface: tenant
header fields (``company_name``, ``industry``, ``size_band``, ``primary_region``)
plus *which* catalog IDs to include for queues/projects/dashboards/KPIs/HR
request types. Everything else is frozen in the catalog and applied
automatically.

This module answers a single question per turn: **do we already know enough
about the user to provision their tenant?** When the answer is yes, the
conversation flow can skip clarification entirely and head straight to bundle
suggestion + preview. When the answer is no, we return the *specific*
tenant fields that are still missing so the replier can ask a single targeted
question instead of inventing open-ended follow-ups.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.models.extraction_result import ExtractionResult
from domain.models.session import Session


class TenantField(str, Enum):
    """Mutable tenant-header fields the AI may need from the user."""

    INDUSTRY = "industry"
    COMPANY_NAME = "company_name"
    SIZE_BAND = "size_band"
    PRIMARY_REGION = "primary_region"


# Required for provisioning: without these we cannot produce a valid manifest.
_REQUIRED_FIELDS: tuple[TenantField, ...] = (
    TenantField.INDUSTRY,
    TenantField.COMPANY_NAME,
)

# Nice-to-have: improve personalization but have sensible catalog defaults.
_OPTIONAL_FIELDS: tuple[TenantField, ...] = (
    TenantField.SIZE_BAND,
    TenantField.PRIMARY_REGION,
)


@dataclass(slots=True, frozen=True)
class ProvisioningReadinessResult:
    is_ready: bool
    missing_required: tuple[TenantField, ...]
    missing_optional: tuple[TenantField, ...]

    def next_field_to_ask(self) -> TenantField | None:
        """Return the single most important field still missing, or None."""
        if self.missing_required:
            return self.missing_required[0]
        if self.missing_optional:
            return self.missing_optional[0]
        return None


class ProvisioningReadiness:
    """Decide whether the session has enough tenant context to provision."""

    @staticmethod
    def evaluate(
        session: Session,
        extracted: ExtractionResult | None,
    ) -> ProvisioningReadinessResult:
        known = ProvisioningReadiness._collect_known_fields(session, extracted)
        missing_required = tuple(f for f in _REQUIRED_FIELDS if f not in known)
        missing_optional = tuple(f for f in _OPTIONAL_FIELDS if f not in known)
        return ProvisioningReadinessResult(
            is_ready=not missing_required,
            missing_required=missing_required,
            missing_optional=missing_optional,
        )

    @staticmethod
    def _collect_known_fields(
        session: Session,
        extracted: ExtractionResult | None,
    ) -> set[TenantField]:
        known: set[TenantField] = set()

        # Industry: either explicitly claimed, preselected, or already chosen.
        # ``generic`` is the synthetic fallback bundle — it represents the
        # *absence* of an identified industry, so it must NOT satisfy this
        # field. Otherwise the first-turn fallback persists as if we already
        # knew the user's industry and clarification gets skipped on turn 2+.
        selected_real_bundle = (
            session.selected_bundle_key and session.selected_bundle_key != "generic"
        )
        if (
            session.company_industry_claim
            or session.preselected_bundle_key
            or selected_real_bundle
        ):
            known.add(TenantField.INDUSTRY)

        # Company name: from session inference or extraction signals.
        company_name_known = bool(session.inferred_company_name) or (
            extracted is not None
            and bool(extracted.personalization_signals.company_name)
        )
        if company_name_known:
            known.add(TenantField.COMPANY_NAME)

        # Size band: any positive team size satisfies it.
        if session.inferred_team_size:
            known.add(TenantField.SIZE_BAND)

        # Primary region: inferred from location mentions.
        if session.inferred_region:
            known.add(TenantField.PRIMARY_REGION)

        return known
