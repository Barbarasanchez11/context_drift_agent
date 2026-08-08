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
