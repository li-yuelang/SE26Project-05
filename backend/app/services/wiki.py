from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, cast, delete, distinct, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.concept import Concept, ConceptRelation, PaperConcept
from app.schemas.wiki import ConceptCreate, ConceptUpdate, RelationCreate


def _paper_view(link: PaperConcept) -> dict:
    paper = link.paper
    return {
        "id": str(paper.id),
        "arxivId": paper.arxiv_id,
        "title": paper.title,
        "year": paper.published_at.year if paper.published_at else None,
        "role": link.evidence or "相关研究",
        "relevance": round(link.relevance * 100),
    }


def _concept_view(concept: Concept) -> dict:
    links = list(concept.paper_links)
    metadata = getattr(concept, "metadata_extra", None) or {}
    description = concept.description or "暂无概念说明"
    summary_points = metadata.get("summaryPoints") or [
        sentence.strip()
        for sentence in description.replace("。", "。\n").splitlines()
        if sentence.strip()
    ][:3]
    mentions = int(metadata.get("mentions", len(links)))
    trend = int(metadata.get("trend", min(100, 35 + len(links) * 8)))
    return {
        "id": str(concept.id),
        "name": concept.name,
        "category": concept.category or "未分类",
        "description": description,
        "aliases": concept.aliases or [],
        "mentions": mentions,
        "paperCount": len(links),
        "trend": trend,
        "updatedAt": concept.updated_at.date().isoformat(),
        "keywords": concept.aliases or [],
        "summaryPoints": summary_points,
        "papers": [_paper_view(link) for link in links],
    }


def _relation_view(relation: ConceptRelation, source_id: UUID) -> dict:
    target = relation.target_concept if relation.source_concept_id == source_id else relation.source_concept
    return {
        "id": str(relation.id),
        "type": relation.relation_type,
        "strength": round(relation.weight * 100),
        "exists": True,
        "concept": {"id": str(target.id), "name": target.name},
    }


def _concept_options():
    return (
        select(Concept)
        .options(
            selectinload(Concept.paper_links).selectinload(PaperConcept.paper),
            selectinload(Concept.outgoing_relations).selectinload(ConceptRelation.target_concept),
            selectinload(Concept.incoming_relations).selectinload(ConceptRelation.source_concept),
        )
    )


async def list_concepts(
    db: AsyncSession,
    *,
    query: str | None = None,
    category: str | None = None,
) -> list[Concept]:
    statement = _concept_options().order_by(Concept.updated_at.desc(), Concept.name)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                Concept.name.ilike(pattern),
                Concept.description.ilike(pattern),
                cast(Concept.aliases, Text).ilike(pattern),
            )
        )
    if category and category != "全部":
        statement = statement.where(Concept.category == category)
    return list((await db.scalars(statement)).unique().all())


async def get_concept(db: AsyncSession, concept_id: UUID) -> Concept:
    concept = await db.scalar(_concept_options().where(Concept.id == concept_id))
    if concept is None:
        raise AppError("概念不存在", code="CONCEPT_NOT_FOUND", status_code=404)
    return concept


async def get_overview(db: AsyncSession, *, query: str | None, category: str | None) -> dict:
    concepts = await list_concepts(db, query=query, category=category)
    categories = list(
        (await db.scalars(select(distinct(Concept.category)).where(Concept.category.is_not(None)))).all()
    )
    relation_count = (await db.scalar(select(func.count()).select_from(ConceptRelation))) or 0
    strong_count = (
        await db.scalar(select(func.count()).select_from(ConceptRelation).where(ConceptRelation.weight >= 0.75))
    ) or 0
    paper_count = (await db.scalar(select(func.count(distinct(PaperConcept.paper_id))))) or 0
    concept_count = (await db.scalar(select(func.count()).select_from(Concept))) or 0

    recent = concepts[:5]
    return {
        "concepts": [_concept_view(item) for item in concepts],
        "relatedConceptsById": {
            str(item.id): [
                *[_relation_view(rel, item.id) for rel in item.outgoing_relations],
                *[_relation_view(rel, item.id) for rel in item.incoming_relations],
            ]
            for item in concepts
        },
        "categoryOptions": ["全部", *sorted(categories)],
        "stats": {
            "concepts": concept_count,
            "papers": paper_count,
            "relations": relation_count,
            "strongRelations": strong_count,
        },
        "activity": [
            {
                "id": str(item.id),
                "title": f"更新概念：{item.name}",
                "description": item.description or "概念信息已更新",
                "time": item.updated_at.strftime("%Y-%m-%d %H:%M"),
                "color": "blue",
            }
            for item in recent
        ],
    }


async def get_detail(db: AsyncSession, concept_id: UUID) -> dict:
    concept = await get_concept(db, concept_id)
    relations = [
        *[_relation_view(rel, concept.id) for rel in concept.outgoing_relations],
        *[_relation_view(rel, concept.id) for rel in concept.incoming_relations],
    ]
    return {"concept": _concept_view(concept), "relatedConcepts": relations}


async def create_concept(db: AsyncSession, payload: ConceptCreate) -> dict:
    concept = Concept(**payload.model_dump())
    db.add(concept)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError("概念名称已存在", code="CONCEPT_EXISTS", status_code=409) from None
    return (await get_detail(db, concept.id))["concept"]


async def update_concept(db: AsyncSession, concept_id: UUID, payload: ConceptUpdate) -> dict:
    concept = await get_concept(db, concept_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(concept, field, value)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError("概念名称已存在", code="CONCEPT_EXISTS", status_code=409) from None
    return (await get_detail(db, concept_id))["concept"]


async def delete_concept(db: AsyncSession, concept_id: UUID) -> None:
    concept = await get_concept(db, concept_id)
    await db.delete(concept)
    await db.commit()


async def create_relation(db: AsyncSession, source_id: UUID, payload: RelationCreate) -> dict:
    await get_concept(db, source_id)
    await get_concept(db, payload.target_concept_id)
    if source_id == payload.target_concept_id:
        raise AppError("概念不能关联自身", code="INVALID_RELATION", status_code=400)
    relation = ConceptRelation(
        source_concept_id=source_id,
        target_concept_id=payload.target_concept_id,
        relation_type=payload.relation_type,
        weight=payload.weight,
    )
    db.add(relation)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError("该概念关系已存在", code="RELATION_EXISTS", status_code=409) from None
    detail = await get_detail(db, source_id)
    return next(item for item in detail["relatedConcepts"] if item["id"] == str(relation.id))


async def delete_relation(db: AsyncSession, source_id: UUID, relation_id: UUID) -> None:
    result = await db.execute(
        delete(ConceptRelation).where(
            ConceptRelation.id == relation_id,
            or_(
                ConceptRelation.source_concept_id == source_id,
                ConceptRelation.target_concept_id == source_id,
            ),
        )
    )
    if result.rowcount == 0:
        raise AppError("概念关系不存在", code="RELATION_NOT_FOUND", status_code=404)
    await db.commit()
