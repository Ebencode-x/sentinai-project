"""One door for secrets: incident text is cleaned here before any model sees it."""

from src.models.events import LogIncident
from src.services.secret_sanitizer import SecretSanitizer

_SANITIZER = SecretSanitizer()

_TEXT_FIELDS = ("trigger_line", "stacktrace", "context_before_error")


def redact_text(text: str) -> tuple[str, int]:
    """Return the text with secrets masked and how many were found."""
    if not text:
        return text, 0
    result = _SANITIZER.sanitize(text)
    return result.text, len(result.redactions)


def redact_incident(incident: LogIncident) -> tuple[LogIncident, int]:
    """Return an incident whose free-text fields have no secrets, and the count.

    The incident_id is left alone, so deduplication is not affected.
    """
    updates: dict[str, str] = {}
    total = 0
    for name in _TEXT_FIELDS:
        value = getattr(incident, name, "")
        if not isinstance(value, str) or not value:
            continue
        cleaned, count = redact_text(value)
        total += count
        if cleaned != value:
            updates[name] = cleaned
    if not updates:
        return incident, 0
    return incident.model_copy(update=updates), total


# Ingest runs this on every event before it is fingerprinted and stored.
# Entropy detection is off here: ids, hashes and request tokens are normal in
# logs, and masking them would change fingerprints for no security gain.
_INGEST_SANITIZER = SecretSanitizer(entropy_detection=False)


def redact_known_secrets(text: str) -> str:
    """Mask named key formats only (no entropy guessing). Safe for fingerprints."""
    if not text:
        return text
    return _INGEST_SANITIZER.sanitize(text).text
