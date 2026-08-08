# Synthetic Context Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone script that generates 3 synthetic questions about a dataset and tests whether its existing documentation can answer them, writing the result back to DataHub as `context_answerable` and `context_qa_confidence`.

**Architecture:** Extract shared LLM call logic into `agent/llm/client.py` so both the existing judge and the new validator reuse it. The validator lives in `agent/llm/validator.py` and is wired together by a standalone demo script `scripts/validate_context.py` — nothing touches the existing polling pipeline.

**Tech Stack:** Python 3.11+, Pydantic, DataHub Python SDK, Anthropic/OpenAI/Groq SDKs (already installed), pytest with unittest.mock.

## Global Constraints

- All code and comments in English
- Do not modify `agent/pipeline.py`, `agent/datahub/poller.py`, or `agent/__main__.py`
- Follow existing patterns: `from __future__ import annotations` at top of every file, Pydantic BaseModel for data classes, typed hints everywhere
- Run `uv run pytest` to verify tests; run `uv run ruff check .` to verify linting

---

### Task 1: Extract shared LLM client to `agent/llm/client.py`

**Files:**
- Create: `agent/llm/client.py`
- Modify: `agent/llm/judge.py`
- Modify: `tests/test_judge.py` (update mock paths)

**Interfaces:**
- Produces: `call_llm(prompt, provider, api_key, model, tool_name=None, tool_schema=None) -> dict`
  - When `tool_name` + `tool_schema` are provided: uses Anthropic tool_use for structured output
  - When omitted: Anthropic returns plain JSON text; OpenAI/Groq use `json_object` mode

- [ ] **Step 1: Write the failing test for `call_llm` (Anthropic JSON mode, no tool)**

Create `tests/test_client.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent.llm.client import call_llm


def _make_anthropic_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "message"
    block.text = text
    message = MagicMock()
    message.content = [block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


class TestCallLlm:
    def test_anthropic_json_mode_returns_dict(self) -> None:
        data = {"answered": True, "confidence": 0.9, "reasoning": "clear"}
        mock_client = _make_anthropic_text_response(json.dumps(data))
        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = call_llm("some prompt", "anthropic", "fake-key", "claude-sonnet-4-6")
        assert result == data

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            call_llm("prompt", "cohere", "key", "model")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_client.py -v
```
Expected: `ModuleNotFoundError` or `ImportError` — `client.py` does not exist yet.

- [ ] **Step 3: Create `agent/llm/client.py`**

```python
from __future__ import annotations

import json
import re

import anthropic
import groq as groq_sdk
import openai

_LLM_TIMEOUT = 30


def call_llm(
    prompt: str,
    provider: str,
    api_key: str,
    model: str,
    tool_name: str | None = None,
    tool_schema: dict | None = None,
) -> dict:
    if provider == "anthropic":
        client = anthropic.Anthropic(api_key=api_key)
        if tool_name and tool_schema:
            message = client.messages.create(
                model=model,
                max_tokens=256,
                tools=[tool_schema],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
                timeout=_LLM_TIMEOUT,
            )
            for block in message.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return block.input  # type: ignore[return-value]
            raise ValueError(f"Anthropic response missing tool_use block: {message.content!r}")
        else:
            message = client.messages.create(
                model=model,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
                timeout=_LLM_TIMEOUT,
            )
            raw = message.content[0].text if message.content else ""
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
            return json.loads(raw)  # type: ignore[return-value]

    if provider == "openai":
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            timeout=_LLM_TIMEOUT,
        )
        return json.loads(response.choices[0].message.content)  # type: ignore[return-value]

    if provider == "groq":
        client = groq_sdk.Groq(api_key=api_key)
        last_error: json.JSONDecodeError | None = None
        raw = ""
        for _ in range(2):
            response = client.chat.completions.create(
                model=model,
                max_tokens=512,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
                timeout=_LLM_TIMEOUT,
            )
            raw = response.choices[0].message.content or ""
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
            try:
                return json.loads(raw)  # type: ignore[return-value]
            except json.JSONDecodeError as exc:
                last_error = exc
        raise ValueError(f"Groq returned non-JSON after 2 attempts: {raw!r}") from last_error

    raise ValueError(
        f"Unsupported LLM provider: {provider!r}. Use 'anthropic', 'openai', or 'groq'."
    )
```

