# anki-automator

CLI que automatiza a etapa de mineracao de palavras do metodo Mairo Vergara: recebe uma lista numerada em `.txt`, chama o Claude para gerar explicacao/traducao/5 exemplos por palavra, gera audio TTS via Google Translate (`gTTS`) e cria os cards no Anki via AnkiConnect, com revisao interativa e checkpoint para retomar onde parou.

## Pre-requisitos

1. **Anki Desktop** instalado e aberto.
2. **AnkiConnect** add-on: Anki > Tools > Add-ons > Get Add-ons > codigo `2055492159` > restart do Anki.
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

Linhas em branco sao ignoradas. Linhas mal formatadas sao reportadas no inicio e o script pergunta se voce quer continuar com as validas.

## Uso

```bash
uv run anki-automator --file exemplos/lista_exemplo.txt --deck "Ingles::Mineracao"
```

Flags:

- `--file` (obrigatorio): caminho do `.txt`
- `--deck` (default `English::Mining`): deck de destino, criado se nao existir
- `--note-type` (default `Basic`)
- `--batch-size` (default `10`): palavras por chamada do Claude
- `--model` (default `claude-haiku-4-5-20251001`)
- `--no-resume`: ignora o `.state.json` e comeca do zero

## Atalhos no loop interativo

- `1`-`5`: usa o exemplo correspondente como front do card
- `e`: digita uma frase custom
- `s`: pula a palavra (vai pro `skipped`, nao recriada em resume)
- `q`: salva checkpoint e sai

## Formato do card gerado

- **Front**: frase em ingles + `[sound:<arquivo>.mp3]`
- **Back**: `*Palavra*: traducao`
- **Tag**: `anki-automator`

## Resumibilidade

A cada palavra processada o script grava `<seu_arquivo>.txt.state.json` ao lado do input. Rode o mesmo comando para continuar de onde parou. Use `--no-resume` para comecar do zero.

## Testes

```bash
uv run pytest
```
