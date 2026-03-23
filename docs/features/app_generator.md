# App Generator

## Responsibility

Validates and packages the final workspace payload that is returned to the frontend.

## Pipeline

```
session_id + bundle_key + preview_data + dummy_data
  └─ load app.json          (from TemplateRepository)
  └─ validate_generation_json
  └─ validate_dummy_data_json
  └─ AppPayloadContract.validate_contract()
  └─ AppPayloadFormatter.format()  → AppPayload
```

## Key Files

| File                                       | Role                                           |
|--------------------------------------------|------------------------------------------------|
| `agents/app_generator/service.py`          | Orchestrates assembly pipeline                 |
| `agents/app_generator/contract.py`         | Defines and validates the payload contract     |
| `agents/app_generator/validators.py`       | Per-field validation rules                     |
| `agents/app_generator/formatter.py`        | Constructs the final `AppPayload` model        |

## Output Shape

The assembled `AppPayload` contains:
- `generation_json` — bundle config (modules, statuses, KPI definitions)
- `dummy_data_json` — personalised sample store records

Both are passed directly to the API response via `AppPayloadResponseSchema`.
