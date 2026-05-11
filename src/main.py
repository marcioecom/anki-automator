"""CLI entry point: orchestrates parsing -> enrichment -> interactive review -> Anki insert."""
from __future__ import annotations

import argparse
import re
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


def _bold_in_sentence(sentence: str, word: str) -> str:
    """Wrap occurrences of `word` (case-insensitive, word-boundary) with <b>...</b>.

    Preserves the original casing of the match. Returns the sentence unchanged
    if the word is not found.
    """
    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    return pattern.sub(lambda m: f"<b>{m.group(0)}</b>", sentence)


def _make_front_back(sentence: str, ew: llm.EnrichedWord, media_filename: str | None) -> tuple[str, str]:
    bolded = _bold_in_sentence(sentence, ew.palavra)
    front = bolded + (f" [sound:{media_filename}]" if media_filename else "")
    back = f"<b>{ew.palavra.capitalize()}</b>: {ew.traducao}"
    return front, back


def main() -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="anki-automator")
    ap.add_argument("--file", required=True, type=Path)
    ap.add_argument("--deck", default="English::Mining")
    ap.add_argument("--note-type", default="Basic")
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument(
        "--provider",
        choices=["anthropic", "groq"],
        default="groq",
        help="LLM provider (default: groq - free tier).",
    )
    ap.add_argument(
        "--model",
        default=None,
        help="Override model. Defaults: anthropic=claude-haiku-4-5-20251001, groq=llama-3.3-70b-versatile.",
    )
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()
    model = args.model or llm.DEFAULT_MODELS[args.provider]

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
        console.print(
            f"[cyan]Resuming: {len(state.processed)} processed, "
            f"{len(state.skipped)} skipped previously.[/cyan]"
        )

    pending = [w for w in words if w.numero not in state.processed and w.numero not in state.skipped]
    if not pending:
        console.print("[green]Nothing to do - all words already processed.[/green]")
        return 0

    def _sigint_handler(_signum, _frame):
        console.print("\n[yellow]Saving checkpoint before exit...[/yellow]")
        checkpoint.save(state, state_path)
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)

    console.print(
        f"[bold]Enriching {len(pending)} word(s) via {args.provider} ({model})...[/bold]"
    )
    enriched = llm.enrich_words(
        pending, provider=args.provider, model=model, batch_size=args.batch_size
    )
    enriched_by_num = {ew.numero: ew for ew in enriched}

    media_dir = Path(tempfile.gettempdir()) / "anki-automator-media"
    created = 0
    skipped = 0
    failed = 0

    for word in pending:
        ew = enriched_by_num.get(word.numero)
        if ew is None:
            console.print(
                f"[red]{args.provider} did not return data for #{word.numero} '{word.palavra}', skipping.[/red]"
            )
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

    console.print(
        Panel(
            f"[green]Created: {created}[/green]   "
            f"[yellow]Skipped: {skipped}[/yellow]   "
            f"[red]Failed: {failed}[/red]",
            title="Summary",
            border_style="bold",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
