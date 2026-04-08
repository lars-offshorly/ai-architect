from __future__ import annotations

import copy

# ---------------------------------------------------------------------------
# ALL_FEATURE_FLAGS
# Seeded verbatim from docs/api-mocks.json orchestration.GET./feature_flags.
# All isEnabled values are set to False — resolve_flags.py enables them per bundle.
# Keys are flag names (str) for fast lookup; id and module are preserved.
# ---------------------------------------------------------------------------

ALL_FEATURE_FLAGS: list[dict] = [
    {
        "id": 111,
        "name": "activity-feed-announcement-popup",
        "description": "activity-feed-announcement-popup",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 180,
        "name": "activity-feed-announcement-read-all",
        "description": "activity-feed-announcement-read-all",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 113,
        "name": "activity-feed-announcement-repeat",
        "description": "activity-feed-announcement-repeat",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 178,
        "name": "activity-feed-announcement-rules",
        "description": "activity-feed-announcement-rules",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 114,
        "name": "activity-feed-announcement-share-by-email",
        "description": "activity-feed-announcement-share-by-email",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 147,
        "name": "activity-feed-filter-calendar",
        "description": "activity-feed-filter-calendar",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 148,
        "name": "activity-feed-filter-dashboard",
        "description": "activity-feed-filter-dashboard",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 149,
        "name": "activity-feed-filter-hrhub",
        "description": "activity-feed-filter-hrhub",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 150,
        "name": "activity-feed-filter-tickets",
        "description": "activity-feed-filter-tickets",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 151,
        "name": "activity-feed-filter-todo",
        "description": "activity-feed-filter-todo",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 152,
        "name": "activity-feed-filter-weaves",
        "description": "activity-feed-filter-weaves",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 74,
        "name": "activity-feed-module",
        "description": "Activity Feed Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 185,
        "name": "activity-feed-module-scheduled-announcements",
        "description": "activity-feed-module-scheduled-announcements",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 137,
        "name": "activity-feed-nav-notification",
        "description": "activity-feed-nav-notification",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 138,
        "name": "activity-feed-nav-search",
        "description": "activity-feed-nav-search",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 139,
        "name": "activity-feed-nav-settings",
        "description": "activity-feed-nav-settings",
        "isEnabled": False,
        "module": "Notifications",
    },
    {
        "id": 131,
        "name": "activity-feed-notification",
        "description": "activity-feed-notification",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 110,
        "name": "activity-feed-notifications-toast",
        "description": "Activity Feed Notifications Toast",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 125,
        "name": "activity-feed-unread-count",
        "description": "activity-feed-unread-count",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 187,
        "name": "ai-toolkit-module",
        "description": "AI Toolkit Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 181,
        "name": "app-file-download-dialog",
        "description": "app-file-download-dialog",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 90,
        "name": "app-homepage-hr-hub",
        "description": "app-homepage-hr-hub",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 83,
        "name": "autologout-by-ttl",
        "description": "Auto Logout by TTL",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 109,
        "name": "calendar_module",
        "description": "Calendar module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 92,
        "name": "chat-bot",
        "description": "chat-bot",
        "isEnabled": False,
        "module": "AI Chat Bot",
    },
    {
        "id": 107,
        "name": "chat-float",
        "description": "Chat boxes that floats on right bottom",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 5,
        "name": "chat-module",
        "description": "Chat Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 130,
        "name": "chat-notification",
        "description": "chat-notification",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 124,
        "name": "chat-unread-count",
        "description": "chat-unread-count",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 157,
        "name": "chatbot-module",
        "description": "Chatbot Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 2,
        "name": "dashboard-module",
        "description": "Dashboard Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 177,
        "name": "docbot-module",
        "description": "AI Document Verification Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 40,
        "name": "hrhub-admin-hangout",
        "description": "HR Hub Admin Hangout",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 179,
        "name": "hrhub-employee-handbook",
        "description": "HRHUB Employee Handbook",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 38,
        "name": "hrhub-employee-movement",
        "description": "Hr Hub Employee Movement",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 37,
        "name": "hrhub-live-feed",
        "description": "Hr Hub Live Feed",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 3,
        "name": "hrhub-module",
        "description": "Hr Hub Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 42,
        "name": "hrhub-my-tasks",
        "description": "Hr Hub My Tasks",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 120,
        "name": "hrhub-onboarding",
        "description": "Enable Onboarding form",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 174,
        "name": "hrhub-overview",
        "description": "HR Hub Overview",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 39,
        "name": "hrhub-tasks",
        "description": "Hr Hub Tasks",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 207,
        "name": "kpi-advanced-type",
        "description": "kpi-advanced-type",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 123,
        "name": "kpi-module",
        "description": "KPI Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 188,
        "name": "menu-ai-toolkit-nav",
        "description": "Menu Ai Toolkit Nav",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 65,
        "name": "menu-calendar-nav",
        "description": "Menu Calendar Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 59,
        "name": "menu-dashboard-nav",
        "description": "Menu Dashboard Nav",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 58,
        "name": "menu-favorites-nav",
        "description": "Menu Favorites Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 71,
        "name": "menu-games-nav",
        "description": "Menu Games Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 62,
        "name": "menu-kanban-nav",
        "description": "Menu Kanban Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 60,
        "name": "menu-knit-show-nav",
        "description": "Menu Knit Show Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 61,
        "name": "menu-know-your-knit-nav",
        "description": "Menu Know Your Knit Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 70,
        "name": "menu-kpi-nav",
        "description": "Menu KPI Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 72,
        "name": "menu-reports-nav",
        "description": "Menu Reports Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 63,
        "name": "menu-timeline-nav",
        "description": "Menu Timeline Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 66,
        "name": "menu-todos-nav",
        "description": "Menu Todos Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 64,
        "name": "menu-whiteboard-nav",
        "description": "Menu Whiteboard Navigation",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 132,
        "name": "profile-module",
        "description": "Knit user profile module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 7,
        "name": "projects-module",
        "description": "Projects Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 135,
        "name": "push-notification",
        "description": "push-notification",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 198,
        "name": "rewards-module",
        "description": "Rewards Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 54,
        "name": "search-toolbar",
        "description": "Search Toolbar on the Header",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 55,
        "name": "sidebar-help-nav",
        "description": "Help navigation on the right sidebar",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 57,
        "name": "sidebar-invite-user-nav",
        "description": "Invite user navigation on the right sidebar",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 56,
        "name": "sidebar-notification-nav",
        "description": "Notification navigation on the right sidebar",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 6,
        "name": "tickets-module",
        "description": "Tickets Module",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 206,
        "name": "tickets-unread-count",
        "description": "tickets-unread-count",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 169,
        "name": "use-office-timezone",
        "description": "use-office-timezone",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 192,
        "name": "user-online-status",
        "description": "user-online-status",
        "isEnabled": False,
        "module": "Global",
    },
    {
        "id": 4,
        "name": "weaves-module",
        "description": "Weaves Module",
        "isEnabled": False,
        "module": "Global",
    },
]

