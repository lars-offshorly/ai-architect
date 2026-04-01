from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.app_generator.schemas import (
    KNOWN_BUNDLE_KEYS,
    AssetMgmtConfig,
    AssetMgmtStores,
    AssetStoreItem,
    DashboardWidgetEntity,
    DummyDataJsonSchema,
    FeatureFlagItem,
    FieldServiceConfig,
    FieldServiceStores,
    GenerationJsonSchema,
    GenericConfig,
    GenericStores,
    HrHubConfig,
    HrHubStores,
    KpiDefinitionItem,
    KpiStoreItem,
    MaintenanceStoreItem,
    MilestoneStoreItem,
    ProjectOpsConfig,
    ProjectOpsStores,
    ProjectStoreItem,
    QueueStoreItem,
    SchedulingStoreItem,
    TaskParentRef,
    TaskStoreItem,
    TicketAssigneeRef,
    TicketAuthorDetails,
    TicketStatusObject,
    TicketStoreItem,
    WeaveAttributes,
    WeaveStoreItem,
    WidgetPosition,
    WorkOrderStoreItem,
)

# ---------------------------------------------------------------------------
# Helpers: load real template files
# ---------------------------------------------------------------------------

_BUNDLES_DIR = Path("src/templates/bundles")
_DOCS_DIR = Path("docs")


def _load_app_json(bundle: str) -> dict[str, object]:
    return json.loads((_BUNDLES_DIR / bundle / "app.json").read_text())


def _load_dummy_data_json(bundle: str) -> dict[str, object]:
    raw = json.loads((_BUNDLES_DIR / bundle / "dummy_data.json").read_text())
    # Templates omit schema_version and session_id; add them for schema validation.
    raw.setdefault("schema_version", "1.0")
    raw.setdefault("session_id", "test-session-000")
    return raw


def _load_sample_dummy_data() -> dict[str, object]:
    raw = json.loads((_DOCS_DIR / "sample_dummy_data.json").read_text())
    # sample_dummy_data.json uses "bundle" instead of "bundle_key".
    if "bundle" in raw and "bundle_key" not in raw:
        raw["bundle_key"] = raw.pop("bundle")
    raw.setdefault("schema_version", "1.0")
    raw.setdefault("session_id", "test-session-sample")
    return raw


# ===========================================================================
# GenerationJsonSchema — template files as ground truth
# ===========================================================================


class TestGenerationJsonSchemaTemplates:
    """Each bundle's app.json must validate cleanly against GenerationJsonSchema."""

    def test_hr_hub_app_json_validates(self) -> None:
        data = _load_app_json("hr_hub")
        result = GenerationJsonSchema.model_validate(data)
        assert result.bundle_key == "hr_hub"
        assert result.schema_version == "1.0"
        assert "tickets" in result.modules
        assert len(result.config["kpi_definitions"]) >= 1  # type: ignore[arg-type]

    def test_project_ops_app_json_validates(self) -> None:
        data = _load_app_json("project_ops")
        result = GenerationJsonSchema.model_validate(data)
        assert result.bundle_key == "project_ops"
        assert "tasks" in result.modules

    def test_asset_mgmt_app_json_validates(self) -> None:
        data = _load_app_json("asset_mgmt")
        result = GenerationJsonSchema.model_validate(data)
        assert result.bundle_key == "asset_mgmt"
        assert "assets" in result.modules

    def test_field_service_app_json_validates(self) -> None:
        data = _load_app_json("field_service")
        result = GenerationJsonSchema.model_validate(data)
        assert result.bundle_key == "field_service"
        assert "work_orders" in result.modules

    def test_generic_app_json_validates(self) -> None:
        data = _load_app_json("generic")
        result = GenerationJsonSchema.model_validate(data)
        assert result.bundle_key == "generic"
        assert "tickets" in result.modules


# ===========================================================================
# GenerationJsonSchema — bundle config sub-schema validation
# ===========================================================================


