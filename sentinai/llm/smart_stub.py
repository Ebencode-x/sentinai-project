"""Smart stub provider — intelligent offline responses for DevOps/security queries."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sentinai.llm.base import LLMProvider, LLMRequest, LLMResponse

_DEMO_NOTICE = "\n\n[Demo mode — connect ANTHROPIC_API_KEY for live AI-powered analysis.]"

_RESPONSES: list[tuple[tuple[str, ...], str]] = [
    (
        ("hello", "hi", "hey", "who are you", "what are you", "introduce", "about"),
        "I'm SentinAI Assistant — your AI-powered security operations analyst. "
        "I monitor logs, detect anomalies, classify incidents by severity, "
        "and generate actionable remediation steps with confidence scores. "
        "Ask me about incidents, health, scan results, API usage, or DevOps practices.",
    ),
    (
        (
            "incident",
            "incidents",
            "open",
            "critical",
            "high",
            "medium",
            "low",
            "alert",
            "alerts",
            "triage",
            "queue",
            "active",
            "unresolved",
        ),
        "Incident triage: SentinAI classifies incidents as critical/high/medium/low. "
        "Critical incidents require immediate action — isolate the affected service, "
        "review the trigger line, and apply the generated patch. "
        "Open incidents appear on your dashboard with severity badges and timestamps. "
        "Use POST /scan-now to trigger a fresh detection cycle.",
    ),
    (
        (
            "scan",
            "scanning",
            "scan-now",
            "log",
            "logs",
            "detect",
            "detection",
            "monitor",
            "monitoring",
            "tail",
            "watcher",
            "pipeline",
        ),
        "SentinAI scans logs continuously using a real-time watcher. "
        "It detects ERROR, EXCEPTION, CRITICAL, and HTTP 5xx signals. "
        "Each scan deduplicates incidents via fingerprint window to prevent alert fatigue. "
        "Trigger manual scan: POST /scan-now with X-API-Key header. "
        "Check /stats for total scan runs, last timestamp, and detection rates.",
    ),
    (
        (
            "health",
            "status",
            "ready",
            "live",
            "uptime",
            "running",
            "ping",
            "alive",
            "connected",
            "connection",
        ),
        "Health endpoints: GET /health/live for liveness, GET /health/ready for full check. "
        "Readiness verifies pipeline, metrics, disk, audit logger, and LLM client. "
        "All checks return JSON: status ok | degraded | error. "
        "Disk minimum threshold is 100MB — configure log rotation to prevent exhaustion. "
        "Health probes are Kubernetes-compatible.",
    ),
    (
        (
            "fix",
            "patch",
            "remediation",
            "suggest",
            "suggestion",
            "resolve",
            "solution",
            "repair",
            "code",
            "diff",
            "apply",
        ),
        "Remediation workflow: SentinAI generates a suggestion per incident containing "
        "a code fix, unified diff patch, and test guidance. "
        "Confidence scores range 0.0-1.0. Apply patches with confidence > 0.7 "
        "after peer review. Review at GET /suggestions or /suggestions/latest. "
        "AST-based semantic validation blocks unsafe patches automatically.",
    ),
    (
        (
            "security",
            "vulnerability",
            "exploit",
            "attack",
            "threat",
            "risk",
            "auth",
            "authentication",
            "injection",
            "xss",
            "sqli",
            "csrf",
        ),
        "Security posture: SentinAI monitors for auth failures, injection patterns, "
        "privilege escalation, and anomalous request rates. "
        "PatchSemanticValidator enforces AUTH, PRIV, SEC, TAINT rule sets. "
        "For critical incidents: isolate service, rotate credentials, audit access logs. "
        "Defense-in-depth: rate limiting, input validation, security headers at every layer.",
    ),
    (
        (
            "docker",
            "container",
            "deploy",
            "deployment",
            "kubernetes",
            "k8s",
            "helm",
            "image",
            "registry",
            "compose",
        ),
        "Deployment: SentinAI runs as ebencodex/sentinai:latest on Docker Hub. "
        "Required env vars: SENTINAI_API_KEY, ANTHROPIC_API_KEY, LLM_PROVIDER=claude. "
        "Container runs as non-root (UID 1001) with read-only filesystem. "
        "For Kubernetes: use Secret resources, never ConfigMaps for credentials. "
        "Expose port 7860. Liveness: GET /health/live | Readiness: GET /health/ready.",
    ),
    (
        (
            "api",
            "endpoint",
            "route",
            "request",
            "curl",
            "http",
            "swagger",
            "docs",
            "redoc",
            "openapi",
        ),
        "SentinAI REST API — all endpoints require X-API-Key header except /health. "
        "Key routes: GET /incidents, GET /suggestions, POST /scan-now, POST /chat, "
        "GET /stats, GET /metrics, GET /health/live, GET /health/ready. "
        "Interactive docs: /docs (Swagger UI) and /redoc. "
        "Rate limiting: per-tenant token bucket, 100 req/min default.",
    ),
    (
        (
            "metric",
            "metrics",
            "performance",
            "latency",
            "p95",
            "p99",
            "prometheus",
            "grafana",
            "throughput",
        ),
        "Metrics: SentinAI tracks suggestion count, fallback rate, avg latency, p95, p99. "
        "Target p95 latency < 3000ms for incident analysis. "
        "GET /metrics returns Prometheus-compatible format for Grafana scraping. "
        "Set up Grafana Cloud free tier with /metrics endpoint for real-time dashboards.",
    ),
    (
        (
            "config",
            "configuration",
            "env",
            "environment",
            "secret",
            "setup",
            "install",
            "integrate",
            "webhook",
            "slack",
        ),
        "Required env vars: SENTINAI_API_KEY, ANTHROPIC_API_KEY, LLM_PROVIDER=claude. "
        "Optional: SENTINAI_SLACK_WEBHOOK_URL for Slack alerts, "
        "SENTINAI_GENERIC_WEBHOOK_URL for custom integrations, "
        "MAX_RECENT_INCIDENTS (default 100), LLM_TIMEOUT_SECONDS (default 25). "
        "Never commit secrets to version control.",
    ),
    (
        ("rate", "limit", "throttle", "quota", "bucket", "429", "too many"),
        "Rate limiting: per-tenant token bucket algorithm. "
        "Default: 100 requests/minute per API key. "
        "Exceeding limit returns HTTP 429 with Retry-After header. "
        "Implement exponential backoff on 429 responses for high-volume integrations.",
    ),
    (
        ("cost", "price", "pricing", "billing", "usage", "expensive", "token"),
        "Cost optimization: SentinAI uses Claude Haiku by default — "
        "the most cost-efficient Anthropic model for real-time operations. "
        "Prompt caching enabled for system prompts — reduces token usage up to 90%. "
        "Monitor consumption via /stats and set MAX_RECENT_INCIDENTS to control costs.",
    ),
    (
        ("test", "testing", "pytest", "ci", "pipeline", "coverage", "unit"),
        "CI pipeline: pytest + coverage (686 tests), ruff linting, bandit security analysis. "
        "Coverage enforced at 80%+ threshold. "
        "Pre-commit: ruff check . --fix && ruff format . && pytest tests/ -q. "
        "All generated patches include test guidance for safe deployment.",
    ),
]

_FALLBACK = (
    "I'm SentinAI Assistant — your DevOps security operations analyst. "
    "I can help with: incident triage, log analysis, remediation patches, "
    "security response, API usage, container deployment, and observability. "
    "Try: 'What incidents are open?' or 'How do I configure webhooks?'"
)


_BLOCKED_PATTERNS = (
    "api key",
    "apikey",
    "secret",
    "password",
    "token",
    "credential",
    "env",
    "environment variable",
    "print all",
    "reveal",
    "show me all",
    "ignore previous",
    "ignore all",
    "dan",
    "jailbreak",
    "bypass",
    "system prompt",
    "your instructions",
    "what are you told",
    "anthropic engineer",
    "admin",
    "root access",
    "sudo",
)

_BLOCKED_RESPONSE = (
    "I cannot help with that request. "
    "SentinAI Assistant is scoped to DevOps security operations only: "
    "incident triage, log analysis, remediation, and observability. "
    "Attempts to extract credentials or bypass system rules are logged."
)


def _is_blocked(question: str) -> bool:
    q = question.lower()
    return any(pattern in q for pattern in _BLOCKED_PATTERNS)


def _match_response(question: str) -> str:
    if _is_blocked(question):
        return _BLOCKED_RESPONSE + _DEMO_NOTICE
    q = question.lower()
    for keywords, response in _RESPONSES:
        if any(kw in q for kw in keywords):
            return response + _DEMO_NOTICE
    return _FALLBACK + _DEMO_NOTICE


@dataclass
class SmartStubProvider(LLMProvider):
    """Offline provider with DevOps/security domain knowledge.

    Zero network calls. Keyword-matched responses.
    Activates automatically when ANTHROPIC_API_KEY is unavailable or placeholder.
    """

    provider_name: str = "smart_stub"
    calls: list[LLMRequest] = field(default_factory=list)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        user_msg = next((m.content for m in request.messages if m.role == "user"), "")
        response = _match_response(user_msg)
        return LLMResponse(
            content=response,
            model="smart-stub-v1",
            provider=self.provider_name,
            input_tokens=len(user_msg.split()),
            output_tokens=len(response.split()),
            latency_ms=12.0,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        self.calls.append(request)
        user_msg = next((m.content for m in request.messages if m.role == "user"), "")
        response = _match_response(user_msg)
        words = response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.02)
