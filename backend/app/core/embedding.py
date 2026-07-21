from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from app.config import Settings, settings
from app.core._debug_log import log_embedding_request, log_embedding_response


class EmbeddingProviderError(RuntimeError):
    """Raised when an embedding provider cannot return a valid vector batch."""

    error_code = "EMBEDDING_ERROR"
    retryable = True


class EmbeddingConfigurationError(EmbeddingProviderError):
    error_code = "EMBEDDING_ERROR"
    retryable = False


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
            error = EmbeddingProviderError(
                f"Embedding dimension must be {self.EXPECTED_DIMENSION}"
            )
            error.retryable = False
            raise error
        api_key = self.config.embedding_api_key or self.config.llm_api_key
        if not api_key:
            raise EmbeddingConfigurationError("Embedding API key is not configured")
        base_url = self.config.embedding_base_url or self.config.llm_base_url
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        results: list[list[float]] = []
        batch_size = max(1, self.config.embedding_batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload = {"model": self.config.embedding_model, "input": batch, "dimensions": self.config.embedding_dimension}
            log_embedding_request(self.config.embedding_model, len(batch), payload)
            try:
                response = await self._post(f"{base_url.rstrip('/')}/embeddings", headers, payload)
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code if exc.response is not None else 0
                _log_emb_response_body(status_code, exc.response)
                error = EmbeddingProviderError(
                    "Embedding provider rate limit exceeded"
                    if status_code == 429
                    else f"Embedding request returned HTTP {status_code}"
                )
                error.retryable = status_code == 429 or status_code >= 500
                error.error_code = "EMBEDDING_RATE_LIMIT" if status_code == 429 else "EMBEDDING_ERROR"
                raise error from exc
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError) as exc:
                raise EmbeddingProviderError(f"Embedding request failed: {exc}") from exc
            except httpx.HTTPError as exc:
                error = EmbeddingProviderError(f"Embedding request failed: {exc}")
                error.retryable = False
                raise error from exc
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


def _log_emb_response_body(status: int, response: Any) -> None:
    """Extract and log embedding response body text."""
    try:
        body = response.text
    except Exception:
        body = str(response)[:3000]
    log_embedding_response(status, body)


def get_embedding_provider(config: Settings = settings) -> OpenAICompatibleEmbeddingProvider:
    return OpenAICompatibleEmbeddingProvider(config=config)
