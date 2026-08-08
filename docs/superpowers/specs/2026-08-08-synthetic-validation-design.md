# Synthetic Context Validation

**Date:** 2026-08-08  
**Status:** Approved  

---

## Problem

The existing pipeline detects whether context *became stale* after a schema change. It does not measure whether the context was *sufficient* in the first place for a downstream AI agent to use with confidence.

A dataset could have zero drift but still have a description so thin that an agent can't answer basic questions about it. This module surfaces that.

---

## Goal

Given a dataset's existing documentation (description + glossary terms), generate 3 synthetic questions a downstream agent might ask, then test whether the documentation alone can answer them. Write the result back to DataHub as `context_answerable` and `context_qa_confidence`.

---

## Scope

- Standalone script, not integrated into the polling loop
- Does not touch `agent/pipeline.py` or `agent/datahub/poller.py`
- Reuses existing LLM and DataHub infrastructure
- Manual trigger only (run on demand during demo or CI)

---

## Architecture

```
agent/llm/
├── client.py       ← new: shared _call_llm() extracted from judge.py
├── judge.py        ← updated: imports call_llm from client.py
├── validator.py    ← new: generate_questions + answer_from_context
└── prompts.py      ← updated: 2 new prompt functions

scripts/
└── validate_context.py   ← standalone demo script

tests/
└── test_validator.py     ← 3 test cases, LLM mocked
```

---

## Data Flow

```
validate_context.py
    │
    ├── fetch context via GraphQL (reuses fetcher.py)
    │
    ├── validator.generate_questions(context) → list[str]  # 3 questions
    │
    ├── validator.answer_from_context(question, context) → AnswerResult  # x3
    │        LLM receives ONLY documentation — no schema, no real data
    │
    ├── compute avg_confidence across 3 AnswerResults
    │
    ├── print summary to terminal
    │
    └── writer.write_qa_result(urn, ValidationResult)
            context_answerable = avg_confidence > 0.5
            context_qa_confidence = avg_confidence (float)
```

---

## Models

Added to `agent/models.py`:

```python
class AnswerResult(BaseModel):
    question: str
    answered: bool
    confidence: float
    reasoning: str

class ValidationResult(BaseModel):
    questions: list[AnswerResult]
    context_answerable: bool    # True if avg_confidence > 0.5
    context_qa_confidence: float
```

---

## LLM Prompts

Two new functions in `prompts.py`:

**`build_question_generation_prompt(context)`**  
Instructs the LLM to generate exactly 3 realistic questions a downstream data agent might ask about the dataset, based on its description and glossary terms. Output: JSON array of 3 strings.

**`build_answer_prompt(question, context)`**  
Passes the question and documentation only. Instructs the LLM to answer from the documentation or explicitly state it lacks information. Output: structured JSON with `answered`, `confidence`, `reasoning`.

---

## Error Handling

| Failure point | Behaviour |
|---|---|
| Question generation fails | Log warning, script exits cleanly, nothing written to DataHub |
| Single answer fails | `answered=false`, `confidence=0.0` for that question; continue with the rest |
| Writeback fails | Log error, do not re-raise (validation result is already printed) |

---

## DataHub Properties Written

| Property | Type | Example |
|---|---|---|
| `context_answerable` | string (`"true"/"false"`) | `"true"` |
| `context_qa_confidence` | string (float) | `"0.73"` |

Same mechanism as existing `context_stale` properties — `customProperties` via Python SDK.

---

## Tests

`tests/test_validator.py` — LLM mocked in all cases:

1. Rich context → 3 high-confidence answers → `context_answerable=true`
2. Thin context → low-confidence answers → `context_answerable=false`
3. One question fails → other two continue → avg computed correctly

---

## Out of Scope

- Automatic trigger on drift detection (future iteration)
- Configurable question count (fixed at 3)
- Per-question writeback to DataHub (only aggregate result written)
- Adversarial evaluation (separate feature, future iteration)
