---
bundle: asset_mgmt
industry_hint: base
modules: [assets, maintenance, tickets, dashboard]
required_slots: [asset_types, location_count]
version: "1.0"
---

# Asset Management Base Template

## Assets

- name: "Warehouse Forklift A-12"
  type: Vehicle
  location: "{{location_name}}"
- name: "HVAC Unit R-301"
  type: Facility Equipment
  location: "{{location_name}}"
- name: "Server Rack 04"
  type: IT Infrastructure
  location: "{{location_name}}"
- name: "Safety Scanner S-9"
  type: Inspection Equipment
  location: "{{location_name}}"

## Maintenance

- title: "Quarterly inspection for forklift fleet"
  frequency: Quarterly
- title: "Replace HVAC filters"
  frequency: Monthly
- title: "UPS battery diagnostics"
  frequency: Biannual

## Tickets

- title: "Asset check-out request"
  type: Inquiry
  queue: Asset Desk
- title: "Report damaged equipment"
  type: Issue
  queue: Maintenance Team
- title: "Update asset ownership"
  type: Change Request
  queue: Asset Admin

## Dashboard

- widget: asset_status_overview
- widget: maintenance_calendar
- widget: ticket_volume_chart
- widget: lifecycle_cost_summary
