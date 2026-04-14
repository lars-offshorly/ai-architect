"""Unit tests for PreviewFlow._to_internal_widgets with CJ's dashboard output format."""

from __future__ import annotations

import pytest

from orchestrators.preview_flow import PreviewFlow


class TestToInternalWidgets:
    """Test widget mapping from CJ's dashboard generation output to internal format."""

    def test_maps_type_id_to_type_string(self):
        """typeId integers are correctly mapped to type strings."""
        raw_widgets = [
            {"typeId": 1, "name": "Number Widget", "settings": {"id": 1}},
            {"typeId": 2, "name": "Text Widget", "settings": {"id": 2}},
            {"typeId": 3, "name": "Bar Chart", "settings": {"id": 3}},
            {"typeId": 4, "name": "List Widget", "settings": {"id": 4}},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert len(result) == 4
        assert result[0]["type"] == "number"
        assert result[1]["type"] == "text"
        assert result[2]["type"] == "bar"
        assert result[3]["type"] == "list"

    def test_extracts_chart_type_from_settings(self):
        """Chart widgets (typeId=3) use settings.chartType for refined type."""
        raw_widgets = [
            {
                "typeId": 3,
                "name": "Bar Chart",
                "settings": {"chartType": "bar", "id": 1},
            },
            {
                "typeId": 3,
                "name": "Horizontal Bar",
                "settings": {"chartType": "barHorizontal", "id": 2},
            },
            {
                "typeId": 3,
                "name": "Pie Chart",
                "settings": {"chartType": "pie", "id": 3},
            },
            {
                "typeId": 3,
                "name": "Line Chart",
                "settings": {"chartType": "line", "id": 4},
            },
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["type"] == "bar"
        assert result[1]["type"] == "hbar"
        assert result[2]["type"] == "pie"
        assert result[3]["type"] == "line"

    def test_extracts_positioning_from_settings(self):
        """Widget positioning is extracted from settings.xAxis/yAxis/width/height."""
        raw_widgets = [
            {
                "typeId": 1,
                "name": "Widget 1",
                "settings": {
                    "id": 1,
                    "xAxis": 0,
                    "yAxis": 0,
                    "width": 3,
                    "height": 3,
                },
            },
            {
                "typeId": 2,
                "name": "Widget 2",
                "settings": {
                    "id": 2,
                    "xAxis": 3,
                    "yAxis": 0,
                    "width": 9,
                    "height": 3,
                },
            },
            {
                "typeId": 3,
                "name": "Widget 3",
                "settings": {
                    "id": 3,
                    "xAxis": 0,
                    "yAxis": 3,
                    "width": 6,
                    "height": 6,
                },
            },
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["position"] == {"row": 0, "col": 0, "width": 3, "height": 3}
        assert result[1]["position"] == {"row": 0, "col": 3, "width": 9, "height": 3}
        assert result[2]["position"] == {"row": 3, "col": 0, "width": 6, "height": 6}

    def test_extracts_widget_id_from_settings(self):
        """Widget ID is extracted from settings.id or raw.id."""
        raw_widgets = [
            {"typeId": 1, "name": "Widget A", "settings": {"id": 42}},
            {"typeId": 1, "name": "Widget B", "id": 99, "settings": {}},
            {"typeId": 1, "name": "Widget C"},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["id"] == "widget-42"
        assert result[1]["id"] == "widget-99"
        assert result[2]["id"] == "widget-3"  # Falls back to index

    def test_extracts_title_from_name_field(self):
        """Title is extracted from 'name' field (CJ's format)."""
        raw_widgets = [
            {"typeId": 1, "name": "Dashboard Summary", "settings": {"id": 1}},
            {"typeId": 2, "name": "Key Findings", "settings": {"id": 2}},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["title"] == "Dashboard Summary"
        assert result[1]["title"] == "Key Findings"

    def test_fallback_to_title_field(self):
        """Falls back to 'title' field if 'name' is missing."""
        raw_widgets = [
            {"typeId": 1, "title": "Widget Title", "settings": {"id": 1}},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["title"] == "Widget Title"

    def test_fallback_positioning_when_settings_missing(self):
        """Uses 2-column grid layout when settings are missing."""
        raw_widgets = [
            {"typeId": 1, "name": "Widget 1"},
            {"typeId": 1, "name": "Widget 2"},
            {"typeId": 1, "name": "Widget 3"},
            {"typeId": 1, "name": "Widget 4"},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["position"] == {"row": 0, "col": 0, "width": 2, "height": 1}
        assert result[1]["position"] == {"row": 0, "col": 2, "width": 2, "height": 1}
        assert result[2]["position"] == {"row": 1, "col": 0, "width": 2, "height": 1}
        assert result[3]["position"] == {"row": 1, "col": 2, "width": 2, "height": 1}

    def test_handles_unknown_type_id(self):
        """Unknown typeId defaults to 'number'."""
        raw_widgets = [
            {"typeId": 999, "name": "Unknown Widget", "settings": {"id": 1}},
            {"typeId": None, "name": "Null Type", "settings": {"id": 2}},
            {"name": "No Type Field", "settings": {"id": 3}},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert result[0]["type"] == "number"
        assert result[1]["type"] == "number"
        assert result[2]["type"] == "number"

    def test_handles_empty_list(self):
        """Empty widget list returns empty result."""
        result = PreviewFlow._to_internal_widgets([])
        assert result == []

    def test_handles_non_list_input(self):
        """Non-list input returns empty result."""
        assert PreviewFlow._to_internal_widgets(None) == []
        assert PreviewFlow._to_internal_widgets({}) == []
        assert PreviewFlow._to_internal_widgets("invalid") == []

    def test_skips_non_dict_widgets(self):
        """Non-dict items in the list are skipped."""
        raw_widgets = [
            {"typeId": 1, "name": "Valid Widget", "settings": {"id": 1}},
            "invalid",
            None,
            {"typeId": 2, "name": "Another Valid", "settings": {"id": 2}},
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert len(result) == 2
        assert result[0]["title"] == "Valid Widget"
        assert result[1]["title"] == "Another Valid"

    def test_real_cj_dashboard_output(self):
        """Integration test with actual CJ dashboard generation output structure."""
        raw_widgets = [
            {
                "id": 1,
                "name": "Dashboard Summary",
                "typeId": 2,
                "order": 0,
                "description": "Summary text...",
                "settings": {
                    "width": 12,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 0,
                    "id": 1,
                },
            },
            {
                "id": 6,
                "name": "Records with Deficit (count)",
                "typeId": 1,
                "order": 0,
                "settings": {
                    "width": 3,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 15,
                    "format": "number",
                    "id": 6,
                },
                "datasets": [{"module": "HR Hub", "dataSource": "employees"}],
            },
            {
                "id": 13,
                "name": "Total Deficit (hours) by Department",
                "typeId": 3,
                "order": 0,
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 0,
                    "yAxis": 21,
                    "chartType": "bar",
                    "id": 27,
                },
            },
            {
                "id": 15,
                "name": "Absence count by department",
                "typeId": 3,
                "order": 0,
                "settings": {
                    "width": 6,
                    "height": 6,
                    "xAxis": 0,
                    "yAxis": 27,
                    "chartType": "barHorizontal",
                    "id": 31,
                },
            },
            {
                "id": 21,
                "name": "Top Departments to Prioritize (by deficit)",
                "typeId": 4,
                "order": 0,
                "settings": {
                    "width": 6,
                    "height": 3,
                    "xAxis": 0,
                    "yAxis": 45,
                    "id": 43,
                },
            },
        ]

        result = PreviewFlow._to_internal_widgets(raw_widgets)

        assert len(result) == 5

        # Text widget
        assert result[0]["id"] == "widget-1"
        assert result[0]["type"] == "text"
        assert result[0]["title"] == "Dashboard Summary"
        assert result[0]["position"] == {"row": 0, "col": 0, "width": 12, "height": 3}

        # Number widget
        assert result[1]["id"] == "widget-6"
        assert result[1]["type"] == "number"
        assert result[1]["title"] == "Records with Deficit (count)"
        assert result[1]["position"] == {"row": 15, "col": 0, "width": 3, "height": 3}

        # Bar chart
        assert result[2]["id"] == "widget-27"
        assert result[2]["type"] == "bar"
        assert result[2]["title"] == "Total Deficit (hours) by Department"
        assert result[2]["position"] == {"row": 21, "col": 0, "width": 6, "height": 6}

        # Horizontal bar chart
        assert result[3]["id"] == "widget-31"
        assert result[3]["type"] == "hbar"
        assert result[3]["title"] == "Absence count by department"
        assert result[3]["position"] == {"row": 27, "col": 0, "width": 6, "height": 6}

        # List widget
        assert result[4]["id"] == "widget-43"
        assert result[4]["type"] == "list"
        assert result[4]["title"] == "Top Departments to Prioritize (by deficit)"
        assert result[4]["position"] == {"row": 45, "col": 0, "width": 6, "height": 3}
