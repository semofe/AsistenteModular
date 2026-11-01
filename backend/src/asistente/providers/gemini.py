"""Adaptador de Gemini sin dependencias hacia la interfaz."""

from __future__ import annotations

import asyncio

from asistente.providers.base import ChatMessage, ChatProvider, GenerationResult, SourceCitation


class GeminiProvider(ChatProvider):
    def __init__(self, api_key: str, model: str, web_search_enabled: bool = True) -> None:
        self.api_key = api_key
        self.model = model
        self.web_search_enabled = web_search_enabled

    @staticmethod
    def _sources(response: object) -> list[SourceCitation]:
        """Extrae fuentes de grounding sin depender de campos opcionales."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return []
        metadata = getattr(candidates[0], "grounding_metadata", None)
        chunks = getattr(metadata, "grounding_chunks", None) or []
        sources: list[SourceCitation] = []
        seen: set[str] = set()
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            url = str(getattr(web, "uri", "") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            title = str(getattr(web, "title", "") or url).strip()
            sources.append(SourceCitation(title=title, url=url))
        return sources

    async def generate(self, messages: list[ChatMessage]) -> GenerationResult:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Falta instalar la dependencia google-genai del backend."
            ) from exc

        system_parts = [m.content for m in messages if m.role == "system"]
        conversation = [m for m in messages if m.role != "system"]
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part.from_text(text=message.content)],
            )
            for message in conversation
        ]
        config_options: dict[str, object] = {
            "system_instruction": "\n\n".join(system_parts) or None,
            "temperature": 0.6,
        }
        if self.web_search_enabled:
            config_options["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        config = types.GenerateContentConfig(**config_options)

        def request() -> GenerationResult:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            usage = response.usage_metadata
            input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
            thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
            total_tokens = int(getattr(usage, "total_token_count", 0) or 0)
            return GenerationResult(
                text=response.text or "No pude generar una respuesta.",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                thinking_tokens=thinking_tokens,
                total_tokens=total_tokens or input_tokens + output_tokens + thinking_tokens,
                sources=self._sources(response),
            )

        return await asyncio.to_thread(request)
