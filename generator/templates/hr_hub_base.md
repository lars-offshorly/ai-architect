---
bundle: hr_hub
industry_hint: base
modules: [tickets, queues, kpis, dashboard]
required_slots: [team_size, primary_use_case]
version: "1.0"
---

# HR Hub Base Template

## Tickets

- title: "Onboard {{employee_name}} into core systems"
  type: Issue
  queue: HR Operations
- title: "Employee policy clarification for {{department_name}}"
  type: Inquiry
  queue: HR Helpdesk
- title: "Benefits enrollment update for {{employee_name}}"
  type: Change Request
  queue: People Services
- title: "Access request for {{tool_name}}"
  type: Issue
  queue: IT Support

## Queues

- name: HR Operations
- name: HR Helpdesk
- name: People Services
- name: IT Support

## KPIs

- label: Open HR Tickets
- label: Average Resolution Time
- label: Employee Satisfaction Score
- label: SLA Compliance

## Dashboard

- widget: ticket_volume_chart
- widget: queue_load_chart
- widget: resolution_time_trend
- widget: kpi_summary
