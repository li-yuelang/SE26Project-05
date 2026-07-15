from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.config import Settings, settings


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot return a valid vector batch."""


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAICompatibleEmbeddingProvider:
    """OpenAI-compatible embeddings client with strict 1536-dimension checks."""

    EXPECTED_DIMENSION = 1536

    def __init__(self, config: Settings = settings, client: Any | None = None):
        self.config = config
        self.client = client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.config.embedding_dimension != self.EXPECTED_DIMENSION:
            raise EmbeddingProviderError(
                f"Embedding dimension must be {self.EXPECTED_DIMENSION}"
            )
        api_key = self.config.embedding_api_key or self.config.llm_api_key
        if not api_key:
            raise EmbeddingProviderError("Embedding API key is not configured")
        base_url = self.config.embedding_base_url or self.config.llm_base_url
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        results: list[list[float]] = []
        batch_size = max(1, self.config.embedding_batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {"model": self.config.embedding_model, "input": batch}
            try:
                response = await self._post(f"{base_url.rstrip('/')}/embeddings", headers, payload)
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            except (httpx.HTTPError, OSError) as exc:
                raise EmbeddingProviderError(f"Embedding request failed: {exc}") from exc
            try:
                body = response.json()
                rows = body["data"]
                rows = sorted(rows, key=lambda row: row.get("index", 0))
                vectors = [[float(value) for value in row["embedding"]] for row in rows]
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                raise EmbeddingProviderError("Embedding response has an invalid shape") from exc
            if len(vectors) != len(batch):
                raise EmbeddingProviderError(
                    f"Embedding provider returned {len(vectors)} vectors for {len(batch)} inputs"
                )
            for vector in vectors:
                if len(vector) != self.EXPECTED_DIMENSION:
                    raise EmbeddingProviderError(
                        "Embedding dimension mismatch: "
                        f"expected {self.EXPECTED_DIMENSION}, got {len(vector)}"
                    )
            results.extend(vectors)
        return results

    async def _post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        if self.client is not None:
            return await self.client.post(url, headers=headers, json=payload)
        timeout = httpx.Timeout(self.config.embedding_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, json=payload)


def get_embedding_provider(config: Settings = settings) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(config=config)