# Fast-lookup index: flag name → entry dict (same object as in ALL_FEATURE_FLAGS)
_FLAG_INDEX: dict[str, dict] = {f["name"]: f for f in ALL_FEATURE_FLAGS}


# ---------------------------------------------------------------------------
# BUNDLE_REGISTRY
# 9 bundles: project_mgmt, ticketing, hr_hub, weaves,
#            chat, video_call, smart_vault, announcements, calendar
#
# flags            — feature flag names this bundle enables
# permission_services — permission service names to include
# landing_pages    — user landing page configs (shape from /users/me)
# compatible_addons — addon bundle keys auto-included
# default_metrics  — metric slugs from METRICS_CATALOG
# ---------------------------------------------------------------------------

BUNDLE_REGISTRY: dict[str, dict] = {
    "project_mgmt": {
        "flags": [
            "projects-module",
            "dashboard-module",
            "menu-dashboard-nav",
            "kpi-module",
            "menu-kpi-nav",
            "push-notification",
            "activity-feed-module",
            "activity-feed-notification",
            "activity-feed-notifications-toast",
            "activity-feed-unread-count",
            "activity-feed-filter-dashboard",
            "activity-feed-filter-todo",
            "profile-module",
        ],
        "permission_services": ["projects", "kpi", "notifications"],
        "landing_pages": [
            {
                "id": 108,
                "module": "Projects",
                "selectionAutoShow": False,
                "default": "List",
                "showTutorial": True,
            },
            {
                "id": 311,
                "module": "Dashboard",
                "selectionAutoShow": True,
                "default": "Dashboard",
                "showTutorial": False,
            },
        ],
        "compatible_addons": ["chat", "video_call", "smart_vault", "announcements"],
        "default_metrics": [
            "on_time_delivery_rate",
            "project_health_status",
            "cycle_time",
            "capacity_utilization",
        ],
    },
    "ticketing": {
        "flags": [
            "tickets-module",
            "tickets-unread-count",
            "dashboard-module",
            "menu-dashboard-nav",
            "kpi-module",
            "menu-kpi-nav",
            "push-notification",
            "activity-feed-module",
            "activity-feed-notification",
            "activity-feed-notifications-toast",
            "activity-feed-unread-count",
            "activity-feed-filter-tickets",
            "profile-module",
        ],
        "permission_services": ["tickets", "kpi", "notifications"],
        "landing_pages": [
            {
                "id": 321,
                "module": "Tickets",
                "selectionAutoShow": True,
                "default": "Ticket",
                "showTutorial": True,
            },
            {
                "id": 311,
                "module": "Dashboard",
                "selectionAutoShow": True,
                "default": "Dashboard",
                "showTutorial": False,
            },
        ],
        "compatible_addons": ["chat", "announcements"],
        "default_metrics": [
            "avg_resolution_time",
            "sla_compliance",
            "active_work_items",
            "cycle_time",
        ],
    },
    "hr_management": {
        "flags": [
            "hrhub-module",
            "hrhub-overview",
            "hrhub-employee-movement",
            "hrhub-onboarding",
            "hrhub-employee-handbook",
            "hrhub-admin-hangout",
            "hrhub-tasks",
            "hrhub-my-tasks",
            "hrhub-live-feed",
            "app-homepage-hr-hub",
            "dashboard-module",
            "menu-dashboard-nav",
            "kpi-module",
            "menu-kpi-nav",
            "push-notification",
            "activity-feed-module",
            "activity-feed-notification",
            "activity-feed-notifications-toast",
            "activity-feed-unread-count",
            "activity-feed-filter-hrhub",
            "profile-module",
            "rewards-module",
        ],
        "permission_services": ["hr_hub", "kpi", "notifications"],
        "landing_pages": [
            {
                "id": 311,
                "module": "Dashboard",
                "selectionAutoShow": True,
                "default": "Dashboard",
                "showTutorial": False,
            },
        ],
        "compatible_addons": ["chat", "weaves", "announcements"],
        "default_metrics": [
            "active_headcount",
            "attendance_rate",
            "leave_balance_utilization",
            "capacity_utilization",
        ],
    },
    "weaves": {
        "flags": [
            "weaves-module",
            "activity-feed-filter-weaves",
            "kpi-advanced-type",
        ],
        "permission_services": ["weaves"],
        "landing_pages": [
            {
                "id": 6,
                "module": "Weaves",
                "selectionAutoShow": False,
                "default": "Weave",
                "showTutorial": False,
            },
        ],
        "compatible_addons": [],
        "default_metrics": [],
    },
    # --- Addons ---
    "chat": {
        "flags": [
            "chat-module",
            "chat-float",
            "chat-notification",
            "chat-unread-count",
        ],
        "permission_services": [],
        "landing_pages": [],
        "compatible_addons": [],
        "default_metrics": [],
    },
    "video_call": {
        # No feature flag in the JSON — controlled elsewhere (known gap)
        "flags": [],
        "permission_services": [],
        "landing_pages": [],
        "compatible_addons": [],
        "default_metrics": [],
    },
    "smart_vault": {
        "flags": [
            "ai-toolkit-module",
            "menu-ai-toolkit-nav",
        ],
        "permission_services": ["ai_toolkit"],
        "landing_pages": [],
        "compatible_addons": [],
        "default_metrics": [],
    },
    "announcements": {
        "flags": [
            "activity-feed-announcement-popup",
            "activity-feed-announcement-read-all",
            "activity-feed-module-scheduled-announcements",
            "activity-feed-announcement-rules",
        ],
        "permission_services": ["notifications"],
        "landing_pages": [],
        "compatible_addons": [],
        "default_metrics": [],
    },
    "calendar": {
        "flags": [
            "calendar_module",
            "menu-calendar-nav",
            "activity-feed-filter-calendar",
        ],
        "permission_services": ["calendar"],
        "landing_pages": [],
        "compatible_addons": [],
        "default_metrics": [],
    },
    "generic": {
        "flags": [],
        "permission_services": [],
        "landing_pages": [],
        "compatible_addons": [],
        "default_metrics": [],
    },
}


