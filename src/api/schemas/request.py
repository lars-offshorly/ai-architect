from __future__ import annotations

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str | None = None


class ReplyRequest(BaseModel):
    message: str = Field(min_length=1)


class ConfirmBundleRequest(BaseModel):
    confirmed: bool
