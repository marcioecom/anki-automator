# anki-automator

CLI that automates the word-mining step of the Mairo Vergara English study method: takes a numbered `.txt` word list, calls an LLM (Groq or Anthropic) to produce a Portuguese explanation, translation, and 5 short English example sentences per word, generates Google Translate TTS audio via `gTTS`, and creates Anki cards through AnkiConnect with interactive review and a resumable checkpoint.

## Prerequisites

1. **Anki Desktop** installed and open.
2. **AnkiConnect** add-on: Anki > Tools > Add-ons > Get Add-ons > code `2055492159` > restart Anki.
3. **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/).
4. At least one LLM API key (only the provider you plan to use):
   - **Groq** (default, free tier): `GROQ_API_KEY` - get one at https://console.groq.com/keys
   - **Anthropic** (higher quality, paid): `ANTHROPIC_API_KEY`

## Setup

```bash
git clone <repo> && cd anki-automator
uv venv && uv pip install -e ".[dev]"
cp .env.example .env
# edit .env and fill in GROQ_API_KEY (or ANTHROPIC_API_KEY)
```

## Input format

```
1. obviously
2. turned around
3. considerable (context: "considerable amount of …")
```

Blank lines are ignored. Malformed lines are reported up front and the script asks whether to continue with the valid ones.

## Usage

```bash
# Default: Groq (free tier)
uv run anki-automator --file exemplos/lista_exemplo.txt --deck "English::Mining"

# Using Anthropic (Claude)
uv run anki-automator --file list.txt --deck "English::Mining" --provider anthropic

# Forcing a specific model
uv run anki-automator --file list.txt --provider groq --model llama-3.1-8b-instant
```

Flags:

- `--file` (required): path to the `.txt` list
- `--deck` (default `English::Mining`): target deck, created if it does not exist
- `--note-type` (default `Basic`)
- `--batch-size` (default `10`): words per LLM call
- `--provider` (default `groq`): `groq` or `anthropic`
- `--model` (default depends on provider):
  - `groq`: `llama-3.3-70b-versatile`
  - `anthropic`: `claude-haiku-4-5-20251001`
- `--no-resume`: ignore the `.state.json` and start fresh

## Interactive loop shortcuts

- `1`-`5`: use the corresponding example as the card front
- `e`: type a custom sentence
- `s`: skip this word (marked as `skipped`, not retried on resume)
- `q`: save checkpoint and quit

## Generated card format

- **Front**: English sentence with the target word wrapped in `<b>...</b>` + `[sound:<file>.mp3]`
- **Back**: `<b>Word</b>: translation` (capitalized, bold)
- **Tag**: `anki-automator`

## Resumability

After each processed word the script writes `<your_file>.txt.state.json` next to the input. Re-run the same command to pick up where you stopped. Use `--no-resume` to start from scratch.

## Tests

```bash
uv run pytest
```
