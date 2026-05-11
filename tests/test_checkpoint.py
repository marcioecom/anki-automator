from pathlib import Path

import pytest

from src.checkpoint import CheckpointState, checkpoint_path_for, load, save


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
