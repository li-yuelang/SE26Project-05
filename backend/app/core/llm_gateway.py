from typing import Protocol


class LLMGateway(Protocol):
    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str: ...
