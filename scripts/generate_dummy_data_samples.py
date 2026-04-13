#!/usr/bin/env python3
"""Generate dummy_data_json samples from the Preview Generator pipeline.

Runs the pipeline directly (no server needed) for three scenarios:
  1. hr_dashboard        → hr_management bundle  (Tier 1 — rich data)
  2. marketing_agency    → marketing bundle       (Tier 3 — generic fallback)
  3. logistics_docops    → generic bundle         (Tier 3 — generic fallback)

Output:
  docs/sample-output/dummy-data/hr_dashboard.json
  docs/sample-output/dummy-data/marketing_agency_kpi.json
  docs/sample-output/dummy-data/logistics_docops.json

Usage:
  cd /home/christian/AI-Architect/ai-architect
  PYTHONPATH=src python scripts/generate_dummy_data_samples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is on the path so imports resolve without installing the package.
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))  # catalog/ lives at project root, not src/

from catalog.bundle_catalog import BundleCatalog  # noqa: E402
from agents.preview_generator.service import PreviewGeneratorService  # noqa: E402

REGISTRY_PATH = ROOT / "src" / "templates" / "bundle_registry.yaml"
OUTPUT_DIR = ROOT / "docs" / "sample-output" / "dummy-data"

# ---------------------------------------------------------------------------
# Scenario definitions
# Each entry: (filename_stem, bundle_key, conversation_history)
# ---------------------------------------------------------------------------

SCENARIOS = [
    (
        "hr_dashboard",
        "hr_management",
        [
            {
                "role": "user",
                "content": (
                    "We're Crestwood HR Solutions, about 200 employees across three "
                    "branches — Manila, Cebu, and Davao. We need a system to manage "
                    "onboarding, leave requests, equipment provisioning, and employee "
                    "performance tracking. Our HR team is 12 people."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Got it. I'll set up an HR Management dashboard tailored for "
                    "Crestwood HR Solutions."
                ),
            },
        ],
    ),
    (
        "marketing_agency_kpi",
        "marketing",
        [
            {
                "role": "user",
                "content": (
                    "We're a marketing agency called Bright Signal Co. We run campaigns "
                    "for about 15 clients simultaneously. We need to track KPIs like "
                    "monthly leads, conversion rates, cost per acquisition, and campaign "
                    "ROI. Team of 30 people split across creative, media buying, and "
                    "analytics."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Understood. I'll configure a KPI-focused workspace for Bright "
                    "Signal Co."
                ),
            },
        ],
    ),
    (
        "logistics_docops",
        "generic",
        [
            {
                "role": "user",
                "content": (
                    "We're FastMove Logistics, handling import/export documentation for "
                    "about 500 shipments per month. We need to automate document "
                    "processing — bill of lading, customs declarations, invoices — and "
                    "track compliance across our 8-person operations team."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "I'll set up a document operations workspace for FastMove Logistics."
                ),
            },
        ],
    ),
]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    catalog = BundleCatalog(REGISTRY_PATH)
    service = PreviewGeneratorService(catalog)

    for filename_stem, bundle_key, conversation in SCENARIOS:
        print(f"Generating: {filename_stem} (bundle={bundle_key}) ...", end=" ")

        _, dummy_data_json = service.generate(
            session_id=f"sample-{filename_stem}",
            bundle_key=bundle_key,
            conversation_history=conversation,
        )

        out_path = OUTPUT_DIR / f"{filename_stem}.json"
        out_path.write_text(json.dumps(dummy_data_json, indent=2), encoding="utf-8")
        print(f"→ {out_path.relative_to(ROOT)}")

    print(
        "\nNote: marketing and logistics use Tier 3 (generic fallback).\n"
        "      hr_dashboard uses Tier 1 (full personalized data).\n"
        "      To get rich data for marketing/logistics, add Tier 1 support\n"
        "      in src/agents/preview_generator/nodes/sample_data.py."
    )


if __name__ == "__main__":
    main()
