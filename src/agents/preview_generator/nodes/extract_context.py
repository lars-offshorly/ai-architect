from __future__ import annotations

import re

from core.logging import get_logger

from ..schemas import PersonDetail, TeamDetail, UserContext, WorkItemDetail
from ..state import PreviewGeneratorState

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets — Phase 1 (deterministic keyword scan)
# Phase 2 replaces _detect_* with a structured LLM call; these become fallback.
# ---------------------------------------------------------------------------

_LEGAL_KEYWORDS = frozenset([
    "litigation", "matter", "attorney", "paralegal", "counsel", "court",
    "filing", "docket", "case", "law firm", "legal", "lawsuit", "plaintiff",
    "defendant", "deposition", "arbitration", "settlement",
])
_TECH_KEYWORDS = frozenset([
    "sprint", "standup", "backlog", "scrum", "kanban", "agile",
    "developer", "engineer", "software", "deploy", "release", "codebase",
    "repository", "pull request", "devops", "ci/cd",
])
_CONSULTING_KEYWORDS = frozenset([
    "engagement", "consultant", "consulting", "deliverable", "client work",
    "statement of work", "sow", "retainer", "billable", "advisory",
])
_HR_KEYWORDS = frozenset([
    "onboarding", "offboarding", "employee", "headcount", "payroll",
    "performance review", "hr", "human resources", "leave", "attendance",
    "recruitment", "hiring", "org chart",
])
_AGILE_KEYWORDS = frozenset([
    "sprint", "sprints", "scrum", "kanban", "agile", "backlog", "backlogs",
    "standup", "standups", "velocity", "story points", "retrospective", "epic",
    "epics", "iteration", "iterations",
])
_WATERFALL_KEYWORDS = frozenset([
    "milestone", "phase", "waterfall", "gantt", "wbs", "work breakdown",
    "baseline", "deliverable", "gate review",
])
_LITIGATION_KEYWORDS = frozenset([
    "litigation", "matter", "case", "court", "filing", "docket",
    "discovery", "deposition", "arbitration",
])
_SUPPORT_KEYWORDS = frozenset([
    "support", "helpdesk", "help desk", "ticket", "issue", "request",
    "incident", "sla", "escalation", "resolution", "service desk",
])
_REMOTE_KEYWORDS = frozenset([
    "remote", "distributed", "work from home", "wfh", "hybrid",
    "across time zones", "global team", "different locations",
])
_CLIENT_KEYWORDS = frozenset([
    "clients", "client", "customers", "external", "client-facing",
    "customer success", "account",
])
_SMALL_KEYWORDS = frozenset([
    "small team", "startup", "just us", "handful", "few of us",
    "small company", "small business", "solopreneur",
])
_ENTERPRISE_KEYWORDS = frozenset([
    "enterprise", "corporation", "large company", "thousands of employees",
    "global", "multinational", "conglomerate",
])

