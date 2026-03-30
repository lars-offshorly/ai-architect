from __future__ import annotations

# pylint: disable=too-few-public-methods
import re

from catalog.bundle_catalog import BundleCatalog
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extraction_result import ExtractionResult

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "of",
    "or",
    "process",
    "the",
    "to",
    "workflow",
}
_SLOT_DERIVED_FIELDS: frozenset[MissingFieldType] = frozenset(
    {
        MissingFieldType.COMPANY_NAME,
        MissingFieldType.PRIMARY_USE_CASE,
        MissingFieldType.ENTITY_TYPE,
        MissingFieldType.INDUSTRY_HINT,
    }
)
_FIELD_ORDER = {field: index for index, field in enumerate(MissingFieldType)}


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(value.casefold())
        if len(token) >= 3 and token not in _STOPWORDS
    }


class MissingFieldDetector:
    def __init__(
        self,
        catalog: BundleCatalog,
        required_slots_by_bundle: dict[str, list[str]],
    ) -> None:
        self._catalog = catalog
        self._required_slots_by_bundle = required_slots_by_bundle

    def compute(
        self,
        extracted: ExtractionResult,
        bundle_key: str | None,
    ) -> list[MissingFieldType]:
        missing: list[MissingFieldType] = []
        cs = extracted.classification_signals

        if not cs.workflow_hints and not cs.intents:
            missing.append(MissingFieldType.PRIMARY_USE_CASE)
        if not cs.entities:
            missing.append(MissingFieldType.ENTITY_TYPE)

        required_slots = self._required_slots_by_bundle.get(bundle_key or "", [])
        for slot in required_slots:
            try:
                field = MissingFieldType(slot)
            except ValueError:
                continue
            if field not in _SLOT_DERIVED_FIELDS:
                continue
            if not self._has_slot_value(extracted, field):
                missing.append(field)

        bundle = self._catalog.get(bundle_key or "")
        if (
            bundle is not None
            and bundle.required_signals
            and not self._has_required_signal_overlap(
                bundle.required_signals, extracted
            )
        ):
            missing.append(MissingFieldType.WORKFLOW_TYPE)

        return sorted(set(missing), key=lambda field: _FIELD_ORDER[field])

    def _has_slot_value(
        self,
        extracted: ExtractionResult,
        field: MissingFieldType,
    ) -> bool:
        cs = extracted.classification_signals
        ps = extracted.personalization_signals
        if field == MissingFieldType.COMPANY_NAME:
            return bool(ps.company_name)
        if field == MissingFieldType.PRIMARY_USE_CASE:
            return bool(cs.workflow_hints or cs.intents)
        if field == MissingFieldType.ENTITY_TYPE:
            return bool(cs.entities)
        if field == MissingFieldType.INDUSTRY_HINT:
            return bool(cs.domain_hints)
        return False

    def _has_required_signal_overlap(
        self,
        required_signals: list[str],
        extracted: ExtractionResult,
    ) -> bool:
        cs = extracted.classification_signals
        extracted_terms = [
            _normalize_text(term)
            for term in (
                cs.keywords
                + cs.entities
                + cs.intents
                + cs.workflow_hints
                + cs.domain_hints
                + cs.metrics
            )
            if _normalize_text(term)
        ]
        if not extracted_terms:
            return False

        tokenized_extracted = [_tokenize(term) for term in extracted_terms]

        for signal in required_signals:
            normalized_signal = _normalize_text(signal)
            if not normalized_signal:
                continue
            signal_tokens = _tokenize(normalized_signal)
            for term, term_tokens in zip(
                extracted_terms, tokenized_extracted, strict=True
            ):
                if normalized_signal in term or term in normalized_signal:
                    return True
                if (
                    signal_tokens
                    and term_tokens
                    and signal_tokens.intersection(term_tokens)
                ):
                    return True
        return False
