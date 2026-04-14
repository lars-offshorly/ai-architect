# System Overview

## Purpose

AI Architect is a conversational AI backend that guides users through a structured onboarding flow to generate a personalised workspace configuration and realistic sample data for a target business bundle.

## High-Level Flow

```
User message
  └─ POST /sessions                         → start session
  └─ POST /sessions/{id}/reply              → continue conversation
  └─ POST /sessions/{id}/confirm            → confirm bundle
  └─ POST /sessions/{id}/preview            → generate preview + payload
```

## Component Breakdown

| Component               | Location                        | Responsibility                                 |
|-------------------------|---------------------------------|------------------------------------------------|
| Interpreter             | `src/agents/interpreter/`       | Extract signals, classify bundle               |
| Replier                 | `src/agents/replier/`           | Generate clarification questions + suggestions |
| Preview Generator       | `src/agents/preview_generator/` | Fetch + personalise preview templates          |
| App Generator           | `src/agents/app_generator/`     | Validate + package final payload               |
| Conversation Flow       | `src/orchestrators/`            | Coordinate multi-turn conversation             |
| Preview Flow            | `src/orchestrators/`            | Coordinate template generation pipeline        |
| Domain Models           | `src/domain/`                   | Shared business objects                        |
| Repositories            | `src/repositories/`             | State + file access                            |
| Templates               | `src/templates/`                | Pre-created bundle JSON assets                 |

## Bundle Types

Catalog keys defined in `src/templates/bundle_registry.yaml`:

- **hr_management** → renders as `hr_hub` — HR teams managing employees, leave, and onboarding
- **project_mgmt** → renders as `project_mgmt` — Project delivery, milestones, and task tracking
- **ticketing** → renders as `ticketing` — Support tickets, queues, and SLA management
- **finance** → renders as `project_mgmt` — Budgeting, invoicing, and financial reporting
- **marketing** → renders as `project_mgmt` — Campaign and content management
- **sales** → renders as `project_mgmt` — Lead tracking and pipeline management
- **healthcare** → renders as `ticketing` — Patient records and appointment workflows
- **legal_services** → renders as `ticketing` — Case management and legal documentation
- **construction** → renders as `project_mgmt` — Site and contractor management
- **real_estate** → renders as `project_mgmt` — Property listings and tenant management
- **education** → renders as `project_mgmt` — Course and student management
- **all_microservices** → renders as `hr_hub` — Full platform with all services
- **generic** → renders as `generic` — Fallback for unmapped requests
