"""Subscriptions & recommendations API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.services.recommendation import recommendation_service

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


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
    """Get today's paper digest based on user subscriptions."""
    from sqlalchemy import select
    from app.models.paper import Paper, UserPaper
    from app.models.task import Subscription
    subs = (await db.scalars(
        select(Subscription).where(Subscription.user_id == user.id, Subscription.enabled == True)
    )).all()
    library_ids = set(
        (await db.scalars(select(UserPaper.paper_id).where(UserPaper.user_id == user.id))).all()
    )

    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    topic_groups = []
    for sub in subs:
        keywords = sub.topic_keywords or []
        if not keywords:
            continue
        conditions = []
        for kw in keywords:
            conditions.append(Paper.title.ilike(f"%{kw}%"))
            conditions.append(Paper.abstract.ilike(f"%{kw}%"))
        from sqlalchemy import or_
        papers = (await db.scalars(
            select(Paper).where(
                or_(*conditions),
                Paper.published_at >= datetime.now(timezone.utc) - timedelta(days=1),
            ).limit(5)
        )).all()

        topic_groups.append({
            "topic": sub.topic_keywords[0] if sub.topic_keywords else "General",
            "keywords": sub.topic_keywords,
            "papers": [
                {
                    "paper_id": str(p.id), "arxiv_id": p.arxiv_id,
                    "title": p.title, "authors": p.authors or [],
                    "abstract": p.abstract or "", "primary_category": p.primary_category or "",
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "arxiv_url": p.arxiv_url,
                    "in_library": p.id in library_ids,
                }
                for p in papers
            ],
        })

    return success({"date": today, "topic_groups": topic_groups})


@router.get("/recommendations", response_model=dict)
async def get_recommendations(user: CurrentUser, db: DbSession):
    """Get personalized paper recommendations."""
    result = await recommendation_service.get_recommendations(db, user)
    return success(result)
