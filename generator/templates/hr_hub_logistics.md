---
bundle: hr_hub
industry_hint: logistics
modules: [tickets, queues, kpis, dashboard]
required_slots: [team_size, primary_use_case]
version: "1.0"
---

# HR Hub Logistics Template

## Tickets

- title: "Driver onboarding packet for {{employee_name}}"
  type: Issue
  queue: Driver Success
- title: "Shift assignment update for {{employee_name}}"
  type: Change Request
  queue: Workforce Planning
- title: "Warehouse safety training enrollment"
  type: Inquiry
  queue: Compliance Desk
- title: "PPE replacement request for {{location_name}}"
  type: Issue
  queue: Operations Support

## Queues

- name: Driver Success
- name: Workforce Planning
- name: Compliance Desk
- name: Operations Support

## KPIs

- label: Driver Onboarding Completion
- label: Training Compliance Rate
- label: Open Workforce Tickets
- label: Shift Coverage Gaps

## Dashboard

- widget: onboarding_pipeline
- widget: shift_coverage_map
- widget: compliance_tracker
- widget: queue_load_chart
