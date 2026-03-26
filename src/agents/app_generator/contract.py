from __future__ import annotations

from pydantic import BaseModel


class AppPayloadContract(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str]
    generation_json: dict[str, object]
    dummy_data_json: dict[str, object]

    _REQUIRED_GENERATION_KEYS: frozenset[str] = frozenset(
        {"schema_version", "bundle_key", "modules", "config"}
    )
    _REQUIRED_DUMMY_KEYS: frozenset[str] = frozenset(
        {"bundle_key", "stores"}
    )

    def validate_contract(self) -> list[str]:
        errors: list[str] = []
        gen_missing = self._REQUIRED_GENERATION_KEYS - self.generation_json.keys()
        if gen_missing:
            errors.append(f"generation_json missing keys: {gen_missing}")
        dummy_missing = self._REQUIRED_DUMMY_KEYS - self.dummy_data_json.keys()
        if dummy_missing:
            errors.append(f"dummy_data_json missing keys: {dummy_missing}")
        if not self.modules:
            errors.append("modules list must not be empty")
        return errors
