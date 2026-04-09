from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from onboarding.processor import OnboardingProcessor

router = APIRouter(tags=["onboarding"])
PROCESSOR = OnboardingProcessor()


class OnboardRequest(BaseModel):
    message: str = Field(min_length=1)


class ReplyRequest(BaseModel):
    message: str = Field(min_length=1)


@router.post("/onboard")
async def onboard(request: Request, body: OnboardRequest) -> dict[str, object]:
    user_id = getattr(request.state, "user_id", None)
    auth_token = getattr(request.state, "auth_token", None)
    return await PROCESSOR.start_session(
        message=body.message,
        user_id=user_id,
        auth_token=auth_token,
    )


@router.post("/onboard/{session_id}/reply")
async def onboard_reply(session_id: str, body: ReplyRequest) -> dict[str, object]:
    return await PROCESSOR.reply(session_id=session_id, message=body.message)
