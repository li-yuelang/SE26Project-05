"""arXiv 定时抓取的 Celery 任务。"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.task import FetchTask
from app.services.arxiv_fetch import ArxivFetchError, build_search_query, fetch_arxiv_papers
from app.services.paper_service import upsert_arxiv_papers
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300, acks_late=True)
def run_fetch_task(self, task_id: str) -> dict:
    """执行单个 FetchTask：从 arXiv 拉取论文 → 去重入库。

    由 Celery Beat 定时调度或手动触发。
    """
    import asyncio

    return asyncio.run(_async_fetch_and_save(task_id, self))


async def _async_fetch_and_save(task_id: str, celery_task) -> dict:
    """异步执行抓取逻辑。"""
    from uuid import UUID

    task_uuid = UUID(task_id)

    async with AsyncSessionLocal() as db:
        task = await db.scalar(select(FetchTask).where(FetchTask.id == task_uuid))
        if not task:
            raise ValueError(f"FetchTask not found: {task_id}")

        if task.status in ("running", "completed"):
            return {"status": "skipped", "reason": f"Task is already {task.status}"}

        # 标记为运行中
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        task.execution_log = task.execution_log or []
        task.execution_log.append({
            "time": datetime.now(timezone.utc).strftime("%H:%M"),
            "level": "info",
            "content": "任务开始执行。",
        })
        await db.commit()

        try:
            query = (
                build_search_query(keywords=task.keywords, categories=task.categories)
                or task.keywords[0] if task.keywords else "*"
            )
            max_results = 80

            raw_papers = await fetch_arxiv_papers(
                query=query,
                max_results=max_results,
                sort_by="submittedDate",
                sort_order="descending",
            )

            task.execution_log.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M"),
                "level": "info",
                "content": f"已拉取 {len(raw_papers)} 条候选论文记录。",
            })
            await db.commit()

            # 去重入库
            inserted, skipped = await upsert_arxiv_papers(db, raw_papers)

            task.execution_log.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M"),
                "level": "info",
                "content": f"完成 arXiv 结果去重，过滤重复论文 {skipped} 篇。",
            })
            await db.commit()

            task.status = "completed"
            task.finished_at = datetime.now(timezone.utc)
            task.execution_log.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M"),
                "level": "info",
                "content": f"结构化摘要生成完成，新增 {inserted} 篇论文。",
            })
            await db.commit()

            return {
                "status": "completed",
                "total_fetched": len(raw_papers),
                "inserted": inserted,
                "skipped": skipped,
            }

        except ArxivFetchError as e:
            task.status = "failed"
            task.finished_at = datetime.now(timezone.utc)
            task.error_message = str(e)
            task.execution_log.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M"),
                "level": "error",
                "content": f"arXiv API 错误: {e}",
            })
            await db.commit()
            raise celery_task.retry(exc=e)

        except Exception as e:
            task.status = "failed"
            task.finished_at = datetime.now(timezone.utc)
            task.error_message = str(e)
            task.execution_log.append({
                "time": datetime.now(timezone.utc).strftime("%H:%M"),
                "level": "error",
                "content": f"任务执行异常: {e}",
            })
            await db.commit()
            raise
