"""Contrato común para proveedores de modelos de lenguaje."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class SourceCitation:
    """Fuente pública usada para fundamentar una respuesta."""

    title: str
    url: str


@dataclass(frozen=True, slots=True)
class SourceCitation:
    """Fuente pública usada para fundamentar una respuesta."""

    title: str
    url: str

@dataclass(slots=True)
class GenerationResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    sources: list[SourceCitation] = field(default_factory=list)


class ChatProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[ChatMessage]) -> GenerationResult:
        """Genera una respuesta a partir del contexto ya limitado."""
