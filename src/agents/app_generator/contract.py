from __future__ import annotations

from pydantic import BaseModel, ValidationError

from agents.app_generator.schemas import DummyDataJsonSchema, GenerationJsonSchema


class AppPayloadContract(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str]
    generation_json: dict[str, object]
    dummy_data_json: dict[str, object]

    def validate_contract(self) -> list[str]:
        """Return a list of human-readable error strings.

        Each embedded JSON blob is validated via the full Pydantic schema so
        that all field-level constraints are checked, not just key presence.
        """
        errors: list[str] = []

        try:
            GenerationJsonSchema.model_validate(self.generation_json)
        except ValidationError as exc:
            errors.append(f"generation_json schema errors: {exc}")

        try:
            DummyDataJsonSchema.model_validate(self.dummy_data_json)
        except ValidationError as exc:
            errors.append(f"dummy_data_json schema errors: {exc}")

        if not self.modules:
            errors.append("modules list must not be empty")

        return errors
