# AI Architect System Overview

AI Architect is an AI-powered onboarding conversation pipeline designed to automate the process of classifying user needs, generating a preview of an application, and finally provisioning a workspace.

## System Purpose
The system operates as a 3-part pipeline:
1. **[Dev A] AI Bundle Classifier**: Classifies user requirements from conversation history into specific application "bundles."
2. **[Dev B] JSON Preview Generator**: (Current Focus) Generates an `AppPayload` containing `generation_json` (workspace configuration) and `dummy_data_json` (sample data).
3. **[Dev C] JSON App Generator**: Uses the generated JSON payload to provision the final workspace for the user.

## Core Components
Here are the main directories and entry points:

| Component | Files/Directories | Purpose |
| :--- | :--- | :--- |
| **Main Entry** | `src/main.py` | FastAPI application entry point |
| **Preview Generator** | `src/agents/preview_generator/` | Core logic for the LangGraph-based preview pipeline |
| **API Endpoints** | `src/api/routers/preview.py` | HTTP endpoint for preview generation |
| **Orchestrator** | `src/orchestrators/preview_flow.py` | Coordinates the flow between different pipeline nodes |
| **Data Models** | `src/domain/models/` | Pydantic models for sessions, payloads, and conversation messages |
| **Documentation** | `docs/features/` | Detailed feature specifications and implementation logs |

## Feature Status

### Phase 1: Core Pipeline (COMPLETE)
- [x] LangGraph-powered state management and pipeline execution.
- [x] Automated context extraction from conversation history.
- [x] Feature flag and KPI resolution for specific bundles.
- [x] Deterministic sample data generation (employees, projects, tickets).
- [x] Schema validation and conditional retry logic.

### Phase 2: Refinement & LLM Integration (IN PROGRESS)
- [/] **Catalog Key Migration**: Updating bundle keys to align with Dev A's latest classification outputs (`hr_management`, `project_mgmt`, etc.).
- [/] **Config Shape Optimization**: Refining JSON output to match specific requirements for the App Generator (Dev C).
- [ ] **LLM-Enhanced Extraction**: Implementing LLM nodes for more sophisticated context parsing.
- [ ] **Edit Flow**: Enabling users to modify generated previews via natural language instructions.

## Getting Started
To run the system locally:
```bash
poetry install
make dev
```
For testing:
```bash
make test
```
Documentation is available at `http://localhost:8000/docs`.
