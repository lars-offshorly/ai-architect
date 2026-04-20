# Feature: Preview Data Population Logic

## 1. Feature Overview

**Feature Name:** Preview Data Population Logic

**Short Description:** Generates realistic, industry-personalized sample records (employees, projects, tickets, weaves) that populate the workspace preview, making the AI's workspace recommendation tangible and verifiable.

**Business Purpose:** A preview with empty tables is useless for validation. The data population logic fills the preview with contextually appropriate sample records — legal firms see attorneys and case names, tech companies see developers and sprint names, consulting firms see engagement managers and client projects — so users can immediately assess whether the AI understood their needs.

**Problem It Solves:** Generic placeholder data ("Employee 1", "Project A") does not help users evaluate whether the workspace fits their domain. The population logic uses signals extracted from the conversation — company name, team names, mentioned roles, work methodology — to generate sample data that mirrors the user's actual work environment.

---

## 2. Scope

### In Scope

- **Context extraction (`extract_user_context`)** — keyword-based scanning of conversation history to extract company name, industry detail, team names, role mentions, work types, methodology, and signal phrases.
- **Data tier selection (`select_data_tier`)** — routes to Tier 1 (personalized) or Tier 3 (generic fallback) based on whether the bundle is in the registry.
- **Employee generation** — 8+ sample employee records with industry-appropriate roles, extracted team names as departments, and culturally diverse name pool.
- **Project generation** — 5+ project records with names templated by work type (sprint names, case names, milestone names).
- **Ticket generation** — 6+ ticket records with titles and types appropriate to the bundle (support tickets, HR requests, legal filings).
- **Weave generation** — 3+ weave (spreadsheet) records linked to generated employees and projects.
- **KPI sample values** — deterministic display values attached to each resolved KPI metric.
- **Terminology awareness** — uses industry context to select from role pools, project naming templates, and ticket type catalogs.

### Out of Scope

- LLM-generated sample data for niche industries (Tier 2 — Phase 2).
- Terminology map application (e.g., renaming "Project" → "Matter" in the output) — documented in the plan but not yet implemented.
- Real data ingestion from user's existing systems.
- Randomized or session-unique data — all generation is deterministic and index-based.
- Avatar/image generation for employee records.

### Limitations

- The name pool is fixed at 10 entries. Sessions extracting more than 10 people from conversation will cycle back to the beginning of the pool.
- Work type detection depends on keyword matching — subtle references to work methodology may not be captured.
- Tier 3 fallback uses `project_mgmt` as the default bundle for sample data structure, which may not perfectly match all unknown bundle types.

---

## 3. Business Rules

1. **Minimum record counts must always be met:**
   - Employees: 8 minimum
   - Projects: 5 minimum (when `project_mgmt` or equivalent bundle is resolved)
   - Tickets: 6 minimum (when `ticketing` or equivalent bundle is resolved)
   - Weaves: 3 minimum (when `weaves` bundle is resolved)

2. **Extracted people take priority over generic names.** If the user mentions "our lead Sarah Chen" in conversation, "Sarah Chen" replaces one of the default name pool entries in the generated employee list.

3. **Extracted team names become department names.** If the user mentions "Engineering team" and "QA team," those become department values on employee records instead of generic department names.

4. **Role pool selection is industry-driven:**
   - Legal industry → Senior Attorney, Associate Attorney, Paralegal, Legal Counsel, Managing Partner
   - Technology industry → Engineering Manager, Senior Developer, QA Engineer, DevOps Engineer, Product Manager
   - HR industry → HR Manager, Talent Acquisition Specialist, Payroll Coordinator, Benefits Administrator
   - Consulting industry → Engagement Manager, Delivery Lead, Solutions Architect, Business Analyst
   - Unknown/generic → Project Manager, Team Lead, Analyst, Coordinator, Specialist, Director

5. **Project naming follows work type:**
   - `sprint` → "Mobile App MVP — Sprint 1", "API Refactor — Sprint 3", etc.
   - `litigation` → "Martinez v. Apex Corp", "State v. Morrison", etc.
   - `waterfall` → "Enterprise Platform Migration", "Annual Compliance Review", etc.
   - `support_request` → "CRM Integration Phase 2", "Infrastructure Upgrade", etc.
   - Default → "Client Onboarding Portal", "Quarterly Review Dashboard", etc.

6. **Ticket titles follow bundle type:**
   - `ticketing` → bug reports and feature requests ("Login page not loading", "Dashboard export to CSV")
   - `hr_hub` → HR requests ("Benefits enrollment update", "PTO request — Maria Santos")
   - Default → general support items

7. **All date fields use deterministic offsets from a sliding base date.** Start dates are offset 60 days into the past; due dates are 30+ days in the future. No randomization.

8. **Email addresses are derived from names.** Format: `{first}.{last}@{company_slug}.com`. Company slug comes from extracted company name or defaults to `"company"`.

9. **Tier 3 uses the same generation functions as Tier 1** but with a `None` UserContext, causing all personalization branches to fall through to generic defaults.

---

## 4. User Flow / Workflow

### Context Extraction Phase

