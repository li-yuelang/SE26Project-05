"""抓取任务业务逻辑服务层。"""

import logging
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.task import FetchTask
from app.schemas.task import FetchTaskResponse, TaskUpdateRequest

logger = logging.getLogger(__name__)


async def list_tasks(db: AsyncSession) -> tuple[list[FetchTaskResponse], int]:
    """获取所有抓取任务，按创建时间降序。"""
    query = select(FetchTask).order_by(FetchTask.created_at.desc())
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.scalar(count_q)) or 0

    rows = (await db.execute(query)).scalars().all()
    items = [FetchTaskResponse.model_validate(r) for r in rows]
    return items, total


async def get_task_detail(db: AsyncSession, task_id: UUID) -> FetchTaskResponse:
    """获取单个任务详情。"""
    task = await db.scalar(select(FetchTask).where(FetchTask.id == task_id))
    if not task:
        raise AppError("任务不存在", code="TASK_NOT_FOUND", status_code=404)
    return FetchTaskResponse.model_validate(task)


async def update_task(
    db: AsyncSession,
    task_id: UUID,
    changes: TaskUpdateRequest,
) -> FetchTaskResponse:
    """更新任务（状态、调度、关键词等）。"""
    update_data = changes.model_dump(exclude_none=True)
    if not update_data:
        return await get_task_detail(db, task_id)

    result = await db.execute(
        update(FetchTask).where(FetchTask.id == task_id).values(**update_data).returning(FetchTask)
    )
    updated = result.scalar_one_or_none()
    if not updated:
        raise AppError("任务不存在", code="TASK_NOT_FOUND", status_code=404)
    await db.commit()
    return FetchTaskResponse.model_validate(updated)


async def reset_tasks(db: AsyncSession) -> list[FetchTaskResponse]:
    """将所有失败/暂停的任务重置为已计划状态，并清空错误信息。"""
    await db.execute(
        update(FetchTask)
        .where(FetchTask.status.in_(["failed", "paused"]))
        .values(status="scheduled", error_message=None, execution_log=[])
    )
    await db.commit()

    rows = (await db.execute(select(FetchTask).order_by(FetchTask.created_at.desc()))).scalars().all()
    return [FetchTaskResponse.model_validate(r) for r in rows]
