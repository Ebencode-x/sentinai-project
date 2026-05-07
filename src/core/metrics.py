"""Runtime metrics collection for SentinAI observability (Milestone 4 + 5).

Milestone 4 - internal snapshot()
    Tracks LLM provider latency and suggestion outcomes so stats_snapshot()
    can expose p95 latency, fallback rate, and source breakdown to dashboards
    or external monitoring tools.

Milestone 5 - Prometheus instruments
    Each MetricsCollector instance owns a private CollectorRegistry so that
    tests can create isolated collectors without cross-contaminating the
    process-level default registry.  The module-level `metrics` singleton
    uses a shared registry that the /metrics route scrapes.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

_LATENCY_WINDOW = 200
_LATENCY_BUCKETS = (50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000)


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

    registry: CollectorRegistry = field(
        default_factory=CollectorRegistry,
        init=True,
        repr=False,
    )

    def __post_init__(self) -> None:
        reg = self.registry
        self._prom_suggestions = Counter(
            "sentinai_suggestions_total",
            "Total remediation suggestions generated",
            registry=reg,
        )
        self._prom_fallbacks = Counter(
            "sentinai_fallbacks_total",
            "Suggestions served from the heuristic fallback (LLM unavailable)",
            registry=reg,
        )
        self._prom_provider_calls = Counter(
            "sentinai_provider_calls_total",
            "Total calls made to the configured LLM provider",
            registry=reg,
        )
        self._prom_latency = Histogram(
            "sentinai_llm_latency_ms",
            "End-to-end LLM call latency in milliseconds",
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        )
        self._prom_fallback_rate = Gauge(
            "sentinai_fallback_rate",
            "Rolling fallback rate (fallbacks / total suggestions)",
            registry=reg,
        )

    def record(self, *, latency_ms: float, source: str) -> None:
        with self._lock:
            self._latencies_ms.append(latency_ms)
            self.total_suggestions += 1
            if source == "fallback":
                self.total_fallbacks += 1
            if source in ("provider", "fallback"):
                self.total_provider_calls += 1

        self._prom_suggestions.inc()
        self._prom_latency.observe(latency_ms)
        if source == "fallback":
            self._prom_fallbacks.inc()
        if source in ("provider", "fallback"):
            self._prom_provider_calls.inc()
        rate = (
            self.total_fallbacks / self.total_suggestions
            if self.total_suggestions
            else 0.0
        )
        self._prom_fallback_rate.set(rate)

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


shared_registry = CollectorRegistry()
metrics = MetricsCollector(registry=shared_registry)
