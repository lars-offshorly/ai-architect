from __future__ import annotations

import pytest

from agents.preview_generator.modifier import TemplateModifier
from domain.models.extracted_info import ExtractedInfo


def _make_extracted(**kwargs: object) -> ExtractedInfo:
    return ExtractedInfo(session_id="test-session", **kwargs)


def test_modifier_injects_company_name() -> None:
    template = {"title": "{{company_name}} Workspace", "stores": {}}
    modifier = TemplateModifier()
    result = modifier.inject(template, _make_extracted(company_name="Acme Corp"))
    assert result["title"] == "Acme Corp Workspace"


def test_modifier_injects_employee_name() -> None:
    template = {"stores": {"tickets": [{"assignee": "{{employee_name}}"}]}}
    modifier = TemplateModifier()
    result = modifier.inject(template, _make_extracted(employee_names=["Jane Smith"]))
    tickets = result["stores"]["tickets"]  # type: ignore[index]
    assert tickets[0]["assignee"] == "Jane Smith"


def test_modifier_adds_session_id() -> None:
    template = {"stores": {}}
    modifier = TemplateModifier()
    result = modifier.inject(template, _make_extracted())
    assert result["session_id"] == "test-session"


def test_modifier_leaves_non_placeholder_text_unchanged() -> None:
    template = {"title": "Unchanged Title", "stores": {}}
    modifier = TemplateModifier()
    result = modifier.inject(template, _make_extracted())
    assert result["title"] == "Unchanged Title"


def test_modifier_deep_copies_template() -> None:
    template: dict[str, object] = {"stores": {"tickets": [{"id": "t-001"}]}}
    modifier = TemplateModifier()
    result = modifier.inject(template, _make_extracted())
    result["stores"]["tickets"].append({"id": "t-new"})  # type: ignore[index]
    assert len(template["stores"]["tickets"]) == 1  # type: ignore[index]
