"""Secrets in stored incidents do not reach the chat system prompt."""

from src.api.chat import _build_system_prompt

SNL = "snl_" + "a1B2c3D4" * 5
BEARER_TOKEN = "abcDEF123456abcDEF123456abcDEF"


def test_system_prompt_masks_secrets_in_trigger_lines():
    incidents = [
        {
            "severity": "critical",
            "status": "open",
            "source": "agrolink",
            "trigger_line": f"ERROR key={SNL} Authorization: Bearer {BEARER_TOKEN}",
        }
    ]
    prompt = _build_system_prompt(incidents, {})
    assert SNL not in prompt
    assert BEARER_TOKEN not in prompt
    assert "agrolink" in prompt


def test_system_prompt_still_shows_plain_titles():
    incidents = [{"severity": "low", "status": "open", "source": "x", "trigger_line": "disk full"}]
    assert "disk full" in _build_system_prompt(incidents, {})