class TestGenerationJsonSchemaConfigSubSchemas:
    """config is validated against the correct bundle-specific model."""

    def test_hr_hub_config_parses_all_fields(self) -> None:
        data = _load_app_json("hr_hub")
        config = HrHubConfig.model_validate(data["config"])
        assert len(config.ticket_categories) >= 1
        assert len(config.default_statuses) >= 1
        assert len(config.default_priorities) >= 1
        assert len(config.queue_names) >= 1
        assert all(isinstance(k, KpiDefinitionItem) for k in config.kpi_definitions)

    def test_project_ops_config_parses_all_fields(self) -> None:
        data = _load_app_json("project_ops")
        config = ProjectOpsConfig.model_validate(data["config"])
        assert len(config.task_statuses) >= 1
        assert len(config.task_priorities) >= 1
        assert len(config.milestone_statuses) >= 1
        assert all(isinstance(k, KpiDefinitionItem) for k in config.kpi_definitions)

    def test_asset_mgmt_config_parses_all_fields(self) -> None:
        data = _load_app_json("asset_mgmt")
        config = AssetMgmtConfig.model_validate(data["config"])
        assert len(config.asset_statuses) >= 1
        assert len(config.maintenance_types) >= 1
        assert len(config.maintenance_statuses) >= 1

    def test_field_service_config_parses_all_fields(self) -> None:
        data = _load_app_json("field_service")
        config = FieldServiceConfig.model_validate(data["config"])
        assert len(config.work_order_statuses) >= 1
        assert len(config.work_order_priorities) >= 1
        assert len(config.service_types) >= 1

    def test_generic_config_parses_all_fields(self) -> None:
        data = _load_app_json("generic")
        config = GenericConfig.model_validate(data["config"])
        assert len(config.ticket_statuses) >= 1
        assert len(config.ticket_priorities) >= 1

    def test_kpi_definition_item_fields_present(self) -> None:
        data = _load_app_json("hr_hub")
        config = HrHubConfig.model_validate(data["config"])
        first_kpi = config.kpi_definitions[0]
        assert first_kpi.key
        assert first_kpi.label
        assert first_kpi.unit


# ===========================================================================
# GenerationJsonSchema — invalid input cases
# ===========================================================================


class TestGenerationJsonSchemaInvalidInputs:
    """Schema must reject malformed generation_json payloads."""

    def _valid_hr_hub(self) -> dict[str, object]:
        return copy.deepcopy(_load_app_json("hr_hub"))

    def test_missing_schema_version_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["schema_version"]
        with pytest.raises(ValidationError, match="schema_version"):
            GenerationJsonSchema.model_validate(data)

    def test_wrong_schema_version_raises(self) -> None:
        data = self._valid_hr_hub()
        data["schema_version"] = "2.0"
        with pytest.raises(ValidationError, match="schema_version"):
            GenerationJsonSchema.model_validate(data)

    def test_missing_bundle_key_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["bundle_key"]
        with pytest.raises(ValidationError, match="bundle_key"):
            GenerationJsonSchema.model_validate(data)

    def test_unknown_bundle_key_raises(self) -> None:
        data = self._valid_hr_hub()
        data["bundle_key"] = "nonexistent_bundle"
        with pytest.raises(ValidationError):
            GenerationJsonSchema.model_validate(data)

    def test_missing_modules_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["modules"]
        with pytest.raises(ValidationError, match="modules"):
            GenerationJsonSchema.model_validate(data)

    def test_empty_modules_raises(self) -> None:
        data = self._valid_hr_hub()
        data["modules"] = []
        with pytest.raises(ValidationError, match="modules"):
            GenerationJsonSchema.model_validate(data)

    def test_missing_config_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["config"]
        with pytest.raises(ValidationError, match="config"):
            GenerationJsonSchema.model_validate(data)

    def test_config_wrong_bundle_raises(self) -> None:
        # Load project_ops config into an hr_hub payload — should fail because
        # hr_hub config requires ticket_categories, queue_names, etc.
        hr_hub_data = self._valid_hr_hub()
        project_ops_data = _load_app_json("project_ops")
        hr_hub_data["config"] = project_ops_data["config"]
        with pytest.raises(ValidationError):
            GenerationJsonSchema.model_validate(hr_hub_data)

    def test_config_empty_kpi_definitions_raises(self) -> None:
        data = self._valid_hr_hub()
        data["config"] = copy.deepcopy(data["config"])  # type: ignore[arg-type]
        data["config"]["kpi_definitions"] = []  # type: ignore[index]
        with pytest.raises(ValidationError):
            GenerationJsonSchema.model_validate(data)

    def test_config_kpi_definition_missing_unit_raises(self) -> None:
        data = self._valid_hr_hub()
        data["config"] = copy.deepcopy(data["config"])  # type: ignore[arg-type]
        data["config"]["kpi_definitions"] = [{"key": "x", "label": "X"}]  # type: ignore[index]
        with pytest.raises(ValidationError, match="unit"):
            GenerationJsonSchema.model_validate(data)

    def test_config_empty_ticket_categories_raises(self) -> None:
        data = self._valid_hr_hub()
        data["config"] = copy.deepcopy(data["config"])  # type: ignore[arg-type]
        data["config"]["ticket_categories"] = []  # type: ignore[index]
        with pytest.raises(ValidationError):
            GenerationJsonSchema.model_validate(data)


