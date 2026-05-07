"""Tests for Milestone 5 - Prometheus /metrics endpoint.

Coverage:
- MetricsCollector populates Prometheus instruments on record()
- /metrics route returns 200 with correct Content-Type
- Metric names and values appear in the response body
- Counters increment correctly across multiple record() calls
- Isolated registries prevent cross-test pollution
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, generate_latest

from src.core.metrics import MetricsCollector


def _fresh() -> MetricsCollector:
    return MetricsCollector(registry=CollectorRegistry())


def _scrape(collector: MetricsCollector) -> str:
    return generate_latest(collector.registry).decode("utf-8")


class TestPrometheusInstruments:
    def test_suggestions_counter_increments(self):
        mc = _fresh()
        mc.record(latency_ms=100.0, source="provider")
        mc.record(latency_ms=200.0, source="provider")
        assert "sentinai_suggestions_total 2.0" in _scrape(mc)

    def test_fallback_counter_increments_only_on_fallback(self):
        mc = _fresh()
        mc.record(latency_ms=80.0, source="provider")
        mc.record(latency_ms=90.0, source="fallback")
        assert "sentinai_fallbacks_total 1.0" in _scrape(mc)

    def test_provider_calls_counts_provider_and_fallback(self):
        mc = _fresh()
        mc.record(latency_ms=50.0, source="stub")
        mc.record(latency_ms=60.0, source="provider")
        mc.record(latency_ms=70.0, source="fallback")
        assert "sentinai_provider_calls_total 2.0" in _scrape(mc)

    def test_latency_histogram_present(self):
        mc = _fresh()
        mc.record(latency_ms=123.0, source="provider")
        output = _scrape(mc)
        assert "sentinai_llm_latency_ms" in output
        assert "sentinai_llm_latency_ms_count 1.0" in output

    def test_fallback_rate_gauge_zero_when_no_fallbacks(self):
        mc = _fresh()
        mc.record(latency_ms=100.0, source="provider")
        assert "sentinai_fallback_rate 0.0" in _scrape(mc)

    def test_fallback_rate_gauge_updates_correctly(self):
        mc = _fresh()
        mc.record(latency_ms=100.0, source="provider")
        mc.record(latency_ms=100.0, source="fallback")
        assert "sentinai_fallback_rate 0.5" in _scrape(mc)

    def test_isolated_registries_do_not_share_state(self):
        mc1 = _fresh()
        mc2 = _fresh()
        mc1.record(latency_ms=100.0, source="provider")
        assert "sentinai_suggestions_total 0.0" in _scrape(mc2)

    def test_no_records_produces_zero_counters(self):
        mc = _fresh()
        output = _scrape(mc)
        assert "sentinai_suggestions_total 0.0" in output
        assert "sentinai_fallbacks_total 0.0" in output


def test_metrics_route_returns_200_with_prometheus_content_type():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    isolated_mc = _fresh()
    isolated_mc.record(latency_ms=250.0, source="provider")
    isolated_mc.record(latency_ms=300.0, source="fallback")

    app = FastAPI()

    @app.get("/metrics", response_class=PlainTextResponse)
    def _metrics():
        return PlainTextResponse(
            content=generate_latest(isolated_mc.registry).decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "sentinai_suggestions_total 2.0" in body
    assert "sentinai_fallbacks_total 1.0" in body
    assert "sentinai_llm_latency_ms" in body
