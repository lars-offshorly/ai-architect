# AI Architect Project Plan

## Overview
The AI Architect is a system that helps users design and generate workspace configurations and dummy data for various business bundles (like HR Hub, Project Ops, etc.) through a conversational onboarding process.

## Architecture
The system is built as a state-driven pipeline using **LangGraph** for orchestration and **FastAPI** for the API layer.

### High-Level Data Flow
1. User message → FastAPI `/onboard` endpoint
2. → OnboardingProcessor
3. → Onboarding Graph (LangGraph) which includes:
   - `conversation_classifier`
   - `intent_extraction`
   - `slot_filler`
   - `clarification` (Human-in-the-Loop)
   - `bundle_confirmer`
   - `json_assembler`
4. → Data Generator Pipeline (Retriever → Personaliser → Validator)
5. → Outputs: `generation_json` and `dummy_data_json`

### Shared State: `OnboardingState`
All nodes communicate via a central `OnboardingState` object which includes:
- `messages`: conversation history
- `slots`: extracted variables (e.g., `team_size`, `industry_hint`)
- `onboarding_intents`: structured classification of user intent and bundle choice
- `turn_count`: track how many interactions have occurred
- `confirmed`: boolean flag indicating if the user has approved the bundle suggestion
- `generation_json`: final backend configuration payload
- `dummy_data_json`: final realistic sample data payload

## Data Structures for Frontend
The system generates two JSON chunks:
1. **Generation JSON**: Scaffold configuration (used by backend)
2. **Dummy Data JSON**: Realistic mock data for frontend stores

The Dummy Data JSON has a root structure:
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

Each store array must contain objects that conform to the TypeScript entities defined in the respective frontend repository modules (e.g., `fe-repositories/tickets/entities/TicketEntity.ts`).

## Conversational Scenarios
The AI follows specific thinking patterns in conversations, as illustrated in the reference documentation:

### Scenario 1: Specialized Industry (Legal Services)
- User expresses need for case progress and attorney workload visibility
- AI detects entities: Legal Cases (Work) and Attorneys (People)
- AI infers metrics: Delivery Performance and Operational Efficiency
- Through clarification, AI confirms work structure: deadline-driven and staged work
- Final bundle selection: Legal Services Bundle (Tickets, Chat, Video Call, Weaves Spreadsheet, Dashboard)

### Scenario 2: General Productivity to Software Consulting
- User wants to see team activities and results
- AI detects entities: Teams (grouped people) and Work (unspecified)
- AI narrows down module requirement: Projects vs. Tickets
- User confirms hybrid model: both Projects and Tickets
- User specifies industry: Software Consulting and Offshore work
- Final bundle selection: Professional Services Bundle
- Metrics: On-time delivery %, Project Risk, Utilization %, and Ticket Resolution Time

## Current Status
Based on the documentation review, the system appears to be implemented correctly and consistently with the requirements:
- State Management: Uses the `OnboardingState` pattern and `MessagesState` extension
- Orchestration: Correctly implements the `interrupt/resume` lifecycle in `processor.py`
- Data Generator: The 3-strategy fallback in the retriever and structured output personalisation follow requirements
- Async/Settings: Every node uses `get_openai_chat_model` and `get_settings`, adhering to centralized config and async-only rules

## Next Steps
- Review and update documentation as the system evolves
- Test the onboarding flow with various bundle selections
- Ensure generated dummy data matches frontend entity expectations
- Consider adding new bundles based on market demand
