"""Subscriptions & recommendations API endpoints."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.subscription import SubscriptionCreate, SubscriptionUpdate
from app.services.recommendation import recommendation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


def _calculate_digest_relevance(paper: object, terms: list[str]) -> tuple[float, list[str]]:
    """Return a deterministic lexical score and the matched subscription terms."""
    normalized_terms = list(dict.fromkeys(term.strip().lower() for term in terms if term.strip()))
    if not normalized_terms:
        return 0.0, []

    title = (getattr(paper, "title", "") or "").lower()
    abstract = (getattr(paper, "abstract", "") or "").lower()
    categories = [getattr(paper, "primary_category", "") or ""]
    categories.extend(getattr(paper, "categories", None) or [])
    category_text = " ".join(categories).lower()

    matched: list[str] = []
    title_hits = 0
    category_hits = 0
    for term in normalized_terms:
        in_title = term in title
        in_abstract = term in abstract
        in_category = term in category_text
        if in_title or in_abstract or in_category:
            matched.append(term)
        title_hits += int(in_title)
        category_hits += int(in_category)

    term_count = len(normalized_terms)
    coverage = len(matched) / term_count
    title_ratio = title_hits / term_count
    category_ratio = category_hits / term_count
    score = 0.5 * coverage + 0.35 * title_ratio + 0.15 * category_ratio
    return round(min(score, 1.0), 4), matched


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

    # Trigger background arXiv sync so new subscription has data immediately
    try:
        from app.tasks.digest import sync_subscription_arxiv_task
        sync_subscription_arxiv_task.delay()
    except Exception:
        logger.warning("Failed to dispatch background arXiv sync for new subscription", exc_info=True)

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
        keywords = [keyword.strip() for keyword in (sub.topic_keywords or []) if keyword.strip()]
        categories = [category.strip() for category in (sub.categories or []) if category.strip()]
        terms = [*keywords, *categories]
        if not terms:
            continue
        conditions = []
        for kw in keywords:
            conditions.append(Paper.title.ilike(f"%{kw}%"))
            conditions.append(Paper.abstract.ilike(f"%{kw}%"))
        for category in categories:
            conditions.append(Paper.primary_category == category)
            conditions.append(Paper.categories.contains([category]))
        from sqlalchemy import or_
        candidates = (await db.scalars(
            select(Paper).where(
                or_(*conditions),
                Paper.published_at >= datetime.now(timezone.utc) - timedelta(days=1),
            ).order_by(Paper.published_at.desc()).limit(50)
        )).all()
        ranked_papers = []
        for paper in candidates:
            relevance_score, matched_terms = _calculate_digest_relevance(paper, terms)
            ranked_papers.append((paper, relevance_score, matched_terms))
        ranked_papers.sort(key=lambda item: item[1], reverse=True)

        topic_groups.append({
            "topic": terms[0],
            "keywords": terms,
            "papers": [
                {
                    "paper_id": str(p.id), "arxiv_id": p.arxiv_id,
                    "title": p.title, "authors": p.authors or [],
                    "abstract": p.abstract or "", "primary_category": p.primary_category or "",
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "arxiv_url": p.arxiv_url,
                    "in_library": p.id in library_ids,
                    "relevance_score": relevance_score,
                    "reason": f"命中订阅条件：{'、'.join(matched_terms[:3])}",
                }
                for p, relevance_score, matched_terms in ranked_papers[:5]
            ],
        })

    return success({"date": today, "topic_groups": topic_groups})


@router.get("/recommendations", response_model=dict)
async def get_recommendations(user: CurrentUser, db: DbSession):
    """Get personalized paper recommendations."""
    result = await recommendation_service.get_recommendations(db, user)
    return success(result)


@router.post("/push-now", response_model=dict)
async def push_now(user: CurrentUser, db: DbSession):
    """Immediately refresh digest for the user's subscriptions."""
    from sqlalchemy import select
    from app.models.paper import Paper, UserPaper
    from app.models.task import Subscription
    from datetime import datetime, timedelta, timezone

    logger.info("Immediate push triggered by user %s", user.id)
    subs = (await db.scalars(
        select(Subscription).where(Subscription.user_id == user.id, Subscription.enabled == True)
    )).all()
    library_ids = set(
        (await db.scalars(select(UserPaper.paper_id).where(UserPaper.user_id == user.id))).all()
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    topic_groups = []
    for sub in subs:
        keywords = [keyword.strip() for keyword in (sub.topic_keywords or []) if keyword.strip()]
        categories = [category.strip() for category in (sub.categories or []) if category.strip()]
        terms = [*keywords, *categories]
        if not terms:
            continue
        conditions = []
        for kw in keywords:
            conditions.append(Paper.title.ilike(f"%{kw}%"))
            conditions.append(Paper.abstract.ilike(f"%{kw}%"))
        for category in categories:
            conditions.append(Paper.primary_category == category)
            conditions.append(Paper.categories.contains([category]))
        from sqlalchemy import or_
        candidates = (await db.scalars(
            select(Paper).where(
                or_(*conditions),
                Paper.published_at >= datetime.now(timezone.utc) - timedelta(days=1),
            ).order_by(Paper.published_at.desc()).limit(50)
        )).all()
        ranked_papers = []
        for paper in candidates:
            relevance_score, matched_terms = _calculate_digest_relevance(paper, terms)
            ranked_papers.append((paper, relevance_score, matched_terms))
        ranked_papers.sort(key=lambda item: item[1], reverse=True)

        topic_groups.append({
            "topic": terms[0],
            "keywords": terms,
            "papers": [
                {
                    "paper_id": str(p.id), "arxiv_id": p.arxiv_id,
                    "title": p.title, "authors": p.authors or [],
                    "abstract": p.abstract or "", "primary_category": p.primary_category or "",
                    "published_at": p.published_at.isoformat() if p.published_at else None,
                    "arxiv_url": p.arxiv_url,
                    "in_library": p.id in library_ids,
                    "relevance_score": relevance_score,
                    "reason": f"命中订阅条件：{'、'.join(matched_terms[:3])}",
                }
                for p, relevance_score, matched_terms in ranked_papers[:5]
            ],
        })

    return success({"date": today, "topic_groups": topic_groups}, "Immediate push completed")
