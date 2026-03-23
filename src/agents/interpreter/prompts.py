from __future__ import annotations

EXTRACTION_SYSTEM_PROMPT = (
    "Extract structured information from the user's workspace onboarding message.\n"
    "Identify:\n"
    "- company_name: name of the company or team (if mentioned)\n"
    "- industry_hint: industry or domain (e.g. healthcare, logistics, consulting)\n"
    "- primary_use_case: one-sentence summary of what they want to manage\n"
    "- entity_type: 'people' for HR/team, 'work' for projects/tasks, 'asset' for equipment\n"
    "- employee_names: any staff names mentioned\n"
    "- role_names: job titles or roles mentioned\n"
    "- department_names: team or department names mentioned\n"
    "- metrics: KPIs or measurement terms mentioned\n"
    "- status_labels: any workflow state names mentioned\n"
    "Return null for fields that are not present. Do not invent values."
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
    "Summarize the following workspace onboarding conversation into a single concise paragraph.\n"
    "Focus on: what the user wants to manage, their entity type, any business context, "
    "and any confirmed preferences.\n"
    "Be factual and brief — 2–4 sentences maximum."
)
