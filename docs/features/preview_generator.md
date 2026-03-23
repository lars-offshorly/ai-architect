# Preview Generator

## Responsibility

Fetches pre-created JSON bundle templates and personalises them with extracted user-specific data.

## Pipeline

```
bundle_key + ExtractedInfo
  └─ TemplateFetcher   → raw preview.json, raw dummy_data.json  (from disk)
  └─ TemplateModifier  → inject {{placeholders}} with extracted fields
  └─ DummyDataInjector → inject employee names, company name into store records
  └─ validators        → assert required keys and bundle_key match
```

## Key Files

| File                                               | Role                                       |
|----------------------------------------------------|--------------------------------------------|
| `agents/preview_generator/service.py`              | Coordinates the full generation pipeline   |
| `agents/preview_generator/fetcher.py`              | Loads JSON from `src/templates/bundles/`   |
| `agents/preview_generator/modifier.py`             | Replaces `{{placeholders}}` in templates   |
| `agents/preview_generator/dummy_data.py`           | Injects names into store record arrays     |
| `agents/preview_generator/validators.py`           | Validates output structure                 |

## Placeholder System

Templates use `{{field_name}}` syntax. The full map is in `modifier.py`.

Examples:
- `{{company_name}}` → `extracted.company_name`
- `{{employee_name}}` → `extracted.employee_names[0]`
- `{{hr_manager}}` → `extracted.role_names[0]`

## Template Location

```
src/templates/bundles/
  hr_hub/
    preview.json      ← personalised for display
    app.json          ← config schema for backend
    dummy_data.json   ← seeded sample records
```
