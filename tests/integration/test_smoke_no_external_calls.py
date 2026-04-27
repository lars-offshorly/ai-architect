import pytest
from api.deps import get_interpreter_service
from domain.models.interpreter_request import InterpreterRequest


@pytest.mark.asyncio
async def test_interpreter_service_handles_none_llm():
    """Verify that InterpreterService returns a stub when LLM is disabled."""
    # This test should already be marked as 'integration' by our conftest hook,
    # and the 'disable_external_calls' fixture is autouse=True in tests/integration/conftest.py.
    # So we expect DISABLE_LLM_CALLS=true to be set.
    
    service = get_interpreter_service()
    # If the speedup is working, service should have been built with llm=None
    assert service._extractor is None
    assert service._classifier is None
    
    request = InterpreterRequest(
        session_id="test-session",
        user_message="I want a leave request app",
        history=[]
    )
    
    extracted, suggested = await service.interpret(request)
    
    # Verify we got stubbed output
    assert extracted.session_id == "test-session"
    assert suggested.selected_bundle is not None
    assert suggested.reasoning == "Deterministic stub"
