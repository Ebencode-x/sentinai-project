[![CI](https://github.com/Ebencode-x/sentinai-project/actions/workflows/ci.yml/badge.svg)](https://github.com/Ebencode-x/sentinai-project/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![Release](https://img.shields.io/badge/release-v0.1.0-teal)](https://github.com/Ebencode-x/sentinai-project/releases/tag/v0.1.0)
[![License](https://img.shields.io/badge/license-MIT-green)]()

# SentinAI: Self-Healing DevOps Agent

> **Detects production failures. Calls an LLM. Fires a Slack alert with a proposed code patch, before your on-call engineer opens their laptop.**

No manual triage. No copy-pasting stack traces into a chatbot. No missed alerts at 3 AM.

Live instance: [sentinai.onrender.com](https://sentinai.onrender.com) (free hosting, the first request after idle can take about a minute). Access needs an account, so to explore it yourself run it locally with the Quick Start below.

---

## What It Does

SentinAI watches your application logs in real time. The moment it sees an error, it:

1. Aggregates the full stack trace into a structured incident
2. Sends it to an LLM (Claude or OpenAI) for analysis
3. Gets back a structured remediation plan: summary, code fix, config change, confidence score, risks, a unified diff patch, and unit-test guidance
4. Records an audit entry for the incident
5. Fires a Slack alert and/or a generic webhook payload your existing tools can consume
6. Exposes everything through a REST API, a login-protected dashboard, and a Prometheus `/metrics` endpoint

By default SentinAI only proposes fixes. Opening pull requests automatically is an opt-in setting, and applied patches can be rolled back through a propose-then-confirm flow.

---

## Architecture

```
┌─────────────────────┐
│   Your application  │  generates ERROR / EXCEPTION / 500
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
│                                  │  Audit log     │      │
│                                  │  REST API      │      │
│                                  └────────────────┘      │
└──────────────────────────────────────────────────────────┘
```

Storage: accounts, sessions and audit events live in a SQL database (SQLite by default, Postgres in production, schema managed by Alembic). Incidents, suggestions, settings and the rollback ledger are kept in JSON files under `logs/`. The audit log is also appended to `logs/sentinai-audit.jsonl` as a fallback.

---

## Features

**Detection and analysis**
- Real-time log watching with rotation-safe tailing
- Incident deduplication and fingerprinting
- Claude and OpenAI providers behind one abstraction layer, plus a SmartStub mode that works offline with no API key
- Structured JSON remediation output with unified diff patches and unit-test guidance

**Safety**
- AST-level semantic patch validation
- Prompt injection defense
- Secret sanitizer (pattern and entropy based)
- Sandbox execution block
- Autonomy setting: "Propose only" (default) or "Auto-create GitHub PR"
- Rollback ledger for applied patches, admin only, propose then confirm

**Operations**
- Dashboard (React, TypeScript, Tailwind) with Overview, Incidents, Audit, Policy, Diff and Settings pages
- Multi-user accounts with `admin` and `viewer` roles and server-side session tokens
- Notification channels (Slack, webhook) with routing by incident severity
- Audit events stored in the database, so history survives redeploys
- AI assistant chat with SSE streaming
- Prometheus `/metrics` endpoint
- Windows desktop app (Tauri)
- CI on every push: pytest with coverage, ruff, bandit, ESLint, a production frontend build, then Docker image build and deploy

---

## Quick Start

### Option A: Docker (recommended)

```bash
git clone https://github.com/Ebencode-x/sentinai-project.git
cd sentinai-project
cp .env.example .env          # set the admin account and your keys
docker compose up
```

On first start SentinAI runs the database migrations and creates an admin account from `SENTINAI_ADMIN_EMAIL` and `SENTINAI_ADMIN_PASSWORD`. Open `http://localhost:8000` and sign in with it.

### Option B: Python

```bash
git clone https://github.com/Ebencode-x/sentinai-project.git
cd sentinai-project
pip install -r requirements.txt
cp .env.example .env          # set the admin account and your keys
(cd frontend && npm ci && npm run build)
uvicorn src.main:app --reload
```

### Option C: Windows Desktop App

Download `SentinAI_0.1.0_x64-setup.exe` from the [latest release](https://github.com/Ebencode-x/sentinai-project/releases/tag/v0.1.0) and run the installer.

---

## Configuration

Copy `.env.example` to `.env`. Everything has a default except the admin account and your provider key.

| Variable | Default | Description |
|---|---|---|
| `SENTINAI_ADMIN_EMAIL` | none | Email of the first admin, created on first start when no account exists |
| `SENTINAI_ADMIN_PASSWORD` | none | Password for that admin |
| `DATABASE_URL` | `sqlite:///./sentinai.db` | SQLAlchemy URL. Use a Postgres URL in production |
| `LLM_PROVIDER` | `stub` | `anthropic`, `openai` or `stub` |
| `ANTHROPIC_API_KEY` / `LLM_API_KEY` | empty | Provider key |
| `LLM_MODEL` | provider default | Optional model override |
| `LLM_TIMEOUT_SECONDS` | `25` | Per-request timeout |
| `LLM_MAX_RETRIES` | `3` | Retries before falling back |
| `LLM_RETRY_BACKOFF_SECONDS` | `1.0` | Delay between retries |
| `LOG_FILE_PATH` | `logs/app.log` | The log file SentinAI tails |
| `MAX_RECENT_INCIDENTS` | `100` | Incidents kept in memory |
| `INCIDENT_DEDUPE_WINDOW` | `200` | How many fingerprints are remembered |
| `AUTONOMY_MODE` | `propose_only` | `propose_only` or `auto_pr` |
| `GITHUB_TOKEN` / `GITHUB_REPO` | empty | Needed only for pull request creation |
| `SLACK_WEBHOOK_URL` | empty | Optional Slack alerts |
| `SENTINAI_CORS_ORIGINS` | empty | Comma-separated allowed origins |

---

## Roles and Sessions

| Role | Can do |
|---|---|
| `viewer` | Read incidents, suggestions, audit events, settings and the rollback ledger |
| `admin` | Everything a viewer can, plus trigger scans, change the autonomy mode, manage notification channels, and propose or confirm rollbacks |

Sign in with `POST /api/auth/login`. The response contains a session token that lasts 8 hours; send it in the `X-Session-Token` header.

---

## API Reference

Paths below are served under `/api`, except the health probes and `/metrics`.

| Method | Endpoint | Access | Description |
|---|---|---|---|
| POST | `/api/auth/login` | public | Exchange email and password for a session token |
| POST | `/api/auth/logout` | user | End the session |
| GET | `/api/auth/me` | user | Current user and role |
| GET | `/health/live`, `/health/ready` | public | Liveness and readiness probes |
| GET | `/api/stats` | user | Metrics snapshot |
| GET | `/api/incidents` | user | Recent incidents |
| GET | `/api/suggestions` | user | Remediation suggestions |
| GET | `/api/audit` | user | Audit events |
| POST | `/api/scan-now` | admin | Trigger a manual scan |
| GET, PATCH | `/api/settings/autonomy` | user, admin | Read or change the autonomy mode |
| GET, POST | `/api/settings/channels` | user, admin | List or add notification channels |
| PATCH, DELETE | `/api/settings/channels/{id}` | admin | Update or remove a channel |
| GET | `/api/rollbacks` | user | Rollback ledger |
| POST | `/api/rollbacks/{id}/propose` | admin | Check a rollback and propose it |
| POST | `/api/rollbacks/{id}/confirm` | admin | Apply a proposed rollback |
| POST | `/api/chat` | user | AI assistant (SSE streaming) |
| GET | `/metrics` | public | Prometheus metrics |

Interactive docs are available at `/docs` when the server is running.

---

## Deployment

A push to `main` runs the full CI pipeline. When tests, lint, security and the frontend build pass, the Docker image `ebencodex/sentinai:latest` is built and pushed, then a Render deploy hook starts the new deployment. For production use a Postgres `DATABASE_URL` so accounts and audit history survive redeploys.

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=src
```

Frontend checks:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

---

## Project Structure

```
sentinai-project/
├── src/
│   ├── api/            # FastAPI routes: auth, audit, chat, incidents, settings, rollbacks, health
│   ├── core/           # Config, app state, audit logger, metrics
│   ├── db/             # SQLAlchemy models and sessions
│   ├── integrations/   # LLM clients, GitHub, Slack, notifier
│   ├── models/         # Pydantic event models
│   └── services/       # LogWatcher, RemediationEngine
├── sentinai/
│   └── llm/            # Provider-agnostic LLM abstraction layer
├── alembic/            # Database migrations
├── frontend/           # React + Vite dashboard
├── src-tauri/          # Tauri desktop app (Windows build released)
├── vulnerable-app/     # Demo app that generates errors
├── scripts/
├── tests/
├── docs/
├── docker-compose.yml
└── Dockerfile
```

---

## Roadmap

- [ ] Production log sources: feed SentinAI real application logs and validate detection against live attacks
- [ ] Cheaper primary LLM provider (DeepSeek adapter) with Anthropic as fallback
- [ ] Password reset and rate limiting hardening
- [ ] Multi-tenant accounts and teams
- [ ] Grafana dashboard template
- [ ] macOS and Linux desktop builds

---

## Built By

**Ebenezer Richard Masanja**, ICT student at Mbeya University of Science and Technology (MUST), Tanzania.

> *"I started learning Python a few months ago. This is what happened."*

[![GitHub](https://img.shields.io/badge/GitHub-Ebencode--x-181717?style=flat-square&logo=github)](https://github.com/Ebencode-x)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-ebenezer--masanja-0A66C2?style=flat-square&logo=linkedin)](https://www.linkedin.com/in/ebenezer-masanja/)

---

## License

MIT. Free to use, modify, and distribute.
