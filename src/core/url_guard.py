"""SSRF guard for outbound channel URLs (webhook and Slack)."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

ALLOWED_PORTS = {443}
MAX_URL_LENGTH = 2048
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal")


class UnsafeUrlError(ValueError):
    """Raised when a channel URL could reach an internal address."""


def _check_ip(raw: str) -> None:
    ip = ipaddress.ip_address(raw.split("%")[0])
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if not ip.is_global or ip.is_multicast:
        raise UnsafeUrlError("URL points to an internal or reserved address")


def validate_channel_url(
    url: str,
    resolver: Callable = socket.getaddrinfo,
) -> str:
    """Return the cleaned URL or raise UnsafeUrlError."""
    url = (url or "").strip()
    if not url or len(url) > MAX_URL_LENGTH:
        raise UnsafeUrlError("URL is empty or too long")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise UnsafeUrlError("Only https URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeUrlError("Credentials inside the URL are not allowed")
    host = parts.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    try:
        port = parts.port or 443
    except ValueError:
        raise UnsafeUrlError("URL has an invalid port") from None
    if port not in ALLOWED_PORTS:
        raise UnsafeUrlError("Only port 443 is allowed")
    lowered = host.lower()
    if lowered == "localhost" or lowered.endswith(BLOCKED_SUFFIXES):
        raise UnsafeUrlError("Internal host names are not allowed")
    try:
        ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        pass
    else:
        _check_ip(host)
        return url
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise UnsafeUrlError("Host name could not be resolved") from None
    if not infos:
        raise UnsafeUrlError("Host name could not be resolved")
    for info in infos:
        _check_ip(info[4][0])
    return url
