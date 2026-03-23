# AI Architect

AI-powered onboarding conversation pipeline built with FastAPI.

## Prerequisites

- Python `>=3.10,<3.12`
- Poetry (2.x recommended)

## Setup (Poetry)

1. Install dependencies (including dev tools):
   ```bash
   poetry install --with dev
   ```
2. Create env file:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with valid values for the services you use (at minimum set `OPENAI_API_KEY`; set Pinecone/DB/JWT values as needed).

## Run the API

Use Makefile targets (Poetry-backed):

```bash
make dev
```

Or production mode:

```bash
make run
```

Default server: `http://0.0.0.0:8000`  
FastAPI docs: `http://0.0.0.0:8000/docs`

## Test

```bash
make test
make test-unit
make test-integration
```

## Lint and Format

Run full lint pipeline (`black + ruff + flake8 + mypy + pylint + vulture`):

```bash
make lint
```

Run formatter targets:

```bash
make format
```

Lint specific files/directories:

```bash
make lint-file src/agents/interpreter/service.py tests/unit/interpreter/test_extractor.py
# or
make lint-file src/agents/interpreter/
```

Lint staged files only:

```bash
make lint-staged
```

Lint files changed against `dev` branch:

```bash
make lint-mr
make check-mr
```

## Utility Commands

```bash
make validate-templates
make generate-template BUNDLE=my_bundle
make seed BUNDLE=hr_hub
```

## Notes

- `requirements.txt` is intentionally informational only; dependency management is handled by Poetry via `pyproject.toml`.
- If you need pip-compatible output, export from Poetry:
  ```bash
  poetry export -f requirements.txt --output requirements.lock.txt --without-hashes --with dev
  ```
