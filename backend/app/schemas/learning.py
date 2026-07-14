"""Schemas for learning management."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Bookmark
# ---------------------------------------------------------------------------
class BookmarkCreate(BaseModel):
    paper_id: UUID
    folder: str | None = None


class BookmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paper_id: UUID
    folder: str | None = None
    created_at: datetime
    # paper summary fields (populated by service)
    paper_title: str | None = None
    paper_authors: list[str] | None = None
    paper_primary_category: str | None = None


# ---------------------------------------------------------------------------
# Note
# ---------------------------------------------------------------------------
class NoteCreate(BaseModel):
    paper_id: UUID
    content: str = Field(..., min_length=1, max_length=50000)
    anchor: dict | None = None
    is_public: bool = False


class NoteUpdate(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=50000)
    anchor: dict | None = None
    is_public: bool | None = None


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paper_id: UUID
    content: str
    anchor: dict | None = None
    is_public: bool = False
    created_at: datetime
    updated_at: datetime
    paper_title: str | None = None
    paper_authors: list[str] | None = None


# ---------------------------------------------------------------------------
# Comment
# ---------------------------------------------------------------------------
class CommentCreate(BaseModel):
    paper_id: UUID
    content: str = Field(..., min_length=1, max_length=10000)
    anchor: dict | None = None


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paper_id: UUID
    content: str
    anchor: dict | None = None
    created_at: datetime
    user_display_name: str | None = None
    paper_title: str | None = None


# ---------------------------------------------------------------------------
# Reading History
# ---------------------------------------------------------------------------
class ReadingHistoryRecord(BaseModel):
    paper_id: UUID
    progress: int = Field(default=0, ge=0, le=100)


class ReadingHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    paper_id: UUID
    progress: int = 0
    last_read_at: datetime
    paper_title: str | None = None
    paper_authors: list[str] | None = None
    paper_primary_category: str | None = None


# ---------------------------------------------------------------------------
# Followed Topic
# ---------------------------------------------------------------------------
class FollowedTopicCreate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    keywords: list[str] = Field(default_factory=list)


class FollowedTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    topic: str
    keywords: list[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Learning Overview
# ---------------------------------------------------------------------------
class LearningOverview(BaseModel):
    bookmark_count: int = 0
    note_count: int = 0
    comment_count: int = 0
    reading_history_count: int = 0
    followed_topic_count: int = 0
    recent_reading: list[ReadingHistoryOut] = Field(default_factory=list)
    recent_notes: list[NoteOut] = Field(default_factory=list)
    followed_topics: list[FollowedTopicOut] = Field(default_factory=list)
