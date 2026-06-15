"""Atomic JSON checkpoint to resume interrupted runs."""
from __future__ import annotations

import json
import os
from pathlib import Path

from src.types import CheckpointState


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
