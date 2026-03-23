from __future__ import annotations

import json
from pathlib import Path

from core.exceptions import TemplateLoadError
from domain.services.template_selection import TemplateSelectionService


class TemplateRepository:
    def __init__(self, templates_dir: Path | None = None) -> None:
        self._selector = TemplateSelectionService(templates_dir)

    def load_preview_json(self, bundle_key: str) -> dict[str, object]:
        path = self._selector.preview_json_path(bundle_key)
        return self._load_json(path)

    def load_app_json(self, bundle_key: str) -> dict[str, object]:
        path = self._selector.app_json_path(bundle_key)
        return self._load_json(path)

    def load_dummy_data(self, bundle_key: str) -> dict[str, object]:
        path = self._selector.dummy_data_path(bundle_key)
        return self._load_json(path)

    def bundle_exists(self, bundle_key: str) -> bool:
        return self._selector.bundle_dir_exists(bundle_key)

    def _load_json(self, path: Path) -> dict[str, object]:
        if not path.exists():
            raise TemplateLoadError(str(path), "file not found")
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise TemplateLoadError(str(path), str(exc)) from exc
        if not isinstance(data, dict):
            raise TemplateLoadError(str(path), "expected a JSON object at root")
        return data
