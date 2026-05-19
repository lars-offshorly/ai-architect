from __future__ import annotations

from pathlib import Path


class TemplateSelectionService:
    def __init__(self, templates_dir: Path | None = None) -> None:
        from core.config import get_settings  # noqa: PLC0415

        self._templates_dir = templates_dir or Path(get_settings().TEMPLATES_DIR)

    def preview_json_path(self, bundle_key: str) -> Path:
        return self._templates_dir / bundle_key / "preview.json"

    def app_json_path(self, bundle_key: str) -> Path:
        return self._templates_dir / bundle_key / "app.json"

    def dummy_data_path(self, bundle_key: str) -> Path:
        return self._templates_dir / bundle_key / "dummy_data.json"

    def bundle_dir_exists(self, bundle_key: str) -> bool:
        return (self._templates_dir / bundle_key).is_dir()