- [ ] **Step 4: Update `agent/llm/judge.py` to import from `client.py`**

Replace the entire `_call_llm` function body and the three SDK imports with:

```python
from __future__ import annotations

from datetime import UTC, datetime

from agent.llm.client import call_llm
from agent.llm.prompts import build_prompt
from agent.models import ContextSnapshot, DriftResult, RichContext, SchemaDiff

_TOOL_NAME = "report_drift"
_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": "Report whether the dataset context is stale after a schema change.",
    "input_schema": {
        "type": "object",
        "properties": {
            "context_stale": {"type": "boolean"},
            "context_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "context_drift_reason": {"type": "string"},
        },
        "required": ["context_stale", "context_confidence", "context_drift_reason"],
    },
}


def evaluate(
    diff: SchemaDiff,
    context: ContextSnapshot,
    llm_provider: str,
    api_key: str,
    model: str,
    rich_context: RichContext | None = None,
) -> DriftResult:
    prompt = build_prompt(diff, context, rich_context)
    data = call_llm(prompt, llm_provider, api_key, model, tool_name=_TOOL_NAME, tool_schema=_TOOL_SCHEMA)
    return _parse_response(data, diff.dataset_urn)


def _parse_response(data: dict, dataset_urn: str) -> DriftResult:
    required = {"context_stale", "context_confidence", "context_drift_reason"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"LLM response missing fields {missing}: {data!r}")

    return DriftResult(
        dataset_urn=dataset_urn,
        evaluated_at=datetime.now(UTC),
        context_stale=bool(data["context_stale"]),
        context_confidence=float(data["context_confidence"]),
        context_drift_reason=str(data["context_drift_reason"]),
    )
```

- [ ] **Step 5: Update mock paths in `tests/test_judge.py`**

The mocks previously patched `agent.llm.judge.anthropic.Anthropic` and `agent.llm.judge.groq_sdk.Groq`. These must now point to `client.py`:

```python
# In TestEvaluate.test_returns_drift_result_for_anthropic:
with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):

# In TestEvaluate.test_anthropic_uses_tool_use_with_timeout:
with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):

# In TestEvaluate.test_groq_strips_markdown_fenced_json:
with patch("agent.llm.client.groq_sdk.Groq", return_value=mock_client):

# In TestEvaluate.test_groq_strips_plain_code_fence:
with patch("agent.llm.client.groq_sdk.Groq", return_value=mock_client):

# In TestEvaluate.test_raises_value_error_on_non_json_response:
with patch("agent.llm.client.groq_sdk.Groq", return_value=mock_client):

# In TestEvaluate.test_raises_value_error_on_missing_fields:
with patch("agent.llm.client.groq_sdk.Groq", return_value=mock_client):

# In TestEvaluate.test_raises_on_anthropic_timeout:
with patch("agent.llm.client.anthropic.Anthropic", return_value=client):
```

Also update `test_raises_on_unknown_provider` — it calls `evaluate()` with provider `"cohere"`. The error message now comes from `client.py` instead of `judge.py`, but the match string `"Unsupported LLM provider"` stays the same, so no change needed there.

- [ ] **Step 6: Run all tests to verify nothing broke**

```bash
uv run pytest tests/test_client.py tests/test_judge.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add agent/llm/client.py agent/llm/judge.py tests/test_client.py tests/test_judge.py
git commit -m "refactor: extract shared LLM call logic to client.py"
```

---

### Task 2: Add `AnswerResult` and `ValidationResult` to `agent/models.py`

**Files:**
- Modify: `agent/models.py`

**Interfaces:**
- Produces:
  ```python
  class AnswerResult(BaseModel):
      question: str
      answered: bool
      confidence: float
      reasoning: str

  class ValidationResult(BaseModel):
      questions: list[AnswerResult]
      context_answerable: bool
      context_qa_confidence: float
  ```

- [ ] **Step 1: Add models to `agent/models.py`**

Append at the end of `agent/models.py`:

```python
class AnswerResult(BaseModel):
    question: str
    answered: bool
    confidence: float
    reasoning: str


class ValidationResult(BaseModel):
    questions: list[AnswerResult]
    context_answerable: bool        # True if avg_confidence > 0.5
    context_qa_confidence: float    # average confidence across all questions
```

