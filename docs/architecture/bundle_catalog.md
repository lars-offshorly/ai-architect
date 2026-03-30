# Bundle Catalog

Bundles are defined in `src/templates/bundle_registry.yaml` and seeded from `catalog/bundles.json`.

## hr_hub — HR Hub

- **Entity type:** people
- **Default modules:** tickets, queues, kpis, dashboard
- **Required slots:** team_size, primary_use_case
- **Industry hints:** human resources, people operations, talent, hr, healthcare, logistics
- **Customisable fields:** company_name, employee_names, department_names, role_names, status_labels

## project_ops — Project Operations

- **Entity type:** work
- **Default modules:** tasks, timelines, milestones, dashboard
- **Required slots:** project_count, team_size
- **Industry hints:** project management, consulting, delivery, implementation
- **Customisable fields:** company_name, project_names, team_names, milestone_labels

## asset_mgmt — Asset Management

- **Entity type:** asset
- **Default modules:** assets, maintenance, tickets, dashboard
- **Required slots:** asset_types, location_count
- **Industry hints:** asset, equipment, facility, fleet, warehouse
- **Customisable fields:** company_name, asset_categories, location_names, status_labels

## field_service — Field Service

- **Entity type:** work
- **Default modules:** work_orders, scheduling, forms, dashboard
- **Required slots:** service_zones, technician_count
- **Industry hints:** field service, dispatch, technician, onsite, repair
- **Customisable fields:** company_name, technician_names, zone_names, service_types

## generic — Custom Workspace

- **Entity type:** work
- **Default modules:** tickets, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** custom, general, other
- **Customisable fields:** company_name, primary_use_case
