# ADR-001: Bundle Classification Strategy

**Status:** Accepted
**Date:** 2026-03-23

## Context

The system needs to determine which workspace bundle best matches a user's needs from a short conversation. Options considered:
1. Pure LLM zero-shot classification
2. LLM classification + deterministic rule boosts
3. Keyword matching only

## Decision

Use **LLM classification with deterministic rule boosts** (`agents/interpreter/classifier.py` + `agents/interpreter/rules.py`).

## Rationale

- LLM alone is inconsistent on short messages with sparse signals
- Pure keyword matching misses paraphrases and domain-specific phrasing
- Combining both gives LLM flexibility with deterministic floor guarantees
- Rule boosts are capped at `1.0` to prevent overrides of genuine LLM signal
- `CONFIDENCE_THRESHOLD` (default `0.6`) makes the fallback explicit and configurable

## Consequences

- `rules.py` must be updated when new bundles are added
- Threshold can be tuned per environment via `.env`
- Classification result includes full ranked list for observability
