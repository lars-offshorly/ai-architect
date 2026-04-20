# External Integrations & Infrastructure — Codemap

**Last Updated:** 2026-04-13

## Overview

This map covers external services, middleware, and infrastructure that the AI Architect API depends on.

---

## LLM Services

### OpenAI Integration

**File:** `src/core/llm_client.py`

```python
class LLMClient:
    def __init__(self, provider: str = "openai"):
        if provider == "openai":
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        elif provider == "anthropic":
            self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    def invoke(
        self,
        messages: list[dict],
        model: str = "gpt-4-turbo",
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> str:
        """Call LLM and return response text."""
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
```

**Used By:**
- Interpreter Agent — bundle classification + extraction
- Replier Agent — clarification question generation
- Preview Generator (Phase 2) — extract_user_context LLM fallback

**Configuration:**
- `LLM_PROVIDER` — "openai" or "anthropic"
- `OPENAI_API_KEY` — API key
- `OPENAI_MODEL` — Model name (default: "gpt-4-turbo")
- `LLM_TEMPERATURE` — Creativity level (default: 0.3 for consistent results)

### Anthropic Integration

**Library:** anthropic

```python
from anthropic import Anthropic

client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "..."}
    ],
)
```

**Equivalent to OpenAI with consistent interface.**

**Cost Comparison:**
- GPT-4 Turbo: ~$0.01-0.03 per 1K tokens
- Claude 3: ~$0.003-0.015 per 1K tokens

---

## Vector Database

### Pinecone Integration

**File:** `src/core/pinecone_client.py`

```python
class PineconeClient:
    def __init__(self):
        self._client = pinecone.Pinecone(
            api_key=settings.PINECONE_API_KEY,
            environment=settings.PINECONE_ENVIRONMENT,
        )
        self._index = self._client.Index(settings.PINECONE_INDEX_NAME)
    
    def initialize(self):
        """Connect to Pinecone."""
        # Verify connection
        self._index.describe_index_stats()
    
    async def close(self):
        """Close connection."""
        # Cleanup if needed
```

**Optional Usage:**
- Semantic search for bundle classification (Phase 2)
- User query understanding
- Documentation retrieval (RAG)

**Configuration:**
- `PINECONE_API_KEY` — API key
- `PINECONE_ENVIRONMENT` — Environment (e.g., "gcp-starter")
- `PINECONE_INDEX_NAME` — Index name (e.g., "ai-architect-embeddings")

**Current Status:** Initialized but not actively used in Phase 1.

---

## Database (Future)

### PostgreSQL (Phase 3)

**Planned Dependencies:**
- sqlalchemy
- asyncpg (async driver)
- alembic (migrations)

**Schema Overview:**
```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    confirmed BOOLEAN DEFAULT FALSE,
    selected_bundle_key VARCHAR(50),
    preselected_intent VARCHAR(100),
    preselected_bundle_key VARCHAR(50),
    -- JSON columns for model storage
    accumulated_extraction JSONB,
    latest_classification JSONB,
    latest_recommendation JSONB,
);

CREATE TABLE conversation_messages (
    message_id UUID PRIMARY KEY,
    session_id UUID REFERENCES sessions(session_id) ON DELETE CASCADE,
    turn_number INTEGER,
    role VARCHAR(10),  -- "user" or "assistant"
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
);

CREATE INDEX idx_messages_session ON conversation_messages(session_id);
```

---

## Middleware

### Authentication Middleware

**File:** `src/api/middleware/auth.py`

```python
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract Bearer token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            if settings.DEBUG:
                request.state.user_id = "debug-user"
                return await call_next(request)
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing authorization token"},
                )
        
        token = auth_header[7:]  # Remove "Bearer "
        
        try:
            # Validate token (JWT, API key, or custom)
            user_id = validate_token(token)
            request.state.user_id = user_id
        except InvalidTokenError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
            )
        
        return await call_next(request)
```

**Configuration:**
- `DEBUG` — If true, bypass auth for local testing
- `AUTH_SECRET` — Secret for token validation (if using JWT)
- `TOKEN_EXPIRY` — Token lifetime (default: 24 hours)

### Rate Limiting Middleware

