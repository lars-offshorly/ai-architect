---
bundle: project_ops
industry_hint: base
modules: [tasks, timelines, milestones, dashboard]
required_slots: [project_count, team_size]
version: "1.0"
---

# Project Operations Base Template

## Tasks

- title: "Create kickoff checklist for {{project_name}}"
  priority: High
  status: Open
- title: "Assign owner for delivery workstream"
  priority: Medium
  status: Open
- title: "Review weekly risk register"
  priority: Medium
  status: In Progress
- title: "Prepare stakeholder status update"
  priority: Low
  status: Open

## Timelines

- name: Discovery
  duration_weeks: 2
- name: Delivery
  duration_weeks: 6
- name: Stabilization
  duration_weeks: 2

## Milestones

- title: "Requirements sign-off"
  target_week: 2
- title: "Initial release"
  target_week: 6
- title: "Go-live"
  target_week: 10

## Dashboard

- widget: task_burndown_chart
- widget: milestone_tracker
- widget: delivery_health_summary
- widget: risk_heatmap
