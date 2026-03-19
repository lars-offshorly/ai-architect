from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from core import get_logger
from onboarding import OnboardingProcessor

router = APIRouter(prefix="", tags=["onboarding"])
logger = get_logger(__name__)
PROCESSOR = OnboardingProcessor()


class OnboardingMessageRequest(BaseModel):
    message: str = Field(min_length=1)


def _request_user_id(request: Request) -> str | None:
    user_id = getattr(request.state, "user_id", None)
    if isinstance(user_id, str) and user_id.strip():
        return user_id
    return None


def _request_auth_token(request: Request) -> str | None:
    auth_token = getattr(request.state, "auth_token", None)
    if isinstance(auth_token, str) and auth_token.strip():
        return auth_token
    return None


@router.post("/onboard")
async def onboard(
    payload: OnboardingMessageRequest,
    request: Request,
) -> dict[str, object]:
    try:
        return await PROCESSOR.start_session(
            message=payload.message,
            user_id=_request_user_id(request),
            auth_token=_request_auth_token(request),
        )
    except Exception as exc:
        logger.error("Failed to start onboarding session: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start onboarding session.",
        ) from exc


@router.post("/onboard/{session_id}/reply")
async def onboard_reply(
    session_id: str,
    payload: OnboardingMessageRequest,
) -> dict[str, object]:
    if not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must not be empty.",
        )

    try:
        return await PROCESSOR.reply(session_id=session_id, message=payload.message)
    except Exception as exc:
        logger.error("Failed to continue onboarding session %s: %s", session_id, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to continue onboarding session.",
        ) from exc
