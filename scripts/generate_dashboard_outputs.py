"""Generate pre-computed dashboard outputs for Group B bundle templates.

Calls the live Dashboard Gen service with each input template and stores the
converted widget output in dashboard_output_templates/.

Usage:
    poetry run python scripts/generate_dashboard_outputs.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).parents[1]
TEMPLATES_DIR = ROOT / "dashboard_templates"
OUTPUT_DIR = ROOT / "dashboard_output_templates"
OUTPUT_DIR.mkdir(exist_ok=True)

AUTH_URL = os.environ.get("KNIT_AUTH_URL", "https://orchestration.idealforliving.com/api/v1/login/")
DASHBOARD_URL = os.environ.get("DASHBOARD_SERVICE_URL", "https://dashboard-generator-ai.idealforliving.com")
EMAIL = os.environ.get("KNIT_EMAIL", "")
PASSWORD = os.environ.get("KNIT_PASSWORD", "")
GENERATE_PATH = "/api/v1/dashboards/generate/"

# Group B templates to generate
GROUP_B_TEMPLATES = [
    "healthcare_clinic",
    "healthcare_hospital",
    "healthcare_pharma",
    "legal_compliance_office",
    "legal_corporate_counsel",
    "legal_litigation_firm",
    "construction_general_contractor",
    "construction_infrastructure",
    "construction_residential",
    "real_estate_brokerage",
    "real_estate_commercial",
    "real_estate_property_mgmt",
    "education_edtech",
    "education_k12",
    "education_university",
    "all_microservices_ecommerce",
    "all_microservices_enterprise_saas",
    "all_microservices_fintech",
    "generic_consulting",
    "generic_nonprofit",
    "generic_small_business",
]

# typeId → widget type string (mirrors PreviewFlow._to_internal_widgets)
_TYPE_ID_MAP = {1: "number", 2: "text", 3: "bar", 4: "list"}


def get_token() -> str:
    print(f"Authenticating with {AUTH_URL} ...")
    resp = httpx.post(
        AUTH_URL,
        json={"email": EMAIL, "password": PASSWORD},
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    for key in ("token", "access_token", "key"):
        if isinstance(data.get(key), str) and data[key]:
            print("  Token obtained.")
            return data[key]
    nested = data.get("data", {})
    if isinstance(nested, dict):
        for key in ("token", "access_token", "key"):
            if isinstance(nested.get(key), str) and nested[key]:
                print("  Token obtained.")
                return nested[key]
    raise RuntimeError(f"Could not parse token from auth response: {data}")


_VALID_MODULES = {"HR Hub", "Projects", "Tickets"}

# Map unsupported module values → nearest valid enum member
_MODULE_MAP: dict[str, str] = {
    "Healthcare": "Tickets",
    "Legal Services": "Tickets",
    "Construction": "Projects",
    "Real Estate": "Projects",
    "Education": "Projects",
    "Orders": "Tickets",
    "Returns": "Tickets",
    "Fulfillment": "Tickets",
    "Compliance": "Tickets",
    "API Gateway": "Tickets",
    "Payments": "Tickets",
    "Custom Workspace": "Projects",
    "Programs": "Projects",
    "Fundraising": "Projects",
}

_CHART_TYPES = {"bar", "pie", "line", "scatter", "hbar", "list"}
_OP_TO_AGGREGATION = {"count": "count", "sum": "sum", "percentage": "count", "list": "count"}


def _calc_to_data_config(calculation: dict) -> dict:
    """Convert calculation.datasets[0] → data_config format expected by the service."""
    datasets = calculation.get("datasets", [])
    ds = datasets[0] if datasets else {}
    group_by_raw = ds.get("group_by", [])
    group_by = [group_by_raw] if isinstance(group_by_raw, str) else list(group_by_raw)
    filters = ds.get("filters", {})
    fields = []
    if isinstance(filters, dict):
        for v in filters.values():
            if isinstance(v, list):
                fields.extend(str(x) for x in v)
            elif v:
                fields.append(str(v))
    return {
        "module": _map_module(ds.get("module", "Projects")),
        "data_source": ds.get("data_source", ""),
        "group_by": group_by,
        "fields": fields,
        "aggregation": _OP_TO_AGGREGATION.get(ds.get("operation", "count"), "count"),
    }


def _sanitize_name(name: str) -> str:
    """Strip characters not matching ^[a-zA-Z0-9 \\-]+$."""
    import re
    name = name.replace("&", "and")
    name = re.sub(r"[^a-zA-Z0-9 \-]", "", name)
    return name.strip()


def _map_module(module: str) -> str:
    if module in _VALID_MODULES:
        return module
    return _MODULE_MAP.get(module, "Projects")


def preprocess_template(template: dict) -> dict:
    """Fix validation issues before sending to the service:
    - Sanitize dashboard_name (remove chars outside ^[a-zA-Z0-9 \\-]+$)
    - Add title from name for chart/list widgets missing title
    - Remap unsupported module values to valid enum members
    - Fill null date ranges with last 12 months
    """
    import copy
    import re

    t = copy.deepcopy(template)

    # Fix dashboard_name
    if "dashboard_name" in t:
        t["dashboard_name"] = _sanitize_name(t["dashboard_name"])

    today = date.today()
    date_to = today.isoformat()
    date_from = (today - timedelta(days=365)).isoformat()

    for widget in t.get("widgets", []):
        wtype = widget.get("type", "")

        # Add title from name for chart/list widgets
        if wtype in _CHART_TYPES and not widget.get("title") and widget.get("name"):
            widget["title"] = widget["name"]

        # Chart/list widgets: convert calculation → data_config when needed
        calc = widget.get("calculation")
        if wtype in _CHART_TYPES and isinstance(calc, dict) and "data_config" not in widget:
            widget["data_config"] = _calc_to_data_config(calc)
            del widget["calculation"]

        # Fix module + date defaults in data_config
        dc = widget.get("data_config")
        if isinstance(dc, dict):
            # Hoist module/data_source from nested datasets[0] when missing at top level
            nested_ds = dc.get("datasets", [])
            if nested_ds and isinstance(nested_ds[0], dict):
                ds0 = nested_ds[0]
                if not dc.get("module") and ds0.get("module"):
                    dc["module"] = ds0["module"]
                if not dc.get("data_source") and ds0.get("data_source"):
                    dc["data_source"] = ds0["data_source"]
            if dc.get("module"):
                dc["module"] = _map_module(dc["module"])
            if not dc.get("date_from"):
                dc["date_from"] = date_from
            if not dc.get("date_to"):
                dc["date_to"] = date_to

        # Fix module in calculation.datasets (number widgets keep calculation)
        remaining_calc = widget.get("calculation", {})
        if isinstance(remaining_calc, dict):
            for ds in remaining_calc.get("datasets", []):
                if isinstance(ds, dict) and ds.get("module"):
                    ds["module"] = _map_module(ds["module"])

    return t


def to_internal_widgets(raw_widgets: list) -> list[dict]:
    """Mirror PreviewFlow._to_internal_widgets exactly."""
    if not isinstance(raw_widgets, list):
        return []
    widgets: list[dict] = []
    for idx, raw in enumerate(raw_widgets, start=1):
        if not isinstance(raw, dict):
            continue

        type_id = raw.get("typeId")
        widget_type = (
            _TYPE_ID_MAP.get(type_id) if isinstance(type_id, int) else None
        ) or "number"

        if type_id == 3:
            settings = raw.get("settings", {})
            if isinstance(settings, dict):
                chart_type = settings.get("chartType", "bar")
                if chart_type == "barHorizontal":
                    widget_type = "hbar"
                elif chart_type in ("pie", "line", "scatter"):
                    widget_type = chart_type

        title = raw.get("name") or raw.get("title")
        if not isinstance(title, str) or not title.strip():
            title = f"Widget {idx}"

        settings = raw.get("settings", {})
        if isinstance(settings, dict) and "yAxis" in settings:
            row = settings.get("yAxis", 0)
            col = settings.get("xAxis", 0)
            width = settings.get("width", 2)
            height = settings.get("height", 1)
        else:
            row = (idx - 1) // 2
            col = ((idx - 1) % 2) * 2
            width = 2
            height = 1

        widget_id = None
        if isinstance(settings, dict):
            widget_id = settings.get("id")
        if widget_id is None:
            widget_id = raw.get("id")
        if widget_id is None:
            widget_id = idx

        widgets.append({
            "id": f"widget-{widget_id}",
            "type": widget_type,
            "title": title,
            "position": {"row": row, "col": col, "width": width, "height": height},
        })
    return widgets


def call_service(token: str, payload: dict, timeout: float = 300.0) -> dict | None:
    url = f"{DASHBOARD_URL.rstrip('/')}{GENERATE_PATH}"
    try:
        resp = httpx.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=timeout,
        )
    except httpx.TimeoutException:
        print(f"  ERROR: timed out after {timeout}s")
        return None
    except httpx.RequestError as exc:
        print(f"  ERROR: network error — {exc}")
        return None

    if not resp.is_success:
        print(f"  ERROR: HTTP {resp.status_code} — {resp.text[:300]}")
        return None

    data = resp.json()
    if not data.get("success"):
        print(f"  ERROR: success=false — {str(data)[:300]}")
        return None
    return data


def process_template(template_name: str, token: str) -> bool:
    input_path = TEMPLATES_DIR / f"{template_name}.json"
    output_path = OUTPUT_DIR / f"{template_name}.json"

    print(f"\n[{template_name}]")
    with input_path.open(encoding="utf-8") as f:
        template = json.load(f)

    template = preprocess_template(template)

    print(f"  Calling service ({len(template.get('widgets', []))} input widgets) ...")
    t0 = time.time()
    response = call_service(token, template)
    elapsed = time.time() - t0

    if response is None:
        print(f"  SKIPPED (service error) after {elapsed:.1f}s")
        return False

    raw_widgets = response.get("debug_payload", {}).get("widgets", [])
    widgets = to_internal_widgets(raw_widgets)
    print(f"  Done in {elapsed:.1f}s — {len(raw_widgets)} raw → {len(widgets)} widgets")

    output = {
        "source_template": template_name,
        "generated_at": date.today().isoformat(),
        "widgets": widgets,
    }
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"  Written → {output_path.relative_to(ROOT)}")
    return True


def main() -> None:
    if not EMAIL or not PASSWORD:
        print("ERROR: KNIT_EMAIL and KNIT_PASSWORD must be set in .env or environment.")
        sys.exit(1)

    # Load .env if running outside poetry
    env_path = ROOT / ".env"
    if env_path.exists() and not EMAIL:
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    token = get_token()
    succeeded, failed = [], []

    for name in GROUP_B_TEMPLATES:
        ok = process_template(name, token)
        (succeeded if ok else failed).append(name)

    print(f"\n{'='*60}")
    print(f"Done: {len(succeeded)} succeeded, {len(failed)} failed")
    if failed:
        print("Failed:", ", ".join(failed))


if __name__ == "__main__":
    main()
