"""Síntesis mediante el servicio en línea usado por Microsoft Edge."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EdgeTTSSettings:
    voice: str = "es-MX-DaliaNeural"
    rate: str = "+0%"
    volume: str = "+0%"
    pitch: str = "+0Hz"


def synthesize_edge(text: str, output: Path, settings: EdgeTTSSettings) -> None:
    import edge_tts

    async def generate() -> None:
        communicate = edge_tts.Communicate(
            text,
            settings.voice,
            rate=settings.rate,
            volume=settings.volume,
            pitch=settings.pitch,
        )
        await communicate.save(str(output))

    asyncio.run(generate())


def list_spanish_voices() -> list[dict[str, str]]:
    import edge_tts

    async def load() -> list[dict[str, str]]:
        voices = await edge_tts.list_voices()
        return [
            {
                "name": str(voice["ShortName"]),
                "locale": str(voice["Locale"]),
                "gender": str(voice["Gender"]),
                "display_name": str(voice.get("FriendlyName", voice["ShortName"])),
            }
            for voice in voices
            if str(voice.get("Locale", "")).startswith("es-")
        ]

    return asyncio.run(load())


async def stream_edge(
    text: str, settings: EdgeTTSSettings
):
    """Entrega audio MP3 conforme Edge lo genera."""
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        settings.voice,
        rate=settings.rate,
        volume=settings.volume,
        pitch=settings.pitch,
    )
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]
