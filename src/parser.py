"""Parse a numbered English word list into structured `Word` records."""
from __future__ import annotations

import re
from pathlib import Path

from src.types import ParseError, Word


_LINE_RE = re.compile(
    r"""^\s*
        (?P<num>\d+)\s*\.\s*
        (?P<rest>.+?)\s*$
    """,
    re.VERBOSE,
)

_CONTEXT_RE = re.compile(
    r"""^(?P<word>.+?)\s*
        \(\s*context\s*:\s*
        [\"“]?(?P<ctx>.+?)[\"”]?\s*
        \)\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_word_list(path: Path) -> tuple[list[Word], list[ParseError]]:
    words: list[Word] = []
    errors: list[ParseError] = []
    text = Path(path).read_text(encoding="utf-8")
    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            errors.append(ParseError(line_number=idx, content=raw, reason="not a numbered line"))
            continue
        numero = int(m.group("num"))
        rest = m.group("rest").strip()
        cm = _CONTEXT_RE.match(rest)
        if cm:
            palavra = cm.group("word").strip()
            contexto = cm.group("ctx").strip()
        else:
            palavra = rest
            contexto = None
        words.append(Word(numero=numero, palavra=palavra, contexto=contexto))
    return words, errors