# ===========================================================================
# GenerationJsonSchema — optional fields default correctly
# ===========================================================================


class TestGenerationJsonSchemaOptionalFields:
    """Optional fields must default to sensible empty values."""

    def test_feature_flags_defaults_to_empty_list(self) -> None:
        data = _load_app_json("hr_hub")
        result = GenerationJsonSchema.model_validate(data)
        assert result.feature_flags == []

    def test_slots_used_defaults_to_empty_list(self) -> None:
        # generic/app.json has slots_used; strip it to test the default.
        data = _load_app_json("generic")
        data.pop("slots_used", None)
        result = GenerationJsonSchema.model_validate(data)
        assert result.slots_used == []

    def test_display_name_defaults_to_empty_string(self) -> None:
        data = _load_app_json("hr_hub")
        data.pop("display_name", None)
        result = GenerationJsonSchema.model_validate(data)
        assert result.display_name == ""

    def test_feature_flags_parses_when_present(self) -> None:
        data = _load_app_json("hr_hub")
        data["feature_flags"] = [
            {
                "id": 111,
                "name": "App Homepage HR Hub",
                "isEnabled": True,
                "module": "dashboard",
            }
        ]
        result = GenerationJsonSchema.model_validate(data)
        assert len(result.feature_flags) == 1
        assert isinstance(result.feature_flags[0], FeatureFlagItem)
        assert result.feature_flags[0].id == 111

    def test_slots_used_parses_when_present(self) -> None:
        data = _load_app_json("hr_hub")
        result = GenerationJsonSchema.model_validate(data)
        assert "team_size" in result.slots_used


# ===========================================================================
# DummyDataJsonSchema — template files as ground truth
# ===========================================================================


class TestDummyDataJsonSchemaTemplates:
    """Each bundle's dummy_data.json must validate cleanly against DummyDataJsonSchema."""

    def test_hr_hub_dummy_data_validates(self) -> None:
        data = _load_dummy_data_json("hr_hub")
        result = DummyDataJsonSchema.model_validate(data)
        assert result.bundle_key == "hr_hub"
        assert "tickets" in result.stores
        assert "queues" in result.stores
        assert "kpis" in result.stores
        assert "dashboard_widgets" in result.stores

    def test_project_ops_dummy_data_validates(self) -> None:
        data = _load_dummy_data_json("project_ops")
        result = DummyDataJsonSchema.model_validate(data)
        assert result.bundle_key == "project_ops"
        assert "tasks" in result.stores
        assert "milestones" in result.stores

    def test_asset_mgmt_dummy_data_validates(self) -> None:
        data = _load_dummy_data_json("asset_mgmt")
        result = DummyDataJsonSchema.model_validate(data)
        assert result.bundle_key == "asset_mgmt"
        assert "assets" in result.stores
        assert "maintenance" in result.stores

    def test_field_service_dummy_data_validates(self) -> None:
        data = _load_dummy_data_json("field_service")
        result = DummyDataJsonSchema.model_validate(data)
        assert result.bundle_key == "field_service"
        assert "work_orders" in result.stores
        assert "scheduling" in result.stores

    def test_generic_dummy_data_validates(self) -> None:
        data = _load_dummy_data_json("generic")
        result = DummyDataJsonSchema.model_validate(data)
        assert result.bundle_key == "generic"
        assert "tickets" in result.stores


