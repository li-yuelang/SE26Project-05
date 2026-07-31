"""Tests for LLM gateway — fully mocked HTTP client."""

import pytest

from app.config import Settings
from app.core.llm_gateway import LLMProviderError, OpenAICompatibleLLM


class FakeLLMResponse:
    def __init__(self, body: dict):
        self._json = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._json


class FakeLLMClient:
    def __init__(self, responses: list[FakeLLMResponse]):
        self._responses = iter(responses)
        self._calls: list[dict] = []

    async def post(self, url: str, *, headers: dict, json: dict) -> FakeLLMResponse:
        self._calls.append({"url": url, "headers": headers, "payload": json})
        try:
            return next(self._responses)
        except StopIteration:
            return FakeLLMResponse(
                {"choices": [{"message": {"content": "default response"}}]}
            )


def test_generate_returns_content_when_valid_response() -> None:
    client = FakeLLMClient([
        FakeLLMResponse({"choices": [{"message": {"content": "Hello from LLM"}}]})
    ])
    config = Settings(llm_api_key="sk-test")
    llm = OpenAICompatibleLLM(config=config, client=client)
    # Must use asyncio
    import asyncio
    result = asyncio.run(llm.generate("What is AI?"))
    assert result == "Hello from LLM"
    assert client._calls[0]["payload"]["messages"][-1]["content"] == "What is AI?"


def test_generate_with_system_prompt() -> None:
    client = FakeLLMClient([
        FakeLLMResponse({"choices": [{"message": {"content": "OK"}}]})
    ])
    config = Settings(llm_api_key="sk-test")
    llm = OpenAICompatibleLLM(config=config, client=client)
    import asyncio
    asyncio.run(llm.generate("Question", system_prompt="You are helpful."))
    messages = client._calls[0]["payload"]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are helpful."
    assert messages[1]["role"] == "user"


def test_generate_raises_when_no_api_key() -> None:
    config = Settings(llm_api_key=None)
    llm = OpenAICompatibleLLM(config=config)
    import asyncio
    with pytest.raises(LLMProviderError, match="API key"):
        asyncio.run(llm.generate("hello"))


def test_generate_raises_on_invalid_response_shape() -> None:
    client = FakeLLMClient([
        FakeLLMResponse({})  # missing "choices"
    ])
    config = Settings(llm_api_key="sk-test")
    llm = OpenAICompatibleLLM(config=config, client=client)
    import asyncio
    with pytest.raises(LLMProviderError, match="invalid shape"):
        asyncio.run(llm.generate("hello"))


def test_generate_raises_on_empty_response() -> None:
    client = FakeLLMClient([
        FakeLLMResponse({"choices": [{"message": {"content": "   "}}]})
    ])
    config = Settings(llm_api_key="sk-test")
    llm = OpenAICompatibleLLM(config=config, client=client)
    import asyncio
    with pytest.raises(LLMProviderError, match="empty"):
        asyncio.run(llm.generate("hello"))
