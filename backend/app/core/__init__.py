"""Shared infrastructure helpers.

LLM Gateway and Embedding Provider singletons are initialised lazily so that
the application can still start (e.g. for health checks) when credentials
are not yet configured.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_llm_gateway = None
_embedding_provider = None


def get_llm_gateway():
    """Return the global LLM gateway singleton (lazy initialisation)."""
    global _llm_gateway
    if _llm_gateway is None:
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not set – LLM calls will fail at runtime")
        from app.core.openai_provider import OpenAILLMGateway

        _llm_gateway = OpenAILLMGateway()
    return _llm_gateway


def get_embedding_provider():
    """Return the global embedding provider singleton (lazy initialisation)."""
    global _embedding_provider
    if _embedding_provider is None:
        if not settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not set – embedding calls will fail at runtime")
        from app.core.openai_provider import OpenAIEmbeddingProvider

        _embedding_provider = OpenAIEmbeddingProvider()
    return _embedding_provider
