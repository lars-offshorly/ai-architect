from __future__ import annotations

import re


def sanitize_text(text: str, max_length: int = 4000) -> str:
    """Strip HTML tags, truncate to max_length, and strip surrounding whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = text[:max_length]
    return text.strip()
