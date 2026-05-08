# ADR-003: Preview Payload Contract

**Status:** Superseded
**Original Date:** 2026-03-23
**Superseded Date:** 2026-05-08

## Context

The original preview payload contract split the response into
`generation_json` and `dummy_data_json`.

That made sense when AI Architect owned a broad internal generation shape:

```json
{
  "generation_json": {
    "feature_flags": [],
    "modules": [],
    "config": {}
  },
  "dummy_data_json": {
    "stores": {}
  }
}
```

The integration direction has changed. Murad's BE-translator / knit-builder
service already defines the workspace template contract through its
`GenerationSchema`, consumed by:

```http
POST /organizations/me/generate/
```

If AI Architect can use Murad's template schema from the start, then
`generation_json` is no longer needed as a public payload wrapper. Keeping it
would duplicate and obscure the real backend contract.

## Decision

The target payload contract should be split into two explicit top-level
concerns:

```json
{
  "schema_version": "1.0",
  "session_id": "...",
  "bundle_key": "ticketing",
  "display_name": "Ticketing",
  "modules": [],
  "generation_schema": {
    "dashboards": {},
    "projects": null,
    "tickets": null,
    "hrHub": null,
    "kpi": null
  },
  "sample_data": {
    "bundle_key": "ticketing",
    "session_id": "...",
    "company_name": "...",
    "services": {
      "tickets": {
        "queues": []
      },
      "projects": {
        "projects": []
      },
      "hrHub": {
        "teams": [],
        "employees": []
      },
      "weaves": {
        "folders": [],
        "worksheets": []
      },
      "calendar": {
        "calendars": []
      },
      "kpi": {
        "kpis": []
      }
    }
  },
  "preview_type": "confirmed",
  "warning": null
}
```

`generation_schema` is the AI Architect handoff field containing Murad's
`GenerationSchema` object. When calling Murad's
`POST /organizations/me/generate/`, the contents of `generation_schema` should
be sent as the request body, not wrapped in an extra `generation_schema` key.

`sample_data` is the service-oriented seed/import payload used by backend
flows. It should be based on real Knit service endpoint shapes, not frontend
store state.

`generation_json` and `dummy_data_json` should be considered legacy
compatibility fields, not the target contract.

## Rationale

- Murad's template schema is the actual backend generation contract.
- Re-wrapping Murad's schema inside `generation_json.knit_builder_payload`
  creates unnecessary nesting.
- `feature_flags` are not needed by Murad's translator because they are the same
  for all organizations.
- The previous `config` block cannot currently be applied through Murad's module
  schemas.
- `sample_data` remains necessary because template generation and data
  seeding are different concerns.
- Separating `generation_schema` from `sample_data` makes ownership clear:
  generation schema data goes to the translator, sample data goes to the
  seed/import flow.
- `sample_data` is a clearer name than `dummy_data_json` because the payload is
  expected to be consumed by backend flows, not treated as throwaway mock data.
- `sample_data.services` is clearer than `sample_data.stores` because the data
  should map to backend services and their create/import endpoints, not frontend
  state containers.

## Consequences

- Public API responses should eventually expose `generation_schema` directly
  instead of requiring consumers to read `generation_json.knit_builder_payload`.
- Existing code and tests that depend on `generation_json.feature_flags` or
  `generation_json.config` need a migration plan.
- Preview/edit behavior that currently toggles feature flags should be reviewed,
  because those flags are no longer part of the target backend generation
  contract.
- `sample_data` should remain in the payload.
- `dummy_data_json` should be migrated to `sample_data`.
- `sample_data.stores` should not be the target shape. Use
  `sample_data.services`.
- Ticket sample data must be shaped correctly for backend use, with tickets
  nested inside queues where applicable.
- Non-dashboard builder modules must not be populated with guessed IDs; they
  require Murad's confirmed schemas and template IDs.

## Migration Guidance

During migration, it is acceptable to support both fields temporarily:

