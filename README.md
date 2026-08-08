[![CI](https://github.com/Ebencode-x/sentinai-project/actions/workflows/ci.yml/badge.svg)](https://github.com/Ebencode-x/sentinai-project/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-686%20passing-brightgreen)]()
[![Release](https://img.shields.io/badge/release-v0.1.0-teal)](https://github.com/Ebencode-x/sentinai-project/releases/tag/v0.1.0)
[![License](https://img.shields.io/badge/license-MIT-green)]()

# SentinAI — Self-Healing DevOps Agent

> **Detects production failures. Calls an LLM. Fires a Slack alert with a proposed code patch — before your on-call engineer opens their laptop.**

No manual triage. No copy-pasting stack traces into ChatGPT. No missed alerts at 3 AM.

---

## What It Does

SentinAI watches your application logs in real time. The moment it sees an error, it:

1. Aggregates the full stack trace into a structured incident
2. Sends it to an LLM (Claude or OpenAI) for analysis
3. Gets back a structured remediation plan — summary, code fix, config change, confidence score, risks, a concrete unified diff patch, and unit-test guidance
4. Fires a rich Slack alert and/or a generic webhook payload your existing tools can consume
5. Exposes everything over a REST API with live observability metrics — including a Prometheus `/metrics` endpoint ready for Grafana

---

## Architecture

```
┌─────────────────────┐
│   Vulnerable App    │  generates ERROR / EXCEPTION / 500
│   :9000             │
└────────┬────────────┘
         │ writes to
         ▼
┌─────────────────────┐
│   logs/app.log      │
└────────┬────────────┘
         │ tailed by
         ▼
┌──────────────────────────────────────────────────────────┐
│  SentinAI Core  :8000                                    │
│                                                          │
│  LogWatcher ──► IncidentNormalizer ──► RemediationEngine │
│                      │                       │           │
│               fingerprint +            LLM adapter       │
│               dedup window         (Claude / OpenAI /    │
│                                         stub)            │
│                                          │               │
│                                  ┌───────┴────────┐      │
│                                  │  Slack alert   │      │
│                                  │  GitHub PR     │      │
│                                  │  REST API      │      │
│                                  └────────────────┘      │
└──────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Status |
|---|---|
| Real-time log watching (inode-safe rotation) | ✅ |
| Incident deduplication + fingerprinting | ✅ |
| Claude (Haiku/Sonnet) analysis | ✅ |
| OpenAI (GPT-4o-mini) analysis | ✅ |
| SmartStub mode — offline fallback, no API key required | ✅ |
| Prompt caching (90% cost reduction) | ✅ |
| Structured JSON remediation output | ✅ |
| Unified diff patch generation | ✅ |
| AST-level semantic patch validation | ✅ |
| Prompt injection defense (6 pattern categories) | ✅ |
| Unit-test guidance per incident | ✅ |
| Slack rich alert | ✅ |
| GitHub PR auto-creation | ✅ |
| Prometheus `/metrics` endpoint | ✅ |
| FastAPI REST API | ✅ |
| AI assistant chat (SSE streaming) | ✅ |
| Real-time observability charts | ✅ |
| Immutable JSONL audit log | ✅ |
| Desktop app — Windows (Tauri) | ✅ |
| CI/CD (GitHub Actions) | ✅ |
| 686 tests, 100% passing | ✅ |

---

## Quick Start

### Option A — Docker (recommended)

```bash
git clone https://github.com/Ebencode-x/sentinai-project.git
cd sentinai-project
cp .env.example .env          # add your API keys
docker-compose up
```

API is live at `http://localhost:8000`

### Option B — Python

```bash
git clone https://github.com/Ebencode-x/sentinai-project.git
cd sentinai-project
pip install -r requirements.txt
cp .env.example .env          # add your API keys
uvicorn src.main:app --reload
```

### Option C — Windows Desktop App

Download `SentinAI_0.1.0_x64-setup.exe` from the [latest release](https://github.com/Ebencode-x/sentinai-project/releases/tag/v0.1.0) and run the installer.

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```env
# LLM Provider: anthropic | openai | stub
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Slack (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# GitHub PR auto-creation (optional)
GITHUB_TOKEN=ghp_...
GITHUB_REPO=your-org/your-repo

# SentinAI API key (set to anything for local dev)
SENTINAI_API_KEY=sk-sentinai-dev-local
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness + dependency checks |
| GET | `/incidents` | List recent incidents |
| GET | `/stats` | Metrics snapshot |
| POST | `/scan-now` | Trigger manual scan |
| POST | `/api/chat` | AI assistant (SSE streaming) |
| GET | `/metrics` | Prometheus metrics |

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=src
```

686 tests across unit, integration, and end-to-end suites.

---

## Project Structure

```
sentinai-project/
├── src/
│   ├── api/          # FastAPI routes (auth, chat, incidents, health)
│   ├── core/         # Config, metrics, rate limiter, state
│   ├── integrations/ # LLM clients, GitHub, Slack, notifier
│   ├── models/       # Pydantic event models
│   └── services/     # LogWatcher, RemediationEngine, pipeline
├── sentinai/
│   └── llm/          # Provider-agnostic LLM abstraction layer
├── src-tauri/        # Tauri desktop app (Windows/macOS/Linux)
├── frontend/         # React + Vite dashboard
├── tests/            # 686 tests
├── docker-compose.yml
└── Dockerfile
```

---

## Roadmap

- [ ] Railway / AWS deployment
- [ ] Multi-tenant API (teams + quota)
- [ ] Grafana dashboard template
- [ ] macOS + Linux desktop builds
- [ ] React Native mobile app
- [ ] Product Hunt launch

---

## Built By

**Ebenezer Richard Masanja** — First-year ICT student, Mbeya University of Science and Technology (MUST), Tanzania.

> *"I started learning Python a few months ago. This is what happened."*

[![GitHub](https://img.shields.io/badge/GitHub-Ebencode--x-181717?style=flat-square&logo=github)](https://github.com/Ebencode-x)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-ebenezer--masanja-0A66C2?style=flat-square&logo=linkedin)](https://www.linkedin.com/in/ebenezer-masanja/)

---

---
## License
MIT — free to use, modify, and distribute.

<!-- rollback smoke test marker: safe to remove -->
