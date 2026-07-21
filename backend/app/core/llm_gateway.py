from __future__ import annotations

import json
from typing import Any, Protocol

import httpx

from app.config import Settings, settings
from app.core._debug_log import log_llm_request, log_llm_response


class LLMProviderError(RuntimeError):
    """Raised when an OpenAI-compatible LLM request cannot be completed."""

    error_code = "LLM_ERROR"
    retryable = True


class LLMConfigurationError(LLMProviderError):
    error_code = "LLM_CONFIG_ERROR"
    retryable = False


class LLMRateLimitError(LLMProviderError):
    error_code = "LLM_RATE_LIMIT"
    retryable = True


class LLMGateway(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


class OpenAICompatibleLLM:
    """Small chat-completions client shared by OpenAI-compatible gateways."""

    def __init__(self, config: Settings = settings, client: Any | None = None):
        self.config = config
        self.client = client

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        api_key = self.config.llm_api_key
        if not api_key:
            raise LLMConfigurationError("LLM API key is not configured")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": self.config.llm_model,
            "messages": messages,
            "temperature": self.config.llm_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.llm_max_tokens,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{self.config.llm_base_url.rstrip('/')}/chat/completions"
        log_llm_request(messages, self.config.llm_model, payload["max_tokens"])
        try:
            response = await self._post(url, headers, payload)
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else 0
            _log_response_body(status_code, exc.response)
            if status_code == 429:
                raise LLMRateLimitError("LLM provider rate limit exceeded") from exc
            error = LLMProviderError(f"LLM request returned HTTP {status_code}")
            error.retryable = status_code >= 500
            error.error_code = "LLM_SERVER_ERROR" if status_code >= 500 else "LLM_ERROR"
            raise error from exc
        except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError) as exc:
            raise LLMProviderError(f"LLM request failed: {exc}") from exc
        except httpx.HTTPError as exc:
            error = LLMProviderError(f"LLM request failed: {exc}")
            error.retryable = False
            raise error from exc
        try:
            response_body = response.json()
            log_llm_response(200, json.dumps(response_body, ensure_ascii=False))
            content = response_body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            _log_response_body(200, response)
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


def _log_response_body(status: int, response: Any) -> None:
    """Extract and log response body text, safe for any response type."""
    try:
        body = response.text
    except Exception:
        body = str(response)[:3000]
    log_llm_response(status, body)


def get_llm_gateway(config: Settings = settings) -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(config=config)
