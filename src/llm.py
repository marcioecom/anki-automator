"""Enrich words with explanation, translation, and examples via the Claude API."""
from __future__ import annotations

from typing import Iterable

from anthropic import Anthropic
from pydantic import BaseModel, Field

from src.parser import Word


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


ENRICH_TOOL = {
    "name": "enrich_words",
    "description": "Returns enriched data for a batch of English words.",
    "input_schema": {
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
    },
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


def enrich_words(
    words: list[Word],
    *,
    model: str,
    batch_size: int = 10,
    client: Anthropic | None = None,
) -> list[EnrichedWord]:
    if not words:
        return []
    client = client or Anthropic()
    by_num: dict[int, Word] = {w.numero: w for w in words}
    out: list[EnrichedWord] = []
    for batch in _chunks(words, batch_size):
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
            tools=[ENRICH_TOOL],
            tool_choice={"type": "tool", "name": "enrich_words"},
            messages=[{"role": "user", "content": _format_user_message(batch)}],
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise RuntimeError("Claude did not return a tool_use block")
        payload = tool_use.input
        for item in payload["words"]:
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
