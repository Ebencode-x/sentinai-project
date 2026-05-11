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


class LLMUnsupportedFeatureError(LLMError):
    """Called a method the chosen provider does not support."""
