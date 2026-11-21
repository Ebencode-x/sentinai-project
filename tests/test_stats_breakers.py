from sentinai.llm.breaker import get_breaker
from src.core.state import AppState


def test_no_breakers_before_any_call():
    assert AppState().stats_snapshot()["llm_breakers"] == []


def test_a_known_provider_host_is_listed_by_host_only():
    get_breaker("https://llm.example.test/v1/chat?key=secret")
    snap = AppState().stats_snapshot()["llm_breakers"]
    assert [b["name"] for b in snap] == ["llm.example.test"]
    assert snap[0]["state"] == "closed"
    assert "secret" not in str(snap)


def test_an_open_breaker_reports_the_time_left():
    breaker = get_breaker("https://llm.example.test")
    for _ in range(int(breaker.snapshot()["threshold"])):
        breaker.record_failure()
    entry = AppState().stats_snapshot()["llm_breakers"][0]
    assert entry["state"] == "open"
    assert entry["retry_in_seconds"] > 0
