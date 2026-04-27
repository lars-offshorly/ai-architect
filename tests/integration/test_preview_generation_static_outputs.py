"""Integration tests for static dashboard output enrichment in PreviewFlow."""

from __future__ import annotations

import pytest

from api.deps import get_preview_flow

_HISTORY: list[dict[str, str]] = [
    {"role": "user", "content": "Build me a dashboard preview for my team."}
]


@pytest.mark.parametrize(
    "bundle_key,variant_key",
    [
        ("hr_management", "app-01"),
        ("project_mgmt", "app-01"),
        ("ticketing", "app-01"),
        ("finance", "app-01"),
        ("marketing", "app-01"),
        ("sales", "app-01"),
    ],
)
def test_preview_flow_populates_widgets_for_group_a_bundles(
    bundle_key: str, variant_key: str
) -> None:
    flow = get_preview_flow()

    payload = flow.run(
        session_id=f"sess-{bundle_key}",
        bundle_key=bundle_key,
        conversation_history=_HISTORY,
        variant_key=variant_key,
    )

    widgets = payload.dummy_data_json["stores"]["dashboard_widgets"]
    assert isinstance(widgets, list)
    assert widgets, f"Expected static widgets for {bundle_key}:{variant_key}"


def test_preview_flow_returns_empty_widgets_for_bundle_without_static_output() -> None:
    flow = get_preview_flow()

    payload = flow.run(
        session_id="sess-unknown",
        bundle_key="unknown_bundle",
        conversation_history=_HISTORY,
        variant_key="app-01",
    )

    assert payload.dummy_data_json["stores"]["dashboard_widgets"] == []
