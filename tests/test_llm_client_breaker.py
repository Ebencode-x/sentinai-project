import httpx
import pytest

from sentinai.llm.breaker import BreakerState, get_breaker
from sentinai.llm.exceptions import LLMCircuitOpenError
from src.core.config import settings
from src.integrations import llm_client as lc

URL = "https://llm.test/v1/chat/completions"


@pytest.fixture
def network(monkeypatch):
    """Route every httpx.Client through a counting MockTransport."""
    monkeypatch.delenv("SENTINAI_BREAKER_THRESHOLD", raising=False)
    monkeypatch.delenv("SENTINAI_BREAKER_COOLDOWN", raising=False)
    monkeypatch.setattr(settings, "llm_max_retries", 1)
    state = {"status": 503, "hits": 0}
    real_client = httpx.Client

    def handler(request):
        state["hits"] += 1
        return httpx.Response(state["status"], json={"ok": True})

    def fake_client(*args, **kwargs):
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(lc.httpx, "Client", fake_client)
    return state


def _post():
    return lc._post_json_with_retry(url=URL, headers={}, json_body={}, timeout_seconds=1.0)


def _fail_times(count):
    for _ in range(count):
        with pytest.raises(httpx.HTTPStatusError):
            _post()


def test_repeated_503_opens_the_circuit_and_stops_network_calls(network):
    _fail_times(3)
    assert network["hits"] == 3
    with pytest.raises(LLMCircuitOpenError):
        _post()
    assert network["hits"] == 3


def test_client_errors_never_open_the_circuit(network):
    network["status"] = 401
    _fail_times(5)
    assert network["hits"] == 5
    assert get_breaker(URL).state is BreakerState.CLOSED


def test_remediation_stack_trips_the_breaker_chat_uses(network):
    _fail_times(3)
    assert get_breaker("https://llm.test/v1").state is BreakerState.OPEN


def test_a_success_resets_the_failure_count(network):
    _fail_times(2)
    network["status"] = 200
    assert _post() == {"ok": True}
    network["status"] = 503
    _fail_times(2)
    assert get_breaker(URL).state is BreakerState.CLOSED
