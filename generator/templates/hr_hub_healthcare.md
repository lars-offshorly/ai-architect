---
bundle: hr_hub
industry_hint: healthcare
modules: [tickets, queues, kpis, dashboard]
required_slots: [team_size, primary_use_case]
version: "1.0"
---

# HR Hub Healthcare Template

## Tickets

- title: "Nurse credentialing verification for {{employee_name}}"
  type: Issue
  queue: Credentialing
- title: "Clinical onboarding schedule for {{department_name}}"
  type: Change Request
  queue: Workforce Planning
- title: "Immunization record follow-up"
  type: Inquiry
  queue: Compliance
- title: "Badge and EMR access setup for {{employee_name}}"
  type: Issue
  queue: IT Access

## Queues

- name: Credentialing
- name: Workforce Planning
- name: Compliance
- name: IT Access

## KPIs

- label: Credentialing Completion Rate
- label: Clinical Onboarding Turnaround
- label: Compliance Ticket Backlog
- label: Access Provisioning SLA

## Dashboard

- widget: credentialing_status_board
- widget: onboarding_pipeline
- widget: compliance_alerts
- widget: queue_load_chart
