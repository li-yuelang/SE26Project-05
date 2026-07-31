from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, cast, distinct, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.concept import Concept, ConceptRelation, ConceptRelationEvidence, PaperConcept, UserConcept
from app.models.paper import UserPaper
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


def _concept_view(concept: Concept, *, paper_ids: set[UUID] | None = None) -> dict:
    links = [
        link for link in concept.paper_links
        if paper_ids is None or link.paper_id in paper_ids
    ]
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


def _user_concept_view(concept: UserConcept) -> dict:
    description = concept.description or "暂无概念说明"
    return {
        "id": str(concept.id),
        "name": concept.name,
        "category": concept.category or "未分类",
        "description": description,
        "aliases": concept.aliases or [],
        "mentions": 0,
        "paperCount": 0,
        "trend": 0,
        "updatedAt": concept.updated_at.date().isoformat(),
        "keywords": concept.aliases or [],
        "summaryPoints": [description] if description != "暂无概念说明" else [],
        "papers": [],
    }


def _relation_view(
    relation: ConceptRelation,
    source_id: UUID,
    paper_ids: set[UUID],
) -> dict:
    target = relation.target_concept if relation.source_concept_id == source_id else relation.source_concept
    evidence = [item for item in relation.evidence_records if item.paper_id in paper_ids]
    strength = max((item.confidence for item in evidence), default=relation.weight or 0.0)
    return {
        "id": str(relation.id),
        "type": relation.relation_type,
        "strength": round(strength * 100),
        "exists": True,
        "concept": {"id": str(target.id), "name": target.name},
    }


def _concept_options():
    return (
        select(Concept)
        .options(
            selectinload(Concept.paper_links).selectinload(PaperConcept.paper),
            selectinload(Concept.outgoing_relations)
            .selectinload(ConceptRelation.target_concept),
            selectinload(Concept.incoming_relations)
            .selectinload(ConceptRelation.source_concept),
            selectinload(Concept.outgoing_relations).selectinload(ConceptRelation.evidence_records),
            selectinload(Concept.incoming_relations).selectinload(ConceptRelation.evidence_records),
        )
    )


def _owned_paper_ids(user_id: UUID):
    return select(UserPaper.paper_id).where(UserPaper.user_id == user_id)


async def _paper_id_set(db: AsyncSession, user_id: UUID) -> set[UUID]:
    return set((await db.scalars(select(UserPaper.paper_id).where(UserPaper.user_id == user_id))).all())


async def list_concepts(
    db: AsyncSession,
    *,
    user_id: UUID,
    query: str | None = None,
    category: str | None = None,
) -> list[Concept]:
    statement = _concept_options().where(
        Concept.paper_links.any(PaperConcept.paper_id.in_(_owned_paper_ids(user_id)))
    ).order_by(Concept.updated_at.desc(), Concept.name)
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


async def _list_user_concepts(
    db: AsyncSession, user_id: UUID, *, query: str | None = None, category: str | None = None
) -> list[UserConcept]:
    statement = select(UserConcept).where(UserConcept.user_id == user_id, UserConcept.hidden.is_(False))
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(UserConcept.name.ilike(pattern), UserConcept.description.ilike(pattern))
        )
    if category and category != "全部":
        statement = statement.where(UserConcept.category == category)
    return list((await db.scalars(statement.order_by(UserConcept.updated_at.desc(), UserConcept.name))).all())


async def _get_visible_concept(db: AsyncSession, user_id: UUID, concept_id: UUID) -> Concept | None:
    return await db.scalar(
        _concept_options().where(
            Concept.id == concept_id,
            Concept.paper_links.any(PaperConcept.paper_id.in_(_owned_paper_ids(user_id))),
        )
    )


async def _get_concept_or_owned_custom(
    db: AsyncSession, user_id: UUID, concept_id: UUID
) -> tuple[Concept | None, UserConcept | None]:
    custom = await db.scalar(
        select(UserConcept).where(
            UserConcept.id == concept_id,
            UserConcept.user_id == user_id,
            UserConcept.hidden.is_(False),
        )
    )
    if custom is not None:
        return None, custom
    return await _get_visible_concept(db, user_id, concept_id), None


async def _visible_relation_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
    statement = (
        select(distinct(ConceptRelationEvidence.relation_id))
        .join(UserPaper, UserPaper.paper_id == ConceptRelationEvidence.paper_id)
        .where(UserPaper.user_id == user_id)
    )
    return set((await db.scalars(statement)).all())


def _relations_for(
    concept: Concept,
    *,
    visible_concept_ids: set[UUID],
    visible_relation_ids: set[UUID],
    paper_ids: set[UUID],
) -> list[dict]:
    relations = [*concept.outgoing_relations, *concept.incoming_relations]
    result = []
    for relation in relations:
        target_id = (
            relation.target_concept_id
            if relation.source_concept_id == concept.id
            else relation.source_concept_id
        )
        if relation.id in visible_relation_ids and target_id in visible_concept_ids:
            result.append(_relation_view(relation, concept.id, paper_ids))
    return result