- [ ] **Step 2: Verify with a quick import check**

```bash
uv run python -c "from agent.models import AnswerResult, ValidationResult; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agent/models.py
git commit -m "feat: add AnswerResult and ValidationResult models"
```

---

### Task 3: Add validation prompts to `agent/llm/prompts.py`

**Files:**
- Modify: `agent/llm/prompts.py`

**Interfaces:**
- Consumes: `ContextSnapshot` from `agent.models`
- Produces:
  - `build_question_generation_prompt(context: ContextSnapshot) -> str`
  - `build_answer_prompt(question: str, context: ContextSnapshot) -> str`

- [ ] **Step 1: Write failing tests**

Add to a new file `tests/test_prompts.py`:

```python
from __future__ import annotations

from agent.llm.prompts import build_answer_prompt, build_question_generation_prompt
from agent.models import ContextSnapshot

CONTEXT = ContextSnapshot(
    dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,customers,PROD)",
    description="Customer master table with credit and order history.",
    glossary_terms=["CreditLimit", "HighValueCustomer"],
    custom_properties={},
)


class TestBuildQuestionGenerationPrompt:
    def test_includes_description(self) -> None:
        prompt = build_question_generation_prompt(CONTEXT)
        assert "Customer master table" in prompt

    def test_includes_glossary_terms(self) -> None:
        prompt = build_question_generation_prompt(CONTEXT)
        assert "CreditLimit" in prompt

    def test_requests_exactly_three_questions(self) -> None:
        prompt = build_question_generation_prompt(CONTEXT)
        assert "3" in prompt or "three" in prompt.lower()

    def test_requests_json_output(self) -> None:
        prompt = build_question_generation_prompt(CONTEXT)
        assert "questions" in prompt


class TestBuildAnswerPrompt:
    def test_includes_question(self) -> None:
        prompt = build_answer_prompt("Can I filter by credit limit?", CONTEXT)
        assert "Can I filter by credit limit?" in prompt

    def test_includes_description(self) -> None:
        prompt = build_answer_prompt("Any question?", CONTEXT)
        assert "Customer master table" in prompt

    def test_instructs_documentation_only(self) -> None:
        prompt = build_answer_prompt("Any question?", CONTEXT)
        assert "documentation" in prompt.lower()

    def test_requests_json_with_answered_field(self) -> None:
        prompt = build_answer_prompt("Any question?", CONTEXT)
        assert "answered" in prompt
        assert "confidence" in prompt
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_prompts.py -v
```
Expected: `ImportError` — functions don't exist yet.

- [ ] **Step 3: Add the two prompt functions to `agent/llm/prompts.py`**

Append at the end of `agent/llm/prompts.py`:

```python
def build_question_generation_prompt(context: ContextSnapshot) -> str:
    description = context.description or "(no description)"
    glossary = ", ".join(context.glossary_terms) if context.glossary_terms else "none"

    return f"""You are a data analyst. Given a dataset's documentation, generate exactly 3 realistic questions that a downstream AI agent might ask before using this dataset.

## Dataset documentation
Description: "{description}"
Glossary terms: {glossary}

## Task
Generate questions that test whether the documentation is sufficient for an AI agent to use this dataset with confidence. Questions must be grounded in the actual content described — not generic.

Respond with ONLY a JSON object — no preamble, no explanation outside the JSON:
{{
  "questions": [
    "<specific question 1>",
    "<specific question 2>",
    "<specific question 3>"
  ]
}}"""


def build_answer_prompt(question: str, context: ContextSnapshot) -> str:
    description = context.description or "(no description)"
    glossary = ", ".join(context.glossary_terms) if context.glossary_terms else "none"

    return f"""You are a data analyst. Answer the question using ONLY the documentation provided below. Do NOT use external knowledge or assumptions beyond what is written.

## Dataset documentation
Description: "{description}"
Glossary terms: {glossary}

## Question
{question}

## Task
If the documentation contains enough information to answer confidently, set answered=true and confidence accordingly.
If the documentation is too vague or missing key information, set answered=false.

Respond with ONLY a JSON object — no preamble, no explanation outside the JSON:
{{
  "answered": <true|false>,
  "confidence": <float 0.0-1.0>,
  "reasoning": "<one sentence explaining why you can or cannot answer>"
}}"""
```

