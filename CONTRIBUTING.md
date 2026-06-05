# Contributing to SentinAI

Thank you for your interest in contributing to SentinAI — an open-source self-healing DevOps agent built to production-grade standards.

---

## Before You Start

- Read the [README](README.md) to understand what SentinAI does and how it works
- Check [open issues](https://github.com/Ebencode-x/sentinai-project/issues) before opening a new one — your idea or bug may already be tracked
- For large changes, open an issue first to discuss the approach before writing code

---

## How to Contribute

### Reporting Bugs
Use the **Bug Report** issue template. Include:
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, Docker version)
- Relevant logs from the terminal or `/health/ready` endpoint

### Suggesting Features
Use the **Feature Request** issue template. Explain:
- The problem your feature solves
- How it fits into SentinAI's architecture
- Any alternatives you considered

### Submitting a Pull Request

```bash
# 1. Fork the repo and clone your fork
git clone https://github.com/YOUR_USERNAME/sentinai-project.git
cd sentinai-project

# 2. Create a feature branch
git checkout -b feat/your-feature-name

# 3. Set up the dev environment
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Make your changes and run tests
pytest tests/ -v --cov=src

# 5. Commit with a clear message
git commit -m "feat: describe what you changed"

# 6. Push and open a PR
git push origin feat/your-feature-name
```

---

## Code Standards

- **Python**: Follow PEP 8. Type hints required for all new functions.
- **Tests**: Every new feature or bug fix must include a test. We maintain 686+ tests — keep that green.
- **Commits**: Use conventional commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
- **No secrets**: Never commit API keys, tokens, or credentials. Use `.env` and `.env.example`.

---

## Project Structure

```
src/
├── api/          # FastAPI routes
├── core/         # Config, metrics, rate limiter
├── integrations/ # LLM clients, Slack, GitHub
├── models/       # Pydantic models
└── services/     # Core business logic
```

Start in `src/services/` for backend logic and `src/api/` for endpoint changes.

---

## Questions?

Open a [Discussion](https://github.com/Ebencode-x/sentinai-project/discussions) or reach out via [LinkedIn](https://www.linkedin.com/in/ebenezer-masanja/).
