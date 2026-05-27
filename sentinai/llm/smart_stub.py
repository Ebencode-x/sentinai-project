"""Smart stub provider — intelligent offline responses for DevOps/security queries."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sentinai.llm.base import LLMProvider, LLMRequest, LLMResponse


_RESPONSES: list[tuple[tuple[str, ...], str]] = [
    (
        ("hello", "hi", "hey", "who are you", "what are you"),
        "I\'m SentinAI Assistant — your AI-powered security operations analyst. "
        "I monitor your system logs, detect anomalies, and provide actionable remediation guidance. "
        "Ask me about your incidents, system health, scan results, or DevOps best practices.",
    ),
    (
        ("incident", "incidents", "open", "critical", "alert", "alerts"),
        "Based on live system state: I can see your current incident queue. "
        "Critical incidents require immediate triage — check severity levels and trigger lines. "
        "For each open incident, review the proposed remediation and apply the patch after validation. "
        "Run `POST /scan-now` to trigger a fresh scan cycle.",
    ),
    (
        ("scan", "scanning", "scan-now", "log", "logs", "detect", "detection"),
        "SentinAI scans your application logs continuously, detecting ERROR, EXCEPTION, "
        "and HTTP 5xx signals. Each scan run deduplicates incidents using a fingerprint window "
        "to prevent alert fatigue. Trigger a manual scan via `POST /scan-now` with your API key. "
        "Check `/stats` for scan cadence and last run timestamp.",
    ),
    (
        ("health", "status", "ready", "live", "uptime", "running"),
        "System health checks: pipeline state, metrics collector, disk space, audit logger, "
        "and LLM client are all verified on `/health/ready`. "
        "If any check fails, inspect container logs immediately. "
        "Disk minimum threshold is 100MB — ensure log rotation is configured.",
    ),
    (
        ("fix", "patch", "remediation", "suggest", "suggestion", "code", "error"),
        "Remediation workflow: SentinAI analyzes each incident and generates a structured suggestion "
        "containing a code fix, config change, unified diff patch, and test guidance. "
        "Confidence scores range 0.0–1.0. Apply patches with confidence > 0.7 after peer review. "
        "Always run the suggested unit tests before deploying to production.",
    ),
    (
        ("security", "vulnerability", "exploit", "attack", "threat", "risk"),
        "Security posture: SentinAI monitors for authentication failures, injection patterns, "
        "privilege escalation attempts, and anomalous request rates. "
        "For critical security incidents, isolate the affected service immediately, "
        "rotate credentials, and audit access logs. "
        "Apply defense-in-depth — WAF, rate limiting, and input validation at every layer.",
    ),
    (
        ("docker", "container", "deploy", "deployment", "kubernetes", "k8s"),
        "Container deployment: SentinAI runs as a Docker container (`ebencodex/sentinai:latest`). "
        "Set `SENTINAI_API_KEY`, `ANTHROPIC_API_KEY`, and `LLM_PROVIDER=claude` as environment secrets. "
        "For Kubernetes, use a Secret resource — never embed credentials in ConfigMaps. "
        "Health probe: `GET /health/live` for liveness, `GET /health/ready` for readiness.",
    ),
    (
        ("api", "endpoint", "route", "request", "curl", "http"),
        "SentinAI API endpoints: `/health` (public), `/health/ready`, `/stats`, `/incidents`, "
        "`/suggestions`, `/suggestions/latest`, `/scan-now`, `/chat`, `/metrics`. "
        "All protected endpoints require `X-API-Key` header. "
        "Full interactive docs available at `/docs` (Swagger UI) and `/redoc`.",
    ),
    (
        ("metric", "metrics", "performance", "latency", "p95", "p99"),
        "LLM metrics tracked: total suggestions, fallback rate, average latency, p95, p99. "
        "High fallback rates indicate LLM parsing issues — check provider logs. "
        "Target p95 latency < 3000ms for incident analysis. "
        "Use `/metrics` endpoint for Prometheus-compatible scraping.",
    ),
    (
        ("config", "configuration", "env", "environment", "secret", "variable"),
        "Required environment variables: `SENTINAI_API_KEY` (auth), `ANTHROPIC_API_KEY` (LLM), "
        "`LLM_PROVIDER=claude`, `LLM_MODEL`, `LOG_FILE_PATH`, `MAX_RECENT_INCIDENTS`. "
        "Optional: `SENTINAI_SLACK_WEBHOOK_URL` for Slack notifications, "
        "`SENTINAI_GENERIC_WEBHOOK_URL` for custom integrations. "
        "Never commit secrets to version control — use HF Secrets or Docker env flags.",
    ),
]

_FALLBACK = (
    "I\'m SentinAI Assistant operating in offline mode. "
    "I can help with: incident triage, log analysis, remediation guidance, "
    "security best practices, API usage, and deployment configuration. "
    "Ask me something specific about your system or DevOps workflow."
)


def _match_response(question: str) -> str:
    q = question.lower()
    for keywords, response in _RESPONSES:
        if any(kw in q for kw in keywords):
            return response
    return _FALLBACK


@dataclass
class SmartStubProvider(LLMProvider):
    """Intelligent offline provider with DevOps/security domain knowledge.

    Zero network calls. Keyword-matched responses with Silicon Valley quality.
    Activates automatically when ANTHROPIC_API_KEY is unavailable.
    """

    provider_name: str = "smart_stub"
    calls: list[LLMRequest] = field(default_factory=list)

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        user_msg = next(
            (m.content for m in request.messages if m.role == "user"), ""
        )
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
        user_msg = next(
            (m.content for m in request.messages if m.role == "user"), ""
        )
        response = _match_response(user_msg)
        words = response.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.02)
