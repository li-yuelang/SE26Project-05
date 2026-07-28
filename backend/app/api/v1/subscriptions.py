"""Subscriptions & recommendations API endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.paper import UserPaper
from app.models.task import Subscription
from app.schemas.common import success
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.services.paper_retrieval import (
    calculate_lexical_relevance,
    paper_hybrid_retriever,
)
from app.services.recommendation import recommendation_service

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _calculate_digest_relevance(
    paper: object,
    terms: list[str],
) -> tuple[float, list[str]]:
    """Backward-compatible wrapper for digest relevance tests."""
    return calculate_lexical_relevance(paper, terms)


# ---------------------------------------------------------------------------
# Manage subscriptions
# ---------------------------------------------------------------------------
@router.get("", response_model=dict)
async def list_subscriptions(user: CurrentUser, db: DbSession):
    """List current user's subscriptions."""
    from sqlalchemy import select
    from app.models.task import Subscription
    subs = (await db.scalars(
        select(Subscription).where(Subscription.user_id == user.id)
    )).all()
    items = [
        {
            "id": str(s.id), "topic_keywords": s.topic_keywords or [],
            "categories": s.categories or [], "frequency": s.frequency,
            "enabled": s.enabled, "created_at": s.created_at.isoformat(),
        }
        for s in subs
    ]
    return success({"items": items, "total": len(items)})


@router.post("", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_subscription(body: SubscriptionCreate, user: CurrentUser, db: DbSession):
    from app.models.task import Subscription
    sub = Subscription(
        user_id=user.id, topic_keywords=body.topic_keywords,
        categories=body.categories, frequency=body.frequency,
        enabled=body.enabled,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return success({
        "id": str(sub.id), "topic_keywords": sub.topic_keywords or [],
        "categories": sub.categories or [], "frequency": sub.frequency,
        "enabled": sub.enabled, "created_at": sub.created_at.isoformat(),
    }, "Subscription created")


@router.put("/{subscription_id}", response_model=dict)
async def update_subscription(
    subscription_id: UUID, body: SubscriptionUpdate, user: CurrentUser, db: DbSession,
):
    from sqlalchemy import select
    from app.models.task import Subscription
    sub = await db.scalar(
        select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == user.id)
    )
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    if body.topic_keywords is not None:
        sub.topic_keywords = body.topic_keywords
    if body.categories is not None:
        sub.categories = body.categories
    if body.frequency is not None:
        sub.frequency = body.frequency
    if body.enabled is not None:
        sub.enabled = body.enabled
    await db.commit()
    await db.refresh(sub)
    return success({
        "id": str(sub.id), "topic_keywords": sub.topic_keywords or [],
        "categories": sub.categories or [], "frequency": sub.frequency,
        "enabled": sub.enabled, "created_at": sub.created_at.isoformat(),
    }, "Subscription updated")


@router.delete("/{subscription_id}", response_model=dict)
async def delete_subscription(subscription_id: UUID, user: CurrentUser, db: DbSession):
    from sqlalchemy import select
    from app.models.task import Subscription
    result = await db.execute(
        select(Subscription).where(Subscription.id == subscription_id, Subscription.user_id == user.id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subscription not found")
    await db.delete(sub)
    await db.commit()
    return success(None, "Subscription deleted")


# ---------------------------------------------------------------------------
# Digest & Recommendations
# ---------------------------------------------------------------------------
@router.get("/digest", response_model=dict)
async def get_daily_digest(user: CurrentUser, db: DbSession):
    """Read today's pre-synchronised arXiv papers from the local database."""
    subs = (await db.scalars(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.enabled.is_(True),
        )
    )).all()
    library_ids = set(
        (await db.scalars(select(UserPaper.paper_id).where(UserPaper.user_id == user.id))).all()
    )

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    prepared_subscriptions = []
    for sub in subs:
        keywords = [keyword.strip() for keyword in (sub.topic_keywords or []) if keyword.strip()]
        categories = [category.strip() for category in (sub.categories or []) if category.strip()]
        terms = [*keywords, *categories]
        if not terms:
            continue
        prepared_subscriptions.append((keywords, categories, terms))

    query_embeddings = await paper_hybrid_retriever.embed_queries(
        ["；".join(keywords) for keywords, _, _ in prepared_subscriptions]
    )
    topic_groups = []
    for (keywords, categories, terms), query_embedding in zip(
        prepared_subscriptions,
        query_embeddings,
        strict=True,
    ):
        ranked_papers = await paper_hybrid_retriever.search(
            db,
            terms=keywords,
            categories=categories,
            query_embedding=query_embedding,
            since=now - timedelta(days=1),
            result_limit=5,
        )
        topic_groups.append({
            "topic": terms[0],
            "keywords": terms,
            "papers": [
                {
                    "paper_id": str(item.paper.id),
                    "arxiv_id": item.paper.arxiv_id,
                    "title": item.paper.title,
                    "authors": item.paper.authors or [],
                    "abstract": item.paper.abstract or "",
                    "primary_category": item.paper.primary_category or "",
                    "published_at": (
                        item.paper.published_at.isoformat()
                        if item.paper.published_at
                        else None
                    ),
                    "arxiv_url": item.paper.arxiv_url,
                    "in_library": item.paper.id in library_ids,
                    "relevance_score": item.score,
                    "reason": item.reason,
                }
                for item in ranked_papers
            ],
        })

    return success({"date": today, "topic_groups": topic_groups})


@router.get("/recommendations", response_model=dict)
async def get_recommendations(user: CurrentUser, db: DbSession):
    """Get personalized paper recommendations."""
    result = await recommendation_service.get_recommendations(db, user)
    return success(result)
