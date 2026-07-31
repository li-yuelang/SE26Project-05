from typing import Protocol
from uuid import UUID


class SearchService(Protocol):
    async def search_chunks(self, query: str, *, paper_ids: list[UUID] | None = None) -> list[UUID]: ...
