from __future__ import annotations

from dataclasses import dataclass

from core.logging import get_logger
from domain.models.bundle import BundleSuggestion
from domain.models.classification_result import ClassificationResult
from domain.models.extraction_result import ExtractionResult

from .canonical_manifest_registry import (
    CanonicalManifestRegistry,
    CanonicalManifestRegistryError,
)

logger = get_logger(__name__)


@dataclass(slots=True)
class CanonicalBundleResolver:
    registry: CanonicalManifestRegistry
    strict_mapping: bool = True

    def resolve(
        self,
        session_id: str,
        user_message: str,
        extracted: ExtractionResult | None = None,
    ) -> ClassificationResult:
        manifests_by_industry = self.registry.by_industry()
        mapping = self.registry.industry_bundle_map()

        if self.strict_mapping:
            self.registry.validate_mapping_coverage()

        industry = self._infer_industry(user_message, extracted, mapping)

        if industry is None:
            if self.strict_mapping:
                raise CanonicalManifestRegistryError(
                    "No mapped canonical industry signal matched the request"
                )
            fallback = BundleSuggestion(
                bundle_key="generic",
                display_name="Custom Workspace",
                confidence=0.45,
                reasoning="No canonical industry signal matched",
                matched_signals=[],
            )
            logger.warning(
                "session=%s canonical resolver fallback to generic", session_id
            )
            return ClassificationResult(
                session_id=session_id,
                selected_bundle=fallback,
                ranked_candidates=[fallback],
                confidence_status="fallback_generic",
                top_confidence=fallback.confidence,
                reasoning="Canonical resolver fallback",
            )

        bundle_key = str(mapping[industry]["bundle_key"])
        suggestion = BundleSuggestion(
            bundle_key=bundle_key,
            display_name=bundle_key.replace("_", " ").title(),
            confidence=0.95,
            reasoning=f"Matched canonical manifest industry '{industry}'",
            matched_signals=[industry],
        )
        if industry not in manifests_by_industry and self.strict_mapping:
            raise CanonicalManifestRegistryError(
                f"Mapped industry '{industry}' has no canonical manifest"
            )

        return ClassificationResult(
            session_id=session_id,
            selected_bundle=suggestion,
            ranked_candidates=[suggestion],
            confidence_status="proceed",
            top_confidence=suggestion.confidence,
            reasoning="Canonical manifest resolver",
        )

    @staticmethod
    def _infer_industry(
        user_message: str,
        extracted: ExtractionResult | None,
        mapping: dict[str, dict[str, object]],
    ) -> str | None:
        haystack_parts = [user_message.lower()]
        if extracted is not None:
            cs = extracted.classification_signals
            haystack_parts.extend(x.lower() for x in cs.domain_hints)
            haystack_parts.extend(x.lower() for x in cs.keywords)
            haystack_parts.extend(x.lower() for x in cs.intents)
            haystack_parts.extend(x.lower() for x in cs.workflow_hints)
        haystack = " ".join(haystack_parts)

        for industry in mapping:
            if industry.lower() in haystack:
                return industry

        for industry, spec in mapping.items():
            aliases = spec.get("aliases", [])
            if isinstance(aliases, list) and any(
                isinstance(token, str) and token.lower() in haystack for token in aliases
            ):
                return industry

        return None