# ---------------------------------------------------------------------------
# METRICS_CATALOG
# 17 KPI metrics keyed by slug.
# value types: "percentage" | "count" | "duration" | "status" | "ratio"
# ---------------------------------------------------------------------------

METRICS_CATALOG: dict[str, dict] = {
    # Delivery performance
    "on_time_delivery_rate": {
        "key": "on_time_delivery_rate",
        "label": "On-time Delivery Rate",
        "type": "percentage",
        "source_service": "projects",
    },
    "project_health_status": {
        "key": "project_health_status",
        "label": "Project Health Status",
        "type": "status",
        "source_service": "projects",
    },
    "avg_case_duration": {
        "key": "avg_case_duration",
        "label": "Avg. Case Duration",
        "type": "duration",
        "source_service": "projects",
    },
    "upcoming_deadlines": {
        "key": "upcoming_deadlines",
        "label": "Upcoming Deadlines",
        "type": "count",
        "source_service": "projects",
    },
    # Operational efficiency
    "avg_resolution_time": {
        "key": "avg_resolution_time",
        "label": "Avg. Resolution Time",
        "type": "duration",
        "source_service": "tickets",
    },
    "cycle_time": {
        "key": "cycle_time",
        "label": "Cycle Time",
        "type": "duration",
        "source_service": "projects",
    },
    "sla_compliance": {
        "key": "sla_compliance",
        "label": "SLA Compliance",
        "type": "percentage",
        "source_service": "tickets",
    },
    "billable_vs_nonbillable": {
        "key": "billable_vs_nonbillable",
        "label": "Billable vs Non-Billable",
        "type": "ratio",
        "source_service": "projects",
    },
    "workload_distribution": {
        "key": "workload_distribution",
        "label": "Workload Distribution",
        "type": "ratio",
        "source_service": "hr_hub",
    },
    # Team productivity
    "capacity_utilization": {
        "key": "capacity_utilization",
        "label": "Capacity Utilization",
        "type": "percentage",
        "source_service": "hr_hub",
    },
    "active_work_items": {
        "key": "active_work_items",
        "label": "Active Work Items",
        "type": "count",
        "source_service": "projects",
    },
    "planned_vs_actual": {
        "key": "planned_vs_actual",
        "label": "Planned vs Actual",
        "type": "ratio",
        "source_service": "projects",
    },
    # HR metrics
    "active_headcount": {
        "key": "active_headcount",
        "label": "Active Headcount",
        "type": "count",
        "source_service": "hr_hub",
    },
    "attendance_rate": {
        "key": "attendance_rate",
        "label": "Attendance Rate",
        "type": "percentage",
        "source_service": "hr_hub",
    },
    "leave_balance_utilization": {
        "key": "leave_balance_utilization",
        "label": "Leave Balance Utilization",
        "type": "percentage",
        "source_service": "hr_hub",
    },
    "cases_per_attorney": {
        "key": "cases_per_attorney",
        "label": "Cases per Attorney",
        "type": "ratio",
        "source_service": "projects",
    },
    "case_load_distribution": {
        "key": "case_load_distribution",
        "label": "Case Load Distribution",
        "type": "ratio",
        "source_service": "hr_hub",
    },
}


def get_flag_snapshot() -> list[dict]:
    """Return a deep copy of ALL_FEATURE_FLAGS with all flags disabled.
    Callers mutate this copy — the source list is never modified."""
    return copy.deepcopy(ALL_FEATURE_FLAGS)
