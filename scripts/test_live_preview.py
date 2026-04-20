"""Live integration test script for the full Preview Generation pipeline.

Runs PreviewFlow end-to-end with:
  - BundleTemplateLoader  → picks the correct app-0*.json variant
  - DashboardTemplateRegistry  → loads dashboard template for the bundle
  - Live DashboardClient  → POSTs to the real dashboard generation service
  - Personalizer (LLM)    → personalises the dashboard report

Outputs the full AppPayload JSON (generation_json + dummy_data_json) to stdout
and writes it to scripts/output/<bundle_key>_preview_output.json.

Usage:
    PYTHONPATH=src python scripts/test_live_preview.py
    PYTHONPATH=src python scripts/test_live_preview.py --bundle healthcare
    PYTHONPATH=src python scripts/test_live_preview.py --bundle all_microservices --use-case "ecommerce online store"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap — add src/ AND project root to path so all packages resolve.
# src/     → agents, api, core, domain, orchestrators, repositories …
# root/    → catalog/ (lives at project root, not inside src/)
# ---------------------------------------------------------------------------
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))           # catalog, etc.
sys.path.insert(0, str(_project_root / "src"))   # agents, core, …

from agents.preview_generator.bundle_template_loader import BundleTemplateLoader
from agents.preview_generator.dashboard.auth import KnitAuthService
from agents.preview_generator.dashboard.client import DashboardClient
from agents.preview_generator.dashboard.templates import DashboardTemplateRegistry
from agents.preview_generator.service import PreviewGeneratorService
from catalog.bundle_catalog import BundleCatalog
from core.config import get_settings
from orchestrators.preview_flow import PreviewFlow


def build_flow(settings) -> PreviewFlow:
    catalog = BundleCatalog(Path(settings.BUNDLE_REGISTRY_PATH))

    auth = KnitAuthService(
        auth_url=settings.KNIT_AUTH_URL,
        email=settings.KNIT_EMAIL,
        password=settings.KNIT_PASSWORD,
        ttl_seconds=settings.DASHBOARD_AUTH_TOKEN_TTL_SECONDS,
    )
    dashboard_client = DashboardClient(
        base_url=settings.DASHBOARD_SERVICE_URL,
        auth_service=auth,
    )

    return PreviewFlow(
        preview_generator_service=PreviewGeneratorService(catalog),
        bundle_display_names={b.bundle_key: b.display_name for b in catalog.list_all()},
        dashboard_client=dashboard_client,
        dashboard_template_registry=DashboardTemplateRegistry(),
        bundle_template_loader=BundleTemplateLoader(),
    )


def run(bundle_key: str, use_case: str | None, session_id: str) -> dict:
    settings = get_settings()

    if not settings.KNIT_EMAIL or not settings.KNIT_PASSWORD:
        print("ERROR: KNIT_EMAIL and KNIT_PASSWORD must be set in .env", file=sys.stderr)
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Bundle  : {bundle_key}")
    print(f"  Use-case: {use_case or '(none — will default to app-01.json)'}")
    print(f"  Session : {session_id}")
    print(f"{'='*60}\n")

    flow = build_flow(settings)

    conversation_history = []
    if use_case:
        conversation_history = [{"role": "user", "content": use_case}]

    payload = flow.run(
        session_id=session_id,
        bundle_key=bundle_key,
        conversation_history=conversation_history,
    )

    return {
        "generation_json": payload.generation_json,
        "dummy_data_json": payload.dummy_data_json,
    }


def print_summary(result: dict) -> None:
    gen = result["generation_json"]
    dummy = result["dummy_data_json"]
    stores = dummy.get("stores", {})

    print("\n--- generation_json ---")
    print(f"  bundle_key    : {gen.get('bundle_key')}")
    print(f"  schema_version: {gen.get('schema_version')}")
    print(f"  modules       : {gen.get('modules')}")
    enabled = [f["name"] for f in gen.get("feature_flags", []) if f.get("isEnabled")]
    print(f"  flags enabled : {len(enabled)}")

    print("\n--- dummy_data_json ---")
    print(f"  bundle_key  : {dummy.get('bundle_key')}")
    print(f"  session_id  : {dummy.get('session_id')}")
    print(f"  company_name: {dummy.get('company_name')}")
    print(f"  stores      : {list(stores.keys())}")
    for key, val in stores.items():
        if isinstance(val, list):
            print(f"    {key}: {len(val)} items")
            if val:
                print(f"      [0]: {json.dumps(val[0], default=str)[:120]}")
        elif isinstance(val, dict):
            print(f"    {key}: (dict with keys {list(val.keys())[:6]})")

    widgets = stores.get("dashboard_widgets", [])
    print(f"\n--- dashboard_widgets ({len(widgets)} total) ---")
    for w in widgets:
        pos = w.get("position", {})
        print(
            f"  [{w.get('id')}] type={w.get('type')!r:8s} "
            f"title={w.get('title')!r} "
            f"row={pos.get('row')} col={pos.get('col')} "
            f"w={pos.get('width')} h={pos.get('height')}"
        )

    gen_output = stores.get("dashboard_generation_output", {})
    if gen_output:
        print("\n--- dashboard_generation_output ---")
        print(f"  success        : {gen_output.get('success')}")
        dashboard = gen_output.get("dashboard", {})
        print(f"  dashboard.id   : {dashboard.get('id')}")
        print(f"  dashboard.url  : {dashboard.get('url')}")
        print(f"  execution_time : {gen_output.get('execution_time')}")
        widget_counts = gen_output.get("widgets", {})
        print(f"  widget counts  : {widget_counts}")
        errors = gen_output.get("errors", [])
        if errors:
            print(f"  errors         : {errors}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live preview generation test")
    parser.add_argument(
        "--bundle",
        default="all_microservices",
        help="Bundle key to test (default: all_microservices)",
    )
    parser.add_argument(
        "--use-case",
        default=None,
        help="Primary use-case string for template variant selection",
    )
    parser.add_argument(
        "--session-id",
        default="live-test-001",
        help="Session ID (default: live-test-001)",
    )
    parser.add_argument(
        "--output-dir",
        default="scripts/output",
        help="Directory to write JSON output (default: scripts/output)",
    )
    args = parser.parse_args()

    result = run(
        bundle_key=args.bundle,
        use_case=args.use_case,
        session_id=args.session_id,
    )

    print_summary(result)

    # Write full JSON output
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.bundle}_preview_output.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nFull output written to: {out_path}")


if __name__ == "__main__":
    main()
