"""Runtime metrics collection for SentinAI observability (Milestone 4).

Tracks LLM provider latency and suggestion outcomes so stats_snapshot()
can expose p95 latency, fallback rate, and source breakdown to dashboards
or external monitoring tools.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

_LATENCY_WINDOW = 200


@dataclass
class MetricsCollector:
    """Thread-safe collector for LLM call metrics."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _latencies_ms: Deque[float] = field(
        default_factory=lambda: deque(maxlen=_LATENCY_WINDOW),
        init=False,
        repr=False,
    )
    total_suggestions: int = field(default=0, init=False)
    total_fallbacks: int = field(default=0, init=False)
    total_provider_calls: int = field(default=0, init=False)

    def record(self, *, latency_ms: float, source: str) -> None:
        with self._lock:
            self._latencies_ms.append(latency_ms)
            self.total_suggestions += 1
            if source == "fallback":
                self.total_fallbacks += 1
            if source in ("provider", "fallback"):
                self.total_provider_calls += 1

    def snapshot(self) -> dict:
        with self._lock:
            samples = list(self._latencies_ms)

        if not samples:
            return {
                "total_suggestions": self.total_suggestions,
                "total_fallbacks": self.total_fallbacks,
                "fallback_rate": 0.0,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
                "p99_latency_ms": None,
                "latency_sample_count": 0,
            }

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        def percentile(p: float) -> float:
            idx = max(0, int(n * p / 100) - 1)
            return round(sorted_samples[min(idx, n - 1)], 2)

        fallback_rate = (
            round(self.total_fallbacks / self.total_suggestions, 4)
            if self.total_suggestions
            else 0.0
        )

        return {
            "total_suggestions": self.total_suggestions,
            "total_fallbacks": self.total_fallbacks,
            "fallback_rate": fallback_rate,
            "avg_latency_ms": round(sum(sorted_samples) / n, 2),
            "p95_latency_ms": percentile(95),
            "p99_latency_ms": percentile(99),
            "latency_sample_count": n,
        }


metrics = MetricsCollector()
