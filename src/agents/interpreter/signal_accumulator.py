from __future__ import annotations

# pylint: disable=too-few-public-methods
from domain.models.extraction_result import (
    ClassificationSignals,
    ExtractionResult,
    PersonalizationSignals,
)


def _union(a: list[str], b: list[str]) -> list[str]:
    seen = set(a)
    return list(a) + [x for x in b if x not in seen]


class SignalAccumulator:
    @staticmethod
    def merge(
        base: ExtractionResult | None, current: ExtractionResult
    ) -> ExtractionResult:
        if base is None:
            return current

        bc = base.classification_signals
        cc = current.classification_signals
        bp = base.personalization_signals
        cp = current.personalization_signals

        merged_cs = ClassificationSignals(
            keywords=_union(bc.keywords, cc.keywords),
            entities=_union(bc.entities, cc.entities),
            intents=_union(bc.intents, cc.intents),
            workflow_hints=_union(bc.workflow_hints, cc.workflow_hints),
            domain_hints=_union(bc.domain_hints, cc.domain_hints),
            metrics=_union(bc.metrics, cc.metrics),
        )

        merged_ps = PersonalizationSignals(
            company_name=(
                cp.company_name if cp.company_name is not None else bp.company_name
            ),
            employee_names=_union(bp.employee_names, cp.employee_names),
            role_names=_union(bp.role_names, cp.role_names),
            department_names=_union(bp.department_names, cp.department_names),
            branch_names=_union(bp.branch_names, cp.branch_names),
            custom_labels=_union(bp.custom_labels, cp.custom_labels),
            terminology={**bp.terminology, **cp.terminology},
        )

        # Prefer current's variant_key when present (latest turn wins); keep
        # the previously accumulated value otherwise so early-set selections
        # survive the next extraction turn.
        merged_variant_key = current.bundle_variant_key or base.bundle_variant_key

        return ExtractionResult(
            session_id=current.session_id,
            classification_signals=merged_cs,
            personalization_signals=merged_ps,
            missing_fields=current.missing_fields,
            bundle_variant_key=merged_variant_key,
        )