1. `extract_user_context` receives the full conversation history (all user and assistant turns).
2. Concatenates all message content into a single text block for scanning.
3. Runs regex patterns to extract:
   - Company name (e.g., "we are Apex Corp" → `company_name: "Apex Corp"`)
   - User's own name and role (e.g., "I'm Sarah, the engineering lead")
   - Team mentions (e.g., "our QA team of 8 people" → `TeamDetail(name="QA", size=8)`)
   - Role mentions (e.g., "our attorneys and paralegals")
4. Runs keyword detection to classify:
   - Industry (legal, tech, consulting, HR, operations)
   - Work types (sprint, litigation, waterfall, support_request)
   - Methodology (agile, waterfall, kanban)
   - Company size (small, mid-sized, enterprise)
5. Extracts key phrases relevant to KPI matching (e.g., "on time delivery", "SLA compliance").
6. Returns a populated `UserContext` object (or one with all-None fields if nothing was detected).

### Tier Selection Phase

1. `select_data_tier` checks if the resolved bundle key exists in `BUNDLE_REGISTRY`.
2. If the key exists and flags were successfully resolved → **Tier 1** (personalized generation).
3. If the key is unknown or resolution returned nothing → **Tier 3** (generic fallback).

### Data Generation Phase

1. `generate_sample_data` dispatches to four builder functions based on data tier:
   - `_build_employees(bundle_key, user_context, count=8)` — generates employee records using the industry-appropriate role pool and extracted team/people names.
   - `_build_projects(bundle_key, user_context, employees, count=5)` — generates project records with work-type-aware naming and assigns leads from the employee list.
   - `_build_tickets(bundle_key, user_context, employees, count=6)` — generates ticket records with bundle-appropriate types and titles.
   - `_build_weaves(user_context, employees, projects, count=4)` — generates weave records linked to employees and projects.
2. Each builder cycles through its data pools deterministically (index-based, no randomness).
3. Returns all four arrays to be stored in pipeline state.

### KPI Value Assignment Phase

1. `build_kpi_metrics` resolves metric slugs (see Module and KPI Mapping Engine).
2. For each resolved metric, assigns a sample display value from a type-indexed pool:
   - Percentage metrics → `[87.5, 92.1, 78.4, 95.0, 83.2]`
   - Count metrics → `[142, 38, 217, 15, 67]`
   - Duration metrics → `[3.2, 1.8, 5.4, 2.1, 4.7]` (days)
   - Status metrics → `["Healthy", "At Risk", "Healthy", "On Track", "Healthy"]`
   - Ratio metrics → `[0.72, 0.85, 0.61, 0.90, 0.78]`
3. Values are assigned by index position in the resolved metrics list, cycling if more metrics than pool entries.

---

## 5. Acceptance Criteria

- [ ] Conversation mentioning "Apex Corp" produces employee emails in the format `*.@apex-corp.com` and `company_name: "Apex Corp"` in the output.
- [ ] Conversation mentioning "our litigation team" and "attorneys" produces legal-industry role names (Senior Attorney, Paralegal) and litigation-style project names (case names).
- [ ] Conversation mentioning "sprints" and "standups" produces agile-style project names and `work_methodology: "agile"` in the user context.
- [ ] Conversation mentioning "our QA team of 12" produces a `TeamDetail` with `name="QA"` and `size=12`, and "QA" appears as a department on some employee records.
- [ ] Empty conversation history produces valid Tier 3 output with generic names, roles, and project titles — no empty arrays.
- [ ] Employee records contain all required fields: `id`, `name`, `role`, `department`, `email`, `is_active`.
- [ ] Project records contain all required fields: `id`, `name`, `status`, `lead`, `team_size`, `start_date`, `due_date`, `completion_pct`.
- [ ] Ticket records contain all required fields: `id`, `title`, `type`, `status`, `priority`, `requester`, `assignee`, `created_at`.
- [ ] Minimum record counts are met for all bundles: 8 employees, 5 projects, 6 tickets.
- [ ] KPI sample values match their declared type — no string value on a percentage metric, no float on a count metric.
- [ ] The same inputs always produce the same outputs (deterministic, no randomization).
- [ ] Tier 3 output for unknown bundle `asset_mgmt` still produces a structurally valid preview with generic data.

---

## 6. Security Considerations

- **User-provided text in sample data fields.** Extracted company names, team names, and person names from conversation history are injected into sample data fields (employee names, email addresses, department names). Phase 2 must sanitize these values by stripping HTML/script tags before inclusion to prevent stored XSS if the preview JSON is rendered without escaping.
- **No PII generation.** The name pool consists of fictional, culturally diverse names. Extracted names from conversation are user-volunteered and not augmented with external data.
- **Deterministic generation prevents information leakage.** Because the same inputs always produce the same outputs, there is no risk of one session's data leaking into another through shared random state or cached intermediate results.
- **Email addresses are synthetic.** Generated emails use the `@{company_slug}.com` domain derived from extracted company name. These are fictional and should not be used for any actual communication.
- **Bounded extraction scope.** The keyword and regex patterns in `extract_user_context` only match specific, documented patterns. They cannot be weaponized to extract arbitrary data from conversation history — unrecognized patterns are simply ignored.
- **No file system access.** Sample data generation is entirely in-memory. No templates are loaded from disk, no files are written. The `TemplateRepository` dependency was removed in Phase 1.
