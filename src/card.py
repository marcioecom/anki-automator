"""Card formatting: builds Anki front/back HTML from enriched word data."""
from __future__ import annotations

import re

from src.types import EnrichedWord


def bold_in_sentence(sentence: str, word: str) -> str:
    """Wrap occurrences of `word` (case-insensitive, word-boundary) with <b>...</b>.

    Preserves the original casing of the match. Returns the sentence unchanged
    if the word is not found.
    """
    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    return pattern.sub(lambda m: f"<b>{m.group(0)}</b>", sentence)


def make_front_back(
    sentence: str, ew: EnrichedWord, media_filename: str | None
) -> tuple[str, str]:
    """Build the front and back HTML for an Anki card.

    Front: the sentence with the target word bolded, optionally appended with
    a [sound:filename.mp3] tag.
    Back: the capitalized word followed by its translation.
    """
    bolded = bold_in_sentence(sentence, ew.palavra)
    front = bolded + (f" [sound:{media_filename}]" if media_filename else "")
    back = f"<b>{ew.palavra.capitalize()}</b>: {ew.traducao}"
    return front, back
