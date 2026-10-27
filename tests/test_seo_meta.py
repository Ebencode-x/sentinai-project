import re
from pathlib import Path

ROOT = Path.cwd()
PUBLIC = ROOT / "frontend" / "public"
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

REQUIRED_TAGS = [
    'name="description"',
    'rel="canonical"',
    'property="og:title"',
    'property="og:description"',
    'property="og:image"',
    'property="og:url"',
    'name="twitter:card"',
    'name="twitter:image"',
]


def _png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def test_index_has_required_meta_tags():
    for tag in REQUIRED_TAGS:
        assert tag in HTML, tag


def test_share_image_urls_are_absolute_https():
    urls = re.findall(r'(?:og|twitter):image" content="([^"]+)"', HTML)
    assert urls
    for url in urls:
        assert url.startswith("https://"), url


def test_og_image_size_and_dimensions():
    path = PUBLIC / "og-image.png"
    assert path.stat().st_size < 300_000
    assert _png_size(path) == (1200, 630)


def test_icons_have_expected_dimensions():
    assert _png_size(PUBLIC / "apple-touch-icon.png") == (180, 180)
    assert _png_size(PUBLIC / "favicon-48.png") == (48, 48)


def test_backend_serves_every_public_file():
    main = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
    for name in ("og-image.png", "apple-touch-icon.png", "favicon-48.png", "robots.txt"):
        assert f'"{name}"' in main, name
        assert (PUBLIC / name).is_file(), name
