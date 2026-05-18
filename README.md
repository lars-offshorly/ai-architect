# AI Architect

AI-powered onboarding conversation pipeline built with FastAPI.

## Prerequisites

- Python `>=3.10,<3.12`
- Poetry `2.x` (recommended)
- `make`

## Quick Start

1. Install dependencies:

   ```bash
   make install
   ```

2. Create your local environment file:

   ```bash
   cp .env.example .env
   ```

3. Update `.env` with required values (at minimum `OPENAI_API_KEY`, `DATABASE_URL`, `REDIS_URL`).

4. Run the API:

   ```bash
   make dev
   ```

App: `http://0.0.0.0:8000/`
API docs: `http://0.0.0.0:8000/docs`

## Make Targets

Use `make help` to list available targets.

### Application

```bash
make install   # Install dependencies with Poetry (including dev)
make run       # Start the API server in production mode
make dev       # Start the API server with hot reload
```

### Tests

```bash
make test              # Run all tests
make test-unit         # Run unit tests only
make test-integration  # Run integration tests only
```

### Linting and Formatting

```bash
make lint
make format
```

Targeted lint commands:

```bash
make lint-file src/agents/interpreter/service.py tests/unit/interpreter/test_extractor.py
make lint-staged
make lint-mr
make check-mr
```

### CI Preflight

Use these to approximate pipeline checks locally:

```bash
make ci-preflight
make ci-preflight-commit
make ci-preflight-full
make ci-preflight-mr
make ci-security
```

Notes:

- `make ci-preflight-commit` mirrors commit pipeline behavior.
- `make ci-preflight-full` runs the full local preflight suite.
- Security checks are non-blocking in the same spirit as CI `allow_failure`.

### Utilities

```bash
make validate-templates
make generate-template BUNDLE=my_bundle
make seed BUNDLE=hr_hub
```


## Authentication

All endpoints except `/health`, `/docs`, `/openapi.json`, and `/redoc` require a bearer session token:

```http
Authorization: Bearer <session_token>
```

Authentication uses the shared Redis session cache used by the other Python
services. Tokens are looked up at `:1:{token}` in `REDIS_URL`; the cached value
must contain a serialized `user` object with an integer `id`.

For local development only, set `DEV_BYPASS=true` to bypass auth.

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | — | Yes | OpenAI API key |
| `DATABASE_URL` | — | Yes | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Yes | Redis connection string for shared auth token cache |
| `OPENAI_MODEL` | `gpt-4.1` | No | Model used for AI agents |
| `CLASSIFIER_TEMPERATURE` | `0.0` | No | Temperature for bundle classifier |
| `CONVERSATIONAL_TEMPERATURE` | `0.3` | No | Temperature for conversational replies |
| `ASSEMBLER_TEMPERATURE` | `0.2` | No | Temperature for payload assembler |
| `CONFIDENCE_PROCEED_THRESHOLD` | `0.75` | No | Min confidence to proceed without clarification |
| `CONFIDENCE_SUGGEST_THRESHOLD` | `0.50` | No | Min confidence to suggest a bundle |
| `SCORE_GAP_MINIMUM` | `0.15` | No | Required margin between top two candidates |
| `MAX_CLARIFICATION_TURNS` | `3` | No | Max turns before forcing a decision |
| `TOP_K_BUNDLES` | `3` | No | Number of bundle candidates to rank |
| `LOG_LEVEL` | `INFO` | No | Application log level |
| `RATE_LIMIT_PER_MINUTE` | `60` | No | Per-IP request rate limit |
| `DEV_BYPASS` | `false` | No | Bypass auth locally and set a default admin user |
| `ENABLE_MOCK_ENDPOINTS` | `false` | No | Mounts mock endpoints at `/mock/**` |
| `SENTRY_DSN` | — | No | Sentry error tracking DSN |
| `LANGCHAIN_TRACING_V2` | `false` | No | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | — | No | LangSmith API key |
| `LANGCHAIN_PROJECT` | `ai-architect` | No | LangSmith project name |

## API Endpoints

Interactive docs: `http://localhost:8000/docs`

### Health

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Returns `{"status": "ok", "version": "0.1.0"}` |

### Sessions

| Method | Path | Description |
|---|---|---|
| `POST` | `/sessions` | Start a new onboarding session |
| `POST` | `/sessions/{session_id}/reply` | Continue a session with a user reply |
| `POST` | `/sessions/{session_id}/confirm` | Confirm or reject the proposed bundle |
| `POST` | `/sessions/{session_id}/preview` | Generate full preview (requires confirmation) |
| `POST` | `/sessions/{session_id}/preview/early` | Generate early preview without confirmation |
| `POST` | `/sessions/{session_id}/preview/edit` | Apply NL edit instruction to existing preview |
| `POST` | `/sessions/{session_id}/app` | Generate final app payload |

### Bundles

| Method | Path | Description |
|---|---|---|
| `GET` | `/bundles/{bundle_key}/metadata` | Get metadata for a bundle key |

### Mock Endpoints

Requires `ENABLE_MOCK_ENDPOINTS=true`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/mock/{bundle_key}` | Full mock payload |
| `GET` | `/mock/{bundle_key}/stores` | Dummy store seed data |
| `GET` | `/mock/{bundle_key}/flags` | Feature flag snapshot |

### Session Status Values

| Status | Meaning |
|---|---|
| `awaiting_input` | AI is asking a clarification question |
| `in_progress` | Conversation ongoing, no bundle locked yet |
| `pending_confirmation` | Bundle proposed, waiting for confirmation |
| `ready_for_preview` | Bundle confirmed and ready for `/preview` |
| `complete` | Flow complete |

## API Usage

Start the server with `make dev` and use the interactive docs at `http://localhost:8000/docs`.
Mock endpoints are available when `ENABLE_MOCK_ENDPOINTS=true`.

## Dependency Management Note

`requirements.txt` is informational. Dependency management is handled by Poetry via `pyproject.toml`.

To export pip-compatible requirements:

```bash
poetry export -f requirements.txt --output requirements.lock.txt --without-hashes --with dev
```
