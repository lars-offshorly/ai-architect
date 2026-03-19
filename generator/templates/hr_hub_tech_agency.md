---
bundle: hr_hub
industry_hint: tech_agency
modules: [tickets, queues, kpis, dashboard]
required_slots: [team_size, primary_use_case]
version: "1.0"
---

# HR Hub Tech Agency Template

## Tickets

- title: "Provision dev laptop for {{employee_name}}"
  type: Issue
  queue: IT Support
- title: "Creative software license request for {{employee_name}}"
  type: Inquiry
  queue: Studio Operations
- title: "Contractor onboarding checklist for {{client_name}} project"
  type: Change Request
  queue: Talent Ops
- title: "Update role scope for {{employee_name}} in team planning"
  type: Inquiry
  queue: People Partners

## Queues

- name: IT Support
- name: Studio Operations
- name: Talent Ops
- name: People Partners

## KPIs

- label: Onboarding Cycle Time
- label: License Provisioning SLA
- label: Open People Requests
- label: Team Capacity Variance

## Dashboard

- widget: onboarding_pipeline
- widget: queue_load_chart
- widget: kpi_summary
- widget: request_type_breakdown
