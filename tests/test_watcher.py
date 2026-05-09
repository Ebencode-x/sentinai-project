"""Tests for Milestone 1: structured JSON LLM output and fallback chain.

Coverage:
- _strip_fences: markdown fence removal
- _try_parse_json: valid JSON, invalid JSON, Pydantic validation failure
- _try_parse_sections: legacy section format still works
- _parse_llm_output: full fallback chain end-to-end
- StubLLMClient: still returns a valid suggestion
"""

from __future__ import annotations

from datetime import datetime, timezone


from src.integrations.llm_client import (
    StubLLMClient,
    _parse_llm_output,
    _strip_fences,
    _try_parse_json,
    _try_parse_sections,
)
from src.models.events import LogIncident


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incident() -> LogIncident:
    return LogIncident(
        incident_id="abc123",
        detected_at_utc=datetime.now(timezone.utc),
        severity="critical",
        trigger_line="ERROR something went wrong",
        stacktrace="ERROR something went wrong\nTraceback...",
        context_before_error="INFO app started",
    )


VALID_JSON_RESPONSE = """{
  "summary": "Unhandled exception in request handler.",
  "code_fix": "Wrap handler in try/except and return 500 with safe message.",
  "config_change": "Set LOG_LEVEL=INFO in production.",
  "confidence": 0.85,
  "risks": "Ensure the catch block does not swallow critical errors silently.",
    "patch_file": "src/services/handler.py",
  "proposed_patch": "try:\\n    process()\\nexcept Exception as e:\\n    raise HTTPException(500)",
  "test_guidance": "1. Mock process() to raise. 2. Assert HTTP 500 returned."
}"""


# ---------------------------------------------------------------------------
# _strip_fences
# ---------------------------------------------------------------------------


def test_strip_fences_removes_json_fence() -> None:
    fenced = "```json\n" + VALID_JSON_RESPONSE + "\n```"
    result = _strip_fences(fenced)
    assert result.startswith("{")
    assert result.endswith("}")


def test_strip_fences_removes_plain_fence() -> None:
    fenced = "```\n" + VALID_JSON_RESPONSE + "\n```"
    result = _strip_fences(fenced)
    assert result.startswith("{")


def test_strip_fences_leaves_clean_json_unchanged() -> None:
    result = _strip_fences(VALID_JSON_RESPONSE)
    assert result.startswith("{")


# ---------------------------------------------------------------------------
# _try_parse_json — Stage 1
# ---------------------------------------------------------------------------


def test_try_parse_json_valid_returns_suggestion() -> None:
    suggestion = _try_parse_json(VALID_JSON_RESPONSE, source="provider")
    assert suggestion is not None
    assert suggestion.summary == "Unhandled exception in request handler."
    assert suggestion.confidence == 0.85
    assert suggestion.source == "provider"
    assert suggestion.provider_error is None


def test_try_parse_json_with_fences_succeeds() -> None:
    fenced = "```json\n" + VALID_JSON_RESPONSE + "\n```"
    suggestion = _try_parse_json(fenced, source="provider")
    assert suggestion is not None
    assert suggestion.confidence == 0.85


def test_try_parse_json_invalid_json_returns_none() -> None:
    result = _try_parse_json("this is not json at all", source="provider")
    assert result is None


def test_try_parse_json_missing_field_returns_none() -> None:
    # confidence field missing — Pydantic should reject it
    bad_json = (
        '{"summary": "ok", "code_fix": "ok", "config_change": "ok", "risks": "ok"}'
    )
    result = _try_parse_json(bad_json, source="provider")
    assert result is None


def test_try_parse_json_confidence_out_of_range_returns_none() -> None:
    bad_json = '{"summary": "ok", "code_fix": "ok", "config_change": "ok", "confidence": 1.5, "risks": "ok"}'
    result = _try_parse_json(bad_json, source="provider")
    assert result is None


def test_try_parse_json_empty_string_returns_none() -> None:
    result = _try_parse_json("", source="provider")
    assert result is None


