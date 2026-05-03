# SentinAI - Self-Healing DevOps Agent

SentinAI is a showcase-ready DevOps assistant built with FastAPI.  
It monitors application logs in near real-time, detects failure signals (for example `ERROR`, `EXCEPTION`, `500`), and prepares AI-ready context for remediation suggestions such as code fixes or configuration changes.

## Why SentinAI

- Reduce time-to-detection for production issues.
- Speed up triage with structured failure context.
- Enable a future "auto-remediate" workflow with human approval gates.

## High-Level Self-Healing Architecture

1. **Log Producer (Dummy Vulnerable App)**
   - A simple FastAPI app intentionally emits occasional `500` and exception traces.
2. **Log Watcher Service (SentinAI Core)**
   - Tails a log file continuously.
   - Detects error patterns (`ERROR`, `EXCEPTION`, `Traceback`, `500`).
   - Groups multiline stack traces into a single incident payload.
3. **Incident Normalizer**
   - Converts raw lines into structured event objects (timestamp, severity, snippet, hash).
4. **AI Analysis Adapter (Scaffold)**
   - Sends incident context to an LLM provider (OpenAI/Claude-ready abstraction).
   - Returns suggested remediation plan:
     - code-level fix hypothesis,
     - configuration tuning suggestions,
     - confidence and risk notes.
5. **Action Layer (Future)**
   - Opens PR drafts, creates Jira/Linear issues, or applies safe config changes behind policy checks.

## Project Structure

```text
sentinai-project/
|-- src/
|   |-- api/
|   |   `-- routes.py
|   |-- core/
|   |   `-- config.py
|   |-- integrations/
|   |   `-- llm_client.py
|   |-- models/
|   |   `-- events.py
|   |-- services/
|   |   |-- remediation_engine.py
|   |   `-- watcher.py
|   `-- main.py
|-- tests/
|   `-- test_watcher.py
|-- logs/
|   `-- .gitkeep
|-- vulnerable-app/
|   |-- app.py
|   `-- requirements.txt
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
`-- .env.example
```

## Core Runtime Flow

1. `src/services/watcher.py` tails `logs/app.log`.
2. Matching patterns trigger incident aggregation.
3. Incident is converted to a `LogIncident` model.
4. `RemediationEngine` sends context to `LLMClient` scaffold.
5. API endpoints expose health and recent incidents.

## Local Development

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Run SentinAI

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 3) Run dummy vulnerable app

```bash
uvicorn vulnerable-app.app:app --reload --host 0.0.0.0 --port 9000
```

### 4) Trigger test errors

Use the vulnerable app endpoint `/boom` several times to generate stack traces.

## Docker / Compose

- `Dockerfile` builds the SentinAI service container.
- `docker-compose.yml` boots:
  - `sentinai` (watcher + API),
  - `vulnerable-app` (error generator).

Run:

```bash
docker compose up --build
```

## API Outline

- `GET /health` - service readiness.
- `GET /incidents` - recently detected incidents.
- `POST /scan-now` - manual scan trigger for demo purposes.

## AI Integration (Scaffold Status)

`src/integrations/llm_client.py` currently defines a provider-agnostic interface and placeholder implementation.

Planned provider implementations:

- OpenAI GPT-4.x
- Anthropic Claude

## Security and Safety Notes

- Never auto-apply code changes in production without review.
- Treat AI suggestions as hypotheses, not truth.
- Add policy checks and RBAC before any write action.

## Next Milestones

1. Add real OpenAI/Claude adapters with retries and rate limiting.
2. Add incident deduplication and fingerprint clustering.
3. Add "suggested patch" generation with unit-test guidance.
4. Add Slack/Webhook notifications and issue tracker integration.

