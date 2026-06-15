"""Shared types — the single seam for domain data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from pydantic import BaseModel, Field


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


class EnrichedWord(BaseModel):
    numero: int
    palavra: str
    contexto: str | None = None
    explicacao: str
    traducao: str
    exemplos: list[str] = Field(min_length=5, max_length=5)


class EnrichedWordFromLLM(BaseModel):
    """Schema for the LLM tool output. Excludes contexto, which is preserved from the original Word."""

    numero: int
    palavra: str
    explicacao: str
    traducao: str
    exemplos: list[str] = Field(min_length=5, max_length=5)


@dataclass
class CheckpointState:
    processed: set[int] = field(default_factory=set)
    skipped: set[int] = field(default_factory=set)
    card_ids: dict[int, int] = field(default_factory=dict)
