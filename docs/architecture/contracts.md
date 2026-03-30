# Data Contracts

## Conversation Turn Response

```json
{
  "status": "awaiting_input | pending_confirmation | ready_for_preview | complete",
  "session_id": "uuid",
  "message": "assistant text (optional)",
  "question": "clarification question (optional)",
  "bundle_key": "hr_hub | project_ops | ... (optional)",
  "slots": {}
}
```

## App Payload Response (`POST /sessions/{id}/preview`)

```json
{
  "schema_version": "1.0",
  "session_id": "uuid",
  "bundle_key": "hr_hub",
  "display_name": "HR Hub",
  "modules": ["tickets", "queues", "kpis", "dashboard"],
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
      "dashboard_widgets": [...]
    }
  }
}
```

## ExtractedInfo (internal)

| Field              | Type           | Description                            |
|--------------------|----------------|----------------------------------------|
| session_id         | str            | Session identifier                     |
| company_name       | str \| None    | Extracted company name                 |
| industry_hint      | str \| None    | Detected industry                      |
| primary_use_case   | str \| None    | One-sentence summary of intent         |
| entity_type        | str \| None    | people / work / asset                  |
| employee_names     | list[str]      | Staff names mentioned                  |
| role_names         | list[str]      | Job titles mentioned                   |
| department_names   | list[str]      | Department/team names                  |
| metrics            | list[str]      | KPI terms mentioned                    |
| status_labels      | list[str]      | Workflow status terms                  |
| slots              | dict           | Key-value slot bag                     |

## Template Placeholder Convention

Templates use `{{field_name}}` syntax for personalisation.
See `src/agents/preview_generator/modifier.py` for the full placeholder map.