# ===========================================================================
# DummyDataJsonSchema — full frontend entity shapes (sample_dummy_data.json)
# ===========================================================================


class TestDummyDataJsonSchemaSampleData:
    """docs/sample_dummy_data.json contains full TypeScript entity shapes; must validate."""

    def test_sample_dummy_data_validates(self) -> None:
        data = _load_sample_dummy_data()
        result = DummyDataJsonSchema.model_validate(data)
        assert result.bundle_key == "hr_hub"
        assert "tickets" in result.stores

    def test_sample_tickets_contain_nested_status_object(self) -> None:
        data = _load_sample_dummy_data()
        result = DummyDataJsonSchema.model_validate(data)
        stores = HrHubStores.model_validate(result.stores)
        ticket = stores.tickets[0]
        assert isinstance(ticket.status, TicketStatusObject)
        assert ticket.status.slug

    def test_sample_kpis_contain_quantitative_details(self) -> None:
        data = _load_sample_dummy_data()
        result = DummyDataJsonSchema.model_validate(data)
        # sample_dummy_data uses hr_hub key but contains kpis in project/tasks form;
        # access via raw stores dict
        kpis = result.stores.get("kpis", [])
        assert len(kpis) >= 1
        first = kpis[0]
        assert "id" in first

    def test_sample_tasks_contain_parent_project_ref(self) -> None:
        data = _load_sample_dummy_data()
        result = DummyDataJsonSchema.model_validate(data)
        # sample_dummy_data.json includes tasks store
        tasks_raw = result.stores.get("tasks")
        if tasks_raw:
            ops_stores = ProjectOpsStores.model_validate({"tasks": tasks_raw})
            task = ops_stores.tasks[0]
            assert task.parentProject is not None
            assert isinstance(task.parentProject, TaskParentRef)

    def test_sample_weaves_contain_attributes(self) -> None:
        data = _load_sample_dummy_data()
        result = DummyDataJsonSchema.model_validate(data)
        weaves_raw = result.stores.get("weaves")
        if weaves_raw:
            stores = ProjectOpsStores.model_validate({"weaves": weaves_raw})
            weave = stores.weaves[0]
            assert weave.name
            assert isinstance(weave.attributes, WeaveAttributes)


# ===========================================================================
# DummyDataJsonSchema — invalid input cases
# ===========================================================================


class TestDummyDataJsonSchemaInvalidInputs:
    """Schema must reject malformed dummy_data_json payloads."""

    def _valid_hr_hub(self) -> dict[str, object]:
        return _load_dummy_data_json("hr_hub")

    def test_missing_schema_version_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["schema_version"]
        with pytest.raises(ValidationError, match="schema_version"):
            DummyDataJsonSchema.model_validate(data)

    def test_wrong_schema_version_raises(self) -> None:
        data = self._valid_hr_hub()
        data["schema_version"] = "2.0"
        with pytest.raises(ValidationError, match="schema_version"):
            DummyDataJsonSchema.model_validate(data)

    def test_missing_bundle_key_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["bundle_key"]
        with pytest.raises(ValidationError, match="bundle_key"):
            DummyDataJsonSchema.model_validate(data)

    def test_unknown_bundle_key_raises(self) -> None:
        data = self._valid_hr_hub()
        data["bundle_key"] = "nonexistent_bundle"
        with pytest.raises(ValidationError):
            DummyDataJsonSchema.model_validate(data)

    def test_missing_session_id_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["session_id"]
        with pytest.raises(ValidationError, match="session_id"):
            DummyDataJsonSchema.model_validate(data)

    def test_missing_stores_raises(self) -> None:
        data = self._valid_hr_hub()
        del data["stores"]
        with pytest.raises(ValidationError, match="stores"):
            DummyDataJsonSchema.model_validate(data)

    def test_stores_not_dict_raises(self) -> None:
        data = self._valid_hr_hub()
        data["stores"] = ["not", "a", "dict"]
        with pytest.raises(ValidationError):
            DummyDataJsonSchema.model_validate(data)

    def test_ticket_in_stores_with_missing_id_raises(self) -> None:
        data = self._valid_hr_hub()
        data = copy.deepcopy(data)
        data["stores"]["tickets"] = [{"title": "No ID Ticket", "status": "pending"}]  # type: ignore[index]
        with pytest.raises(ValidationError, match="id"):
            DummyDataJsonSchema.model_validate(data)


