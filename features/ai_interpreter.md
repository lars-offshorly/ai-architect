# AI Interpreter

## Responsibility

Transforms raw user messages into structured data: extracted entities and ranked bundle suggestions.

## Pipeline

```
user_message
  └─ Extractor      → ExtractedInfo (company, entity_type, roles, slots, ...)
  └─ Classifier     → SuggestedBundles (ranked by confidence)
      └─ rules.py   → deterministic signal boosts applied before final ranking
```

## Key Files

| File                                          | Role                                      |
|-----------------------------------------------|-------------------------------------------|
| `agents/interpreter/service.py`               | Orchestrates extraction + classification  |
| `agents/interpreter/extractor.py`             | Structured LLM extraction                 |
| `agents/interpreter/classifier.py`            | Bundle scoring via LLM + rule boosts      |
| `agents/interpreter/rules.py`                 | Deterministic signal → confidence boosts  |
| `agents/interpreter/summarizer.py`            | Compresses conversation history           |
| `agents/interpreter/prompts.py`               | Prompt templates                          |

## Confidence & Threshold

- Each bundle gets a `confidence` score 0.0–1.0
- `CONFIDENCE_THRESHOLD` (default `0.6`) is the minimum for a bundle to be selected
- Rule boosts from `rules.py` are applied on top of LLM scores, capped at `1.0`
- If no bundle meets the threshold, the replier asks a clarification question

## Domain Models

- `ExtractedInfo` — `src/domain/models/extracted_info.py`
- `BundleSuggestion`, `SuggestedBundles` — `src/domain/models/bundle.py`
- `BundleResolutionService` — `src/domain/services/bundle_resolution.py`
