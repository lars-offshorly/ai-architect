# Bundle Catalog

Bundles are defined in `src/templates/bundle_registry.yaml`. Each bundle has a `bundle_key` (catalog key) and a `render_key` (frontend rendering profile).

## hr_management -- HR Management (render_key: hr_hub)

- **Entity type:** people
- **Default modules:** hr_hub, chat, video_call, kpi, rewards_store, weaves, dashboard
- **Required slots:** team_size, primary_use_case
- **Industry hints:** human resources, people operations, talent, hr
- **Customisable fields:** company_name, employee_names, department_names, role_names, leave_types, status_labels
- **Variants:** hr_management (default), hr_management_recruiting, hr_management_onboarding

## project_mgmt -- Project Management (render_key: project_mgmt)

- **Entity type:** project
- **Default modules:** projects, chat, video_call, kpi, dashboard, announcements
- **Required slots:** project_count, team_size
- **Industry hints:** project management, consulting, delivery, implementation, PMO
- **Customisable fields:** company_name, project_names, team_names, milestone_labels, status_labels
- **Variants:** project_management (default), project_management_client_delivery, project_management_creative

## ticketing -- Ticketing Tool (render_key: ticketing)

- **Entity type:** ticket
- **Default modules:** tickets, chat, video_call, kpi, dashboard, announcements
- **Required slots:** primary_use_case, queue_type
- **Industry hints:** help desk, support tickets, service desk, incident management
- **Customisable fields:** company_name, queue_names, ticket_categories, status_labels, priority_labels
- **Variants:** ticketing (default), ticketing_customer_support, ticketing_facilities

## finance -- Finance (render_key: project_mgmt)

- **Entity type:** transaction
- **Default modules:** weaves, dashboard, notifications
- **Required slots:** primary_use_case
- **Industry hints:** accounting, budgeting, financial management, invoicing
- **Customisable fields:** company_name, account_names, budget_categories, currency_label
- **Variants:** finance (default), finance_enterprise, finance_real_estate

## marketing -- Marketing (render_key: project_mgmt)

- **Entity type:** campaign
- **Default modules:** projects, weaves, chat, video_call, kpi, dashboard
- **Required slots:** primary_use_case, team_size
- **Industry hints:** marketing campaigns, content marketing, digital marketing, lead generation
- **Customisable fields:** company_name, campaign_names, channel_names, status_labels
- **Variants:** marketing (default), marketing_content, marketing_events

## sales -- Sales (render_key: project_mgmt)

- **Entity type:** lead
- **Default modules:** projects, weaves, chat, video_call, kpi, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** CRM, sales pipeline, lead tracker, account management
- **Customisable fields:** company_name, stage_names, product_names, account_names, status_labels
- **Variants:** sales (default), sales_brokerage, sales_wholesale

## healthcare -- Healthcare (render_key: ticketing)

- **Entity type:** patient
- **Default modules:** tickets, chat, video_call, weaves, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** medical records, patient management, clinic management, hospital system
- **Customisable fields:** company_name, department_names, provider_names, appointment_types, status_labels
- **Variants:** healthcare_hospital (default), healthcare_clinic, healthcare_pharma

## legal_services -- Legal Services (render_key: ticketing)

- **Entity type:** case
- **Default modules:** tickets, chat, video_call, weaves, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** law firm, case management, legal operations, litigation management
- **Customisable fields:** company_name, practice_area_names, attorney_names, case_types, status_labels
- **Variants:** legal_litigation_firm (default), legal_corporate_counsel, legal_compliance_office

## construction -- Construction (render_key: project_mgmt)

- **Entity type:** site
- **Default modules:** projects, chat, video_call, kpi, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** construction management, site management, facilities management
- **Customisable fields:** company_name, site_names, project_names, status_labels
- **Variants:** construction_general_contractor (default), construction_infrastructure, construction_residential

## real_estate -- Real Estate (render_key: project_mgmt)

- **Entity type:** listing
- **Default modules:** projects, chat, video_call, kpi, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** real estate management, property management, listing management, leasing
- **Customisable fields:** company_name, property_names, unit_names, tenant_names, status_labels
- **Variants:** real_estate_property_mgmt (default), real_estate_brokerage, real_estate_commercial

## education -- Education (render_key: project_mgmt)

- **Entity type:** course
- **Default modules:** projects, weaves, chat, video_call, kpi, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** e-learning, LMS, course management, student management
- **Customisable fields:** company_name, course_names, instructor_names, subject_names, status_labels
- **Variants:** education_k12 (default), education_university, education_edtech

## all_microservices -- All Microservices (render_key: all_microservices)

- **Entity type:** work
- **Default modules:** hr_hub, tickets, projects, weaves, chat, video_call, kpi, dashboard, announcements, calendar, smart_vault, rewards_store
- **Required slots:** primary_use_case
- **Industry hints:** all in one, complete solution, full platform, enterprise suite
- **Customisable fields:** company_name, primary_use_case, department_names, status_labels
- **Variants:** all_microservices_enterprise_saas (default), all_microservices_ecommerce, all_microservices_fintech

## generic -- Custom Workspace (render_key: generic)

- **Entity type:** work
- **Default modules:** tickets, dashboard
- **Required slots:** primary_use_case
- **Industry hints:** custom, general, misc, other
- **Customisable fields:** company_name, primary_use_case
- **Variants:** generic_small_business (default), generic_consulting, generic_nonprofit