# ===========================================================================
# DummyDataJsonSchema — optional fields default correctly
# ===========================================================================


class TestDummyDataJsonSchemaOptionalFields:
    """Optional fields must default to sensible values."""

    def test_company_name_defaults_to_none(self) -> None:
        data = _load_dummy_data_json("hr_hub")
        result = DummyDataJsonSchema.model_validate(data)
        assert result.company_name is None

    def test_company_name_parses_when_present(self) -> None:
        data = _load_dummy_data_json("hr_hub")
        data["company_name"] = "Acme Corp"
        result = DummyDataJsonSchema.model_validate(data)
        assert result.company_name == "Acme Corp"

    def test_optional_stores_default_to_empty_list(self) -> None:
        # ProjectOpsStores has optional projects and weaves stores.
        data = _load_dummy_data_json("project_ops")
        result = DummyDataJsonSchema.model_validate(data)
        stores = ProjectOpsStores.model_validate(result.stores)
        assert stores.projects == []
        assert stores.weaves == []

    def test_asset_mgmt_optional_tickets_defaults_to_empty(self) -> None:
        data = _load_dummy_data_json("asset_mgmt")
        result = DummyDataJsonSchema.model_validate(data)
        stores = AssetMgmtStores.model_validate(result.stores)
        assert stores.tickets == []


# ===========================================================================
# Store entity sub-model unit tests
# ===========================================================================


class TestKpiStoreItem:
    """KpiStoreItem must accept both the simple template form and the full entity form."""

    def test_simple_template_form_validates(self) -> None:
        item = KpiStoreItem.model_validate(
            {
                "id": "kpi-001",
                "label": "Open Requests",
                "value": 3,
                "unit": "tickets",
                "trend": "up",
            }
        )
        assert item.id == "kpi-001"
        assert item.label == "Open Requests"
        assert item.value == 3
        assert item.trend == "up"

    def test_full_frontend_form_validates(self) -> None:
        item = KpiStoreItem.model_validate(
            {
                "id": 1,
                "name": "Monthly Leads",
                "type": "Quantitative",
                "status": "Ongoing",
                "frequency": "Monthly",
                "assesseeType": "Teams",
                "assessees": ["Marketing Team"],
                "category": "Basic",
                "startDate": "2026-03-01T00:00:00Z",
                "endDate": "2026-03-31T23:59:59Z",
                "isMandatory": True,
                "details": {
                    "target": 100,
                    "thresholds": [50, 80],
                    "condition": "Gte",
                    "dataLabel": "Items",
                    "numberFormat": "Integer",
                    "resultType": "Sum",
                },
                "createdAt": "2026-03-01T00:00:00Z",
                "updatedAt": "2026-03-01T00:00:00Z",
            }
        )
        assert item.id == 1
        assert item.name == "Monthly Leads"
        assert item.type == "Quantitative"
        assert item.details is not None
        assert item.details["target"] == 100

    def test_minimal_form_with_only_id_validates(self) -> None:
        # All fields except id are optional.
        item = KpiStoreItem.model_validate({"id": "kpi-min"})
        assert item.id == "kpi-min"
        assert item.label is None
        assert item.value is None


