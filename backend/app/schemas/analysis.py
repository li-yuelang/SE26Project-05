"""Validated JSON contracts used between the LLM and the analysis pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "；".join(_as_text(item) for item in value if _as_text(item))
    if isinstance(value, dict):
        return "; ".join(f"{key}: {_as_text(item)}" for key, item in value.items() if _as_text(item))
    return str(value).strip()


class AnalysisModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ExtractedConcept(AnalysisModel):
    name_en: str = Field(
        default="",
        validation_alias=AliasChoices("name_en", "english_name", "name", "term", "concept"),
    )
    name_zh: str = Field(
        default="",
        validation_alias=AliasChoices("name_zh", "chinese_name", "alias", "zh_name"),
    )
    description: str = ""
    category: str = ""
    evidence: str = ""
    relevance: float = 1.0

    @field_validator("name_en", "name_zh", "description", "category", "evidence", mode="before")
    @classmethod
    def coerce_text(cls, value: Any) -> str:
        return _as_text(value)


class ExtractedRelation(AnalysisModel):
    source: str = Field(
        default="",
        validation_alias=AliasChoices("source", "source_concept", "subject", "from"),
    )
    target: str = Field(
        default="",
        validation_alias=AliasChoices("target", "target_concept", "object", "to"),
    )
    relation_type: str = Field(
        default="RELATED_TO",
        validation_alias=AliasChoices("relation_type", "type", "relation"),
    )
    evidence: str = ""
    confidence: float = 1.0

    @field_validator("source", "target", "relation_type", "evidence", mode="before")
    @classmethod
    def coerce_text(cls, value: Any) -> str:
        return _as_text(value)


class ExtractedReference(AnalysisModel):
    arxiv_id: str = Field(
        default="",
        validation_alias=AliasChoices("arxiv_id", "arxivId", "id", "arxiv"),
    )
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    context: str = ""
    confidence: float = 1.0

    @field_validator("arxiv_id", "title", "context", mode="before")
    @classmethod
    def coerce_text(cls, value: Any) -> str:
        return _as_text(value)

    @field_validator("authors", mode="before")
    @classmethod
    def coerce_authors(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [_as_text(item) for item in value if _as_text(item)]


class ChunkExtraction(AnalysisModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    relations: list[ExtractedRelation] = Field(default_factory=list)
    references: list[ExtractedReference] = Field(default_factory=list)

    @field_validator("summary", mode="before")
    @classmethod
    def coerce_summary(cls, value: Any) -> str:
        return _as_text(value)

    @field_validator("key_points", "methods", mode="before")
    @classmethod
    def coerce_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [_as_text(item) for item in value if _as_text(item)]


class FinalExtraction(ChunkExtraction):
    research_question: str = ""
    experiments: list[str] = Field(default_factory=list)
    contributions: list[str] = Field(default_factory=list)
    concept_description: str = ""

    @field_validator("research_question", "concept_description", mode="before")
    @classmethod
    def coerce_final_text(cls, value: Any) -> str:
        return _as_text(value)

    @field_validator("experiments", "contributions", mode="before")
    @classmethod
    def coerce_final_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        return [_as_text(item) for item in value if _as_text(item)]


__all__ = [
    "AnalysisModel",
    "ChunkExtraction",
    "ExtractedConcept",
    "ExtractedReference",
    "ExtractedRelation",
    "FinalExtraction",
]
