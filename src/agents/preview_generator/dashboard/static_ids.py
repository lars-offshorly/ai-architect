"""Mapping of bundle keys to canonical dashboard IDs and widget IDs.

Derived from dashboard_template_static_ids.json.
"""

# Mapping of dashboard names to their external IDs
DASHBOARD_IDS = {
    "Tickets Dashboard": 57,
    "Queue Dashboard": 56,
    "Projects Dashboard": 54,
    "Personal Dashboard": 53,
    "Attendance Dashboard": 51,
    "Leaves Dashboard": 52,
    "Home Dashboard": 62,
    "HR Admin Dashboard": 64,
    "KNIT Tickets Dashboard": 48,
}

# Mapping of bundle keys (and render keys) to dashboard names
BUNDLE_TO_DASHBOARD = {
    "ticketing": "Tickets Dashboard",
    "project_mgmt": "Projects Dashboard",
    "hr_hub": "HR Admin Dashboard",
    "hr_management": "HR Admin Dashboard",
    "healthcare": "Tickets Dashboard",
    "legal_services": "Tickets Dashboard",
    "construction": "Projects Dashboard",
    "real_estate": "Projects Dashboard",
    "education": "Projects Dashboard",
    "all_microservices": "Home Dashboard",
    "generic": "Tickets Dashboard",
    # Legacy/Fallback mappings
    "project_management": "Projects Dashboard",
    "construction_real_estate": "Projects Dashboard",
}

# Detailed widget templates from the JSON
WIDGET_TEMPLATES = {
    57: [ # Tickets Dashboard
        {"external_id": 363, "name": "Tickets per Queue"},
        {"external_id": 362, "name": "Tickets per Assignee"},
        {"external_id": 361, "name": "New Tickets"},
        {"external_id": 360, "name": "Reopen Tickets"},
        {"external_id": 359, "name": "Tickets per Status per Week"},
        {"external_id": 358, "name": "Tickets per Type"},
        {"external_id": 357, "name": "Tickets on Hold"},
        {"external_id": 356, "name": "Closed Tickets"},
    ],
    54: [ # Projects Dashboard
        {"external_id": 329, "name": "New Tasks"},
        {"external_id": 328, "name": "Projects per Priority"},
        {"external_id": 327, "name": "Resolved Tasks"},
        {"external_id": 326, "name": "Tasks per Priority"},
        {"external_id": 325, "name": "Projects per Status"},
        {"external_id": 324, "name": "Closed Tasks"},
        {"external_id": 323, "name": "Tasks per Status"},
        {"external_id": 322, "name": "Pending Projects"},
    ],
    62: [ # Home Dashboard
        {"external_id": 438, "name": "Tasks per Priority"},
        {"external_id": 437, "name": "My Tickets per Priority"},
        {"external_id": 436, "name": "My Tasks"},
        {"external_id": 435, "name": "My Tickets"},
        {"external_id": 434, "name": "Attendance Widget"},
    ],
    # Add others if needed, but Group B only needs 57, 54, 62
}
