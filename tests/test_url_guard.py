import pytest

from src.core.url_guard import UnsafeUrlError, validate_channel_url


def fake_resolver(*ips):
    def resolve(host, port, type=0):
        return [(2, 1, 6, "", (ip, port)) for ip in ips]

    return resolve


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.com/x",
        "https://localhost/x",
        "https://app.localhost/x",
        "https://127.0.0.1/x",
        "https://10.0.0.5/x",
        "https://192.168.1.10/x",
        "https://169.254.169.254/latest/meta-data",
        "https://100.64.0.1/x",
        "https://[::1]/x",
        "https://[::ffff:127.0.0.1]/x",
        "https://user:pass@hooks.example.com/x",
        "https://hooks.example.com:8080/x",
        "https:///nohost",
        "",
    ],
)
def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeUrlError):
        validate_channel_url(url, resolver=fake_resolver("93.184.216.34"))


def test_rejects_host_resolving_to_private():
    with pytest.raises(UnsafeUrlError):
        validate_channel_url(
            "https://hooks.example.com/x",
            resolver=fake_resolver("10.1.2.3"),
        )


def test_rejects_when_any_address_is_private():
    with pytest.raises(UnsafeUrlError):
        validate_channel_url(
            "https://hooks.example.com/x",
            resolver=fake_resolver("93.184.216.34", "127.0.0.1"),
        )


def test_rejects_unresolvable_host():
    import socket

    def boom(host, port, type=0):
        raise socket.gaierror("no such host")

    with pytest.raises(UnsafeUrlError):
        validate_channel_url("https://nope.example.com/x", resolver=boom)


def test_accepts_public_host():
    url = "https://hooks.example.com/x"
    assert validate_channel_url(url, resolver=fake_resolver("93.184.216.34")) == url


def test_accepts_public_ip_literal():
    url = "https://8.8.8.8/hook"
    assert validate_channel_url(url) == url
