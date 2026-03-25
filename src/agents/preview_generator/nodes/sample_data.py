"""Pipeline node: generates realistic sample data stores for the selected bundle."""

from __future__ import annotations

import itertools
from datetime import date, timedelta

from core.logging import get_logger

from ..schemas import UserContext
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Name + role pools — deterministic, no randomness (seed by index)
# ---------------------------------------------------------------------------

_DEFAULT_NAMES = [
    "Maria Santos",
    "Carlos Mendez",
    "Ana Reyes",
    "James Okafor",
    "Sofia Lim",
    "David Park",
    "Priya Nair",
    "Lucas Silva",
    "Amara Diallo",
    "Noah Fischer",
]

_LEGAL_ROLES = [
    "Senior Attorney",
    "Associate Attorney",
    "Paralegal",
    "Legal Analyst",
    "Case Manager",
    "Litigation Support Specialist",
]
_TECH_ROLES = [
    "Engineering Manager",
    "Senior Developer",
    "QA Engineer",
    "DevOps Engineer",
    "Product Manager",
    "UX Designer",
]
_HR_ROLES = [
    "HR Manager",
    "Talent Acquisition Specialist",
    "HR Coordinator",
    "People Operations Lead",
    "Benefits Administrator",
]
_GENERAL_ROLES = [
    "Project Manager",
    "Team Lead",
    "Operations Manager",
    "Business Analyst",
    "Coordinator",
    "Senior Associate",
]
_SUPPORT_ROLES = [
    "Support Manager",
    "Help Desk Specialist",
    "IT Support Engineer",
    "Customer Success Rep",
    "Tier 2 Support Agent",
]

_DEPARTMENTS_BY_BUNDLE = {
    "project_mgmt": ["Operations", "Product", "Engineering", "Strategy"],
    "ticketing": ["IT Support", "Customer Success", "Operations", "Engineering"],
    "hr_hub": ["Human Resources", "Talent & Culture", "People Ops", "Finance"],
    "weaves": ["Operations", "Product", "Leadership", "Strategy"],
}

# Project name templates keyed by work_type
_PROJECT_NAMES = {
    "sprint": [
        "Mobile App MVP — Sprint {n}",
        "Backend API Overhaul — Sprint {n}",
        "Dashboard Redesign — Sprint {n}",
        "Platform Migration — Sprint {n}",
    ],
    "litigation": [
        "{client} v. {company} — Discovery",
        "{company} Compliance Review — Q{q}",
        "Regulatory Filing — {company}",
        "Settlement Negotiations — Matter #{n}",
    ],
    "waterfall": [
        "Platform Migration — Phase {n}",
        "Infrastructure Rollout — Phase {n}",
        "Enterprise Deployment — Q{q}",
        "System Integration — Milestone {n}",
    ],
    "support_request": [
        "IT Infrastructure Audit",
        "Service Desk Consolidation",
        "SLA Review — Q{q}",
        "Helpdesk Platform Migration",
    ],
}

_TICKET_TYPES_BY_BUNDLE = {
    "ticketing": [
        ("Bug", "High"),
        ("Feature Request", "Medium"),
        ("Bug", "Critical"),
        ("Improvement", "Low"),
        ("Bug", "Medium"),
        ("Access Request", "Medium"),
    ],
    "hr_hub": [
        ("Onboarding", "High"),
        ("IT Setup", "Medium"),
        ("Leave Request", "Low"),
        ("Equipment Request", "Medium"),
        ("Policy Query", "Low"),
    ],
}

_TICKET_TITLES_BY_BUNDLE = {
    "ticketing": [
        "Login page not loading on mobile",
        "Export to CSV fails for large datasets",
        "Notification emails not delivered",
        "Dashboard widget shows incorrect totals",
        "User permissions not applying on new accounts",
        "Search returns empty results intermittently",
    ],
    "hr_hub": [
        "New hire onboarding — Week 1 checklist",
        "Laptop provisioning for {name}",
        "Annual leave request — {name}",
        "Access credentials not received",
        "Benefits enrollment query — {name}",
    ],
}

_WEAVE_TITLES = [
    "Q1 Operations Review",
    "Team Retrospective — {month}",
    "Stakeholder Update — {project}",
    "Sprint Planning Notes",
    "Risk Assessment Summary",
]

_STATUSES_PROJECT = [
    "In Progress",
    "In Progress",
    "On Hold",
    "Completed",
    "In Progress",
]
_STATUSES_TICKET = ["Open", "In Progress", "Open", "Resolved", "Open", "In Progress"]

_MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _name_pool(user_context: UserContext | None) -> list[str]:
    """People from conversation first, padded with the default pool."""
    if user_context and user_context.people:
        extracted = [p.name for p in user_context.people if p.name]
        combined = extracted + [n for n in _DEFAULT_NAMES if n not in extracted]
        return combined[:10]
    return list(_DEFAULT_NAMES)


def _role_pool(bundle_key: str, user_context: UserContext | None) -> list[str]:
    if user_context and user_context.industry_detail:
        detail = user_context.industry_detail.lower()
        if "legal" in detail or "law" in detail:
            return _LEGAL_ROLES
        if "hr" in detail or "human" in detail:
            return _HR_ROLES
        if "software" in detail or "tech" in detail:
            return _TECH_ROLES
        if "support" in detail or "desk" in detail:
            return _SUPPORT_ROLES
    bundle_map = {
        "ticketing": _SUPPORT_ROLES,
        "hr_hub": _HR_ROLES,
    }
    return bundle_map.get(bundle_key, _GENERAL_ROLES)


def _dept_pool(bundle_key: str) -> list[str]:
    return _DEPARTMENTS_BY_BUNDLE.get(
        bundle_key, ["Operations", "Product", "Engineering"]
    )


