import inspect

import pytest
from pydantic import ValidationError

from src.api.routes import ChannelCreate, ChannelUpdate
from src.core.crypto import MASK_MARK
from src.integrations import notifier


def make_create(url):
    return ChannelCreate(name="ops", type="webhook", url=url, severities=["critical"])


@pytest.mark.parametrize(
    "url",
    [
        "https://169.254.169.254/latest/meta-data",
        "https://127.0.0.1/hook",
        "http://8.8.8.8/hook",
    ],
)
def test_create_rejects_unsafe_url(url):
    with pytest.raises(ValidationError):
        make_create(url)


def test_create_accepts_public_ip_literal():
    assert make_create("https://8.8.8.8/hook").url == "https://8.8.8.8/hook"


def test_update_rejects_unsafe_url():
    with pytest.raises(ValidationError):
        ChannelUpdate(url="https://10.0.0.5/hook")


def test_update_allows_missing_and_masked_url():
    assert ChannelUpdate().url is None
    masked = f"https://hooks.example.com/{MASK_MARK}"
    assert ChannelUpdate(url=masked).url == masked


@pytest.mark.parametrize("send", [notifier._send_slack_to, notifier._send_webhook_to])
def test_send_blocks_internal_url_without_network(monkeypatch, send):
    created = []

    def fake_client(*args, **kwargs):
        created.append(kwargs)
        raise AssertionError("httpx.Client must not be created")

    monkeypatch.setattr(notifier.httpx, "Client", fake_client)
    send("https://127.0.0.1/hook", None, None)
    assert created == []


@pytest.mark.parametrize("send", [notifier._send_slack_to, notifier._send_webhook_to])
def test_send_never_follows_redirects(send):
    assert "follow_redirects=False" in inspect.getsource(send)
