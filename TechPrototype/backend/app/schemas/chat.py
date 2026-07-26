from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=500)


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    paper_ids: list[UUID] | None = None
    scenario: str = Field(default="auto", pattern="^(auto|concept|comparison|lineage)$")
