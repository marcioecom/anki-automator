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
