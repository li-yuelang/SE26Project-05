from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ConceptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    aliases: list[str] = Field(default_factory=list)


class ConceptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    aliases: list[str] | None = None


class RelationCreate(BaseModel):
    target_concept_id: UUID
    relation_type: str = Field(min_length=1, max_length=64)
    weight: float = Field(default=1.0, ge=0, le=1)
