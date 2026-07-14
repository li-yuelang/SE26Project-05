"""Learning management API endpoints – bookmarks, notes, comments, reading history, followed topics."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.learning import (
    BookmarkCreate, BookmarkOut,
    CommentCreate, CommentOut,
    FollowedTopicCreate, FollowedTopicOut,
    LearningOverview,
    NoteCreate, NoteOut, NoteUpdate,
    ReadingHistoryOut, ReadingHistoryRecord,
)
from app.services.learning import learning_service

router = APIRouter(prefix="/learning", tags=["Learning"])


# ---------------------------------------------------------------------------
# Dashboard overview
# ---------------------------------------------------------------------------
@router.get("", response_model=dict)
async def get_learning_overview(user: CurrentUser, db: DbSession):
    """Get learning centre dashboard overview."""
    overview = await learning_service.get_overview(db, user)
    return success(LearningOverview(**overview).model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------
@router.get("/bookmarks", response_model=dict)
async def list_bookmarks(
    user: CurrentUser, db: DbSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    items, total = await learning_service.list_bookmarks(db, user, page, page_size)
    return success({"items": items, "total": total, "page": page, "pageSize": page_size})


@router.post("/bookmarks", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_bookmark(body: BookmarkCreate, user: CurrentUser, db: DbSession):
    try:
        result = await learning_service.add_bookmark(db, user, body.paper_id, body.folder)
        return success(result, "Bookmark added")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.delete("/bookmarks/{paper_id}", response_model=dict)
async def remove_bookmark(paper_id: UUID, user: CurrentUser, db: DbSession):
    await learning_service.remove_bookmark(db, user, paper_id)
    return success(None, "Bookmark removed")


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
@router.get("/notes", response_model=dict)
async def list_notes(
    user: CurrentUser, db: DbSession,
    paper_id: UUID | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    items, total = await learning_service.list_notes(db, user, paper_id, page, page_size)
    return success({"items": items, "total": total, "page": page, "pageSize": page_size})


@router.post("/notes", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_note(body: NoteCreate, user: CurrentUser, db: DbSession):
    try:
        result = await learning_service.create_note(
            db, user, body.paper_id, body.content, body.anchor, body.is_public,
        )
        return success(result, "Note created")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.put("/notes/{note_id}", response_model=dict)
async def update_note(note_id: UUID, body: NoteUpdate, user: CurrentUser, db: DbSession):
    try:
        result = await learning_service.update_note(
            db, user, note_id, body.content, body.anchor, body.is_public,
        )
        return success(result, "Note updated")
    except ValueError as e:
        msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "not found" in msg.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(code, msg)


@router.delete("/notes/{note_id}", response_model=dict)
async def delete_note(note_id: UUID, user: CurrentUser, db: DbSession):
    try:
        await learning_service.delete_note(db, user, note_id)
        return success(None, "Note deleted")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@router.get("/comments", response_model=dict)
async def list_comments(
    db: DbSession,
    paper_id: UUID | None = Query(None),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    items, total = await learning_service.list_comments(db, paper_id, page, page_size)
    return success({"items": items, "total": total, "page": page, "pageSize": page_size})


@router.post("/comments", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_comment(body: CommentCreate, user: CurrentUser, db: DbSession):
    try:
        result = await learning_service.create_comment(db, user, body.paper_id, body.content, body.anchor)
        return success(result, "Comment created")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.delete("/comments/{comment_id}", response_model=dict)
async def delete_comment(comment_id: UUID, user: CurrentUser, db: DbSession):
    try:
        await learning_service.delete_comment(db, user, comment_id)
        return success(None, "Comment deleted")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


# ---------------------------------------------------------------------------
# Reading history
# ---------------------------------------------------------------------------
@router.get("/history", response_model=dict)
async def list_reading_history(
    user: CurrentUser, db: DbSession,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
):
    items, total = await learning_service.list_reading_history(db, user, page, page_size)
    return success({"items": items, "total": total, "page": page, "pageSize": page_size})


@router.post("/history", response_model=dict)
async def record_reading(body: ReadingHistoryRecord, user: CurrentUser, db: DbSession):
    try:
        result = await learning_service.record_reading(db, user, body.paper_id, body.progress)
        return success(result, "Reading progress recorded")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


# ---------------------------------------------------------------------------
# Followed topics
# ---------------------------------------------------------------------------
@router.get("/topics", response_model=dict)
async def list_followed_topics(user: CurrentUser, db: DbSession):
    topics = await learning_service.list_followed_topics(db, user)
    return success({"items": topics, "total": len(topics)})


@router.post("/topics", status_code=status.HTTP_201_CREATED, response_model=dict)
async def follow_topic(body: FollowedTopicCreate, user: CurrentUser, db: DbSession):
    result = await learning_service.follow_topic(db, user, body.topic, body.keywords)
    return success(result, "Topic followed")


@router.delete("/topics/{topic_id}", response_model=dict)
async def unfollow_topic(topic_id: UUID, user: CurrentUser, db: DbSession):
    try:
        await learning_service.unfollow_topic(db, user, topic_id)
        return success(None, "Topic unfollowed")
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