```json
{
  "generation_schema": {},
  "generation_json": {
    "knit_builder_payload": {}
  },
  "sample_data": {},
  "dummy_data_json": {}
}
```

The migration should end with consumers reading `generation_schema` directly and
`sample_data` directly, with `generation_json` and `dummy_data_json` removed from
the public contract.

## Sample Data Shape

`sample_data` should be configurable to match the backend seed/import contract
that Murad or BE defines.

It should not be forced into Murad's `GenerationSchema`, because that schema is
for template/module generation. Instead:

- `generation_schema` follows Murad's template generation schema.
- `sample_data` follows the backend data seeding schema.

The target structure is service-oriented:

```json
{
  "sample_data": {
    "schema_version": "1.0",
    "bundle_key": "ticketing",
    "company_name": "Acme Operations",
    "services": {
      "tickets": {
        "queues": []
      },
      "projects": {
        "projects": []
      },
      "hrHub": {
        "teams": [],
        "employees": []
      },
      "weaves": {
        "folders": [],
        "worksheets": []
      },
      "calendar": {
        "calendars": []
      },
      "kpi": {
        "kpis": []
      }
    }
  }
}
```

Use `services` because these records are intended for backend seed/import
flows. The previous `stores` shape came from frontend mock data and should be
treated as legacy reference material only.

For ticketing, tickets should be nested inside queues:

```json
{
  "sample_data": {
    "bundle_key": "ticketing",
    "services": {
      "tickets": {
        "queues": [
          {
            "client_ref": "queue_support",
            "name": "Support",
            "description": "Customer support requests",
            "managerIds": { "teams": [], "userIds": [] },
            "memberIds": { "teams": [], "userIds": [] },
            "tickets": [
              {
                "client_ref": "ticket_laptop_screen",
                "title": "Laptop screen flickering",
                "description": "My current laptop screen is flickering uncontrollably.",
                "priority": "High",
                "status": "Open",
                "category": "Hardware"
              }
            ]
          }
        ]
      }
    }
  }
}
```

Use `client_ref` for relationships because real backend IDs do not exist until
the seed/import flow creates the records. The backend can create a queue,
project, team, or calendar first, map the `client_ref` to the real ID, and then
attach nested records such as tickets, tasks, employees, worksheets, or events.

Projects should group tasks under projects:

```json
{
  "projects": {
    "projects": [
      {
        "client_ref": "project_marketing_q3",
        "name": "Q3 Marketing Campaign",
        "description": "Launch new product marketing campaign",
        "status": "In Progress",
        "priority": "Normal",
        "startDate": "2026-03-01T00:00:00.000000Z",
        "endDate": "2026-09-30T00:00:00.000000Z",
        "tasks": [
          {
            "client_ref": "task_ad_creatives",
            "name": "Design Ad Creatives",
            "status": "In Progress",
            "progress": 50
          }
        ]
      }
    ]
  }
}
```

HR Hub should group team and employee seed data under `hrHub`:

```json
{
  "hrHub": {
    "teams": [
      {
        "client_ref": "team_marketing",
        "name": "Marketing"
      }
    ],
    "employees": [
      {
        "client_ref": "employee_jane_rivera",
        "firstName": "Jane",
        "lastName": "Rivera",
        "employeeNumber": "EMP-001",
        "employmentStatus": "Active",
        "team": "Marketing",
        "workEmail": "jane.rivera@example.com"
      }
    ]
  }
}
```

Weaves and calendar should follow the same service-oriented pattern:

