from __future__ import annotations

import re
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
    ) -> ClassificationResult | None:
        """Return a ClassificationResult when an industry alias matches, else None.

        Never raises on a no-match query: returning ``None`` is the signal that
        upstream (the interpreter) should try its LLM fallback. The
        ``strict_mapping`` flag now only controls the boot-time consistency
        check between manifests and the industry mapping file.
        """
        manifests_by_industry = self.registry.by_industry()
        mapping = self.registry.industry_bundle_map()

        if self.strict_mapping:
            self.registry.validate_mapping_coverage()

        industry = self._infer_industry(user_message, extracted, mapping)

        if industry is None:
            logger.info(
                "session=%s canonical resolver miss; deferring to LLM stage",
                session_id,
            )
            return None

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

        industry_scores = CanonicalBundleResolver._score_industries(haystack, mapping)
        if not industry_scores:
            return None

        ranked = sorted(industry_scores.items(), key=lambda item: item[1], reverse=True)
        top_industry, top_score = ranked[0]
        if top_score <= 0:
            return None

        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        # Require a minimum margin so mixed-signal prompts ask upstream LLM stage.
        if top_score - second_score < 1.0:
            return None
        return top_industry

    @staticmethod
    def _score_industries(  # pylint: disable=too-many-branches
        haystack: str,
        mapping: dict[str, dict[str, object]],
    ) -> dict[str, float]:
        workflow_terms = {
            "ticket",
            "tickets",
            "ticketing",
            "project",
            "projects",
            "task",
            "tasks",
            "workflow",
            "dashboard",
            "kpi",
        }
        business_type_patterns: dict[str, tuple[str, ...]] = {
            "construction_firm": (
                "construction company",
                "construction firm",
                "contractor company",
                "we are construction",
                "i am construction",
            ),
            "hr_recruitment_agency": (
                "recruitment agency",
                "staffing agency",
                "headhunting firm",
                "hr agency",
                "i am hr",
                "we are hr",
            ),
            "bpo_contact_center": (
                "bpo company",
                "contact center company",
                "call center company",
                "i am bpo",
                "we are bpo",
            ),
        }
        bare_token_boosts: dict[str, tuple[str, ...]] = {
            "construction_firm": ("construction", "contractor"),
            "hr_recruitment_agency": ("hr", "recruitment"),
            "bpo_contact_center": ("bpo", "contact center", "call center"),
        }

        scores: dict[str, float] = dict.fromkeys(mapping, 0.0)
        for industry, spec in mapping.items():
            # Highest-weight signal: explicit business identity phrase.
            for pattern in business_type_patterns.get(industry, ()):
                if CanonicalBundleResolver._contains_term(haystack, pattern):
                    scores[industry] += 4.0

            if CanonicalBundleResolver._contains_term(haystack, industry.lower()):
                scores[industry] += 3.0
            for token in bare_token_boosts.get(industry, ()):
                if CanonicalBundleResolver._contains_term(haystack, token):
                    scores[industry] += 2.5

            aliases = spec.get("aliases", [])
            if not isinstance(aliases, list):
                continue
            for token in aliases:
                if not isinstance(token, str):
                    continue
                normalized = token.lower().strip()
                if not normalized or not CanonicalBundleResolver._contains_term(
                    haystack, normalized
                ):
                    continue
                if normalized in workflow_terms:
                    scores[industry] += 0.4
                elif (
                    "company" in normalized
                    or "agency" in normalized
                    or "firm" in normalized
                ):
                    scores[industry] += 3.0
                else:
                    scores[industry] += 1.5
        return scores

    @staticmethod
    def _contains_term(haystack: str, term: str) -> bool:
        if not term:
            return False
        # Boundary-aware match prevents accidental hits like "site" in "website".
        pattern = r"\b" + re.escape(term) + r"\b"
        return re.search(pattern, haystack) is not None