Also update the import line at the top of `prompts.py` to include `ContextSnapshot`:

The current import is:
```python
from agent.models import ContextSnapshot, RichContext, SchemaDiff
```
`ContextSnapshot` is already imported — no change needed.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_prompts.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/llm/prompts.py tests/test_prompts.py
git commit -m "feat: add question generation and answer prompts"
```

---

### Task 4: Implement `agent/llm/validator.py`

**Files:**
- Create: `agent/llm/validator.py`
- Create: `tests/test_validator.py`

**Interfaces:**
- Consumes:
  - `call_llm(prompt, provider, api_key, model) -> dict` from `agent.llm.client`
  - `build_question_generation_prompt(context)` from `agent.llm.prompts`
  - `build_answer_prompt(question, context)` from `agent.llm.prompts`
  - `ContextSnapshot`, `AnswerResult`, `ValidationResult` from `agent.models`
- Produces:
  - `validate_context_sufficiency(context, provider, api_key, model) -> ValidationResult`

- [ ] **Step 1: Write failing tests**

Create `tests/test_validator.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, call, patch

import pytest

from agent.llm.validator import validate_context_sufficiency
from agent.models import ContextSnapshot, ValidationResult

RICH_CONTEXT = ContextSnapshot(
    dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,customers,PROD)",
    description="Customer master table. credit_limit is the maximum credit in USD. "
                "high_value_customer flag indicates lifetime value > $10,000.",
    glossary_terms=["CreditLimit", "HighValueCustomer"],
    custom_properties={},
)

THIN_CONTEXT = ContextSnapshot(
    dataset_urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,customers,PROD)",
    description=None,
    glossary_terms=[],
    custom_properties={},
)

_QUESTIONS_RESPONSE = json.dumps({
    "questions": [
        "What does credit_limit represent?",
        "Can I use this table to filter high-value customers?",
        "What currency is credit_limit stored in?",
    ]
})


def _make_text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    message = MagicMock()
    message.content = [block]
    client = MagicMock()
    client.messages.create.return_value = message
    return client


