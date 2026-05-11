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