**File:** `src/api/middleware/rate_limit.py`

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self._rpm_limit = requests_per_minute
        self._request_times: dict[str, list[float]] = {}
    
    async def dispatch(self, request: Request, call_next) -> Response:
        user_id = request.state.user_id
        now = time.time()
        
        # Clean old requests (> 60 seconds old)
        self._request_times[user_id] = [
            t for t in self._request_times.get(user_id, [])
            if now - t < 60
        ]
        
        # Check limit
        if len(self._request_times[user_id]) >= self._rpm_limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )
        
        # Record this request
        self._request_times[user_id].append(now)
        
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._rpm_limit)
        response.headers["X-RateLimit-Remaining"] = str(
            self._rpm_limit - len(self._request_times[user_id])
        )
        return response
```

**Endpoint-Specific Limits:**
- `POST /sessions/{id}/preview` — 30 req/min (expensive)
- `POST /sessions/{id}/preview/edit` — 30 req/min
- `POST /sessions/{id}/reply` — 20 req/min
- Other endpoints — 60 req/min (default)

### CORS Middleware

**File:** `src/api/app.py` (built-in FastAPI)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if DEBUG else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Security Note:**
- Debug mode: allow all origins (for local frontend dev)
- Production: explicitly list allowed origins

---

## Logging & Monitoring

### Logging

**File:** `src/core/logging.py`

```python
import logging

def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(name)

def get_session_logger(name: str, session_id: str) -> logging.Logger:
    """Get a logger with session context."""
    logger = get_logger(name)
    # Wrap logger to include session_id in all records
    return SessionContextFilter(logger, session_id)

class SessionContextFilter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f"[session={self.extra['session_id']}] {msg}", kwargs
```

**Log Levels:**
- DEBUG — Development; verbose output
- INFO — Normal operation; key milestones
- WARNING — Recoverable errors; degraded behavior
- ERROR — Failures; operations not completed
- CRITICAL — System-level failures

**Example Log Entries:**
```
[session=uuid-123] Starting preview generation for bundle=hr_management
[session=uuid-123] Tier 1 context: company='Acme' industry='Legal' phrases=3
[session=uuid-123] Preview generation complete modules=['HRHub', 'Dashboard']
```

### Structured Logging (Planned, Phase 2)

Replace print-style logs with JSON for log aggregation:

```json
{
  "timestamp": "2026-04-13T12:34:56Z",
  "level": "INFO",
  "logger": "agents.preview_generator.service",
  "session_id": "uuid-123",
  "message": "Preview generation complete",
  "context": {
    "bundle_key": "hr_management",
    "modules": ["HRHub", "Dashboard"],
    "execution_time_ms": 245
  }
}
```

**Benefits:**
- Centralized log aggregation (ELK, Datadog)
- Easy filtering and alerting
- Performance tracking

---

## Configuration Management

**File:** `src/core/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API
    DEBUG: bool = False
    PORT: int = 8000
    
    # LLM
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4-turbo"
    ANTHROPIC_API_KEY: str = ""
    LLM_TEMPERATURE: float = 0.3
    
    # Vector DB
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""
    PINECONE_INDEX_NAME: str = "ai-architect"
    
    # Bundles & Templates
    BUNDLE_REGISTRY_PATH: str = "catalog/bundle_registry.yaml"
    TEMPLATES_DIR: str = "src/templates"
    
    # Features
    ENABLE_MOCK_ENDPOINTS: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

def get_settings() -> Settings:
    return Settings()
```

**Environment Variables:**

Create `.env` file:
```
DEBUG=True
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
PORT=8000
ENABLE_MOCK_ENDPOINTS=True
```

---

## Error Handling

### Custom Exceptions

**File:** `src/core/exceptions.py`

```python
class AIArchitectError(Exception):
    """Base exception for all AI Architect errors."""
    pass

class SessionNotFoundError(AIArchitectError):
    """Session does not exist."""
    pass

class BundleNotFoundError(AIArchitectError):
    """Bundle key not recognized."""
    pass

class PreviewGenerationError(AIArchitectError):
    """Pipeline failed to generate preview."""
    pass

class ValidationError(AIArchitectError):
    """Input validation failed."""
    pass
```

### HTTP Error Responses

All exceptions are caught by routers and converted to HTTP responses:

```python
@router.get("/sessions/{id}")
async def get_session(id: str, repo: SessionRepository = Depends(...)):
    try:
        return repo.get(id)
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