```json
{
  "weaves": {
    "folders": [
      {
        "client_ref": "folder_budget",
        "name": "Budget"
      }
    ],
    "worksheets": [
      {
        "client_ref": "worksheet_budget_tracker",
        "name": "Budget Tracker",
        "description": "Q3 campaign budget tracking",
        "folder_ref": "folder_budget"
      }
    ]
  },
  "calendar": {
    "calendars": [
      {
        "client_ref": "calendar_company",
        "name": "Company Calendar",
        "type": "organisation",
        "timezone": "Asia/Manila",
        "settings": {
          "defaultView": "month"
        },
        "events": [
          {
            "client_ref": "event_campaign_kickoff",
            "name": "Campaign Kickoff",
            "type": "meeting",
            "startsAt": "2026-03-01T09:00:00+08:00",
            "endsAt": "2026-03-01T10:00:00+08:00"
          }
        ]
      }
    ]
  }
}
```

KPI has no available auto-doc today. Keep KPI sample data minimal and mark it
as pending Murad/BE confirmation:

```json
{
  "kpi": {
    "kpis": [
      {
        "client_ref": "kpi_monthly_leads",
        "name": "Monthly Leads",
        "type": "Quantitative",
        "frequency": "Monthly",
        "details": {
          "target": 100
        }
      }
    ]
  }
}
```

If Murad provides a different seed/import schema, `sample_data` should be
adapted to that schema directly.

## Target Rule

If Murad's `GenerationSchema` can be used from the start, do not create a
separate AI Architect `generation_json` wrapper.

Use:

```text
generation_schema + sample_data
```

not:

```text
generation_json + dummy_data_json
```

## Anticipated Implementation Impact

Changing the public contract from:

```text
generation_json + dummy_data_json.stores
```

to:

```text
generation_schema + sample_data.services
```

will affect more than one serialization point. The current operational path,
documented in `docs/architecture/system_overview.md`, still describes the
preview graph and `AppPayload` as emitting `generation_json` and
`dummy_data_json`.

The implementation should address these areas deliberately.

### 1. Preview LangGraph output

Current graph:

```text
extract_user_context
  -> resolve_bundles_to_flags
  -> select_data_tier
  -> generate_sample_data
  -> build_kpi_metrics
  -> validate_schema
  -> emit_preview
```

Expected changes:

- `emit_preview` should eventually emit `generation_schema` and `sample_data`.
- `generate_sample_data` should produce service-oriented sample data, not
  frontend-style stores.
- `build_kpi_metrics` should write KPI sample records under
  `sample_data.services.kpi.kpis`, pending Murad/BE confirmation.
- `validate_schema` should validate the new contract and stop requiring
  `feature_flags`, `config`, or `dummy_data_json.stores` for the target output.

### 2. Preview generator schemas

Current schema concepts:

- `GenerationJson`
- `DummyDataJson`
- `PreviewOutput`

Expected changes:

- Add or rename target models for `GenerationSchema` and `SampleData`.
- Keep legacy aliases only during migration.
- Replace `stores` validation with `services` validation.
- Define per-service sample-data sections such as:
  - `tickets.queues`
  - `projects.projects`
  - `hrHub.teams`
  - `hrHub.employees`
  - `weaves.folders`
  - `weaves.worksheets`
  - `calendar.calendars`
  - `kpi.kpis`

### 3. PreviewFlow assembly

`PreviewFlow.run()` currently assembles an `AppPayload` with:

```python
generation_json=generation_json,
dummy_data_json=dummy_data_json,
```

Expected changes:

- Assemble `generation_schema` from Murad's schema shape directly.
- Assemble `sample_data` from service-oriented seed data.
- Stop treating `generation_json.knit_builder_payload` as the long-term access
  path.
- Preserve dashboard generation behavior, but expose it through
  `generation_schema.dashboards`.
- Keep non-dashboard generation modules null or empty until Murad confirms exact
  schemas and template IDs.

### 4. API transport schemas and endpoints

Current transport responses use `AppPayloadResponseSchema` with:

- `generation_json`
- `dummy_data_json`

Affected endpoints:

- `POST /sessions/{session_id}/preview`
- `POST /sessions/{session_id}/preview/early`
- `POST /sessions/{session_id}/preview/edit`
- `POST /sessions/{session_id}/app`
- mock endpoints under `/mock`

Expected changes:

