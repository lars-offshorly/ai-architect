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
    "hr_management": "HR Admin Dashboard",
    "healthcare": "Tickets Dashboard",
    "legal_services": "Tickets Dashboard",
    "construction": "Projects Dashboard",
    "real_estate": "Projects Dashboard",
    "education": "Projects Dashboard",
    "all_microservices": "Home Dashboard",
    "generic": "Tickets Dashboard",
    "marketing": "Projects Dashboard",
    "sales": "Projects Dashboard",
    "finance": "Projects Dashboard",
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
    56: [ # Queue Dashboard
        {"external_id": 355, "name": "Reopen Tickets"},
        {"external_id": 354, "name": "Tickets on Hold"},
        {"external_id": 353, "name": "Tickets per Priority"},
        {"external_id": 352, "name": "Tickets per Status per Week"},
        {"external_id": 351, "name": "Tickets per Impact Level"},
        {"external_id": 350, "name": "Closed Tickets"},
        {"external_id": 349, "name": "New Tickets"},
        {"external_id": 348, "name": "Tickets per Assignee"},
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
    53: [ # Personal Dashboard
        {"external_id": 313, "name": "Leaves Taken for the Current Month"},
        {"external_id": 312, "name": "Lates for the Current Month"},
        {"external_id": 311, "name": "Absences for the Current Month"},
        {"external_id": 310, "name": "Available Vacation Leave Credits"},
        {"external_id": 309, "name": "Attendance Widget"},
    ],
    51: [ # Attendance Dashboard
        {"external_id": 300, "name": "Weekly Late for the Current Month"},
        {"external_id": 299, "name": "Weekly Absences for the Current Month"},
        {"external_id": 298, "name": "Total Breaks for the Current Month"},
        {"external_id": 297, "name": "Weekly Overbreak for the Current Month"},
        {"external_id": 296, "name": "Weekly Undertime for the Current Month"},
        {"external_id": 295, "name": "Total Undertime for the Current Month"},
        {"external_id": 294, "name": "Total Late for the Current Month"},
        {"external_id": 293, "name": "Total Absences for the Current Month"},
    ],
    52: [ # Leaves Dashboard
        {"external_id": 306, "name": "Available Leave Credits"},
        {"external_id": 305, "name": "Leave Credits by Type"},
        {"external_id": 304, "name": "Leaves Taken"},
        {"external_id": 303, "name": "Available Sick Leaves"},
        {"external_id": 302, "name": "Leaves Taken by Type"},
        {"external_id": 301, "name": "Available Vacation Leaves"},
    ],
    62: [ # Home Dashboard
        {"external_id": 438, "name": "Tasks per Priority"},
        {"external_id": 437, "name": "My Tickets per Priority"},
        {"external_id": 436, "name": "My Tasks"},
        {"external_id": 435, "name": "My Tickets"},
        {"external_id": 434, "name": "Attendance Widget"},
    ],
    64: [ # HR Admin Dashboard
        {"external_id": 460, "name": "Employee per Age Bracket"},
        {"external_id": 459, "name": "New Hires"},
        {"external_id": 458, "name": "New Hire per Department"},
        {"external_id": 457, "name": "Headcount"},
        {"external_id": 456, "name": "Attrition Rate"},
        {"external_id": 455, "name": "Employee Growth Rate"},
        {"external_id": 454, "name": "Salary Change Rate"},
        {"external_id": 453, "name": "Separated Employees"},
        {"external_id": 452, "name": "Employee per Employment Status"},
        {"external_id": 451, "name": "Employee per Employment Group"},
        {"external_id": 450, "name": "Employees per Gender"},
        {"external_id": 449, "name": "Absenteeism Rate"},
        {"external_id": 448, "name": "Accession Rate"},
        {"external_id": 447, "name": "Average Salary"},
        {"external_id": 446, "name": "90 Day Quit Rate"},
    ],
    48: [ # KNIT Tickets Dashboard
        {"external_id": 423, "name": "Ticket Level (Knit Details)"},
        {"external_id": 424, "name": "Aging Duration"},
        {"external_id": 425, "name": "Closure Hours"},
        {"external_id": 426, "name": "Aging Rate"},
        {"external_id": 427, "name": "Resolution Duration"},
        {"external_id": 428, "name": "Closure Rate"},
        {"external_id": 429, "name": "Resolution Rate"},
        {"external_id": 430, "name": "Tickets"},
    ],
}
