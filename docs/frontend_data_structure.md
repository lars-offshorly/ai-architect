# Frontend Data Structure Analysis

Based on the analysis of the `fe-repositories` directory and the backend `generator/schemas.py`, here is the breakdown of the JSON data structures expected by the frontend.

## Overview
The AI Onboarding Pipeline produces two JSON chunks when onboarding completes:
1. **Generation JSON**: Scaffold configuration.
2. **Dummy Data JSON**: Contains realistic mock data used directly by frontend stores.

The "JSON used by the frontend" primarily refers to the mocked dummy data seeded into the frontend application. The data structure requires a specific root wrapper with corresponding TypeScript entities for each module.

## Root JSON Wrapper (DummyDataJSON)
The AI generator uses the following root structure to pass this data into the frontend. The `stores` object maps directly to frontend domains.

```json
{
  "schema_version": "1.0",
  "session_id": "uuid-string",
  "bundle": "hr_hub",
  "stores": {
    "tickets": [],
    "queues": [],
    "kpis": [],
    "dashboard_widgets": [],
    "tasks": [],
    "milestones": [],
    "assets": [],
    "maintenance": []
  }
}
```

## Module Entities (`fe-repositories/`)
Each array inside the `stores` object must contain objects that conform to the TypeScript interfaces defined in the `fe-repositories/{module}/entities` directory. 

### Examples of Key Entities

#### 1. Tickets (`tickets/entities/TicketEntity.ts`)
The objects inside `stores.tickets` must follow the `TicketEntity` schema:
```typescript
{
  "id": 123,
  "ticketId": "TCK-1001",
  "title": "Need new laptop",
  "description": "My keyboard is broken...",
  "status": {
    "id": 1,
    "name": "Open",
    "slug": "open",
    "status": "open",
    "description": "Ticket is open",
    "color": "#ff0000",
    "icon": null,
    "deletedAt": null
  },
  "assignee": [{ "userId": 42 }],
  "authorDetails": {
    "firstName": "John",
    "lastName": "Doe",
    "userId": 45
  },
  "createdAt": "2026-03-11T12:00:00Z",
  "dueDate": null,
  "queue": null,
  "priority": "High",
  // ... other fields as defined in TicketEntity
}
```

#### 2. Projects & Tasks (`projects/entities/ProjectTaskEntity.ts` & `ProjectEntity.ts`)
If a `projects` bundle is selected, its tasks would be mapped into `stores.tasks` (or related project stores). They must align with the `ProjectTaskEntity` schema, which includes fields such as `assignedTo`, `taskName`, `status`, `taskDuration`, and relations pointing to a `parentProject` (via `ProjectEntity.ts`).

#### 3. KPIs (`kpi/entities/KpiEntity.ts`)
Dummy data meant for `stores.kpis` must conform to the `KpiEntity` structure. Key parameters include `type` ('Qualitative' or 'Quantitative'), `status` ('Completed', 'Not Started', 'Ongoing'), `frequency`, and importantly, the `details` field which splits into union interfaces like `KpiQuantitativeDetails` (containing `target`, `thresholds`, `condition`, `dataLabel`, etc.) or `KpiMoodScaleDetails`.

#### 4. Weaves (`weaves/entities/WeaveEntity.ts`)
For Weaves (spreadsheets/tables), the representations use `WeaveEntity.ts`. Their structures require fields like `attributes` (which hold `formSettings`, `cellStyles`, `mergeCells`), optional `sheets` arrays for nested structures, and details such as `totalColumns` and `totalRows`.

#### 5. HR Hub
HR Hub utilizes standard entities (like projects, tickets, or specific HR forms) under its domain but does not exclusively redefine standard workflow representations outside of small references like `HrHubTasksRepositoryEntity.ts`, which is a simplified payload `{ "message": "...", "taskId": "..." }` used for fetching mechanisms rather than large mock data sets generated directly into UI stores.

#### 6. General Rules for Payload Generation
When generating the target JSON:
1. **Match Array Keys to Store Names**: Use the exact keys required by `StoreData` (`tickets`, `queues`, `tasks`, etc.).
2. **Strict Entity Compliance**: Follow the exact properties, nested objects, and nullability rules (`string | null`) indicated by the TypeScript interfaces in the respective `fe-repositories/<module>/entities/` folders.
3. **Relationships**: Some entities contain nested relationships (e.g., `TicketEntity.status`, `TicketEntity.queue`). These must be populated with structurally valid nested objects.

## Next Steps for Development
When adjusting the AI generator Prompts/Templates or mapping logic:
- Always reference `fe-repositories/<module>/entities/<Name>Entity.ts`.
- Ensure the LLM explicitly returns JSON matching the properties in the TypeScript interface without missing explicitly required keys.

To see a complete, concrete example of a generated structure combining multiple models (Tickets, KPIs, Projects, Tasks, and Weaves) that aligns with frontend TypeScript expectations, view [sample_dummy_data.json](sample_dummy_data.json).