class TestTicketStoreItem:
    """TicketStoreItem must accept both the flat template form and nested frontend form."""

    def test_template_form_flat_status_validates(self) -> None:
        item = TicketStoreItem.model_validate(
            {
                "id": "ticket-001",
                "title": "Annual Leave — Jane Smith",
                "status": "pending",
                "priority": "medium",
                "category": "leave",
                "assignee": "HR Manager",
                "requester": "Jane Smith",
                "created_at": "2026-01-15T09:00:00Z",
            }
        )
        assert item.id == "ticket-001"
        assert item.status == "pending"
        assert item.assignee == "HR Manager"

    def test_full_frontend_form_nested_status_validates(self) -> None:
        item = TicketStoreItem.model_validate(
            {
                "id": 1,
                "ticketId": "TCK-1001",
                "title": "Need new laptop",
                "description": "Keyboard is broken.",
                "status": {
                    "id": 1,
                    "name": "Open",
                    "slug": "open",
                    "status": "open",
                    "description": "Ticket is open",
                    "color": "#ff0000",
                    "icon": None,
                    "deletedAt": None,
                },
                "assignee": [{"userId": 42}],
                "authorDetails": {"firstName": "John", "lastName": "Doe", "userId": 45},
                "createdAt": "2026-03-11T12:00:00Z",
                "dueDate": None,
                "queue": None,
                "priority": "High",
            }
        )
        assert item.id == 1
        assert isinstance(item.status, TicketStatusObject)
        assert item.status.slug == "open"
        assert isinstance(item.assignee, list)
        assert item.assignee[0].userId == 42
        assert isinstance(item.authorDetails, TicketAuthorDetails)

    def test_missing_title_raises(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            TicketStoreItem.model_validate({"id": "t-001"})

    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError, match="id"):
            TicketStoreItem.model_validate({"title": "Some ticket"})


class TestTicketStatusObject:
    def test_valid_status_object_validates(self) -> None:
        obj = TicketStatusObject.model_validate(
            {"id": 1, "name": "Open", "slug": "open", "status": "open"}
        )
        assert obj.slug == "open"
        assert obj.icon is None
        assert obj.deletedAt is None

    def test_missing_slug_raises(self) -> None:
        with pytest.raises(ValidationError, match="slug"):
            TicketStatusObject.model_validate(
                {"id": 1, "name": "Open", "status": "open"}
            )


class TestTaskStoreItem:
    def test_template_form_validates(self) -> None:
        item = TaskStoreItem.model_validate(
            {
                "id": "task-001",
                "title": "Kickoff Meeting",
                "status": "done",
                "priority": "high",
                "assignee": "Maria Garcia",
                "project": "Client Portal Rebuild",
                "due_date": "2026-01-10T09:00:00Z",
            }
        )
        assert item.id == "task-001"
        assert item.title == "Kickoff Meeting"
        assert item.due_date == "2026-01-10T09:00:00Z"

    def test_full_frontend_form_validates(self) -> None:
        item = TaskStoreItem.model_validate(
            {
                "id": "task-1",
                "projectId": "proj-1",
                "taskName": "Design Ad Creatives",
                "status": "In Progress",
                "progress": 50,
                "assignedTo": [],
                "taskDuration": 14,
                "isSubtask": 0,
                "subtasksCount": 0,
                "parentProject": {"id": "proj-1", "name": "Q3 Marketing Campaign"},
                "parentTask": {"id": None, "name": None},
                "taskDependencies": [],
                "customFields": [],
                "createdAt": "2026-03-05T00:00:00Z",
                "updatedAt": "2026-03-11T00:00:00Z",
            }
        )
        assert item.taskName == "Design Ad Creatives"
        assert isinstance(item.parentProject, TaskParentRef)
        assert item.parentProject.id == "proj-1"
        assert item.parentTask is not None
        assert item.parentTask.id is None

    def test_missing_id_raises(self) -> None:
        with pytest.raises(ValidationError, match="id"):
            TaskStoreItem.model_validate({"taskName": "No ID Task"})


class TestMilestoneStoreItem:
    def test_validates_from_template(self) -> None:
        item = MilestoneStoreItem.model_validate(
            {
                "id": "ms-001",
                "name": "Phase 1 Complete",
                "status": "pending",
                "target_date": "2026-02-01T00:00:00Z",
                "project": "Client Portal Rebuild",
            }
        )
        assert item.id == "ms-001"
        assert item.status == "pending"

    def test_optional_fields_default_to_none(self) -> None:
        item = MilestoneStoreItem.model_validate(
            {"id": "ms-min", "name": "Minimal Milestone"}
        )
        assert item.status is None
        assert item.target_date is None
        assert item.project is None


