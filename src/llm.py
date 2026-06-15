"""Enrich words with explanation, translation, and examples via an LLM provider.

Supports two providers, selected at call time:
- "anthropic": Claude (uses tool_use with prompt caching)
- "groq":      Groq (OpenAI-compatible chat completions with tool calling)
"""

from __future__ import annotations

import json
import time
from typing import Iterable, Literal

from anthropic import Anthropic
from groq import Groq
from src.types import EnrichedWord, EnrichedWordFromLLM, Word


Provider = Literal["anthropic", "groq"]


SYSTEM_PROMPT = """
1) Preciso que você me dê uma explicação de 1 parágrafo de 3 até 5 linhas para a tradução de inglês para português de cada palavra da “lista do dia”.
2) Preciso que você me dê traduções de cada palavra da “lista do dia” de inglês para português sem explicação, apenas os termos traduzidos, separados por vírgula e em uma única linha.
3) Preciso que você me dê 5 exemplos de cada palavra da “lista do dia”. Os exemplos devem ser em inglês e devem ter tamanho de apenas 1 linha. Os exemplos devem ter de 20 a 50 caracteres cada.

Explicação, termos traduzidos e exemplos devem ficar agrupados para cada palavra da lista do dia.

Segue um modelo como você deve me mostrar os resultados:

*Play:*
Explicação: "Play" em inglês significa brincar ou jogar. Pode se referir tanto a atividades lúdicas quanto a participação em jogos ou esportes.

Play: Brincar, Jogar

Exemplos:
1. She loves to play with her dog in the park.
2. Let's play a board game after dinner.
3. The children are playing hide-and-seek.
4. He enjoys playing basketball on weekends.
5. The theater will host a play next week.

*Essential:*
Explicação: "Essential" traduzido para o português significa essencial, algo fundamental ou indispensável para algo.

Essential: Essencial

Exemplos:
1. Water is essential for human survival.
2. Good communication is essential in a team.
3. A healthy diet is essential for overall well-being.
4. Sleep is essential for proper cognitive function.
5. Sunscreen is essential for protecting your skin.

*Better:*
Explicação: A palavra "better" em inglês é utilizada para expressar melhoria ou superioridade em relação a algo.

Better: Melhor

Exemplos:
1. Practice makes you better at playing the guitar.
2. Eating fruits and vegetables is better for your health.
3. She hopes for a better future for her children.
4. The new software provides a better user experience.
5. Getting enough sleep makes you feel better.

*Full:*
Explicação: "Full" pode ser traduzido como cheio ou completo. Pode referir-se à capacidade máxima de algo ou à presença de todos os elementos necessários.

Full: Cheio, Completo

Exemplos:
1. The glass is full of water.
2. After the meal, I feel full.
3. Please provide your full name and address.
4. The movie theater was full of excited viewers.
5. The project is in its full implementation stage.

*Portable:*
Explicação: "Portable" em inglês significa portátil, algo que pode ser facilmente transportado de um lugar para outro.

Portable: Portátil

Exemplos:
1. A portable phone charger is handy for travel.
2. We use a portable grill for outdoor cooking.
3. The laptop is lightweight and portable.
4. Portable speakers are great for picnics.
5. This toolbox is designed to be portable.

*Class:*
Explicação: "Class" pode ser traduzido como classe, categoria ou aula. O significado depende do contexto em que a palavra é usada.

Class: Classe, Aula

Exemplos:
1. She is taking a class on photography.
2. The car belongs to the luxury class.
3. The students are in math class right now.
4. This book falls into the mystery genre class.
5. The hotel offers different classes of rooms.

*Bring:*
Explicação: "Bring" em inglês significa trazer, transportar algo de um lugar para outro.

Bring: Trazer

Exemplos:
1. Can you bring the documents to the meeting?
2. She always brings a smile to our faces.
3. Please bring a dish to share at the potluck.
4. He forgot to bring his umbrella in the rain.
5. I'll bring some snacks for the road trip.

*Brown:*
Explicação: "Brown" traduzido para o português significa marrom, uma cor que inclui tons escuros de vermelho e amarelo.

Brown: Marrom

Exemplos:
1. Her eyes are a beautiful shade of brown.
2. The dog has a soft, brown fur coat.
3. The leather couch is a deep brown color.
4. Autumn leaves turn various shades of brown.
5. He prefers to wear brown shoes with his suits.

*Flag:*
Explicação: "Flag" pode ser traduzido como bandeira ou sinalizador. Também é usado para indicar problemas ou alertas.

Flag: Bandeira, Sinalizador

Exemplos:
1. The national flag waved proudly in the wind.
2. Red flags were raised as a warning.
3. They planted a flag at the mountain's summit.
4. The referee threw a flag during the game.
5. The system raised a flag for suspicious activity.

*Fight:*
Explicação: "Fight" em inglês significa lutar, tanto no sentido físico quanto no sentido de enfrentar desafios ou adversidades.

Fight: Lutar

Exemplos:
1. They had a fierce fight in the boxing ring.
2. It's important to fight for justice.
3. Soldiers fight to defend their country.
4. Couples sometimes fight about trivial matters.
5. The team showed determination in the fight for victory.

Se o usuario fornecer um contexto especifico para uma palavra, use esse contexto para guiar a explicacao e os exemplos.

MAPEAMENTO PARA A FERRAMENTA `enrich_words`:
Cada palavra deve ser retornada como um item do array `words` com EXATAMENTE estes campos preenchidos a partir do modelo acima:
- `palavra`: a palavra em ingles (a parte do titulo, ex: "play").
- `explicacao`: o PARAGRAFO COMPLETO que viria apos "Explicação:" (3 a 5 linhas, varias frases). NUNCA apenas a traducao curta. Se for tentado a colocar so "Brincar" aqui, voce esta errado: e para colocar o paragrafo inteiro explicando significado e uso.
- `traducao`: a linha apos o nome da palavra (ex: "Brincar, Jogar"), apenas os termos separados por virgula, cada um Capitalizado.
- `exemplos`: array com exatamente as 5 frases numeradas em ingles (sem a numeracao, so o texto da frase).

Voce DEVE retornar APENAS via a ferramenta `enrich_words`. Nao escreva markdown nem texto fora da ferramenta.
"""


# Shared JSON schema (derived from EnrichedWordFromLLM model).
def _build_tool_parameters() -> dict:
    """Build the JSON schema for the enrich_words tool from EnrichedWordFromLLM."""
    item_schema = EnrichedWordFromLLM.model_json_schema()
    item_schema.pop("$schema", None)
    item_schema.pop("title", None)
    return {
        "type": "object",
        "properties": {
            "words": {
                "type": "array",
                "items": item_schema,
            },
        },
        "required": ["words"],
    }


_TOOL_PARAMETERS = _build_tool_parameters()

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
    max_tokens = max(4096, len(batch) * 600)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
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
    max_tokens = max(4096, len(batch) * 600)
    for attempt in range(3):
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _format_user_message(batch)},
            ],
            tools=[_GROQ_TOOL],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            max_tokens=max_tokens,
            temperature=0.3,
        )
        message = response.choices[0].message
        if message.tool_calls:
            args = message.tool_calls[0].function.arguments
            payload = json.loads(args) if isinstance(args, str) else args
            return payload["words"]
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise RuntimeError(
        f"Groq did not return any tool_calls after 3 attempts (model={model}, batch={[w.palavra for w in batch]})"
    )


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
        raise ValueError(
            f"unknown provider: {provider!r} (expected 'anthropic' or 'groq')"
        )

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
