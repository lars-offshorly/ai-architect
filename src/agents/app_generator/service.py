from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from catalog.bundle_catalog import BundleCatalog
from core.logging import get_logger, get_session_logger
from domain.models.app_payload import AppPayload
from repositories.template_repository import TemplateRepository

from .contract import AppPayloadContract
from .formatter import AppPayloadFormatter
from .config_assembly import map_relationships
from .schemas import DummyDataJsonSchema, GenerationJsonSchema
from .validators import validate_dummy_data_json, validate_generation_json

logger = get_logger(__name__)


class AppGeneratorService:
    def __init__(
        self, template_repo: TemplateRepository, catalog: BundleCatalog
    ) -> None:
        self._repo = template_repo
        self._catalog = catalog
        self._formatter = AppPayloadFormatter()

    def assemble(
        self,
        session_id: str,
        bundle_key: str,
        display_name: str,
        dummy_data: dict[str, object],
    ) -> AppPayload:
        session_logger = get_session_logger(__name__, session_id)
        session_logger.info("Assembling app payload for bundle=%s", bundle_key)

        bundle = self._catalog.get(bundle_key)
        if bundle is None:
            # Fallback to the key itself if not in catalog
            # (unlikely for confirmed session)
            template_dir = bundle_key
            render_key = bundle_key
            entity_definitions = {}
            entity_relationships = []
        else:
            template_dir = bundle.template_dir
            render_key = bundle.render_key
            metadata = getattr(bundle, "metadata", None)
            entity_definitions = (
                metadata.entity_definitions if metadata is not None else {}
            )
            entity_relationships = (
                metadata.entity_relationships if metadata is not None else []
            )

        # Load from the correct directory resolved from the catalog
        generation_json = self._repo.load_app_json(template_dir)
        generation_json["session_id"] = session_id
        # Ensure the payload uses the render key per AD-2
        generation_json["bundle_key"] = render_key
        # AD-2 registry owns canonical modules; older app templates may omit them.
        if (
            not isinstance(generation_json.get("modules"), list)
            or not generation_json.get("modules")
        ) and bundle is not None:
            generation_json["modules"] = list(bundle.default_modules)
        normalized_dummy_data = self._normalize_dummy_data(dummy_data)

        # 1. Legacy structural validation
        validate_generation_json(generation_json, render_key)
        validate_dummy_data_json(normalized_dummy_data, render_key)

        # 1a. Inject relationship map into config
        if entity_relationships:
            relationships = map_relationships(render_key, entity_relationships, entity_definitions)
            config = generation_json.get("config")
            if isinstance(config, dict):
                config["relationships"] = [r.model_dump() for r in relationships]
                session_logger.debug(
                    "Mapped %d relationships for bundle=%s", len(relationships), render_key
                )

        # 2. Strict Pydantic Schema Validation (Integrated from T140)
        # This ensures config and stores sub-schemas are 100% correct.
        GenerationJsonSchema.model_validate(generation_json)
        dummy_schema_input = dict(normalized_dummy_data)
        dummy_schema_input.setdefault(
            "schema_version", generation_json.get("schema_version", "1.0")
        )
        dummy_schema_input.setdefault("bundle_key", render_key)
        dummy_schema_input.setdefault("session_id", session_id)
        dummy_schema_input.setdefault("stores", {})
        DummyDataJsonSchema.model_validate(dummy_schema_input)

        # 3. Contract check
        contract = AppPayloadContract(
            schema_version=str(generation_json.get("schema_version", "1.0")),
            session_id=session_id,
            bundle_key=render_key,
            display_name=display_name,
            modules=list(cast(list[object], generation_json.get("modules", []))),
            generation_json=generation_json,
            dummy_data_json=normalized_dummy_data,
            has_entity_relationships=bool(entity_relationships),
        )
        errors = contract.validate_contract()
        if errors:
            session_logger.warning("Contract validation warnings: %s", errors)

        payload = self._formatter.format(
            session_id=session_id,
            bundle_key=render_key,
            display_name=display_name,
            generation_json=generation_json,
            dummy_data_json=normalized_dummy_data,
        )
        session_logger.info("App payload assembled for session=%s", session_id)
        return payload

    @staticmethod
    def _normalize_dummy_data(data: dict[str, object]) -> dict[str, object]:
        """Normalize incoming dummy_data_json before strict schema validation."""
        normalized = dict(data)
        stores = normalized.get("stores")
        if not isinstance(stores, dict):
            return normalized

        normalized_stores = dict(stores)
        AppGeneratorService._ensure_dashboard_generation_output(normalized_stores)
        kpis = stores.get("kpis")
        if not isinstance(kpis, list):
            normalized["stores"] = normalized_stores
            return normalized

        normalized_kpis: list[object] = []
        for idx, item in enumerate(kpis, start=1):
            if not isinstance(item, dict):
                normalized_kpis.append(item)
                continue
            kpi = dict(item)
            if not kpi.get("id"):
                key = kpi.get("key")
                kpi["id"] = key if isinstance(key, str) and key else idx
            normalized_kpis.append(kpi)

        normalized_stores["kpis"] = normalized_kpis
        normalized["stores"] = normalized_stores
        return normalized

    @staticmethod
    def _ensure_dashboard_generation_output(stores: dict[str, object]) -> None:
        """Backfill OpenAPI-aligned dashboard output when callers omit it."""
        if "dashboard_generation_output" in stores:
            return

        widgets_raw = stores.get("dashboard_widgets")
        if not isinstance(widgets_raw, list):
            widgets_raw = []

        debug_widgets: list[dict[str, object]] = []
        for widget in widgets_raw:
            if not isinstance(widget, dict):
                continue
            widget_type = str(widget.get("type", "number"))
            title = str(widget.get("title", "Widget"))
            if widget_type == "number":
                debug_widgets.append({"type": "number", "name": title, "value": "0"})
            elif widget_type == "list":
                debug_widgets.append(
                    {
                        "type": "list",
                        "name": title,
                        "data_config": {"module": "KPI", "data_source": "kpis"},
                    }
                )
            else:
                debug_widgets.append(
                    {
                        "type": "bar",
                        "title": title,
                        "data_config": {
                            "module": "Operations",
                            "data_source": "items",
                            "group_by": ["status"],
                            "aggregation": "count",
                        },
                    }
                )

        type_counts: dict[str, int] = {
            "text": 0,
            "number": 0,
            "bar": 0,
            "hbar": 0,
            "pie": 0,
            "line": 0,
            "scatter": 0,
            "list": 0,
            "combo": 0,
            "embed": 0,
        }
        for widget in debug_widgets:
            widget_type_value = widget.get("type")
            if isinstance(widget_type_value, str) and widget_type_value in type_counts:
                type_counts[widget_type_value] += 1
        widget_count: dict[str, Any] = {**type_counts, "total": len(debug_widgets)}

        stores["dashboard_generation_output"] = {
            "success": True,
            "dashboard": {
                "id": "dash-preview",
                "name": "Preview Dashboard",
                "url": None,
            },
            "widgets": widget_count,
            "execution_time": "0m 1s",
            "errors": [],
            "debug_payload": {
                "widgets": debug_widgets,
                "total_widgets": len(debug_widgets),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "widget_breakdown": widget_count,
            },
            "generation_metadata": {
                "report_length": 0,
                "widgets_extracted": len(widgets_raw),
                "widgets_explicit": len(widgets_raw),
                "data_sources_used": ["kpis"],
                "processing_steps": ["normalize_dummy_data"],
            },
        }