class TestQueueStoreItem:
    def test_validates_from_template(self) -> None:
        item = QueueStoreItem.model_validate(
            {
                "id": "queue-001",
                "name": "Leave Requests",
                "ticket_count": 2,
                "avg_resolution_days": 2,
            }
        )
        assert item.name == "Leave Requests"
        assert item.ticket_count == 2

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError, match="name"):
            QueueStoreItem.model_validate({"id": "queue-001"})


class TestAssetStoreItem:
    def test_validates_from_template(self) -> None:
        item = AssetStoreItem.model_validate(
            {
                "id": "asset-001",
                "name": "Forklift FLK-01",
                "category": "heavy_equipment",
                "status": "operational",
                "location": "Warehouse A",
                "last_service": "2026-01-01T00:00:00Z",
            }
        )
        assert item.name == "Forklift FLK-01"
        assert item.status == "operational"

    def test_optional_fields_default_to_none(self) -> None:
        item = AssetStoreItem.model_validate(
            {"id": "asset-min", "name": "Unnamed Asset"}
        )
        assert item.category is None
        assert item.location is None


class TestMaintenanceStoreItem:
    def test_validates_from_template(self) -> None:
        item = MaintenanceStoreItem.model_validate(
            {
                "id": "maint-001",
                "asset_id": "asset-002",
                "type": "corrective",
                "status": "in_progress",
                "technician": "Carlos Rivera",
                "scheduled_date": "2026-01-20T08:00:00Z",
            }
        )
        assert item.asset_id == "asset-002"
        assert item.type == "corrective"

    def test_completed_date_defaults_to_none(self) -> None:
        item = MaintenanceStoreItem.model_validate({"id": "maint-min"})
        assert item.completed_date is None
        assert item.notes is None