class TestValidateContextSufficiency:
    def test_rich_context_returns_answerable_true(self) -> None:
        high_confidence_answer = json.dumps({
            "answered": True, "confidence": 0.9,
            "reasoning": "Description clearly explains this field."
        })
        responses = iter([_QUESTIONS_RESPONSE] + [high_confidence_answer] * 3)
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = lambda **kw: _msg(next(responses))

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = validate_context_sufficiency(
                RICH_CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert isinstance(result, ValidationResult)
        assert result.context_answerable is True
        assert result.context_qa_confidence > 0.5
        assert len(result.questions) == 3

    def test_thin_context_returns_answerable_false(self) -> None:
        low_confidence_answer = json.dumps({
            "answered": False, "confidence": 0.1,
            "reasoning": "No description available."
        })
        responses = iter([_QUESTIONS_RESPONSE] + [low_confidence_answer] * 3)
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = lambda **kw: _msg(next(responses))

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = validate_context_sufficiency(
                THIN_CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert result.context_answerable is False
        assert result.context_qa_confidence <= 0.5

    def test_partial_failure_continues_and_averages_correctly(self) -> None:
        good_answer = json.dumps({"answered": True, "confidence": 0.8, "reasoning": "Clear."})
        bad_answer = json.dumps({"answered": False, "confidence": 0.2, "reasoning": "Unclear."})
        # question 1 good, question 2 good, question 3 bad
        responses = iter([_QUESTIONS_RESPONSE, good_answer, good_answer, bad_answer])
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = lambda **kw: _msg(next(responses))

        with patch("agent.llm.client.anthropic.Anthropic", return_value=mock_client):
            result = validate_context_sufficiency(
                RICH_CONTEXT, "anthropic", "fake-key", "claude-sonnet-4-6"
            )

        assert len(result.questions) == 3
        expected_avg = round((0.8 + 0.8 + 0.2) / 3, 4)
        assert result.context_qa_confidence == pytest.approx(expected_avg, abs=0.001)
        assert result.context_answerable is True  # avg = 0.6 > 0.5


def _msg(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    message = MagicMock()
    message.content = [block]
    return message
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_validator.py -v
```
Expected: `ModuleNotFoundError` — `validator.py` does not exist yet.

- [ ] **Step 3: Create `agent/llm/validator.py`**

```python
from __future__ import annotations

import logging

from agent.llm.client import call_llm
from agent.llm.prompts import build_answer_prompt, build_question_generation_prompt
from agent.models import AnswerResult, ContextSnapshot, ValidationResult

log = logging.getLogger(__name__)


def generate_questions(
    context: ContextSnapshot,
    provider: str,
    api_key: str,
    model: str,
) -> list[str]:
    prompt = build_question_generation_prompt(context)
    data = call_llm(prompt, provider, api_key, model)
    questions: list[str] = data.get("questions", [])
    return questions[:3]


def answer_from_context(
    question: str,
    context: ContextSnapshot,
    provider: str,
    api_key: str,
    model: str,
) -> AnswerResult:
    prompt = build_answer_prompt(question, context)
    data = call_llm(prompt, provider, api_key, model)
    return AnswerResult(
        question=question,
        answered=bool(data.get("answered", False)),
        confidence=float(data.get("confidence", 0.0)),
        reasoning=str(data.get("reasoning", "")),
    )


def validate_context_sufficiency(
    context: ContextSnapshot,
    provider: str,
    api_key: str,
    model: str,
) -> ValidationResult:
    questions = generate_questions(context, provider, api_key, model)
    answers: list[AnswerResult] = []
    for question in questions:
        try:
            answer = answer_from_context(question, context, provider, api_key, model)
        except Exception:
            log.warning("Failed to evaluate question %r — defaulting to unanswered", question)
            answer = AnswerResult(
                question=question,
                answered=False,
                confidence=0.0,
                reasoning="LLM call failed",
            )
        answers.append(answer)

    avg_confidence = sum(a.confidence for a in answers) / len(answers) if answers else 0.0
    return ValidationResult(
        questions=answers,
        context_answerable=avg_confidence > 0.5,
        context_qa_confidence=round(avg_confidence, 4),
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_validator.py -v
```
Expected: all 3 PASS.

- [ ] **Step 5: Run full suite to check no regressions**

```bash
uv run pytest -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/llm/validator.py tests/test_validator.py
git commit -m "feat: add context sufficiency validator"
```

---

### Task 5: Add `write_qa_result` to `agent/datahub/writer.py`

**Files:**
- Modify: `agent/datahub/writer.py`
- Modify: `tests/test_writer.py`

**Interfaces:**
- Consumes: `ValidationResult` from `agent.models`
- Produces: `write_qa_result(urn, result, gms_url, token=None, existing_description=None) -> None`
  - Writes `context_answerable` and `context_qa_confidence` as `customProperties`

- [ ] **Step 1: Write failing test**

Open `tests/test_writer.py` and add a new test class at the bottom:

```python
from agent.datahub.writer import write_drift_result, write_qa_result
from agent.models import AnswerResult, DriftResult, ValidationResult

# (keep existing imports and tests unchanged, add below)

class TestWriteQaResult:
    def test_emits_mcp_with_qa_properties(self) -> None:
        result = ValidationResult(
            questions=[
                AnswerResult(
                    question="Is credit_limit in USD?",
                    answered=True,
                    confidence=0.85,
                    reasoning="Description confirms USD.",
                )
            ],
            context_answerable=True,
            context_qa_confidence=0.85,
        )
        mock_emitter = MagicMock()
        with patch("agent.datahub.writer.DatahubRestEmitter", return_value=mock_emitter):
            write_qa_result(
                urn="urn:li:dataset:(urn:li:dataPlatform:snowflake,customers,PROD)",
                result=result,
                gms_url="http://localhost:8080",
            )

        mock_emitter.emit.assert_called_once()
        mcp = mock_emitter.emit.call_args[0][0]
        props = mcp.aspect.customProperties
        assert props["context_answerable"] == "true"
        assert props["context_qa_confidence"] == "0.85"
```

Note: `MagicMock` and `patch` are already imported in `tests/test_writer.py` — check before adding imports.

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_writer.py::TestWriteQaResult -v
```
Expected: `ImportError` — `write_qa_result` does not exist yet.

- [ ] **Step 3: Add `write_qa_result` to `agent/datahub/writer.py`**

Add after the existing `write_drift_result` function. Also add `ValidationResult` to the import:

```python
from agent.models import DriftResult, ValidationResult


def write_qa_result(
    urn: str,
    result: ValidationResult,
    gms_url: str,
    token: str | None = None,
    existing_description: str | None = None,
) -> None:
    custom_properties = {
        "context_answerable": str(result.context_answerable).lower(),
        "context_qa_confidence": str(round(result.context_qa_confidence, 4)),
    }
    emitter = DatahubRestEmitter(gms_server=gms_url, token=token)
    mcp = MetadataChangeProposalWrapper(
        entityUrn=urn,
        aspect=DatasetPropertiesClass(
            description=existing_description,
            customProperties=custom_properties,
        ),
    )
    emitter.emit(mcp)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_writer.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/datahub/writer.py tests/test_writer.py
git commit -m "feat: add write_qa_result to writer"
```

---

### Task 6: Create `scripts/validate_context.py`

**Files:**
- Create: `scripts/validate_context.py`

**Interfaces:**
- Consumes: all modules from Tasks 1–5
- CLI usage: `uv run python scripts/validate_context.py <dataset_urn>`

- [ ] **Step 1: Create the script**

```python
from __future__ import annotations

import argparse
import logging
import sys

from agent.config import Settings
from agent.datahub.graphql import get_context
from agent.datahub.writer import write_qa_result
from agent.llm.validator import validate_context_sufficiency

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate whether a dataset's documentation is sufficient for AI agents."
    )
    parser.add_argument("urn", help="Dataset URN to validate")
    args = parser.parse_args()

    settings = Settings()
    urn: str = args.urn

    log.info("Fetching context for %s", urn)
    context = get_context(urn, settings.datahub_gms_url, settings.datahub_token)

    if not context.description and not context.glossary_terms:
        log.warning("Dataset has no description or glossary terms — validation will likely fail")

    log.info("Running synthetic context validation (3 questions)...")
    result = validate_context_sufficiency(
        context,
        settings.llm_provider,
        settings.get_api_key(),
        settings.llm_model,
    )

    print("\n=== Synthetic Context Validation ===")
    print(f"Dataset:              {urn}")
    print(f"context_answerable:   {result.context_answerable}")
    print(f"context_qa_confidence:{result.context_qa_confidence:.2f}")
    print()
    for i, answer in enumerate(result.questions, 1):
        status = "PASS" if answer.answered else "FAIL"
        print(f"Q{i} [{status}] {answer.question}")
        print(f"     confidence={answer.confidence:.2f} — {answer.reasoning}")
    print()

    log.info("Writing results to DataHub...")
    try:
        write_qa_result(
            urn=urn,
            result=result,
            gms_url=settings.datahub_gms_url,
            token=settings.datahub_token,
            existing_description=context.description,
        )
        log.info("Done. Properties written: context_answerable, context_qa_confidence")
    except Exception as exc:
        log.error("Writeback failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script is importable**

```bash
uv run python -c "import scripts.validate_context; print('OK')" 2>/dev/null || \
uv run python scripts/validate_context.py --help
```
Expected: help text printed with `urn` argument described.

- [ ] **Step 3: Run full test suite one final time**

```bash
uv run pytest -v
uv run ruff check .
```
Expected: all PASS, no lint errors.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate_context.py
git commit -m "feat: add standalone validate_context script"
```

---

## Manual Demo Test

With DataHub running and `.env` configured:

```bash
# Use the same URN as the main demo
uv run python scripts/validate_context.py \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)"
```

Expected output:
```
INFO Fetching context for urn:li:dataset:...
INFO Running synthetic context validation (3 questions)...

=== Synthetic Context Validation ===
Dataset:              urn:li:dataset:...
context_answerable:   True
context_qa_confidence:0.82

Q1 [PASS] What does credit_limit represent?
     confidence=0.90 — Description clearly defines this as maximum credit in USD.
Q2 [PASS] Can I use this table to filter high-value customers?
     confidence=0.85 — Glossary term HighValueCustomer is present.
Q3 [PASS] Is this dataset safe to use for credit risk models?
     confidence=0.70 — Description implies financial use case.

INFO Writing results to DataHub...
INFO Done. Properties written: context_answerable, context_qa_confidence
```

Check DataHub UI: dataset should now show `context_answerable=true` and `context_qa_confidence=0.82` under Custom Properties.
