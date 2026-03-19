---
bundle: project_ops
industry_hint: consulting
modules: [tasks, timelines, milestones, dashboard]
required_slots: [project_count, team_size]
version: "1.0"
---

# Project Operations Consulting Template

## Tasks

- title: "Draft statement of work for {{client_name}}"
  priority: High
  status: Open
- title: "Schedule executive steering check-in"
  priority: Medium
  status: Open
- title: "Publish utilization snapshot"
  priority: Medium
  status: In Progress
- title: "Finalize client handoff notes"
  priority: Low
  status: Open

## Timelines

- name: Discovery Workshop
  duration_weeks: 1
- name: Solution Build
  duration_weeks: 5
- name: Change Enablement
  duration_weeks: 2

## Milestones

- title: "SOW Approved"
  target_week: 1
- title: "Interim Client Demo"
  target_week: 4
- title: "Production Handover"
  target_week: 8

## Dashboard

- widget: utilization_trend
- widget: milestone_tracker
- widget: client_health_index
- widget: delivery_risk_board
