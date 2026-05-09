# SentinAI — Self-Healing DevOps Agent

> **Detects production failures. Calls an LLM. Fires a Slack alert with a proposed code patch — before your on-call engineer opens their laptop.**

[![CI](https://github.com/Ebencode-x/sentinai-project/actions/workflows/ci.yml/badge.svg)](https://github.com/Ebencode-x/sentinai-project/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-72%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

---

## What It Does

SentinAI watches your application logs in real time. The moment it sees an error, it:

1. Aggregates the full stack trace into a structured incident
2. Sends it to an LLM (OpenAI or Claude) for analysis
3. Gets back a structured remediation plan — summary, code fix, config change, confidence score, risks, a concrete patch, and unit-test guidance
4. Fires a rich Slack alert and/or a generic webhook payload your existing tools can consume
5. Exposes everything over a REST API with live observability metrics — including a Prometheus `/metrics` endpoint ready for Grafana

No manual triage. No copy-pasting stack traces into ChatGPT. No missed alerts at 3 AM.

---

## Architecture

```
┌─────────────────────┐
│  Vulnerable App      │  generates ERROR / EXCEPTION / 500
│  :9000               │
└────────┬────────────┘
         │ writes to
         ▼
┌─────────────────────┐
│  logs/app.log        │
└────────┬────────────┘
         │ tailed by
         ▼
┌─────────────────────────────────────────────────────────┐
│  SentinAI Core  :8000                                    │
│                                                          │
│  LogWatcher ──► IncidentNormalizer ──► RemediationEngine │
│                      │                       │           │
│               fingerprint +            LLM adapter       │
│               dedup window         (OpenAI / Claude /    │
│                                         stub)            │
│                                          │               │
│                                    ┌─────▼──────┐        │
│                                    │  Notifier   │        │
│                                    │  Slack  ✓  │        │
│                                    │  Webhook ✓ │        │
│                                    └────────────┘        │
│                                                          │
│  REST API: /health /stats /incidents /suggestions        │
│  MetricsCollector: p95 latency · fallback_rate           │
│  Prometheus: GET /metrics  (Grafana-ready)               │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Real-Time Log Detection

Tails `logs/app.log` continuously with a poll-and-seek strategy. Detects `ERROR`, `EXCEPTION`, `Traceback`, and `500` signals. Aggregates multiline Python stack traces into a single structured incident automatically.

### Structured LLM Analysis

Every incident is sent to the configured LLM provider. The response is validated against a strict Pydantic schema — no fragile string parsing, no silent failures. The schema enforces:

```json
{
  "summary": "Unhandled exception in request handler.",
  "code_fix": "Wrap handler in try/except and return 500 with safe message.",
  "config_change": "Set LOG_LEVEL=INFO in production.",
  "confidence": 0.85,
  "risks": "Ensure catch block does not swallow critical errors silently.",
  "proposed_patch": "try:\n    process()\nexcept Exception as e:\n    raise HTTPException(500)",
  "test_guidance": "1. Mock process() to raise. 2. Assert HTTP 500 returned."
}
```

If the LLM returns malformed output, a 3-stage fallback chain handles it: JSON parse → section parser → stub summary. The API never returns empty.

### Smart Notifications

Routing is severity-aware — not every alert fires everywhere:

| Severity | Slack | Generic Webhook |
|---|---|---|
| `critical` | ✅ immediate | ✅ immediate |
| `warning` | ✅ immediate | — |
| confidence < 0.5 | ⚠️ flagged | ⚠️ flagged |
| source = fallback | 🔴 flagged | 🔴 flagged |

Slack alerts use Block Kit — the same format Datadog and Linear use. Each alert includes the incident ID, trigger line, LLM summary, proposed fix, a visual confidence bar, and a patch preview.

The generic webhook fires a structured JSON payload consumable by PagerDuty, n8n, Zapier, Linear, or any HTTP-capable tool — no custom parser needed.

### Observability Metrics

`GET /stats` returns live runtime metrics:

```json
{
  "service": "sentinai",
  "llm_provider": "openai",
  "buffer_incident_count": 12,
  "total_scan_runs": 340,
  "recent_suggestions_by_source": {
    "stub": 0,
    "provider": 11,
    "fallback": 1
  },
  "llm_metrics": {
    "total_suggestions": 12,
    "total_fallbacks": 1,
    "fallback_rate": 0.0833,
    "avg_latency_ms": 1243.5,
    "p95_latency_ms": 2180.0,
    "p99_latency_ms": 2340.0,
    "latency_sample_count": 12
  }
}
```

### Prometheus Metrics Endpoint

`GET /metrics` exposes the same data in Prometheus text exposition format — ready to scrape with Prometheus and visualize in Grafana:

```
# HELP sentinai_llm_requests_total Total LLM requests made
# TYPE sentinai_llm_requests_total counter
sentinai_llm_requests_total 12.0

# HELP sentinai_llm_fallbacks_total Total LLM fallback responses
# TYPE sentinai_llm_fallbacks_total counter
sentinai_llm_fallbacks_total 1.0

# HELP sentinai_llm_latency_p95_ms 95th percentile LLM latency in milliseconds
# TYPE sentinai_llm_latency_p95_ms gauge
sentinai_llm_latency_p95_ms 2180.0

# HELP sentinai_llm_latency_p99_ms 99th percentile LLM latency in milliseconds
# TYPE sentinai_llm_latency_p99_ms gauge
sentinai_llm_latency_p99_ms 2340.0

# HELP sentinai_fallback_rate Current LLM fallback rate (0.0–1.0)
# TYPE sentinai_fallback_rate gauge
sentinai_fallback_rate 0.0833
```

Add SentinAI as a Prometheus scrape target and you get latency trends, fallback spikes, and request volume in Grafana with zero additional instrumentation.

### Incident Deduplication

Incidents are fingerprinted with SHA-256. Repeated log lines are skipped within a configurable sliding window (`INCIDENT_DEDUPE_WINDOW`, default 200) so repeated failures don't spam your Slack channel.

### Provider Resilience

All LLM HTTP calls retry transient errors (429, 5xx, timeouts) with exponential backoff. If all retries fail, `RemediationEngine` returns a `fallback` suggestion with `provider_error` populated — the API never breaks, alerts still fire.

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/Ebencode-x/sentinai-project.git
cd sentinai-project
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Use stub (no API key needed) or plug in a real provider
LLM_PROVIDER=stub           # stub | openai | claude
LLM_API_KEY=                # your OpenAI or Anthropic key
LLM_MODEL=gpt-4o-mini       # or claude-sonnet-4-20250514

# Optional: enable Slack alerts
SENTINAI_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional: generic webhook for PagerDuty / n8n / Zapier
SENTINAI_GENERIC_WEBHOOK_URL=https://your-tool.com/webhook
```

### 3. Run SentinAI

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Run the vulnerable app (error generator)

```bash
uvicorn vulnerable-app.app:app --reload --host 0.0.0.0 --port 9000
```

### 5. Trigger incidents

```bash
# Hit the vulnerable endpoint a few times
curl http://localhost:9000/boom

# Manually trigger a scan
curl -X POST http://localhost:8000/scan-now

# See what was detected
curl http://localhost:8000/suggestions/latest | python -m json.tool

# Scrape Prometheus metrics
curl http://localhost:8000/metrics
```

---

## Docker

```bash
docker compose up --build
```

Boots both services — SentinAI on `:8000`, vulnerable app on `:9000`.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service readiness check |
| `GET` | `/stats` | Live runtime metrics — latency, fallback rate, scan counts |
| `GET` | `/metrics` | Prometheus text exposition format — scrape with Prometheus/Grafana |
| `GET` | `/incidents` | All detected incidents in the current buffer |
| `GET` | `/suggestions` | All LLM suggestions in the current buffer |
| `GET` | `/suggestions/latest` | Most recent suggestion (404 if none yet) |
| `POST` | `/scan-now` | Manually trigger a log scan |

---

## Project Structure

```
sentinai-project/
├── src/
│   ├── api/
│   │   └── routes.py              # FastAPI route handlers (incl. /metrics)
│   ├── core/
│   │   ├── config.py              # Environment-backed settings
│   │   ├── metrics.py             # Thread-safe MetricsCollector + Prometheus instruments
│   │   └── state.py               # Shared runtime state + scan loop
│   ├── integrations/
│   │   ├── github_client.py       # Opens auto-patch PRs on GitHub (M6)
│   │   ├── llm_client.py          # LLM adapters + 3-stage fallback parser
│   │   └── notifier.py            # Slack Block Kit + generic webhook
│   ├── models/
│   │   └── events.py              # LogIncident + RemediationSuggestion
│   ├── services/
│   │   ├── remediation_engine.py  # LLM orchestration + latency tracking
│   │   └── watcher.py             # Log tailer + stack trace aggregator
│   └── main.py
├── tests/
│   ├── test_watcher.py                       # M1 + M2: 19 tests
│   ├── test_notifications_and_metrics.py     # M3 + M4: 32 tests
│   └── test_prometheus_metrics.py            # M5: 9 tests
├── vulnerable-app/
│   └── app.py                     # Intentional error generator
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Test Suite

```bash
pytest -q

60 passed in 0.81s
```

| Module | Tests | Covers |
|---|---|---|
| `test_watcher.py` | 19 | Fence stripping, JSON parse, Pydantic validation, fallback chain, stub client, patch/guidance fields |
| `test_notifications_and_metrics.py` | 32 | MetricsCollector math, thread safety, notify routing, Slack Block Kit structure, webhook payload, HTTP mocking, error resilience |
| `test_prometheus_metrics.py` | 9 | Prometheus registry isolation, counter/gauge accuracy, `/metrics` response format, content-type header, zero-state output |
| `test_m6_auto_patch.py` | 12 | GitHubClient branch + PR creation, 422 branch-exists handling, Slack PR link block, RemediationEngine PR+Slack wiring |

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `stub` | `stub` · `openai` · `claude` |
| `LLM_API_KEY` | — | OpenAI or Anthropic API key |
| `LLM_MODEL` | — | Model name (e.g. `gpt-4o-mini`) |
| `LLM_TIMEOUT_SECONDS` | `25` | Per-request LLM timeout |
| `LLM_MAX_RETRIES` | `3` | Retry attempts on transient errors |
| `LLM_RETRY_BACKOFF_SECONDS` | `1.0` | Base backoff (doubles each retry) |
| `INCIDENT_DEDUPE_WINDOW` | `200` | Max fingerprints tracked for dedup |
| `MAX_RECENT_INCIDENTS` | `100` | In-memory buffer size |
| `SENTINAI_SLACK_WEBHOOK_URL` | — | Slack Incoming Webhook URL |
| `SENTINAI_GENERIC_WEBHOOK_URL` | — | Generic HTTP webhook target |
| `NOTIFICATION_TIMEOUT_SECONDS` | `8` | Per-notification request timeout |

---

## Milestones

| # | Feature | Status |
|---|---|---|
| 1 | Structured JSON LLM output with Pydantic validation + 3-stage fallback | ✅ Complete |
| 2 | `proposed_patch` and `test_guidance` fields in LLM schema and stub | ✅ Complete |
| 3 | Slack Block Kit alerts + generic HTTP webhook with severity routing | ✅ Complete |
| 4 | `MetricsCollector` — p95/p99 latency, fallback rate, live `/stats` | ✅ Complete |
| 5 | Prometheus `/metrics` endpoint for Grafana integration | ✅ Complete |
| 6 | Auto-patch PR workflow — GitHub branch + PR + Slack PR link notification | ✅ Complete |

---

## Security Notes

- Never auto-apply LLM-suggested patches in production without human review.
- Treat AI suggestions as hypotheses, not ground truth.
- Add RBAC and policy gates before any write action layer.
- Keep `LLM_API_KEY` out of version control — use `.env` locally, secrets manager in production.

---

## Built By

**Ebenezer** · ICT Student, Mbeya University of Science and Technology

[![GitHub](https://img.shields.io/badge/GitHub-Ebencode--x-181717?logo=github)](https://github.com/Ebencode-x)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin)](https://linkedin.com/in/ebenezer)
[![Credly](https://img.shields.io/badge/Credly-Certifications-FF6B00?logo=credly)](https://credly.com/users/ebenezer)

> *Cisco Cybersecurity · Endpoint Security · Network Defense · freeCodeCamp Responsive Web Design*
