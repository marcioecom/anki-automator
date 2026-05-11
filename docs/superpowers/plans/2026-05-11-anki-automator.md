# anki-automator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that converts a numbered word list (`.txt`) into Anki cards (Front: English example sentence + Google Translate TTS audio; Back: `*Word*: PT-BR translation`) by orchestrating the Claude API, gTTS, and AnkiConnect.

**Architecture:** Linear CLI with interactive review (user picks one of 5 example sentences per word) and a resumable JSON checkpoint. Six focused modules: `parser`, `llm`, `tts`, `anki_connect`, `checkpoint`, and `main` (orchestrator).

**Tech Stack:** Python 3.11+, `anthropic`, `gtts`, `requests`, `questionary`, `rich`, `pydantic`, `python-dotenv`. Tests with `pytest`. Dependency management via `uv`.

---

## Pre-Setup

### Task 0: Initialize project skeleton

**Files:**
- Create: `/Users/marciojunior/code/marcioecom/anki-automator/pyproject.toml`
- Create: `/Users/marciojunior/code/marcioecom/anki-automator/.gitignore`
- Create: `/Users/marciojunior/code/marcioecom/anki-automator/.env.example`
- Create: `/Users/marciojunior/code/marcioecom/anki-automator/src/__init__.py`
- Create: `/Users/marciojunior/code/marcioecom/anki-automator/tests/__init__.py`
- Create: `/Users/marciojunior/code/marcioecom/anki-automator/exemplos/lista_exemplo.txt`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/marciojunior/code/marcioecom/anki-automator && git init
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "anki-automator"
version = "0.1.0"
description = "CLI that turns a numbered English word list into Anki cards via Claude + gTTS + AnkiConnect"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "gtts>=2.5.0",
    "requests>=2.32.0",
    "questionary>=2.0.0",
    "rich>=13.7.0",
    "pydantic>=2.7.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[project.scripts]
anki-automator = "src.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

- [ ] **Step 3: Write `.gitignore`**

```
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.state.json
.DS_Store
dist/
build/
*.egg-info/
```

- [ ] **Step 4: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 5: Create empty `__init__.py` files and sample input**

`src/__init__.py` and `tests/__init__.py`: both empty.

`exemplos/lista_exemplo.txt`:

```
1. apple
2. wavered
3. considerable (context: "considerable amount of …")
4. turned around
5. dimension
```

- [ ] **Step 6: Install dependencies**

Run: `cd /Users/marciojunior/code/marcioecom/anki-automator && uv venv && uv pip install -e ".[dev]"`
Expected: venv created, packages installed.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/__init__.py tests/__init__.py exemplos/
git commit -m "chore: project scaffold"
```

---

## Task 1: Parser module

**Files:**
- Create: `src/parser.py`
- Test: `tests/test_parser.py`

- [ ] **Step 1: Write failing tests**

`tests/test_parser.py`:

```python
from pathlib import Path
import pytest
from src.parser import parse_word_list, Word, ParseError


