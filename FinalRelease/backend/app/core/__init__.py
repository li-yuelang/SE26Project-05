"""Shared provider factories."""

from app.core.embedding import get_embedding_provider
from app.core.llm_gateway import get_llm_gateway

__all__ = ["get_embedding_provider", "get_llm_gateway"]
