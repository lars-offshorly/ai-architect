from __future__ import annotations

CONFIDENCE_HIGH: float = 0.8
CONFIDENCE_MEDIUM: float = 0.6
CONFIDENCE_LOW: float = 0.4

MAX_CONVERSATION_TURNS: int = 20
MAX_CLARIFICATION_ATTEMPTS: int = 3
CONVERSATION_HISTORY_WINDOW: int = 6

DEFAULT_TOP_K_BUNDLES: int = 3

MIN_VARIANT_SCORE: int = 3
MIN_VARIANT_GAP: int = 2

PREVIEW_JSON_SCHEMA_VERSION: str = "1.0"
APP_PAYLOAD_SCHEMA_VERSION: str = "2.0"

BUNDLE_REGISTRY_FILENAME: str = "bundle_registry.yaml"
PREVIEW_JSON_FILENAME: str = "preview.json"
APP_JSON_FILENAME: str = "app.json"
DUMMY_DATA_FILENAME: str = "dummy_data.json"


def normalize_variant_confidence(score: int) -> float:
    """Map an integer variant score to a 0.0–1.0 confidence.

    9 is roughly the cap of a clean 3-keyword + 1-entity + 1-intent match;
    anything beyond that is treated as saturated.
    """
    if score <= 0:
        return 0.0
    saturated = min(score, 9)
    return round(saturated / 9.0, 3)
