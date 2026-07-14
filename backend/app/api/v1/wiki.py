from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import success
from app.schemas.wiki import ConceptCreate, ConceptUpdate, RelationCreate
from app.services import wiki as wiki_service

router = APIRouter(prefix="/wiki", tags=["wiki"])


@router.get("")
async def wiki_overview(
    db: DbSession,
    user: CurrentUser,
    query: str | None = Query(default=None, max_length=500),
    category: str | None = Query(default=None, max_length=100),
) -> dict:
    return success(await wiki_service.get_overview(db, query=query, category=category))


@router.get("/concepts")
async def concepts(
    db: DbSession,
    user: CurrentUser,
    query: str | None = Query(default=None, max_length=500),
    category: str | None = Query(default=None, max_length=100),
) -> dict:
    items = await wiki_service.list_concepts(db, query=query, category=category)
    return success({"items": [wiki_service._concept_view(item) for item in items], "total": len(items)})


@router.post("/concepts", status_code=status.HTTP_201_CREATED)
async def create_concept(body: ConceptCreate, db: DbSession, user: CurrentUser) -> dict:
    return success(await wiki_service.create_concept(db, body), "概念已创建")


@router.get("/concepts/{concept_id}")
async def concept_detail(concept_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    return success(await wiki_service.get_detail(db, concept_id))


@router.patch("/concepts/{concept_id}")
async def update_concept(
    concept_id: UUID, body: ConceptUpdate, db: DbSession, user: CurrentUser
) -> dict:
    return success(await wiki_service.update_concept(db, concept_id, body), "概念已更新")


@router.delete("/concepts/{concept_id}", status_code=status.HTTP_200_OK)
async def delete_concept(concept_id: UUID, db: DbSession, user: CurrentUser) -> dict:
    await wiki_service.delete_concept(db, concept_id)
    return success({"id": str(concept_id)}, "概念已删除")


@router.post("/concepts/{concept_id}/relations", status_code=status.HTTP_201_CREATED)
async def create_relation(
    concept_id: UUID, body: RelationCreate, db: DbSession, user: CurrentUser
) -> dict:
    return success(await wiki_service.create_relation(db, concept_id, body), "关系已创建")


@router.delete("/concepts/{concept_id}/relations/{relation_id}")
async def delete_relation(
    concept_id: UUID, relation_id: UUID, db: DbSession, user: CurrentUser
) -> dict:
    await wiki_service.delete_relation(db, concept_id, relation_id)
    return success({"id": str(relation_id)}, "关系已删除")
