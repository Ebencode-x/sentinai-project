"""The incident is cleaned once, at the door to the model."""

from datetime import UTC, datetime

from src.integrations.llm_client import StubLLMClient
from src.models.events import LogIncident
from src.services.incident_redaction import redact_incident, redact_text
from src.services.remediation_engine import RemediationEngine

KEY = "sk-ant-api03-" + "Zx9Yw8Vu7Ts6Rq5Po4Nm3Lk2Ji1Hg0Fe9Dc8Ba7"
DB_URL = "postgresql://user:Sup3rS3cret@db.host.com:5432/postgres"

TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "/app/src/services/event_processor.py", line 93, in to_incident\n'
    "    return LogIncident(\n"
    "sqlalchemy.exc.OperationalError: connection to server at db.host.com failed"
)


def make_incident(**changes) -> LogIncident:
    data = {
        "incident_id": "abc123def4567890",
        "detected_at_utc": datetime(2026, 11, 13, tzinfo=UTC),
        "trigger_line": "ValueError: bad value",
        "stacktrace": "ValueError: bad value",
        "context_before_error": "",
    }
    data.update(changes)
    return LogIncident(**data)


def test_secrets_are_removed_from_all_three_fields():
    incident = make_incident(
        trigger_line=f"auth failed for {KEY}",
        stacktrace=f"connect to {DB_URL} failed",
        context_before_error=f"using key {KEY}",
    )
    cleaned, count = redact_incident(incident)
    assert count >= 3
    for text in (cleaned.trigger_line, cleaned.stacktrace, cleaned.context_before_error):
        assert KEY not in text
        assert "Sup3rS3cret" not in text
    assert cleaned.incident_id == incident.incident_id


def test_clean_incident_comes_back_unchanged():
    incident = make_incident()
    cleaned, count = redact_incident(incident)
    assert count == 0
    assert cleaned is incident


def test_ordinary_traceback_is_not_touched():
    cleaned, count = redact_text(TRACEBACK)
    assert count == 0
    assert cleaned == TRACEBACK


class CapturingClient(StubLLMClient):
    seen = None

    def analyze_incident(self, incident):
        self.seen = incident
        return super().analyze_incident(incident)


def test_engine_gives_the_model_a_clean_incident():
    client = CapturingClient()
    engine = RemediationEngine(llm_client=client)
    engine.suggest_fix(make_incident(trigger_line=f"auth failed for {KEY}"))
    assert client.seen is not None
    assert KEY not in client.seen.trigger_line