**Standard Response Format:**
```json
{
  "detail": "Session not found"
}
```

**For validation errors (422):**
```json
{
  "detail": [
    {
      "loc": ["body", "bundle_key"],
      "msg": "Unknown bundle key",
      "type": "value_error"
    }
  ]
}
```

---

## Monitoring Hooks

### Request Tracing (Optional)

Could be added via:
- OpenTelemetry for distributed tracing
- Jaeger for trace visualization
- X-Trace-ID headers for request correlation

**Example:**
```python
import uuid
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@router.post("/sessions/{id}/preview")
async def generate_preview(id: str, ...):
    with tracer.start_as_current_span("generate_preview") as span:
        span.set_attribute("session_id", id)
        # ... execution ...
```

### Metrics (Optional)

Could be added via:
- Prometheus for metrics collection
- StatsD for timing
- Custom metrics for:
  - Preview generation time
  - Classification accuracy
  - LLM API costs
  - Error rates

---

## Secrets Management (Phase 2)

**Current:** Environment variables in `.env` file
**Planned:** 
- HashiCorp Vault for secrets
- AWS Secrets Manager
- GitHub Secrets (for CI/CD)

**Migration Steps:**
1. Stop committing `.env` to version control
2. Use vault-agent in Docker/K8s
3. Inject secrets at runtime
4. Audit secret access

---

## Deployment Infrastructure

### Docker

**File:** `Dockerfile` (not in current repo; example)

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

COPY src ./src
COPY catalog ./catalog
COPY src/templates ./src/templates

ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Parity

| Env | DEBUG | LLM | Rate Limit | Auth |
|-----|-------|-----|-----------|------|
| Local | True | openai (mock) | 1000 req/min | Bypass |
| Dev | False | openai | 100 req/min | JWT |
| Staging | False | openai | 60 req/min | JWT |
| Production | False | openai | 30 req/min | JWT + 2FA |

---

## Testing Utilities

### Mock LLM Client

**File:** `tests/fixtures/mock_llm.py`

```python
class MockLLMClient:
    def invoke(self, messages, **kwargs) -> str:
        # Return hardcoded responses based on message content
        if "legal" in str(messages):
            return json.dumps({"bundle_key": "legal_services", "confidence": 0.95})
        if "project" in str(messages):
            return json.dumps({"bundle_key": "project_mgmt", "confidence": 0.88})
        return json.dumps({"bundle_key": "generic", "confidence": 0.5})
```

### Mock Pinecone

```python
class MockPineconeIndex:
    def query(self, vector, top_k):
        return {"matches": []}  # Empty results
```

---

## Dependency Versions

**Key Libraries:**

```
FastAPI==0.100.1
Pydantic==2.4.2
LangGraph==0.0.27
OpenAI==1.3.0
Anthropic==0.7.0
Pinecone==2.2.2
pytest==7.4.0
asyncio==standard
```

See `pyproject.toml` for complete dependency list.

---

## Performance Considerations

| Component | Bottleneck | Mitigation |
|-----------|-----------|-----------|
| LLM calls | 500ms+ per call | Cache results, batching |
| Vector DB query | 100ms per query | Index optimization, caching |
| Feature flag resolution | <5ms | In-memory catalog |
| Sample data generation | 50-100ms | Deterministic, parallel |
| HTTP serialization | <10ms | JSON streaming (large payloads) |

---

## Security Checklist

- [ ] API key stored in environment, not source code
- [ ] HTTPS enforced in production (reverse proxy/load balancer)
- [ ] Rate limiting active on expensive endpoints
- [ ] Input sanitization on all user text (before LLM)
- [ ] Auth token validation on all non-public endpoints
- [ ] SQL injection N/A (in-memory only)
- [ ] CSRF tokens (if cookies used)
- [ ] Audit logging enabled (who did what, when)
- [ ] Secrets rotated regularly

---

## Future Integrations

- **Analytics:** Track usage patterns, user satisfaction
- **Notifications:** Email/SMS for long-running operations
- **Payment:** Stripe for billing per workspace
- **SSO:** SAML/OIDC for enterprise auth
- **CDN:** CloudFlare for static assets
- **Error Tracking:** Sentry for exception monitoring
