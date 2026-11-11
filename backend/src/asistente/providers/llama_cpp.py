"""Adaptador para el servidor OpenAI-compatible de llama.cpp."""

from __future__ import annotations

import httpx

from asistente.providers.base import ChatMessage, ChatProvider, GenerationResult


class LlamaCppProvider(ChatProvider):
    def __init__(self, model: str, base_url: str = "http://127.0.0.1:8080") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def generate(self, messages: list[ChatMessage]) -> GenerationResult:
        payload = {
            "model": self.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "stream": False,
            "temperature": 0.6,
            "max_tokens": 800,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self.base_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or input_tokens + output_tokens)
        return GenerationResult(
            text=str(message.get("content") or "No pude generar una respuesta con llama.cpp."),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