# ---------------------------------------------------------------------------
# _try_parse_sections — Stage 2 (legacy fallback)
# ---------------------------------------------------------------------------

SECTION_RESPONSE = """SUMMARY:
Unhandled exception detected in request lifecycle.

CODE_FIX:
Add try/except around the failing call.

CONFIG_CHANGE:
Set LOG_LEVEL=INFO.

CONFIDENCE:
0.70

RISKS:
Validate fix in staging first."""


def test_try_parse_sections_valid_returns_suggestion() -> None:
    suggestion = _try_parse_sections(SECTION_RESPONSE, source="provider")
    assert suggestion is not None
    assert "Unhandled exception" in suggestion.summary
    assert suggestion.confidence == 0.70


def test_try_parse_sections_no_sections_returns_none() -> None:
    result = _try_parse_sections("random text with no sections", source="provider")
    assert result is None


# ---------------------------------------------------------------------------
# _parse_llm_output — full fallback chain
# ---------------------------------------------------------------------------


def test_parse_llm_output_stage1_json_succeeds() -> None:
    suggestion = _parse_llm_output(VALID_JSON_RESPONSE, source="provider")
    assert suggestion.source == "provider"
    assert suggestion.provider_error is None
    assert suggestion.confidence == 0.85


def test_parse_llm_output_stage2_section_fallback() -> None:
    suggestion = _parse_llm_output(SECTION_RESPONSE, source="provider")
    assert suggestion is not None
    assert suggestion.confidence == 0.70


def test_parse_llm_output_stage3_stub_last_resort() -> None:
    suggestion = _parse_llm_output(
        "completely unparseable gibberish @@##", source="provider"
    )
    assert suggestion.source == "fallback"
    assert suggestion.provider_error is not None
    assert suggestion.confidence == 0.1


# ---------------------------------------------------------------------------
# StubLLMClient — still valid
# ---------------------------------------------------------------------------


def test_stub_llm_client_returns_valid_suggestion() -> None:
    client = StubLLMClient()
    incident = _make_incident()
    suggestion = client.analyze_incident(incident)
    assert suggestion.source == "stub"
    assert 0.0 <= suggestion.confidence <= 1.0
    assert suggestion.summary
    assert suggestion.proposed_code_fix


# ---------------------------------------------------------------------------
# Milestone 2 — proposed_patch and test_guidance
# ---------------------------------------------------------------------------


def test_stub_returns_proposed_patch() -> None:
    client = StubLLMClient()
    suggestion = client.analyze_incident(_make_incident())
    assert suggestion.proposed_patch is not None
    assert "try" in suggestion.proposed_patch


def test_stub_returns_test_guidance() -> None:
    client = StubLLMClient()
    suggestion = client.analyze_incident(_make_incident())
    assert suggestion.test_guidance is not None
    assert len(suggestion.test_guidance) > 10


def test_json_parse_includes_patch_and_guidance() -> None:
    json_with_patch = """{
  "summary": "Error in handler.",
  "code_fix": "Add try/except.",
  "config_change": "Set LOG_LEVEL=INFO.",
  "confidence": 0.80,
  "risks": "Test in staging first.",
    "patch_file": "src/services/handler.py",
  "proposed_patch": "try:\\n    process()\\nexcept Exception as e:\\n    raise HTTPException(500)",
  "test_guidance": "1. Mock process() to raise. 2. Assert 500 returned."
}"""
    suggestion = _try_parse_json(json_with_patch, source="provider")
    assert suggestion is not None
    assert suggestion.proposed_patch is not None
    assert "process()" in suggestion.proposed_patch
    assert suggestion.test_guidance is not None


def test_fallback_patch_fields_are_none() -> None:
    suggestion = _parse_llm_output("completely unparseable @@##", source="provider")
    assert suggestion.source == "fallback"
    assert suggestion.proposed_patch is None
    assert suggestion.test_guidance is None
