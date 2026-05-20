from __future__ import annotations

from pydantic import BaseModel

from agents.app_generator.validators import validate_v2_manifest
from core.exceptions import InvalidPayloadError

_REQUIRED_GENERATION_KEYS: frozenset[str] = frozenset(
    {"schema_version", "bundle_key", "modules", "config"}
)
_REQUIRED_DUMMY_KEYS: frozenset[str] = frozenset({"bundle_key", "stores"})


class AppPayloadContract(BaseModel):
    schema_version: str
    session_id: str
    bundle_key: str
    display_name: str
    modules: list[str]
    generation_json: dict[str, object]
    dummy_data_json: dict[str, object]
    # Set to True when the bundle exposes entity_relationships so the contract
    # can warn if relationships were not injected into config.
    has_entity_relationships: bool = False
    v2_manifest: dict[str, object] | None = None

    def validate_contract(self) -> list[str]:
        if self.v2_manifest is not None:
            return _validate_v2(self.v2_manifest)
        return _validate_v1(self)


def _validate_v2(manifest: dict[str, object]) -> list[str]:
    try:
        validate_v2_manifest(manifest)
    except InvalidPayloadError as exc:
        return [str(exc)]
    return []


def _validate_v1(contract: AppPayloadContract) -> list[str]:
    errors: list[str] = []
    gen_missing = _REQUIRED_GENERATION_KEYS - contract.generation_json.keys()
    if gen_missing:
        errors.append(f"generation_json missing keys: {gen_missing}")
    dummy_missing = _REQUIRED_DUMMY_KEYS - contract.dummy_data_json.keys()
    if dummy_missing:
        errors.append(f"dummy_data_json missing keys: {dummy_missing}")
    if not contract.modules:
        errors.append("modules list must not be empty")
    if contract.has_entity_relationships:
        config = contract.generation_json.get("config")
        if not isinstance(config, dict) or "relationships" not in config:
            errors.append(
                "generation_json.config missing 'relationships' key "
                "(bundle has entity_relationships defined)"
            )
    return errors