def _base_date(offset_days: int) -> str:
    return (date.today() - timedelta(days=offset_days)).isoformat()


def _future_date(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


def _work_type(user_context: UserContext | None) -> str:
    if user_context and user_context.work_items:
        return user_context.work_items[0].work_type
    return "waterfall"


def _company_slug(user_context: UserContext | None) -> str:
    if user_context and user_context.company_name:
        return user_context.company_name.split()[0]
    return "Apex"


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def _build_employees(
    bundle_key: str,
    user_context: UserContext | None,
    count: int = 8,
) -> list[dict]:
    names = _name_pool(user_context)
    roles = _role_pool(bundle_key, user_context)
    depts = _dept_pool(bundle_key)

    role_cycle = itertools.cycle(roles)
    dept_cycle = itertools.cycle(depts)

    employees = []
    for i, name in enumerate(names[:count]):
        first = name.split()[0].lower()
        last = name.split()[-1].lower() if len(name.split()) > 1 else "user"
        company = _company_slug(user_context).lower()
        employees.append(
            {
                "id": i + 1,
                "name": name,
                "role": next(role_cycle),
                "department": next(dept_cycle),
                "email": f"{first}.{last}@{company}.com",
                "avatar": None,
                "is_active": True,
            }
        )
    return employees


def _build_projects(
    _bundle_key: str,
    user_context: UserContext | None,
    employees: list[dict],
    count: int = 5,
) -> list[dict]:
    work_type = _work_type(user_context)
    company = _company_slug(user_context)
    templates = _PROJECT_NAMES.get(work_type, _PROJECT_NAMES["waterfall"])

    projects = []
    for i in range(count):
        tmpl = templates[i % len(templates)]
        name = tmpl.format(
            n=i + 1,
            q=((i % 4) + 1),
            client="Martinez",
            company=company,
        )
        lead = employees[i % len(employees)]["name"] if employees else "Unassigned"
        projects.append(
            {
                "id": i + 1,
                "name": name,
                "status": _STATUSES_PROJECT[i % len(_STATUSES_PROJECT)],
                "lead": lead,
                "team_size": 3 + (i % 4),
                "start_date": _base_date(60 - i * 10),
                "due_date": _future_date(30 + i * 14),
                "completion_pct": [68, 42, 15, 100, 30][i % 5],
            }
        )
    return projects


def _build_tickets(
    bundle_key: str,
    _user_context: UserContext | None,
    employees: list[dict],
    count: int = 6,
) -> list[dict]:
    type_priority_pool = _TICKET_TYPES_BY_BUNDLE.get(
        bundle_key, _TICKET_TYPES_BY_BUNDLE["ticketing"]
    )
    title_pool = _TICKET_TITLES_BY_BUNDLE.get(
        bundle_key, _TICKET_TITLES_BY_BUNDLE["ticketing"]
    )

    tickets = []
    for i in range(count):
        t_type, priority = type_priority_pool[i % len(type_priority_pool)]
        raw_title = title_pool[i % len(title_pool)]
        name = employees[i % len(employees)]["name"] if employees else "System"
        title = raw_title.format(name=name.split()[0])

        tickets.append(
            {
                "id": 100 + i + 1,
                "title": title,
                "type": t_type,
                "status": _STATUSES_TICKET[i % len(_STATUSES_TICKET)],
                "priority": priority,
                "requester": (
                    employees[(i + 1) % len(employees)]["name"] if employees else "User"
                ),
                "assignee": (
                    employees[i % len(employees)]["name"] if employees else "Unassigned"
                ),
                "created_at": _base_date(i * 3 + 1),
            }
        )
    return tickets


def _build_weaves(
    _user_context: UserContext | None,
    employees: list[dict],
    projects: list[dict],
    count: int = 4,
) -> list[dict]:
    weaves = []
    for i in range(count):
        tmpl = _WEAVE_TITLES[i % len(_WEAVE_TITLES)]
        project_name = projects[i % len(projects)]["name"] if projects else "Project"
        title = tmpl.format(
            month=_MONTHS[i % 12],
            project=project_name.split("—")[0].strip(),
        )
        creator = employees[i % len(employees)]["name"] if employees else "Admin"
        participants = (
            [e["name"] for e in employees[1:3]] if len(employees) >= 3 else []
        )
        weaves.append(
            {
                "id": i + 1,
                "title": title,
                "created_by": creator,
                "participants": participants,
                "status": "Active" if i % 3 != 2 else "Archived",
                "created_at": _base_date(i * 7 + 2),
            }
        )
    return weaves


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


def generate_sample_data(state: PreviewGeneratorState) -> dict:
    """Produce sample employees, projects, tickets, and weaves.

    Tier 1: uses bundle-aware pools + UserContext personalization.
    Tier 3: falls back to generic data (bundle_key treated as 'project_mgmt').
    Phase 2: Tier 2 will call an LLM for niche industry data generation.
    """
    bundle_key = state.bundle_key if state.data_tier == "tier_1" else "project_mgmt"
    ctx = state.user_context

    employees = _build_employees(bundle_key, ctx)
    projects = _build_projects(bundle_key, ctx, employees)
    tickets = _build_tickets(bundle_key, ctx, employees)
    weaves = _build_weaves(ctx, employees, projects)

    logger.info(
        "session=%s — generated employees=%d projects=%d"
        " tickets=%d weaves=%d (tier=%s)",
        state.session_id,
        len(employees),
        len(projects),
        len(tickets),
        len(weaves),
        state.data_tier,
    )

    return {
        "sample_employees": employees,
        "sample_projects": projects,
        "sample_tickets": tickets,
        "sample_weaves": weaves,
    }
