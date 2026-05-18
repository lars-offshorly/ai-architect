from __future__ import annotations

# pylint: disable=too-few-public-methods
from domain.enums.missing_field_type import MissingFieldType
from domain.models.extraction_result import ExtractionResult

_SLOT_DERIVED_FIELDS: frozenset[MissingFieldType] = frozenset(
    {
        MissingFieldType.COMPANY_NAME,
        MissingFieldType.PRIMARY_USE_CASE,
        MissingFieldType.ENTITY_TYPE,
        MissingFieldType.INDUSTRY_HINT,
    }
)
_FIELD_ORDER = {field: index for index, field in enumerate(MissingFieldType)}


class MissingFieldDetector:
    def __init__(
        self,
        required_slots_by_bundle: dict[str, list[str]],
    ) -> None:
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
