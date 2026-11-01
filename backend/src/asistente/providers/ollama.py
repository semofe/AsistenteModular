"""Adaptador de Ollama para ejecución local."""

from __future__ import annotations

import httpx
import asyncio
import base64

from asistente.providers.base import ChatMessage, ChatProvider, GenerationResult


class OllamaProvider(ChatProvider):
    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def generate(self, messages: list[ChatMessage]) -> GenerationResult:
        # Convertir mensajes al formato de Ollama
        ollama_messages = []
        for msg in messages:
            ollama_msg = {"role": msg.role, "content": msg.content}
            ollama_messages.append(ollama_msg)

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": 0.6,
                "num_predict": 800
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        text = data.get("message", {}).get("content", "")
        input_tokens = data.get("prompt_eval_count", 0)
        output_tokens = data.get("eval_count", 0)
        total_tokens = input_tokens + output_tokens

        return GenerationResult(
            text=text or "No pude generar una respuesta con Ollama.",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thinking_tokens=0,
            total_tokens=total_tokens,
        )
