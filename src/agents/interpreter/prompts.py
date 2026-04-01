from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = (
    "Extract structured signals from the workspace onboarding conversation below.\n\n"
    "Return two sections:\n\n"
    "classification_signals:\n"
    "- keywords: key terms that describe what is being managed "
    "(e.g. 'leave', 'project', 'ticket')\n"
    "- entities: business objects mentioned (e.g. 'employee', 'patient', 'asset')\n"
    "- intents: what the user wants to do (e.g. 'track leave', 'approve requests')\n"
    "- workflow_hints: process or workflow descriptions "
    "(e.g. 'leave approval workflow')\n"
    "- domain_hints: industry or domain signals (e.g. 'healthcare', 'logistics')\n"
    "- metrics: KPIs or measurements mentioned (e.g. 'headcount', 'avg_wait_time')\n\n"
    "personalization_signals:\n"
    "- company_name: name of the company or team (if mentioned)\n"
    "- employee_names: staff names mentioned\n"
    "- role_names: job titles or roles mentioned\n"
    "- department_names: team or department names mentioned\n"
    "- branch_names: office or branch names mentioned\n"
    "- custom_labels: any custom terminology the user uses for their workspace\n"
    "- terminology: key-value pairs of custom label mappings "
    "(e.g. {'ticket': 'case'})\n\n"
    "Return empty lists for absent fields. Do not invent values."
)

CLASSIFICATION_SYSTEM_PROMPT = (
    "Classify and rank workspace bundles for a user's onboarding request.\n"
    "Available bundles:\n{catalog_context}\n\n"
    "For each bundle provide:\n"
    "- bundle_key: the bundle identifier\n"
    "- confidence: 0.0–1.0 score based on how well it matches the user's signals\n"
    "- reasoning: brief explanation\n"
    "- matched_signals: list of words/phrases that matched\n"
    "Rank all bundles, highest confidence first."
)

SUMMARIZATION_SYSTEM_PROMPT = (
    "Summarize the following workspace onboarding conversation into a single "
    "concise paragraph.\n"
    "Focus on: what the user wants to manage, their entity type, any business context, "
    "and any confirmed preferences.\n"
    "Be factual and brief — 2–4 sentences maximum."
)
