from __future__ import annotations

from collections import Counter
from threading import Lock


class InMemoryMetrics:
    """Lightweight process-local counters for runtime observability."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: Counter[str] = Counter()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)


metrics = InMemoryMetrics()
