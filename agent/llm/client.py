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