async def get_overview(
    db: AsyncSession, *, user_id: UUID, query: str | None, category: str | None
) -> dict:
    paper_ids = await _paper_id_set(db, user_id)
    concepts = await list_concepts(db, user_id=user_id, query=query, category=category)
    custom = await _list_user_concepts(db, user_id, query=query, category=category)
    all_concepts = await list_concepts(db, user_id=user_id)
    all_custom = await _list_user_concepts(db, user_id)
    visible_ids = {item.id for item in all_concepts}
    relation_ids = await _visible_relation_ids(db, user_id)
    relation_objects = {
        relation.id: relation
        for concept in all_concepts
        for relation in [*concept.outgoing_relations, *concept.incoming_relations]
        if relation.id in relation_ids
        and (
            relation.target_concept_id in visible_ids
            and relation.source_concept_id in visible_ids
        )
    }
    relation_ids = set(relation_objects)
    categories = sorted({item.category for item in [*all_concepts, *all_custom] if item.category})
    recent = sorted([*all_concepts, *all_custom], key=lambda item: item.updated_at, reverse=True)[:5]

    return {
        "concepts": [
            *[_concept_view(item, paper_ids=paper_ids) for item in concepts],
            *[_user_concept_view(item) for item in custom],
        ],
        "relatedConceptsById": {
            str(item.id): _relations_for(
                item,
                visible_concept_ids=visible_ids,
                visible_relation_ids=relation_ids,
                paper_ids=paper_ids,
            )
            for item in concepts
        },
        "categoryOptions": ["全部", *categories],
        "stats": {
            "concepts": len(all_concepts) + len(all_custom),
            "papers": len(paper_ids),
            "relations": len(relation_ids),
            "strongRelations": sum(
                1
                for relation in relation_objects.values()
                if max(
                    (item.confidence for item in relation.evidence_records if item.paper_id in paper_ids),
                    default=relation.weight or 0.0,
                ) >= 0.75
            ),
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


async def get_detail(db: AsyncSession, user_id: UUID, concept_id: UUID) -> dict:
    concept, custom = await _get_concept_or_owned_custom(db, user_id, concept_id)
    if custom is not None:
        return {"concept": _user_concept_view(custom), "relatedConcepts": []}
    if concept is None:
        raise AppError("概念不存在", code="CONCEPT_NOT_FOUND", status_code=404)
    paper_ids = await _paper_id_set(db, user_id)
    visible_concepts = await list_concepts(db, user_id=user_id)
    relations = _relations_for(
        concept,
        visible_concept_ids={item.id for item in visible_concepts},
        visible_relation_ids=await _visible_relation_ids(db, user_id),
        paper_ids=paper_ids,
    )
    return {"concept": _concept_view(concept, paper_ids=paper_ids), "relatedConcepts": relations}


async def create_concept(db: AsyncSession, user_id: UUID, payload: ConceptCreate) -> dict:
    concept = UserConcept(user_id=user_id, **payload.model_dump())
    db.add(concept)
    try:
        await db.commit()
        await db.refresh(concept)
    except IntegrityError:
        await db.rollback()
        raise AppError("概念名称已存在", code="CONCEPT_EXISTS", status_code=409) from None
    return _user_concept_view(concept)


async def update_concept(
    db: AsyncSession, user_id: UUID, concept_id: UUID, payload: ConceptUpdate
) -> dict:
    concept = await db.scalar(
        select(UserConcept).where(UserConcept.id == concept_id, UserConcept.user_id == user_id)
    )
    if concept is None:
        if await _get_visible_concept(db, user_id, concept_id) is not None:
            raise AppError("分析生成的共享概念不可直接编辑", code="WIKI_READ_ONLY", status_code=403)
        raise AppError("概念不存在", code="CONCEPT_NOT_FOUND", status_code=404)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(concept, field, value)
    try:
        await db.commit()
        await db.refresh(concept)
    except IntegrityError:
        await db.rollback()
        raise AppError("概念名称已存在", code="CONCEPT_EXISTS", status_code=409) from None
    return _user_concept_view(concept)


async def delete_concept(db: AsyncSession, user_id: UUID, concept_id: UUID) -> None:
    concept = await db.scalar(
        select(UserConcept).where(UserConcept.id == concept_id, UserConcept.user_id == user_id)
    )
    if concept is None:
        if await _get_visible_concept(db, user_id, concept_id) is not None:
            raise AppError("分析生成的共享概念不可删除", code="WIKI_READ_ONLY", status_code=403)
        raise AppError("概念不存在", code="CONCEPT_NOT_FOUND", status_code=404)
    await db.delete(concept)
    await db.commit()


async def create_relation(db: AsyncSession, source_id: UUID, payload: RelationCreate, user_id: UUID) -> dict:
    del db, source_id, payload, user_id
    raise AppError("分析生成的共享关系暂不可编辑", code="WIKI_RELATIONS_READ_ONLY", status_code=403)


async def delete_relation(db: AsyncSession, source_id: UUID, relation_id: UUID, user_id: UUID) -> None:
    del db, source_id, relation_id, user_id
    raise AppError("分析生成的共享关系暂不可编辑", code="WIKI_RELATIONS_READ_ONLY", status_code=403)
