---
bundle: generic
industry_hint: base
modules: [tickets, dashboard]
required_slots: [primary_use_case]
version: "1.0"
---

# Generic Base Template

## Tickets

- title: "Initial workspace request intake"
  type: Inquiry
  queue: General Support
- title: "Follow-up on process clarification"
  type: Inquiry
  queue: General Support
- title: "Track unresolved operational issue"
  type: Issue
  queue: Operations Desk
- title: "Submit update to workflow settings"
  type: Change Request
  queue: Admin Desk

## Dashboard

- widget: ticket_volume_chart
- widget: open_vs_closed_tickets
- widget: queue_load_chart
- widget: activity_feed
