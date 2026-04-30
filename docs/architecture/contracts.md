# Data Contracts

## Conversation Turn Response

```json
{
  "status": "awaiting_input | pending_confirmation | ready_for_preview | complete",
  "session_id": "uuid",
  "message": "assistant text (optional)",
  "question": "clarification question (optional)",
  "bundle_key": "hr_management | project_mgmt | ticketing | finance | ... (optional)",
  "slots": {}
}
```

## App Payload Response (`POST /sessions/{id}/preview`)

```json
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "bundle_key": "hr_management",
  "display_name": "HR Management",
  "modules": ["HR Management", "Chat", "Dashboard"],
  "generation_json": {
    "schema_version": "1.0",
    "bundle_key": "hr_hub",
    "modules": [...],
    "config": { ... }
  },
  "dummy_data_json": {
    "bundle_key": "hr_hub",
    "stores": {
      "tickets": [...],
      "queues": [...],
      "kpis": [...],
      "dashboard_widgets": [...],
      "dashboard_generation_output": {}
    }
  }
}
```

## ExtractionResult (internal)

Top-level model passed between interpreter, session state, and preview pipeline.

| Field                    | Type                      | Description                                      |
|--------------------------|---------------------------|--------------------------------------------------|
| session_id               | str                       | Session identifier                               |
| classification_signals   | ClassificationSignals     | Signals used for bundle classification           |
| personalization_signals  | PersonalizationSignals    | Signals used for workspace personalisation       |
| missing_fields           | list[MissingFieldType]    | Required slots not yet collected                 |
| bundle_variant_key       | str \| None               | Selected variant e.g. `app-01`, `app-02`         |

### ClassificationSignals

| Field           | Type       | Description                          |
|-----------------|------------|--------------------------------------|
| keywords        | list[str]  | Domain keywords extracted             |
| entities        | list[str]  | Named entities extracted              |
| intents         | list[str]  | User intents extracted                |
| workflow_hints  | list[str]  | Workflow methodology hints            |
| domain_hints    | list[str]  | Industry/domain hints                 |
| metrics         | list[str]  | KPI terms mentioned                   |

### PersonalizationSignals

| Field            | Type            | Description                          |
|------------------|-----------------|--------------------------------------|
| company_name     | str \| None     | Extracted company name               |
| employee_names   | list[str]       | Staff names mentioned                |
| role_names       | list[str]       | Job titles mentioned                 |
| department_names | list[str]       | Department/team names                |
| branch_names     | list[str]       | Branch/location names                |
| custom_labels    | list[str]       | Custom status or label terms         |
| terminology      | dict[str, str]  | Domain-specific terminology overrides|

## Template Placeholder Convention

Templates use `{{field_name}}` syntax for personalisation.
See `src/agents/preview_generator/modifier.py` for the full placeholder map.
