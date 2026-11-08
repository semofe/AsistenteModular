"""Adaptadores HTTP para proveedores de voz en la nube."""

from __future__ import annotations

from pathlib import Path

import httpx


class CloudTTSError(RuntimeError):
    pass


def _save_audio(response: httpx.Response, output: Path) -> Path:
    if response.status_code >= 400:
        detail = response.text[:500]
        raise CloudTTSError(f"HTTP {response.status_code}: {detail}")
    if not response.content:
        raise CloudTTSError("El proveedor no devolvió audio.")
    content_type = response.headers.get("content-type", "audio/mpeg")
    suffix = ".opus" if "opus" in content_type else ".wav" if "wav" in content_type else ".mp3"
    result = output.with_suffix(suffix)
    result.write_bytes(response.content)
    return result


def synthesize_elevenlabs(
    text: str, output: Path, api_key: str, voice_id: str, model: str
) -> Path:
    if not voice_id:
        raise CloudTTSError("Falta configurar el Voice ID de ElevenLabs.")
    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            params={"output_format": "mp3_44100_128"},
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": model, "language_code": "es"},
        )
    return _save_audio(response, output)


def synthesize_fish(
    text: str, output: Path, api_key: str, reference_id: str, model: str
) -> Path:
    if not reference_id:
        raise CloudTTSError("Falta configurar el Reference ID de Fish Audio.")
    with httpx.Client(timeout=90) as client:
        response = client.post(
            "https://api.fish.audio/v1/tts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "model": model,
            },
            json={
                "text": text,
                "reference_id": reference_id,
                "format": "mp3",
                "latency": "low",
                "normalize": True,
            },
        )
    return _save_audio(response, output)


def synthesize_custom(
    text: str,
    output: Path,
    api_key: str,
    endpoint: str,
    voice: str,
    model: str,
) -> Path:
    if not endpoint.startswith("https://"):
        raise CloudTTSError("La URL personalizada debe utilizar HTTPS.")
    with httpx.Client(timeout=90, follow_redirects=False) as client:
        response = client.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"text": text, "voice": voice, "model": model},
        )
    return _save_audio(response, output)