# Patterns for named-entity extraction
_COMPANY_PATTERNS = [
    re.compile(r"(?:we are|we're|we're at|i work at|i'm from|our company is|company name is|called|named)\s+([A-Z][A-Za-z0-9\s&'.-]{1,40}?)(?:\s*[,.]|\s+and\s|\s+we\b)", re.IGNORECASE),
    re.compile(r"(?:at|for)\s+([A-Z][A-Za-z0-9\s&'.-]{1,40}?)(?:\s*[,.]|\s+we\b|\s+our\b)", re.IGNORECASE),
]
_NAME_PATTERNS = [
    re.compile(r"(?:my name is|i'm|i am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE),
    re.compile(r"(?:this is|meet)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE),
]
_ROLE_PATTERNS = [
    re.compile(r"i(?:'m| am) (?:a |an )?([A-Za-z\s]{3,30}?)(?:\s+at\b|\s+in\b|\s*[,.])", re.IGNORECASE),
    re.compile(r"(?:our|the)\s+([A-Za-z\s]{3,25}?)\s+(?:is|are)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.IGNORECASE),
]
_TEAM_PATTERNS = [
    re.compile(r"(\d+)\s+(?:person |people |member )?(?:team|staff|employee)", re.IGNORECASE),
    re.compile(r"(?:our\s+)?([A-Za-z\s]{3,25}?)\s+team", re.IGNORECASE),
    re.compile(r"([A-Za-z\s]{3,25}?)\s+department", re.IGNORECASE),
]
_SIZE_PATTERNS = [
    re.compile(r"(\d+)\s+(?:person|people|employee|member|staff)", re.IGNORECASE),
    re.compile(r"(?:team of|company of|about)\s+(\d+)", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_text(conversation_history: list[dict]) -> str:
    """Concatenate only user messages, lower-cased, for keyword scanning."""
    parts = [m["content"] for m in conversation_history if m.get("role") == "user"]
    return " ".join(parts)


def _raw_user_text(conversation_history: list[dict]) -> str:
    """Concatenate user messages preserving case, for regex extraction."""
    return " ".join(m["content"] for m in conversation_history if m.get("role") == "user")


def _detect_industry(text: str) -> tuple[str | None, str | None]:
    """Returns (industry_class, industry_detail).
    industry_class maps to broad category; industry_detail is more specific.
    """
    if _LEGAL_KEYWORDS & set(text.split()):
        return "legal", "Law / Litigation"
    if _HR_KEYWORDS & set(text.split()):
        return "hr", "Human Resources"
    if _CONSULTING_KEYWORDS & set(text.split()):
        return "consulting", "Professional Services / Consulting"
    if _TECH_KEYWORDS & set(text.split()):
        return "technology", "Software / Technology"
    if _SUPPORT_KEYWORDS & set(text.split()):
        return "operations", "IT Support / Service Desk"
    return None, None


def _detect_work_type(text: str) -> str:
    """Returns the dominant work type keyword in the text."""
    words = set(re.findall(r"\b\w+\b", text))
    if _LITIGATION_KEYWORDS & words:
        return "litigation"
    if _AGILE_KEYWORDS & words:
        return "sprint"
    if _WATERFALL_KEYWORDS & words:
        return "waterfall"
    if _SUPPORT_KEYWORDS & words:
        return "support_request"
    return "waterfall"  # safe default


def _detect_methodology(text: str) -> str | None:
    words = set(re.findall(r"\b\w+\b", text))
    if _AGILE_KEYWORDS & words:
        return "agile"
    if _WATERFALL_KEYWORDS & words:
        return "waterfall"
    if {"kanban"} & words:
        return "kanban"
    return None


def _extract_company_name(raw_text: str) -> str | None:
    for pattern in _COMPANY_PATTERNS:
        match = pattern.search(raw_text)
        if match:
            candidate = match.group(1).strip().strip(".,")
            if 2 <= len(candidate.split()) <= 5 and candidate[0].isupper():
                return candidate
    return None


def _extract_people(raw_text: str) -> list[PersonDetail]:
    people: list[PersonDetail] = []
    seen_names: set[str] = set()

    # "my name is X" or "I am X" — mark as user
    for pattern in _NAME_PATTERNS:
        for match in pattern.finditer(raw_text):
            name = match.group(1).strip()
            if name and name not in seen_names:
                seen_names.add(name)
                people.append(PersonDetail(name=name, is_user=True))

    # "our {role} is {Name}" — extract role-person pairs
    role_pattern = _ROLE_PATTERNS[1]
    for match in role_pattern.finditer(raw_text):
        role = match.group(1).strip()
        name = match.group(2).strip()
        if name and name not in seen_names and len(role.split()) <= 4:
            seen_names.add(name)
            people.append(PersonDetail(name=name, role=role, is_user=False))

    return people[:10]  # cap at 10 to avoid noise


def _extract_teams(raw_text: str, lower_text: str) -> list[TeamDetail]:
    teams: list[TeamDetail] = []
    seen: set[str] = set()

    known_functions = [
        "engineering", "marketing", "sales", "hr", "human resources",
        "legal", "operations", "product", "design", "finance", "it",
        "support", "customer success", "data", "research",
    ]

    for func in known_functions:
        if func in lower_text:
            key = func.title()
            if key not in seen:
                seen.add(key)
                # Try to extract size
                size_match = re.search(rf"(\d+)\s+(?:person\s+)?{func}", lower_text)
                size = int(size_match.group(1)) if size_match else None
                teams.append(TeamDetail(name=f"{key} Team", size=size, function=func.title()))

    return teams[:5]


def _detect_company_size(text: str) -> str | None:
    # Numeric signals
    for pattern in _SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            n = int(match.group(1))
            if n <= 20:
                return "small"
            if n <= 200:
                return "mid-sized"
            return "enterprise"

    # Keyword signals
    words = set(re.findall(r"\b\w+\b", text))
    if _ENTERPRISE_KEYWORDS & words:
        return "enterprise"
    if _SMALL_KEYWORDS & words:
        return "small"
    return None


def _extract_key_phrases(text: str) -> list[str]:
    """Pull signal phrases relevant to KPI and metric matching."""
    targets = [
        "on time", "deadline", "delivery", "resolution", "sla",
        "capacity", "utilization", "workload", "headcount", "attendance",
        "billable", "client satisfaction", "cycle time", "velocity",
        "case load", "throughput", "escalation",
    ]
    found = []
    for phrase in targets:
        if phrase in text:
            found.append(phrase)
    return found


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

def extract_user_context(state: PreviewGeneratorState) -> dict:
    """Phase 1: keyword-based UserContext extraction.

    Reads state.conversation_history (user messages only).
    Returns {"user_context": UserContext(...)}.

    Phase 2 upgrade: replace _detect_* helpers with a structured LLM call
    (anthropic tool_use / structured output). The keyword logic below becomes
    the fallback when the LLM call fails or confidence is low.
    """
    history = state.conversation_history
    if not history:
        logger.info("session=%s — no conversation history, returning empty UserContext", state.session_id)
        return {"user_context": UserContext()}

    lower = _user_text(history)
    raw = _raw_user_text(history)

    company_name = _extract_company_name(raw)
    company_size = _detect_company_size(lower)
    _, industry_detail = _detect_industry(lower)
    people = _extract_people(raw)
    teams = _extract_teams(raw, lower)
    work_type = _detect_work_type(lower)
    methodology = _detect_methodology(lower)
    key_phrases = _extract_key_phrases(lower)

    has_remote = any(kw in lower for kw in _REMOTE_KEYWORDS)
    has_clients = any(kw in lower for kw in _CLIENT_KEYWORDS)

    work_items = [
        WorkItemDetail(
            work_type=work_type,
            has_deadlines=any(p in lower for p in ["deadline", "due date", "due by", "by friday"]),
            methodology=methodology,
        )
    ]

    # Primary concern: first sentence of first user message that contains a pain-point word
    pain_words = ["struggle", "difficult", "hard to", "problem", "issue", "can't", "cannot", "need to"]
    primary_concern: str | None = None
    for msg in history:
        if msg.get("role") != "user":
            continue
        for sentence in re.split(r"[.!?]", msg["content"]):
            if any(pw in sentence.lower() for pw in pain_words):
                primary_concern = sentence.strip()
                break
        if primary_concern:
            break

    user_context = UserContext(
        company_name=company_name,
        company_size=company_size,
        industry_detail=industry_detail,
        people=people,
        teams=teams,
        work_items=work_items,
        has_remote_teams=has_remote or None,
        has_clients=has_clients or None,
        work_methodology=methodology,
        primary_concern=primary_concern,
        key_phrases=key_phrases,
    )

    logger.info(
        "session=%s — extracted context: company=%r size=%r industry=%r work_type=%s",
        state.session_id,
        company_name,
        company_size,
        industry_detail,
        work_type,
    )
    return {"user_context": user_context}

    # --- Phase 2 LLM upgrade stub ---
    # from agents.preview_generator.llm import extract_context_with_llm
    # try:
    #     llm_context = await extract_context_with_llm(history)
    #     return {"user_context": llm_context}
    # except Exception:
    #     logger.warning("LLM extraction failed, falling back to keyword scan")
    #     return {"user_context": user_context}  # keyword result as fallback
