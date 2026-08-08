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