def write(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "list.txt"
    f.write_text(content, encoding="utf-8")
    return f


def test_parses_simple_line(tmp_path):
    f = write(tmp_path, "345. obviously\n")
    words, errors = parse_word_list(f)
    assert errors == []
    assert words == [Word(numero=345, palavra="obviously", contexto=None)]


def test_parses_multiword_term(tmp_path):
    f = write(tmp_path, "348. turned around\n")
    words, errors = parse_word_list(f)
    assert words == [Word(numero=348, palavra="turned around", contexto=None)]


def test_parses_context_with_smart_quotes(tmp_path):
    f = write(tmp_path, '351. considerable (context: "considerable amount of …")\n')
    words, errors = parse_word_list(f)
    assert words == [Word(numero=351, palavra="considerable", contexto="considerable amount of …")]


def test_parses_context_with_curly_quotes(tmp_path):
    f = write(tmp_path, '351. considerable (context: “considerable amount of …”)\n')
    words, errors = parse_word_list(f)
    assert words[0].contexto == "considerable amount of …"


def test_skips_blank_lines(tmp_path):
    f = write(tmp_path, "1. apple\n\n2. banana\n")
    words, errors = parse_word_list(f)
    assert [w.palavra for w in words] == ["apple", "banana"]
    assert errors == []


def test_reports_malformed_line(tmp_path):
    f = write(tmp_path, "1. apple\nnot-a-numbered-line\n2. banana\n")
    words, errors = parse_word_list(f)
    assert [w.palavra for w in words] == ["apple", "banana"]
    assert len(errors) == 1
    assert errors[0].line_number == 2
    assert "not-a-numbered-line" in errors[0].content


def test_empty_file(tmp_path):
    f = write(tmp_path, "")
    words, errors = parse_word_list(f)
    assert words == []
    assert errors == []


def test_strips_surrounding_whitespace(tmp_path):
    f = write(tmp_path, "  42.   hiking  \n")
    words, errors = parse_word_list(f)
    assert words == [Word(numero=42, palavra="hiking", contexto=None)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/marciojunior/code/marcioecom/anki-automator && uv run pytest tests/test_parser.py -v`
Expected: ImportError or all tests fail.

- [ ] **Step 3: Implement `src/parser.py`**

```python
"""Parse a numbered English word list into structured `Word` records."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Word:
    numero: int
    palavra: str
    contexto: str | None


@dataclass(frozen=True)
class ParseError:
    line_number: int
    content: str
    reason: str


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_parser.py -v`
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/parser.py tests/test_parser.py
git commit -m "feat(parser): numbered word list parser with context support"
```

---

## Task 2: Checkpoint module

**Files:**
- Create: `src/checkpoint.py`
- Test: `tests/test_checkpoint.py`

- [ ] **Step 1: Write failing tests**

`tests/test_checkpoint.py`:

```python
from pathlib import Path
import json
import pytest
from src.checkpoint import CheckpointState, load, save, checkpoint_path_for


def test_checkpoint_path_for():
    assert checkpoint_path_for(Path("/tmp/lista.txt")) == Path("/tmp/lista.txt.state.json")


def test_load_missing_returns_empty(tmp_path):
    state = load(tmp_path / "missing.state.json")
    assert state == CheckpointState(processed=set(), skipped=set(), card_ids={})


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "x.state.json"
    s = CheckpointState(processed={1, 2, 3}, skipped={4}, card_ids={1: 9001, 2: 9002, 3: 9003})
    save(s, p)
    loaded = load(p)
    assert loaded == s


def test_save_is_atomic(tmp_path):
    p = tmp_path / "atomic.state.json"
    save(CheckpointState(processed={1}, skipped=set(), card_ids={1: 5}), p)
    assert p.exists()
    # tmp file must be cleaned up
    assert not (tmp_path / "atomic.state.json.tmp").exists()


def test_save_overwrites(tmp_path):
    p = tmp_path / "x.state.json"
    save(CheckpointState(processed={1}, skipped=set(), card_ids={1: 10}), p)
    save(CheckpointState(processed={1, 2}, skipped=set(), card_ids={1: 10, 2: 20}), p)
    loaded = load(p)
    assert loaded.processed == {1, 2}
    assert loaded.card_ids == {1: 10, 2: 20}


def test_load_corrupted_raises(tmp_path):
    p = tmp_path / "broken.state.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load(p)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_checkpoint.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `src/checkpoint.py`**

```python
"""Atomic JSON checkpoint to resume interrupted runs."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckpointState:
    processed: set[int] = field(default_factory=set)
    skipped: set[int] = field(default_factory=set)
    card_ids: dict[int, int] = field(default_factory=dict)


def checkpoint_path_for(input_path: Path) -> Path:
    return Path(str(input_path) + ".state.json")


def load(path: Path) -> CheckpointState:
    if not path.exists():
        return CheckpointState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"corrupted checkpoint at {path}: {e}") from e
    return CheckpointState(
        processed=set(raw.get("processed", [])),
        skipped=set(raw.get("skipped", [])),
        card_ids={int(k): int(v) for k, v in raw.get("card_ids", {}).items()},
    )


def save(state: CheckpointState, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "processed": sorted(state.processed),
        "skipped": sorted(state.skipped),
        "card_ids": {str(k): v for k, v in state.card_ids.items()},
    }
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_checkpoint.py -v`
Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/checkpoint.py tests/test_checkpoint.py
git commit -m "feat(checkpoint): atomic resumable state file"
```

---

## Task 3: AnkiConnect client

**Files:**
- Create: `src/anki_connect.py`

No unit tests (thin HTTP wrapper; verified manually against running Anki).

- [ ] **Step 1: Implement `src/anki_connect.py`**

```python
"""Thin client for AnkiConnect (https://foosoft.net/projects/anki-connect/)."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import requests


ANKI_CONNECT_URL = "http://127.0.0.1:8765"
ANKI_CONNECT_VERSION = 6


class AnkiConnectError(RuntimeError):
    pass


def _invoke(action: str, **params: Any) -> Any:
    try:
        r = requests.post(
            ANKI_CONNECT_URL,
            json={"action": action, "version": ANKI_CONNECT_VERSION, "params": params},
            timeout=10,
        )
    except requests.ConnectionError as e:
        raise AnkiConnectError(
            "Cannot reach AnkiConnect on http://127.0.0.1:8765. "
            "Open Anki Desktop and ensure the AnkiConnect add-on (2055492159) is installed."
        ) from e
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        raise AnkiConnectError(f"AnkiConnect error on '{action}': {body['error']}")
    return body.get("result")


def health_check() -> None:
    version = _invoke("version")
    if version != ANKI_CONNECT_VERSION:
        raise AnkiConnectError(
            f"AnkiConnect API version mismatch (got {version}, expected {ANKI_CONNECT_VERSION})"
        )


def ensure_deck(deck_name: str) -> None:
    _invoke("createDeck", deck=deck_name)


def store_media_file(local_path: Path) -> str:
    """Upload an MP3 to Anki's media collection. Returns the filename used inside Anki."""
    data = base64.b64encode(local_path.read_bytes()).decode("ascii")
    filename = local_path.name
    _invoke("storeMediaFile", filename=filename, data=data)
    return filename


def add_note(deck: str, note_type: str, front: str, back: str) -> int:
    return _invoke(
        "addNote",
        note={
            "deckName": deck,
            "modelName": note_type,
            "fields": {"Front": front, "Back": back},
            "options": {"allowDuplicate": False},
            "tags": ["anki-automator"],
        },
    )
```

- [ ] **Step 2: Smoke check (manual, optional now)**

If Anki Desktop is open with AnkiConnect installed:
```bash
uv run python -c "from src.anki_connect import health_check; health_check(); print('ok')"
```
Expected: `ok`. If Anki is closed, you'll see the friendly error message - that's also acceptable proof.

- [ ] **Step 3: Commit**

```bash
git add src/anki_connect.py
git commit -m "feat(anki): minimal AnkiConnect HTTP client"
```

---

## Task 4: TTS module

**Files:**
- Create: `src/tts.py`

- [ ] **Step 1: Implement `src/tts.py`**

```python
"""Generate MP3 audio for English sentences via Google Translate TTS (gTTS)."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from gtts import gTTS
from gtts.tts import gTTSError


def _slug(sentence: str) -> str:
    h = hashlib.sha1(sentence.encode("utf-8")).hexdigest()[:12]
    return f"anki-automator-{h}.mp3"


def generate_mp3(sentence: str, output_dir: Path, retries: int = 3) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / _slug(sentence)
    if out.exists():
        return out
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            tts = gTTS(text=sentence, lang="en")
            tts.save(str(out))
            return out
        except (gTTSError, OSError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"gTTS failed after {retries} attempts: {last_err}")
```

- [ ] **Step 2: Smoke check**

```bash
uv run python -c "from pathlib import Path; from src.tts import generate_mp3; p = generate_mp3('hello world', Path('/tmp/anki-tts-test')); print(p, p.stat().st_size)"
```
Expected: a path printed with non-zero file size (a few KB).

- [ ] **Step 3: Commit**

```bash
git add src/tts.py
git commit -m "feat(tts): gTTS MP3 generation with retry and deterministic filenames"
```

---

## Task 5: LLM module (Claude batch enrichment)

**Files:**
- Create: `src/llm.py`

- [ ] **Step 1: Implement `src/llm.py`**

```python
"""Enrich words with explanation, translation, and examples via the Claude API."""
from __future__ import annotations

import json
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
```

- [ ] **Step 2: Smoke check (requires `ANTHROPIC_API_KEY`)**

```bash
cd /Users/marciojunior/code/marcioecom/anki-automator && uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from src.parser import Word
from src.llm import enrich_words
out = enrich_words([Word(numero=1, palavra='apple', contexto=None)], model='claude-haiku-4-5-20251001')
print(out[0].traducao, '|', out[0].exemplos[0])
"
```
Expected: prints a translation (e.g., `Maçã`) and one short English example. If you don't have the key handy yet, skip this and rely on the end-to-end smoke later.

- [ ] **Step 3: Commit**

```bash
git add src/llm.py
git commit -m "feat(llm): Claude batch enrichment with tool_use and prompt caching"
```

---

## Task 6: Main orchestrator

**Files:**
- Create: `src/main.py`

- [ ] **Step 1: Implement `src/main.py`**

```python
"""CLI entry point: orchestrates parsing -> enrichment -> interactive review -> Anki insert."""
from __future__ import annotations

import argparse
import signal
import sys
import tempfile
from pathlib import Path

import questionary
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from src import anki_connect, checkpoint, llm, parser, tts
from src.checkpoint import CheckpointState

console = Console()


def _print_word(ew: llm.EnrichedWord) -> None:
    body_lines = [f"[bold]{ew.palavra}[/bold]  ([italic]{ew.traducao}[/italic])", "", ew.explicacao, ""]
    for i, ex in enumerate(ew.exemplos, start=1):
        body_lines.append(f"  [cyan]{i}[/cyan]. {ex}")
    console.print(Panel("\n".join(body_lines), title=f"#{ew.numero}", border_style="blue"))


def _prompt_choice(ew: llm.EnrichedWord) -> tuple[str, str | None]:
    """Returns (action, sentence). action in {'pick','skip','quit'}."""
    choices = [f"{i}. {ex}" for i, ex in enumerate(ew.exemplos, start=1)]
    choices += ["[e] Edit / write custom sentence", "[s] Skip this word", "[q] Save and quit"]
    answer = questionary.select(f"Pick an example for '{ew.palavra}':", choices=choices).ask()
    if answer is None or answer.startswith("[q]"):
        return "quit", None
    if answer.startswith("[s]"):
        return "skip", None
    if answer.startswith("[e]"):
        custom = questionary.text("Custom sentence:").ask()
        if not custom:
            return "skip", None
        return "pick", custom.strip()
    idx = int(answer.split(".", 1)[0]) - 1
    return "pick", ew.exemplos[idx]


def _make_front_back(sentence: str, ew: llm.EnrichedWord, media_filename: str | None) -> tuple[str, str]:
    front = sentence + (f" [sound:{media_filename}]" if media_filename else "")
    back = f"*{ew.palavra}*: {ew.traducao}"
    return front, back


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="anki-automator")
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--deck", default="English::Mining")
    ap.add_argument("--note-type", default="Basic")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    try:
        anki_connect.health_check()
    except anki_connect.AnkiConnectError as e:
        console.print(f"[red]{e}[/red]")
        return 1

    anki_connect.ensure_deck(args.deck)

    words, errors = parser.parse_word_list(args.file)
    if errors:
        console.print(f"[yellow]Warning: {len(errors)} invalid line(s) skipped:[/yellow]")
        for err in errors:
            console.print(f"  line {err.line_number}: {err.content!r}")
        if not questionary.confirm("Continue with valid lines?").ask():
            return 1
    if not words:
        console.print("[red]No valid words to process. Exiting.[/red]")
        return 1

    state_path = checkpoint.checkpoint_path_for(args.file)
    state: CheckpointState = CheckpointState() if args.no_resume else checkpoint.load(state_path)
    if state.processed or state.skipped:
        console.print(f"[cyan]Resuming: {len(state.processed)} processed, {len(state.skipped)} skipped previously.[/cyan]")

    pending = [w for w in words if w.numero not in state.processed and w.numero not in state.skipped]
    if not pending:
        console.print("[green]Nothing to do - all words already processed.[/green]")
        return 0

    def _sigint_handler(_signum, _frame):
        console.print("\n[yellow]Saving checkpoint before exit...[/yellow]")
        checkpoint.save(state, state_path)
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)

    console.print(f"[bold]Enriching {len(pending)} word(s) via Claude...[/bold]")
    enriched = llm.enrich_words(pending, model=args.model, batch_size=args.batch_size)
    enriched_by_num = {ew.numero: ew for ew in enriched}

    media_dir = Path(tempfile.gettempdir()) / "anki-automator-media"
    created = 0
    skipped = 0
    failed = 0

    for word in pending:
        ew = enriched_by_num.get(word.numero)
        if ew is None:
            console.print(f"[red]Claude did not return data for #{word.numero} '{word.palavra}', skipping.[/red]")
            failed += 1
            continue
        _print_word(ew)
        action, sentence = _prompt_choice(ew)
        if action == "quit":
            break
        if action == "skip":
            state.skipped.add(word.numero)
            checkpoint.save(state, state_path)
            skipped += 1
            continue
        assert sentence is not None
        try:
            mp3_path = tts.generate_mp3(sentence, media_dir)
            media_filename = anki_connect.store_media_file(mp3_path)
        except Exception as e:
            console.print(f"[yellow]TTS failed for '{word.palavra}': {e}[/yellow]")
            if not questionary.confirm("Create the card without audio?").ask():
                state.skipped.add(word.numero)
                checkpoint.save(state, state_path)
                skipped += 1
                continue
            media_filename = None
        front, back = _make_front_back(sentence, ew, media_filename)
        try:
            note_id = anki_connect.add_note(args.deck, args.note_type, front, back)
        except anki_connect.AnkiConnectError as e:
            console.print(f"[red]Anki add_note failed for '{word.palavra}': {e}[/red]")
            failed += 1
            continue
        state.processed.add(word.numero)
        state.card_ids[word.numero] = note_id
        checkpoint.save(state, state_path)
        created += 1
        console.print(f"[green]Card created (id={note_id})[/green]\n")

    console.print(Panel(
        f"[green]Created: {created}[/green]   [yellow]Skipped: {skipped}[/yellow]   [red]Failed: {failed}[/red]",
        title="Summary",
        border_style="bold",
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Sanity check the CLI parser**

```bash
uv run python -m src.main --help
```
Expected: prints argparse help, no traceback.

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat(main): CLI orchestrator with interactive review and resumable run"
```

---

## Task 7: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# anki-automator

CLI que automatiza a etapa de mineracao de palavras do metodo Mairo Vergara: recebe uma lista numerada em `.txt`, chama o Claude para gerar explicacao/traducao/5 exemplos por palavra, gera audio TTS via Google Translate (`gTTS`) e cria os cards no Anki via AnkiConnect, com revisao interativa e checkpoint para retomar onde parou.

## Pre-requisitos

1. **Anki Desktop** instalado e aberto.
2. **AnkiConnect** add-on: Anki > Tools > Add-ons > Get Add-ons > codigo `2055492159` > restart.
3. **Python 3.11+** e [`uv`](https://docs.astral.sh/uv/).
4. Uma **chave da API Anthropic** (`ANTHROPIC_API_KEY`).

## Setup

```bash
git clone <repo> && cd anki-automator
uv venv && uv pip install -e ".[dev]"
cp .env.example .env
# edite o .env e preencha ANTHROPIC_API_KEY
```

## Formato da lista

```
1. obviously
2. turned around
3. considerable (context: "considerable amount of …")
```

## Uso

```bash
uv run anki-automator --file exemplos/lista_exemplo.txt --deck "Ingles::Mineracao"
```

Flags relevantes:

- `--file` (obrigatorio): caminho do `.txt`
- `--deck` (default `English::Mining`): deck de destino, criado se nao existir
- `--note-type` (default `Basic`)
- `--batch-size` (default `10`): palavras por chamada do Claude
- `--model` (default `claude-haiku-4-5-20251001`)
- `--no-resume`: ignora o `.state.json`

## Atalhos no loop interativo

- `1`-`5`: usa o exemplo correspondente
- `e`: digita uma frase custom
- `s`: pula a palavra (vai pro `skipped`, nao recriada em resume)
- `q`: salva checkpoint e sai

## Resumibilidade

A cada palavra processada o script grava `seu_arquivo.txt.state.json` ao lado do input. Rode o mesmo comando para continuar de onde parou. Use `--no-resume` para comecar do zero.

## Testes

```bash
uv run pytest
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup and usage"
```

---

## Final Verification

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -v`
Expected: all parser + checkpoint tests pass.

- [ ] **Step 2: Smoke test end-to-end**

Pre-conditions: Anki Desktop open, AnkiConnect installed, deck `Teste` created in Anki, `.env` with valid `ANTHROPIC_API_KEY`.

```bash
printf "1. apple\n2. run\n3. beautiful\n" > /tmp/smoke.txt
uv run anki-automator --file /tmp/smoke.txt --deck "Teste"
```

Expected:
- Health check passes
- Claude returns 3 enriched entries
- For each, terminal shows panel + 5 examples
- After choosing, you see "Card created (id=...)" three times
- Inspecting the deck in Anki shows 3 cards with audio attached

- [ ] **Step 3: Resume test**

```bash
printf "1. apple\n2. run\n3. beautiful\n4. hiking\n5. injury\n" > /tmp/resume.txt
uv run anki-automator --file /tmp/resume.txt --deck "Teste"
# After 2 cards created, press Ctrl+C
uv run anki-automator --file /tmp/resume.txt --deck "Teste"
```

Expected: second invocation prints "Resuming: 2 processed..." and only prompts for the remaining 3.

- [ ] **Step 4: Error path test**

Close Anki Desktop, then:
```bash
uv run anki-automator --file /tmp/smoke.txt --deck "Teste"
```
Expected: friendly red message about AnkiConnect, no Python traceback.

---

## Self-Review Notes

Spec coverage verified against `/Users/marciojunior/.claude/plans/eu-estudo-ingl-s-usando-stateless-boot.md`:

- Parser, llm, tts, anki_connect, checkpoint, main: each gets its own task with code shown in full.
- Interactive review (1-5 / e / s / q): implemented in `_prompt_choice`.
- Checkpoint atomic write, resume, skip vs processed: implemented and tested.
- Claude batch with prompt caching + tool_use: implemented in `enrich_words`.
- gTTS with deterministic filename and retries: implemented.
- AnkiConnect health_check / storeMediaFile / addNote: implemented.
- Error handling for offline Anki, gTTS failure, Ctrl+C, malformed input: covered in `main.py`.
- README with setup steps including AnkiConnect add-on code: covered.

No `TBD`/`TODO`/placeholders. Types referenced (`Word`, `EnrichedWord`, `CheckpointState`, `ParseError`) all defined in earlier tasks before use.
