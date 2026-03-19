---
bundle: hr_hub
industry_hint: generic
modules: [tickets, queues, kpis, dashboard]
required_slots: [team_size, primary_use_case]
version: "1.0"
---

# HR Hub Generic Template

## Tickets

- title: "New employee onboarding task for {{employee_name}}"
  type: Issue
  queue: HR Support
- title: "HR policy request from {{department_name}}"
  type: Inquiry
  queue: General Operations
- title: "Update staff profile details"
  type: Change Request
  queue: People Services
- title: "Account access request for {{tool_name}}"
  type: Issue
  queue: IT Support

## Queues

- name: HR Support
- name: General Operations
- name: People Services
- name: IT Support

## KPIs

- label: Open HR Requests
- label: Request Resolution Time
- label: Weekly Ticket Throughput
- label: SLA Compliance

## Dashboard

- widget: ticket_volume_chart
- widget: queue_load_chart
- widget: kpi_summary
- widget: request_status_breakdown
