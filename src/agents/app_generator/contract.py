from __future__ import annotations

from pydantic import BaseModel

from agents.app_generator.validators import validate_manifest
from core.exceptions import InvalidPayloadError


class AppPayloadContract(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str]
    manifest: dict[str, object]

    def validate_contract(self) -> list[str]:
        try:
            validate_manifest(self.manifest)
        except InvalidPayloadError as exc:
            return [str(exc)]
        return []
