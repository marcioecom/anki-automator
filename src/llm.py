"""Enrich words with explanation, translation, and examples via an LLM provider.

Supports two providers, selected at call time:
- "anthropic": Claude (uses tool_use with prompt caching)
- "groq":      Groq (OpenAI-compatible chat completions with tool calling)
"""
from __future__ import annotations

import json
from typing import Iterable

from anthropic import Anthropic
from groq import Groq
from pydantic import BaseModel, Field

from src.parser import Word


Provider = str  # "anthropic" | "groq"


class EnrichedWord(BaseModel):
    numero: int
    palavra: str
    contexto: str | None = None
    explicacao: str
    traducao: str
    exemplos: list[str] = Field(min_length=5, max_length=5)


SYSTEM_PROMPT = """Voce e um professor de ingles que ajuda estudantes brasileiros a estudar com o metodo Mairo Vergara.

Para cada palavra em ingles fornecida pelo usuario, voce deve gerar:
1. Uma explicacao em portugues de 1 paragrafo (3-5 linhas) sobre o significado/uso da palavra.
2. A traducao em portugues (pode ter multiplos sinonimos separados por virgula).
3. Exatamente 5 exemplos curtos em ingles. Cada exemplo deve ter entre 20 e 50 caracteres e caber em 1 linha.

Se o usuario fornecer um contexto especifico para uma palavra, use esse contexto para guiar a explicacao e os exemplos.

Voce DEVE retornar APENAS um JSON valido no formato exato especificado pela ferramenta, sem markdown, sem texto adicional."""


# Shared JSON schema (used by both providers; only the wrapper format differs).
_TOOL_PARAMETERS = {
    "type": "object",
    "properties": {
        "words": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "numero": {"type": "integer"},
                    "palavra": {"type": "string"},
                    "explicacao": {"type": "string"},
                    "traducao": {"type": "string"},
                    "exemplos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 5,
                        "maxItems": 5,
                    },
                },
                "required": ["numero", "palavra", "explicacao", "traducao", "exemplos"],
            },
        },
    },
    "required": ["words"],
}

_TOOL_NAME = "enrich_words"
_TOOL_DESCRIPTION = "Returns enriched data for a batch of English words."

_ANTHROPIC_TOOL = {
    "name": _TOOL_NAME,
    "description": _TOOL_DESCRIPTION,
    "input_schema": _TOOL_PARAMETERS,
}

_GROQ_TOOL = {
    "type": "function",
    "function": {
        "name": _TOOL_NAME,
        "description": _TOOL_DESCRIPTION,
        "parameters": _TOOL_PARAMETERS,
    },
}


DEFAULT_MODELS: dict[Provider, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "groq": "llama-3.3-70b-versatile",
}


def _format_user_message(words: list[Word]) -> str:
    lines = []
    for w in words:
        if w.contexto:
            lines.append(f'{w.numero}. {w.palavra} (context: "{w.contexto}")')
        else:
            lines.append(f"{w.numero}. {w.palavra}")
    return "Lista do dia:\n" + "\n".join(lines)


def _chunks(items: list[Word], n: int) -> Iterable[list[Word]]:
    for i in range(0, len(items), n):
        yield items[i : i + n]


def _call_anthropic(batch: list[Word], model: str, client: Anthropic) -> list[dict]:
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_ANTHROPIC_TOOL],
        tool_choice={"type": "tool", "name": _TOOL_NAME},
        messages=[{"role": "user", "content": _format_user_message(batch)}],
    )
    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_use is None:
        raise RuntimeError("Anthropic did not return a tool_use block")
    return tool_use.input["words"]


def _call_groq(batch: list[Word], model: str, client: Groq) -> list[dict]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _format_user_message(batch)},
        ],
        tools=[_GROQ_TOOL],
        tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
        max_tokens=4096,
    )
    message = response.choices[0].message
    if not message.tool_calls:
        raise RuntimeError("Groq did not return any tool_calls")
    args = message.tool_calls[0].function.arguments
    payload = json.loads(args) if isinstance(args, str) else args
    return payload["words"]


def enrich_words(
    words: list[Word],
    *,
    provider: Provider,
    model: str,
    batch_size: int = 10,
    client: Anthropic | Groq | None = None,
) -> list[EnrichedWord]:
    if not words:
        return []
    if provider == "anthropic":
        api_client = client if isinstance(client, Anthropic) else Anthropic()
    elif provider == "groq":
        api_client = client if isinstance(client, Groq) else Groq()
    else:
        raise ValueError(f"unknown provider: {provider!r} (expected 'anthropic' or 'groq')")

    by_num: dict[int, Word] = {w.numero: w for w in words}
    out: list[EnrichedWord] = []
    for batch in _chunks(words, batch_size):
        if provider == "anthropic":
            items = _call_anthropic(batch, model, api_client)
        else:
            items = _call_groq(batch, model, api_client)
        for item in items:
            original = by_num.get(item["numero"])
            contexto = original.contexto if original else None
            out.append(
                EnrichedWord(
                    numero=item["numero"],
                    palavra=item["palavra"],
                    contexto=contexto,
                    explicacao=item["explicacao"],
                    traducao=item["traducao"],
                    exemplos=item["exemplos"],
                )
            )
    return out
