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

- **hr_hub** — HR teams managing employees, leave, and onboarding
- **project_ops** — Project delivery, milestones, and task tracking
- **asset_mgmt** — Physical asset lifecycle and maintenance
- **field_service** — Technician dispatch and work order management
- **generic** — Fallback for requests that don't map to a specific bundle
