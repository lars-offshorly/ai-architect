from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Command

from catalog import BundleCatalog
from core import get_session_logger
from generator import (
    PersonalisationInput,
    personalise_template,
    retrieve_template,
    validate_output,
)

from ..states import OnboardingState

CATALOG = BundleCatalog()


def _resolve_bundle(state: OnboardingState) -> tuple[str, str, str | None]:
    intents = state.get("onboarding_intents")
    fallback_bundle = CATALOG.get_fallback()
    if intents is None:
        return fallback_bundle.bundle_key, fallback_bundle.primary_entity, None

    bundle_key = intents.bundle or fallback_bundle.bundle_key
    bundle = CATALOG.get(bundle_key) or fallback_bundle
    return bundle.bundle_key, intents.entity_type, intents.industry_hint


async def json_assembler(state: OnboardingState) -> Command:
    session_id = state.get("session_id", "")
    session_logger = get_session_logger(__name__, session_id)
    bundle_key, entity_type, industry_hint = _resolve_bundle(state)
    slots = dict(state.get("slots", {}))
    try:
        templates = await retrieve_template(bundle_key, industry_hint)
        template_source = "none"
        if templates:
            first = templates[0]
            if isinstance(first, dict):
                template_source = str(first.get("source", "fetch"))
            else:
                template_source = str(getattr(first, "source", "fetch"))
        session_logger.info(
            "Retrieved %d template(s) for bundle=%s via %s",
            len(templates),
            bundle_key,
            template_source,
        )
        output = await personalise_template(
            templates,
            PersonalisationInput(
                session_id=session_id,
                bundle=bundle_key,
                entity_type=entity_type,
                industry_hint=industry_hint,
                filled_slots=slots,
            ),
        )
    except Exception as exc:
        session_logger.error("JSON assembly failed: %s", exc, exc_info=True)
        raise

    validation_error = validate_output(
        output.generation_json,
        output.dummy_data_json,
        CATALOG,
    )
    if validation_error is not None:
        session_logger.warning(
            "Generated output failed validation: %s",
            validation_error.errors,
        )

    step = f"Workspace generated ✓ via template source: {template_source}"
    return Command(
        goto=END,
        update={
            "generation_json": output.generation_json.model_dump(),
            "dummy_data_json": output.dummy_data_json.model_dump(),
            "thinking_trace": [step],
        },
    )