class TestWorkOrderStoreItem:
    def test_validates_from_template(self) -> None:
        item = WorkOrderStoreItem.model_validate(
            {
                "id": "wo-001",
                "title": "AC Repair — Sunrise Office",
                "status": "dispatched",
                "priority": "high",
                "technician": "Luis Mendez",
                "zone": "North Zone",
                "scheduled_date": "2026-01-20T09:00:00Z",
            }
        )
        assert item.title == "AC Repair — Sunrise Office"
        assert item.priority == "high"

    def test_missing_title_raises(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            WorkOrderStoreItem.model_validate({"id": "wo-001"})


class TestSchedulingStoreItem:
    def test_validates_from_template(self) -> None:
        item = SchedulingStoreItem.model_validate(
            {
                "id": "sched-001",
                "technician": "Luis Mendez",
                "zone": "North Zone",
                "available_slots": 1,
                "booked_slots": 5,
            }
        )
        assert item.technician == "Luis Mendez"
        assert item.booked_slots == 5

    def test_missing_technician_raises(self) -> None:
        with pytest.raises(ValidationError, match="technician"):
            SchedulingStoreItem.model_validate({"id": "sched-001"})


class TestWeaveStoreItem:
    def test_validates_from_sample_data(self) -> None:
        item = WeaveStoreItem.model_validate(
            {
                "id": "weave-1",
                "name": "Budget Tracker",
                "description": "Q3 Campaign Budget Tracking",
                "authorId": 7,
                "shared": False,
                "archived": False,
                "favorite": True,
                "createdAt": "2026-03-01T10:00:00Z",
                "updatedAt": "2026-03-10T14:30:00Z",
                "lastViewedAt": "2026-03-11T09:00:00Z",
                "attributes": {"format": "xlsx"},
            }
        )
        assert item.name == "Budget Tracker"
        assert isinstance(item.attributes, WeaveAttributes)
        assert item.attributes.format == "xlsx"
        assert item.lastViewedAt == "2026-03-11T09:00:00Z"

    def test_attributes_optional(self) -> None:
        item = WeaveStoreItem.model_validate(
            {"id": "weave-min", "name": "Minimal Weave"}
        )
        assert item.attributes is None
        assert item.lastViewedAt is None


class TestDashboardWidgetEntity:
    def test_validates_from_template(self) -> None:
        item = DashboardWidgetEntity.model_validate(
            {
                "id": "widget-001",
                "type": "ticket_summary",
                "title": "Request Overview",
                "position": {"row": 0, "col": 0, "width": 2, "height": 1},
            }
        )
        assert item.type == "ticket_summary"
        assert item.position.width == 2

    def test_position_width_less_than_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            DashboardWidgetEntity.model_validate(
                {
                    "id": "widget-bad",
                    "type": "kpi_grid",
                    "title": "Bad Widget",
                    "position": {"row": 0, "col": 0, "width": 0, "height": 1},
                }
            )


class TestProjectStoreItem:
    def test_validates_from_sample_data(self) -> None:
        item = ProjectStoreItem.model_validate(
            {
                "id": "proj-1",
                "name": "Q3 Marketing Campaign",
                "description": "Launch new product marketing campaign",
                "progress": 25,
                "isFavorite": True,
                "assignedTo": [],
                "adminUsers": [],
                "startDate": "2026-03-01T00:00:00Z",
                "endDate": "2026-09-30T00:00:00Z",
            }
        )
        assert item.name == "Q3 Marketing Campaign"
        assert item.progress == 25
        assert item.isFavorite is True

    def test_progress_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            ProjectStoreItem.model_validate({"id": "p", "name": "Bad", "progress": 150})


# ===========================================================================
# Bundle stores container unit tests
# ===========================================================================


class TestBundleStoreContainers:
    """Bundle store containers must default all stores to empty lists."""

    def test_hr_hub_stores_empty_defaults(self) -> None:
        stores = HrHubStores.model_validate({})
        assert stores.tickets == []
        assert stores.queues == []
        assert stores.kpis == []
        assert stores.dashboard_widgets == []

    def test_project_ops_stores_empty_defaults(self) -> None:
        stores = ProjectOpsStores.model_validate({})
        assert stores.tasks == []
        assert stores.milestones == []
        assert stores.projects == []
        assert stores.weaves == []

    def test_asset_mgmt_stores_empty_defaults(self) -> None:
        stores = AssetMgmtStores.model_validate({})
        assert stores.assets == []
        assert stores.maintenance == []
        assert stores.tickets == []

    def test_field_service_stores_empty_defaults(self) -> None:
        stores = FieldServiceStores.model_validate({})
        assert stores.work_orders == []
        assert stores.scheduling == []

    def test_generic_stores_empty_defaults(self) -> None:
        stores = GenericStores.model_validate({})
        assert stores.tickets == []
        assert stores.kpis == []
        assert stores.dashboard_widgets == []

    def test_hr_hub_stores_validates_full_template(self) -> None:
        data = _load_dummy_data_json("hr_hub")
        stores = HrHubStores.model_validate(data["stores"])
        assert len(stores.tickets) >= 1
        assert len(stores.queues) >= 1
        assert len(stores.kpis) >= 1
        assert len(stores.dashboard_widgets) >= 1

    def test_project_ops_stores_validates_full_template(self) -> None:
        data = _load_dummy_data_json("project_ops")
        stores = ProjectOpsStores.model_validate(data["stores"])
        assert len(stores.tasks) >= 1
        assert len(stores.milestones) >= 1

    def test_asset_mgmt_stores_validates_full_template(self) -> None:
        data = _load_dummy_data_json("asset_mgmt")
        stores = AssetMgmtStores.model_validate(data["stores"])
        assert len(stores.assets) >= 1
        assert len(stores.maintenance) >= 1

    def test_field_service_stores_validates_full_template(self) -> None:
        data = _load_dummy_data_json("field_service")
        stores = FieldServiceStores.model_validate(data["stores"])
        assert len(stores.work_orders) >= 1
        assert len(stores.scheduling) >= 1


# ===========================================================================
# KNOWN_BUNDLE_KEYS constant
# ===========================================================================


def test_known_bundle_keys_contains_all_bundles() -> None:
    assert KNOWN_BUNDLE_KEYS == {
        "hr_hub",
        "project_ops",
        "asset_mgmt",
        "field_service",
        "generic",
    }


def test_known_bundle_keys_is_frozenset() -> None:
    assert isinstance(KNOWN_BUNDLE_KEYS, frozenset)
