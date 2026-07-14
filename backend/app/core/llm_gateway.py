from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.config import Settings, settings


class LLMProviderError(RuntimeError):
    """Raised when an OpenAI-compatible LLM request cannot be completed."""


class LLMGateway(Protocol):
    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str: ...


class OpenAICompatibleLLM:
    """Small chat-completions client shared by OpenAI-compatible gateways."""

    def __init__(self, config: Settings = settings, client: Any | None = None):
        self.config = config
        self.client = client

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        api_key = self.config.llm_api_key
        if not api_key:
            raise LLMProviderError("LLM API key is not configured")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.config.llm_model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            response = await self._post(
                f"{self.config.llm_base_url.rstrip('/')}/chat/completions", headers, payload
            )
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
        except (httpx.HTTPError, OSError) as exc:
            raise LLMProviderError(f"LLM request failed: {exc}") from exc
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("LLM response has an invalid shape") from exc
        if isinstance(content, list):
            content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
        if not isinstance(content, str) or not content.strip():
            raise LLMProviderError("LLM returned an empty response")
        return content.strip()

    async def _post(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
        if self.client is not None:
            return await self.client.post(url, headers=headers, json=payload)
        timeout = httpx.Timeout(self.config.llm_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, headers=headers, json=payload)


OpenAICompatibleLLMProvider = OpenAICompatibleLLM


def get_llm_gateway(config: Settings = settings) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(config=config)