- Add `generation_schema` and `sample_data` to the response contract.
- Decide whether migration responses temporarily include both old and new
  fields.
- Update `/sessions/{session_id}/app` request schema if it remains the BE
  handoff endpoint.
- Ensure Murad's endpoint receives only the contents of `generation_schema`, not
  the full AI Architect payload.

### 5. App/domain payload models

Current models named around `AppPayload` and app generator contracts still
expect `generation_json` and `dummy_data_json`.

Expected changes:

- Update domain and API payload models to include `generation_schema` and
  `sample_data`.
- Update validators to check the new required keys.
- Keep compatibility handling for legacy payloads only if an active client still
  depends on them.

### 6. Bundle template overlay

`PreviewFlow._apply_bundle_template()` currently overlays
`src/templates/bundles/{bundle}/app-0*.json` operational stores into the preview
payload.

Expected changes:

- Decide whether existing `app-0*.json` files remain frontend preview fixtures
  or become seed-data sources.
- If they remain fixtures, add a conversion layer from template stores to
  `sample_data.services`.
- If they become seed-data sources, update the templates to service-oriented
  shape.
- Avoid leaking dashboard widget/frontend-only stores into `sample_data`.

### 7. Dashboard enrichment

Dashboard enrichment currently uses static `dashboard_output_templates/*.json`
and has already produced the confirmed dashboard generation payload.

Expected changes:

- Keep dashboard template/widget ID logic.
- Surface dashboard output under `generation_schema.dashboards`.
- Do not put dashboard widget preview stores into `sample_data` unless BE
  explicitly needs them for seeding.

### 8. Preview edit behavior

The edit flow currently mutates `generation_json.feature_flags`,
`generation_json.config`, and `dummy_data_json.stores`.

Expected changes:

- Re-evaluate which edit commands still make sense in the target contract.
- Edits that add/remove modules should update `generation_schema`.
- Edits that add/remove records should update `sample_data.services`.
- Feature-flag toggles should be removed or treated as legacy preview-only
  behavior unless a current consumer still requires them.

### 9. Frontend and mock consumers

Existing frontend and mock flows may expect:

- `generation_json`
- `dummy_data_json`
- `dummy_data_json.stores`
- `/mock/{bundle_key}/stores`
- `/mock/{bundle_key}/flags`

Expected changes:

- Confirm whether the frontend still renders from stores or will consume
  service-oriented sample data.
- If frontend still needs stores, provide an adapter from `sample_data.services`
  to frontend stores rather than making stores the public backend contract.
- Update mock endpoints to make clear whether they return legacy preview data or
  target handoff data.

### 10. Tests and fixtures

Many current tests assert the legacy contract.

Expected changes:

- Update tests that assert `generation_json.feature_flags`.
- Update tests that assert `generation_json.config`.
- Update tests that assert `dummy_data_json.stores`.
- Add contract tests for:
  - `generation_schema` top-level presence
  - `sample_data.services` top-level presence
  - tickets nested inside queues
  - no `feature_flags` or `config` in the target generation schema
  - Murad request body equals `generation_schema`, not the full handoff payload

### 11. Naming and migration strategy

The codebase currently has several legacy names:

- `generation_json`
- `dummy_data_json`
- `knit_builder_payload`
- `stores`

Expected changes:

- Use `generation_schema` for Murad's `GenerationSchema` object.
- Use `sample_data` for backend seed/import data.
- Use `services` for service-oriented sample records.
- Treat `knit_builder_payload` as a temporary bridge name only.
- Avoid mixing old and new names in new public contracts.

### 12. External confirmations still required

Implementation should not guess:

- non-dashboard `GenerationSchema` module shapes;
- knit-builder template IDs for tickets/projects/hrHub/KPI;
- KPI sample-data schema;
- whether `/sessions/{session_id}/app` remains the final BE handoff endpoint or
  a new handoff/export endpoint is needed.

These should be confirmed with Murad/BE before finalizing the implementation.
