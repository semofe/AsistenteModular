"""Embeddings semánticos remotos para la memoria de Asistente Modular."""
from __future__ import annotations

from typing import Literal


class GeminiEmbeddingProvider:
    model = "gemini-embedding-001"
    dimensions = 768

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def embed(self, text: str, task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]) -> list[float]:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.api_key)
        response = client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type=task_type, output_dimensionality=self.dimensions,
            ),
        )
        if not response.embeddings:
            raise RuntimeError("Gemini no devolvió un embedding.")
        return [float(value) for value in response.embeddings[0].values]