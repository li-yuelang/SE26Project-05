"""Business logic for learning management -- bookmarks, notes, comments, reading history, followed topics."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.learning import Bookmark, Comment, FollowedTopic, Note, ReadingHistory
from app.models.paper import Paper, UserPaper
from app.models.user import User


class LearningService:
    """Stateless service for learning-related CRUD operations."""

    @staticmethod
    async def _get_owned_paper(db: AsyncSession, user_id: UUID, paper_id: UUID) -> Paper | None:
        return await db.scalar(
            select(Paper)
            .join(UserPaper, UserPaper.paper_id == Paper.id)
            .where(Paper.id == paper_id, UserPaper.user_id == user_id)
        )

    # ------------------------------------------------------------------
    # Dashboard overview
    # ------------------------------------------------------------------
    async def get_overview(self, db: AsyncSession, user: User) -> dict:
        bookmark_count = await db.scalar(
            select(func.count(Bookmark.id)).where(Bookmark.user_id == user.id)
        )
        note_count = await db.scalar(
            select(func.count(Note.id)).where(Note.user_id == user.id)
        )
        comment_count = await db.scalar(
            select(func.count(Comment.id)).where(Comment.user_id == user.id)
        )
        history_count = await db.scalar(
            select(func.count(ReadingHistory.id)).where(ReadingHistory.user_id == user.id)
        )
        topic_count = await db.scalar(
            select(func.count(FollowedTopic.id)).where(FollowedTopic.user_id == user.id)
        )

        recent_reading = await self._query_reading_history(db, user.id, limit=5)
        recent_notes = await self._query_notes(db, user.id, limit=5)
        followed_topics = await self._query_followed_topics(db, user.id)

        return {
            "bookmark_count": bookmark_count or 0,
            "note_count": note_count or 0,
            "comment_count": comment_count or 0,
            "reading_history_count": history_count or 0,
            "followed_topic_count": topic_count or 0,
            "recent_reading": recent_reading,
            "recent_notes": recent_notes,
            "followed_topics": followed_topics,
        }

    # ------------------------------------------------------------------
    # Bookmarks
    # ------------------------------------------------------------------
    async def add_bookmark(self, db: AsyncSession, user: User, paper_id: UUID, folder: str | None) -> dict:
        paper = await self._get_owned_paper(db, user.id, paper_id)
        if paper is None:
            raise ValueError("Paper not found")

        existing = await db.scalar(
            select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.paper_id == paper_id)
        )
        if existing:
            existing.folder = folder
            await db.commit()
            await db.refresh(existing)
            return self._serialise_bookmark(existing, paper)

        bookmark = Bookmark(user_id=user.id, paper_id=paper_id, folder=folder)
        db.add(bookmark)
        await db.commit()
        await db.refresh(bookmark)
        return self._serialise_bookmark(bookmark, paper)

    async def remove_bookmark(self, db: AsyncSession, user: User, paper_id: UUID) -> None:
        result = await db.execute(
            select(Bookmark).where(Bookmark.user_id == user.id, Bookmark.paper_id == paper_id)
        )
        bookmark = result.scalar_one_or_none()
        if bookmark is None:
            return
        await db.delete(bookmark)
        await db.commit()

    async def set_bookmarks(
        self,
        db: AsyncSession,
        user: User,
        paper_ids: list[UUID],
        bookmarked: bool,
    ) -> dict:
        """Set every existing selected paper to the requested bookmark state."""
        unique_ids = list(dict.fromkeys(paper_ids))
        paper_result = await db.scalars(select(Paper.id).where(Paper.id.in_(unique_ids)))
        valid_ids = list(paper_result.all())

        bookmark_result = await db.scalars(
            select(Bookmark).where(
                Bookmark.user_id == user.id,
                Bookmark.paper_id.in_(valid_ids),
            )
        )
        existing = list(bookmark_result.all())
        existing_ids = {item.paper_id for item in existing}

        if bookmarked:
            for paper_id in valid_ids:
                if paper_id not in existing_ids:
                    db.add(Bookmark(user_id=user.id, paper_id=paper_id, folder=None))
        else:
            for bookmark in existing:
                await db.delete(bookmark)

        await db.commit()
        return {
            "paperIds": [str(paper_id) for paper_id in valid_ids],
            "bookmarked": bookmarked,
            "processedCount": len(valid_ids),
        }

    async def list_bookmarks(
        self, db: AsyncSession, user: User, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        return await self._paginate(
            db,
            select(Bookmark).where(Bookmark.user_id == user.id).order_by(Bookmark.created_at.desc()),
            page,
            page_size,
            self._serialise_bookmark,
        )

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------
    async def create_note(
        self, db: AsyncSession, user: User, paper_id: UUID, content: str,
        anchor: dict | None = None, is_public: bool = False,
    ) -> dict:
        paper = await self._get_owned_paper(db, user.id, paper_id)
        if paper is None:
            raise ValueError("Paper not found")
        note = Note(user_id=user.id, paper_id=paper_id, content=content, anchor=anchor, is_public=is_public)
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return self._serialise_note(note, paper)

    async def update_note(
        self, db: AsyncSession, user: User, note_id: UUID,
        content: str | None, anchor: dict | None = None, is_public: bool | None = None,
    ) -> dict:
        note = await db.scalar(
            select(Note).where(Note.id == note_id, Note.user_id == user.id)
        )
        if note is None:
            raise ValueError("Note not found")
        if content is not None:
            note.content = content
        if anchor is not None:
            note.anchor = anchor
        if is_public is not None:
            note.is_public = is_public
        await db.commit()
        await db.refresh(note)
        paper = await self._get_owned_paper(db, user.id, note.paper_id)
        return self._serialise_note(note, paper)

    async def delete_note(self, db: AsyncSession, user: User, note_id: UUID) -> None:
        note = await db.scalar(select(Note).where(Note.id == note_id, Note.user_id == user.id))
        if note is None:
            raise ValueError("Note not found")
        await db.delete(note)
        await db.commit()

    async def list_notes(
        self, db: AsyncSession, user: User, paper_id: UUID | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        stmt = select(Note).where(Note.user_id == user.id)
        if paper_id:
            stmt = stmt.where(Note.paper_id == paper_id)
        stmt = stmt.order_by(Note.updated_at.desc())
        return await self._paginate(db, stmt, page, page_size, self._serialise_note)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------
    async def create_comment(
        self, db: AsyncSession, user: User, paper_id: UUID,
        content: str, anchor: dict | None = None,
    ) -> dict:
        paper = await self._get_owned_paper(db, user.id, paper_id)
        if paper is None:
            raise ValueError("Paper not found")
        comment = Comment(user_id=user.id, paper_id=paper_id, content=content, anchor=anchor)
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        return self._serialise_comment(comment, paper, user)

    async def delete_comment(self, db: AsyncSession, user: User, comment_id: UUID) -> None:
        comment = await db.scalar(select(Comment).where(Comment.id == comment_id, Comment.user_id == user.id))
        if comment is None:
            raise ValueError("Comment not found")
        await db.delete(comment)
        await db.commit()

    async def list_comments(
        self, db: AsyncSession, user: User, paper_id: UUID | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        stmt = select(Comment).where(Comment.user_id == user.id)
        if paper_id:
            stmt = stmt.where(Comment.paper_id == paper_id)
        stmt = stmt.order_by(Comment.created_at.desc())
        return await self._paginate(db, stmt, page, page_size, self._serialise_comment)

    # ------------------------------------------------------------------
    # Reading history
    # ------------------------------------------------------------------
    async def record_reading(
        self, db: AsyncSession, user: User, paper_id: UUID, progress: int,
    ) -> dict:
        paper = await self._get_owned_paper(db, user.id, paper_id)
        if paper is None:
            raise ValueError("Paper not found")

        history = await db.scalar(
            select(ReadingHistory).where(
                ReadingHistory.user_id == user.id, ReadingHistory.paper_id == paper_id
            )
        )
        now = datetime.now(timezone.utc)
        if history:
            history.progress = max(history.progress, progress)
            history.last_read_at = now
        else:
            history = ReadingHistory(user_id=user.id, paper_id=paper_id, progress=progress, last_read_at=now)
            db.add(history)
        await db.commit()
        await db.refresh(history)
        return self._serialise_reading_history(history, paper)

    async def list_reading_history(
        self, db: AsyncSession, user: User, page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        stmt = (
            select(ReadingHistory)
            .where(ReadingHistory.user_id == user.id)
            .order_by(ReadingHistory.last_read_at.desc())
        )
        return await self._paginate(db, stmt, page, page_size, self._serialise_reading_history)

    # ------------------------------------------------------------------
    # Followed topics
    # ------------------------------------------------------------------
    async def follow_topic(self, db: AsyncSession, user: User, topic: str, keywords: list[str]) -> dict:
        existing = await db.scalar(
            select(FollowedTopic).where(FollowedTopic.user_id == user.id, FollowedTopic.topic == topic)
        )
        if existing:
            existing.keywords = keywords or existing.keywords
            await db.commit()
            await db.refresh(existing)
            return self._serialise_followed_topic(existing)

        ft = FollowedTopic(user_id=user.id, topic=topic, keywords=keywords)
        db.add(ft)
        await db.commit()
        await db.refresh(ft)
        return self._serialise_followed_topic(ft)

    async def unfollow_topic(self, db: AsyncSession, user: User, topic_id: UUID) -> None:
        ft = await db.scalar(select(FollowedTopic).where(FollowedTopic.id == topic_id, FollowedTopic.user_id == user.id))
        if ft is None:
            raise ValueError("Followed topic not found")
        await db.delete(ft)
        await db.commit()

    async def list_followed_topics(self, db: AsyncSession, user: User) -> list[dict]:
        return await self._query_followed_topics(db, user.id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _serialise_bookmark(bm: Bookmark, paper: Paper | None = None) -> dict:
        if paper is None and bm.paper_id:
            paper = getattr(bm, "paper", None)
        return {
            "id": str(bm.id),
            "paper_id": str(bm.paper_id),
            "folder": bm.folder,
            "created_at": bm.created_at,
            "paper_title": paper.title if paper else None,
            "paper_authors": paper.authors if paper else None,
            "paper_primary_category": paper.primary_category if paper else None,
        }

    @staticmethod
    def _serialise_note(note: Note, paper: Paper | None = None) -> dict:
        if paper is None and note.paper_id:
            paper = getattr(note, "paper", None)
        return {
            "id": str(note.id),
            "paper_id": str(note.paper_id),
            "content": note.content,
            "anchor": note.anchor,
            "is_public": note.is_public,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "paper_title": paper.title if paper else None,
            "paper_authors": paper.authors if paper else None,
        }

    @staticmethod
    def _serialise_comment(comment: Comment, paper: Paper | None = None, u: User | None = None) -> dict:
        if paper is None and comment.paper_id:
            paper = getattr(comment, "paper", None)
        if u is None and comment.user_id:
            u = getattr(comment, "user", None)
        return {
            "id": str(comment.id),
            "paper_id": str(comment.paper_id),
            "content": comment.content,
            "anchor": comment.anchor,
            "created_at": comment.created_at,
            "user_display_name": u.display_name or u.username if u else None,
            "paper_title": paper.title if paper else None,
        }

    @staticmethod
    def _serialise_reading_history(rh: ReadingHistory, paper: Paper | None = None) -> dict:
        if paper is None and rh.paper_id:
            paper = getattr(rh, "paper", None)
        return {
            "id": str(rh.id),
            "paper_id": str(rh.paper_id),
            "progress": rh.progress,
            "last_read_at": rh.last_read_at,
            "paper_title": paper.title if paper else None,
            "paper_authors": paper.authors if paper else None,
            "paper_primary_category": paper.primary_category if paper else None,
        }

    @staticmethod
    def _serialise_followed_topic(ft: FollowedTopic) -> dict:
        return {
            "id": str(ft.id),
            "topic": ft.topic,
            "keywords": ft.keywords or [],
            "created_at": ft.created_at,
        }

    async def _query_reading_history(self, db: AsyncSession, user_id: UUID, limit: int = 5) -> list[dict]:
        stmt = (
            select(ReadingHistory)
            .where(ReadingHistory.user_id == user_id)
            .options(selectinload(ReadingHistory.paper))
            .order_by(ReadingHistory.last_read_at.desc())
            .limit(limit)
        )
        rows = (await db.scalars(stmt)).all()
        return [self._serialise_reading_history(r, r.paper) for r in rows]

    async def _query_notes(self, db: AsyncSession, user_id: UUID, limit: int = 5) -> list[dict]:
        stmt = (
            select(Note)
            .where(Note.user_id == user_id)
            .options(selectinload(Note.paper))
            .order_by(Note.updated_at.desc())
            .limit(limit)
        )
        rows = (await db.scalars(stmt)).all()
        return [self._serialise_note(n, n.paper) for n in rows]

    async def _query_followed_topics(self, db: AsyncSession, user_id: UUID) -> list[dict]:
        stmt = select(FollowedTopic).where(FollowedTopic.user_id == user_id)
        rows = (await db.scalars(stmt)).all()
        return [self._serialise_followed_topic(ft) for ft in rows]

    async def _paginate(
        self, db: AsyncSession, stmt, page: int, page_size: int, serialiser,
    ) -> tuple[list[dict], int]:
        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        total = total or 0
        offset = (page - 1) * page_size
        rows = (await db.scalars(stmt.offset(offset).limit(page_size))).all()
        items = []
        for row in rows:
            paper = await db.get(Paper, getattr(row, "paper_id", None))
            items.append(serialiser(row, paper))
        return items, total


# Module-level singleton – lightweight since service is stateless
learning_service = LearningService()
