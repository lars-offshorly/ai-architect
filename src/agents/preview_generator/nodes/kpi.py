"""Pipeline node: builds KPI metric definitions for the selected bundle."""

from __future__ import annotations

import itertools
from datetime import date, timedelta

from core.logging import get_logger

from ..schemas import KpiMetric
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

_FALLBACK_SLUGS: list[str] = ["capacity_utilization", "active_work_items"]

# ---------------------------------------------------------------------------
# Sample values per metric type — deterministic, index-based
# ---------------------------------------------------------------------------

_SAMPLE_VALUES: dict[str, list[float | int | str]] = {
    "percentage": [87.5, 92.1, 78.4, 95.0, 83.2],
    "count": [142, 38, 217, 15, 67],
    "duration": [3.2, 1.8, 5.4, 2.1, 4.7],  # days
    "status": ["Healthy", "At Risk", "Healthy", "On Track", "Healthy"],
    "ratio": [0.72, 0.85, 0.61, 0.90, 0.78],
}

# Key phrase → extra metric slugs to append (Phase 1: keyword-driven boost)
_PHRASE_TO_METRIC: dict[str, str] = {
    "on time": "on_time_delivery_rate",
    "deadline": "upcoming_deadlines",
    "delivery": "on_time_delivery_rate",
    "resolution": "avg_resolution_time",
    "sla": "sla_compliance",
    "capacity": "capacity_utilization",
    "utilization": "capacity_utilization",
    "workload": "workload_distribution",
    "headcount": "active_headcount",
    "attendance": "attendance_rate",
    "billable": "billable_vs_nonbillable",
    "cycle time": "cycle_time",
    "case load": "case_load_distribution",
}

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
    "hr_management": ["Human Resources", "Talent & Culture", "People Ops", "Finance"],
    "weaves": ["Operations", "Product", "Leadership", "Strategy"],
}
_HR_QUEUE_NAMES = [
    "Onboarding Queue",
    "IT Setup Queue",
    "Leave Management Queue",
    "Equipment Requests Queue",
    "Policy & Compliance Queue",
]
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
    "hr_management": [
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
    "hr_management": [
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


def _pick_value(metric_type: str, index: int) -> float | int | str:
    pool = _SAMPLE_VALUES.get(metric_type, _SAMPLE_VALUES["count"])
    return pool[index % len(pool)]


def _resolve_default_slugs(state: PreviewGeneratorState, bundle_key: str) -> list[str]:
    catalog = state.catalog
    if catalog is None:
        return []
    bundle = catalog.get(bundle_key)
    if bundle is None:
        logger.warning(
            "session=%s — bundle_key=%r not in catalog, using fallbacks",
            state.session_id,
            bundle_key,
        )
        return []
    return bundle.metadata.kpis if bundle.metadata else []


def _collect_signal_boost_slugs(
    state: PreviewGeneratorState,
    metrics_catalog: dict[str, dict[str, object]],
    default_slugs: list[str],
) -> list[str]:
    if state.extraction_result is None:
        return []
    signal_boost_slugs: list[str] = []
    for metric in state.extraction_result.classification_signals.metrics:
        slug = metric if metric in metrics_catalog else _PHRASE_TO_METRIC.get(metric)
        if slug and slug not in default_slugs:
            signal_boost_slugs.append(slug)
    return signal_boost_slugs


def _collect_context_boost_slugs(
    state: PreviewGeneratorState,
    default_slugs: list[str],
) -> list[str]:
    if not state.user_context or not state.user_context.key_phrases:
        return []
    boost_slugs: list[str] = []
    for phrase in state.user_context.key_phrases:
        phrase_slug = _PHRASE_TO_METRIC.get(phrase)
        if phrase_slug and phrase_slug not in default_slugs:
            boost_slugs.append(phrase_slug)
    return boost_slugs


def _dedupe_valid_slugs(
    metrics_catalog: dict[str, dict[str, object]],
    *slug_lists: list[str],
) -> list[str]:
    all_slugs: list[str] = []
    seen: set[str] = set()
    for slug in [s for slugs in slug_lists for s in slugs]:
        if slug not in seen and slug in metrics_catalog:
            seen.add(slug)
            all_slugs.append(slug)
    return all_slugs


def _name_pool(state: PreviewGeneratorState) -> list[str]:
    if state.user_context and state.user_context.people:
        extracted = [person.name for person in state.user_context.people if person.name]
        combined = extracted + [
            name for name in _DEFAULT_NAMES if name not in extracted
        ]
        return combined[:10]
    return list(_DEFAULT_NAMES)


def _role_pool(state: PreviewGeneratorState, bundle_key: str) -> list[str]:
    if state.user_context and state.user_context.industry_detail:
        detail = state.user_context.industry_detail.lower()
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
        "hr_management": _HR_ROLES,
    }
    return bundle_map.get(bundle_key, _GENERAL_ROLES)


def _dept_pool(state: PreviewGeneratorState, bundle_key: str) -> list[str]:
    if state.user_context and state.user_context.teams:
        return [team.name for team in state.user_context.teams]
    branch_names = None
    if state.extraction_result:
        branch_names = (
            state.extraction_result.personalization_signals.branch_names or None
        )
    if branch_names:
        return branch_names
    return _DEPARTMENTS_BY_BUNDLE.get(
        bundle_key, ["Operations", "Product", "Engineering"]
    )


def _base_date(offset_days: int) -> str:
    return (date.today() - timedelta(days=offset_days)).isoformat()


def _future_date(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).isoformat()


def _work_type(state: PreviewGeneratorState) -> str:
    if state.user_context and state.user_context.work_items:
        return state.user_context.work_items[0].work_type
    return "waterfall"


def _company_slug(state: PreviewGeneratorState) -> str:
    if state.user_context and state.user_context.company_name:
        return state.user_context.company_name.split()[0]
    return "Apex"


def _build_sample_employees(
    state: PreviewGeneratorState, bundle_key: str
) -> list[dict]:
    names = _name_pool(state)
    roles = _role_pool(state, bundle_key)
    depts = _dept_pool(state, bundle_key)
    role_cycle = itertools.cycle(roles)
    dept_cycle = itertools.cycle(depts)

    employees: list[dict] = []
    for index, name in enumerate(names[:8]):
        first = name.split()[0].lower()
        last = name.split()[-1].lower() if len(name.split()) > 1 else "user"
        company = _company_slug(state).lower()
        employees.append(
            {
                "id": index + 1,
                "name": name,
                "role": next(role_cycle),
                "department": next(dept_cycle),
                "email": f"{first}.{last}@{company}.com",
                "avatar": None,
                "is_active": True,
            }
        )
    return employees


def _build_sample_projects(
    state: PreviewGeneratorState, bundle_key: str, employees: list[dict]
) -> list[dict]:
    projects: list[dict] = []
    if bundle_key in ("hr_hub", "hr_management"):
        templates = _HR_QUEUE_NAMES
        for index in range(5):
            name = templates[index % len(templates)]
            lead = (
                employees[index % len(employees)]["name"] if employees else "Unassigned"
            )
            projects.append(
                {
                    "id": index + 1,
                    "name": name,
                    "status": _STATUSES_PROJECT[index % len(_STATUSES_PROJECT)],
                    "lead": lead,
                    "team_size": 2 + (index % 3),
                    "start_date": _base_date(60 - index * 10),
                    "due_date": _future_date(30 + index * 14),
                    "completion_pct": [68, 42, 15, 100, 30][index % 5],
                }
            )
        return projects

    work_type = _work_type(state)
    company = _company_slug(state)
    templates = _PROJECT_NAMES.get(work_type, _PROJECT_NAMES["waterfall"])
    for index in range(5):
        template = templates[index % len(templates)]
        name = template.format(
            n=index + 1,
            q=((index % 4) + 1),
            client="Martinez",
            company=company,
        )
        lead = employees[index % len(employees)]["name"] if employees else "Unassigned"
        projects.append(
            {
                "id": index + 1,
                "name": name,
                "status": _STATUSES_PROJECT[index % len(_STATUSES_PROJECT)],
                "lead": lead,
                "team_size": 3 + (index % 4),
                "start_date": _base_date(60 - index * 10),
                "due_date": _future_date(30 + index * 14),
                "completion_pct": [68, 42, 15, 100, 30][index % 5],
            }
        )
    return projects


def _build_sample_tickets(bundle_key: str, employees: list[dict]) -> list[dict]:
    type_priority_pool = _TICKET_TYPES_BY_BUNDLE.get(
        bundle_key, _TICKET_TYPES_BY_BUNDLE["ticketing"]
    )
    title_pool = _TICKET_TITLES_BY_BUNDLE.get(
        bundle_key, _TICKET_TITLES_BY_BUNDLE["ticketing"]
    )
    tickets: list[dict] = []
    for index in range(6):
        ticket_type, priority = type_priority_pool[index % len(type_priority_pool)]
        raw_title = title_pool[index % len(title_pool)]
        name = employees[index % len(employees)]["name"] if employees else "System"
        title = raw_title.format(name=name.split()[0])
        tickets.append(
            {
                "id": 100 + index + 1,
                "title": title,
                "type": ticket_type,
                "status": _STATUSES_TICKET[index % len(_STATUSES_TICKET)],
                "priority": priority,
                "requester": (
                    employees[(index + 1) % len(employees)]["name"]
                    if employees
                    else "User"
                ),
                "assignee": (
                    employees[index % len(employees)]["name"]
                    if employees
                    else "Unassigned"
                ),
                "created_at": _base_date(index * 3 + 1),
            }
        )
    return tickets


def _build_sample_weaves(employees: list[dict], projects: list[dict]) -> list[dict]:
    weaves: list[dict] = []
    for index in range(4):
        template = _WEAVE_TITLES[index % len(_WEAVE_TITLES)]
        project_name = (
            projects[index % len(projects)]["name"] if projects else "Project"
        )
        title = template.format(
            month=_MONTHS[index % 12],
            project=project_name.split("—")[0].strip(),
        )
        creator = employees[index % len(employees)]["name"] if employees else "Admin"
        participants = (
            [emp["name"] for emp in employees[1:3]] if len(employees) >= 3 else []
        )
        weaves.append(
            {
                "id": index + 1,
                "title": title,
                "created_by": creator,
                "participants": participants,
                "status": "Active" if index % 3 != 2 else "Archived",
                "created_at": _base_date(index * 7 + 2),
            }
        )
    return weaves


def _build_sample_stores(state: PreviewGeneratorState) -> dict:
    bundle_key = state.bundle_key if state.data_tier == "tier_1" else "project_mgmt"
    employees = _build_sample_employees(state, bundle_key)
    projects = _build_sample_projects(state, bundle_key, employees)
    tickets = _build_sample_tickets(bundle_key, employees)
    weaves = _build_sample_weaves(employees, projects)
    return {
        "sample_employees": employees,
        "sample_projects": projects,
        "sample_tickets": tickets,
        "sample_weaves": weaves,
    }


def build_kpi_metrics(state: PreviewGeneratorState) -> dict:
    """Assemble KPI metrics for the resolved bundle.

    Starts from bundle's default_metrics list, then boosts with any
    extra metrics implied by UserContext key_phrases. Deduplicates.
    Each metric entry includes a sample value for preview display.

    Returns: {"kpi_metrics": list[dict]}
    """
    if state.catalog is None:
        logger.error("session=%s — BundleCatalog missing in state", state.session_id)
        return {"kpi_metrics": []}

    metrics_catalog = state.catalog.get_metrics_catalog()
    bundle_key = state.bundle_key
    default_slugs = _resolve_default_slugs(state, bundle_key)
    signal_boost_slugs = _collect_signal_boost_slugs(
        state, metrics_catalog, default_slugs
    )
    boost_slugs = _collect_context_boost_slugs(state, default_slugs)
    all_slugs = _dedupe_valid_slugs(
        metrics_catalog, default_slugs, signal_boost_slugs, boost_slugs
    )

    # Fallback: at least show capacity_utilization and active_work_items
    if not all_slugs:
        all_slugs = [s for s in _FALLBACK_SLUGS if s in metrics_catalog]

    # Build output records
    kpi_metrics: list[KpiMetric] = []
    for i, slug in enumerate(all_slugs):
        catalog_entry = metrics_catalog.get(slug)
        if catalog_entry is None:
            continue
        kpi_metrics.append(
            KpiMetric(
                key=catalog_entry["key"],
                label=catalog_entry["label"],
                type=catalog_entry["type"],
                source_service=catalog_entry["source_service"],
                sample_value=_pick_value(catalog_entry["type"], i),
            )
        )

    logger.info(
        "session=%s — built %d KPI metrics for bundle=%r "
        "(default=%d signal_boost=%d boost=%d)",
        state.session_id,
        len(kpi_metrics),
        bundle_key,
        len(default_slugs),
        len(signal_boost_slugs),
        len(boost_slugs),
    )
    sample_updates = _build_sample_stores(state)
    return {"kpi_metrics": kpi_metrics, **sample_updates}
