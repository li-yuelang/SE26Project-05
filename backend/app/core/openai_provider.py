"""OpenAI-compatible implementation of LLMGateway and EmbeddingProvider."""
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from app.config import settings
from app.core.embedding import EmbeddingProvider
from app.core.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


class OpenAILLMGateway(LLMGateway):
    """OpenAI / OpenAI-compatible chat completion gateway.

    Supports both official OpenAI API and self-hosted proxies (e.g. vLLM, LiteLLM)
    by configuring ``OPENAI_BASE_URL``.
    """

    def __init__(self) -> None:
        client_kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature
        self.max_tokens = settings.openai_max_tokens

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        """Send a chat completion request and return the response text."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            return content or ""
        except Exception:
            logger.exception("OpenAI chat completion failed")
            raise

    async def generate_stream(self, prompt: str, *, system_prompt: str | None = None):
        """Yield chunks from a streaming chat completion (for WebSocket / SSE)."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception:
            logger.exception("OpenAI streaming failed")
            raise


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding provider (e.g. text-embedding-3-small, 1536-dim)."""

    def __init__(self) -> None:
        client_kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = settings.openai_embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return []
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [d.embedding for d in response.data]
        except Exception:
            logger.exception("OpenAI embedding failed")
            raise
