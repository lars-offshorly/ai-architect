from __future__ import annotations

import copy

from core.logging import get_logger
from domain.models.extracted_info import ExtractedInfo

logger = get_logger(__name__)


def _inject_employee_names(
    records: list[dict[str, object]],
    names: list[str],
    field: str,
) -> list[dict[str, object]]:
    updated: list[dict[str, object]] = []
    for i, record in enumerate(records):
        item = dict(record)
        if field in item and names:
            item[field] = names[i % len(names)]
        updated.append(item)
    return updated


class DummyDataInjector:
    def inject(
        self,
        dummy_template: dict[str, object],
        extracted: ExtractedInfo,
    ) -> dict[str, object]:
        result = copy.deepcopy(dummy_template)
        stores = result.get("stores")
        if not isinstance(stores, dict):
            return result

        if extracted.employee_names:
            for store_name in ("tickets", "work_orders", "tasks"):
                store = stores.get(store_name)
                if isinstance(store, list):
                    stores[store_name] = _inject_employee_names(
                        store, extracted.employee_names, "requester"
                    )
                    stores[store_name] = _inject_employee_names(
                        stores[store_name], extracted.employee_names, "assignee"
                    )

        result["session_id"] = extracted.session_id
        if extracted.company_name:
            result["company_name"] = extracted.company_name

        logger.info(
            "Dummy data injection complete for session=%s", extracted.session_id
        )
        return result
