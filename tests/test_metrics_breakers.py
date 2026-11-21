from prometheus_client import generate_latest

from sentinai.llm.breaker import get_breaker
from src.core.metrics import shared_registry


def _scrape() -> str:
    return generate_latest(shared_registry).decode("utf-8")


def test_no_breaker_series_before_any_call():
    assert "sentinai_llm_breaker_open{" not in _scrape()


def test_a_closed_breaker_is_exported_by_host():
    get_breaker("https://llm.example.test/v1/chat?key=secret")
    text = _scrape()
    assert 'sentinai_llm_breaker_open{provider="llm.example.test"} 0.0' in text
    assert "secret" not in text


def test_an_open_breaker_exports_one_and_the_time_left():
    breaker = get_breaker("https://llm.example.test")
    for _ in range(int(breaker.snapshot()["threshold"])):
        breaker.record_failure()
    text = _scrape()
    assert 'sentinai_llm_breaker_open{provider="llm.example.test"} 1.0' in text
    line = next(
        row
        for row in text.splitlines()
        if row.startswith('sentinai_llm_breaker_retry_seconds{provider="llm.example.test"}')
    )
    assert float(line.rsplit(" ", 1)[1]) > 0
