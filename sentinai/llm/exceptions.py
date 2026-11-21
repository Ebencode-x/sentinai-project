"""Provider-level exceptions — never leak raw SDK errors to callers."""


class LLMError(Exception):
    """Base for all LLM provider errors."""


class LLMAuthError(LLMError):
    """Invalid or missing API key."""


class LLMRateLimitError(LLMError):
    """Provider rate-limit hit."""


class LLMTimeoutError(LLMError):
    """Request timed out."""


class LLMProviderError(LLMError):
    """Unrecoverable provider-side error (5xx, unexpected schema, etc.)."""


class LLMServerError(LLMProviderError):
    """Transient provider failure (5xx or network error). Safe to retry."""


class LLMCircuitOpenError(LLMProviderError):
    """The circuit breaker for this provider is open; the call was not attempted."""


TRANSIENT_ERRORS: tuple[type[LLMError], ...] = (
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServerError,
)


class LLMUnsupportedFeatureError(LLMError):
    """Called a method the chosen provider does not support."""
