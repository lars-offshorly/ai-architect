import pytest

from api.deps import get_interpreter_service
from domain.models.interpreter_request import InterpreterRequest


@pytest.mark.asyncio
async def test_interpreter_service_handles_none_llm():
    """When LLM is disabled, the interpreter routes through the canonical
    resolver instead of the legacy classifier path.

    The message must match a canonical industry alias for the resolver to
    return a confident bundle (no LLM extraction is available to enrich the
    request beyond ``user_message`` in this mode).
    """
    service = get_interpreter_service()
    assert service._extractor is None
    assert service._llm_industry_classifier is None

    request = InterpreterRequest(
        session_id="test-session",
        user_message="recruitment workflow for our hiring agency",
        history=[],
    )

    extracted, suggested = await service.interpret(request)

    assert extracted.session_id == "test-session"
    assert suggested.selected_bundle is not None
    assert suggested.selected_bundle.bundle_key == "hr_management"
