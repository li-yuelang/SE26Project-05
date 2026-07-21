"""Download, parse, extract, embed and persist one immutable paper version."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import Settings, settings
from app.core.embedding import EmbeddingProvider, EmbeddingProviderError, get_embedding_provider
from app.core.llm_gateway import LLMGateway, get_llm_gateway
from app.database import AsyncSessionLocal
from app.models.paper import Paper, PaperAnalysisRun
from app.services.analysis_errors import classify_analysis_error
from app.services.analysis_extractor import StructuredExtractor
from app.services.analysis_persistence import backfill_unresolved_citations, persist_analysis
from app.services.analysis_runs import (
    claim_analysis_run,
    create_analysis_run,
    heartbeat_analysis_run,
    mark_analysis_completed,
    mark_analysis_failed,
    set_analysis_stage,
)
from app.services.chunking import SemanticChunker
from app.services.pdf_parser import OCRRequiredError, PDFInvalidError, PDFParser


class PaperAnalysisError(RuntimeError):
    """Base exception for failures visible in ``paper_analysis_runs``."""

    error_code = "PARSER_ERROR"
    retryable = False


class PDFDownloadError(PaperAnalysisError):
    error_code = "DOWNLOAD_ERROR"
    retryable = True


async def _read_response_content(response: Any, *, max_bytes: int) -> bytes:
    """Read response bodies incrementally and enforce the real byte limit."""

    if hasattr(response, "aiter_bytes"):
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            data = bytes(chunk)
            size += len(data)
            if size > max_bytes:
                raise PDFDownloadError("PDF exceeds the configured size limit")
            chunks.append(data)
        return b"".join(chunks)
    content = bytes(getattr(response, "content", b""))
    if len(content) > max_bytes:
        raise PDFDownloadError("PDF exceeds the configured size limit")
    return content


async def download_pdf(
    url: str,
    *,
    config: Settings = settings,
    client: Any | None = None,
) -> bytes:
    if not url:
        raise PDFDownloadError("Paper has no pdf_url")
    try:
        if client is None:
            timeout = httpx.Timeout(config.analysis_pdf_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
                response = await http_client.get(url)
        else:
            response = await client.get(url)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError) as exc:
        raise PDFDownloadError(f"Unable to download PDF: {exc}") from exc
    except httpx.HTTPError as exc:
        error = PDFDownloadError(f"Unable to download PDF: {exc}")
        error.retryable = False
        raise error from exc

    status_code = getattr(response, "status_code", 200)
    if status_code >= 400:
        error = PDFDownloadError(f"PDF download returned HTTP {status_code}")
        error.retryable = status_code == 408 or status_code == 429 or status_code >= 500
        error.error_code = "DOWNLOAD_ERROR"
        raise error
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", "")).split(";", 1)[0].strip().casefold()
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        error = PDFDownloadError(f"Unexpected PDF Content-Type: {content_type}")
        error.retryable = False
        raise error
    content_length = headers.get("content-length")
    try:
        if content_length and int(content_length) > config.analysis_pdf_max_bytes:
            raise PDFDownloadError("PDF exceeds the configured size limit")
    except ValueError:
        pass
    content = await _read_response_content(response, max_bytes=config.analysis_pdf_max_bytes)
    if not content.startswith(b"%PDF"):
        error = PDFDownloadError("Downloaded content is not a PDF")
        error.error_code = "PDF_INVALID"
        error.retryable = False
        raise error
    return content


async def _set_stage(run_id: UUID, stage: str) -> None:
    async with AsyncSessionLocal() as db:
        await set_analysis_stage(db, run_id, stage)


async def _heartbeat(run_id: UUID) -> None:
    await heartbeat_analysis_run(run_id)


async def _ensure_run_for_direct_call(
    paper_id: UUID,
    *,
    task_id: str | None,
    force: bool,
    config: Settings,
) -> PaperAnalysisRun:
    async with AsyncSessionLocal() as db:
        run, _ = await create_analysis_run(
            db,
            paper_id,
            force=force,
            config=config,
            celery_task_id=task_id,
            create_outbox=False,
        )
        await db.commit()
        return run


async def run_paper_analysis(
    paper_id: UUID | str,
    *,
    task_id: str | None = None,
    run_id: UUID | str | None = None,
    force: bool = False,
    config: Settings = settings,
    llm: LLMGateway | None = None,
    embedder: EmbeddingProvider | None = None,
    parser: PDFParser | None = None,
    downloader: Any | None = None,
) -> dict[str, Any]:
    paper_uuid = UUID(str(paper_id))
    if run_id is None:
        run = await _ensure_run_for_direct_call(
            paper_uuid, task_id=task_id, force=force, config=config
        )
        run_uuid = run.id
    else:
        run_uuid = UUID(str(run_id))

    async with AsyncSessionLocal() as db:
        paper = await db.scalar(select(Paper).where(Paper.id == paper_uuid))
        run = await db.get(PaperAnalysisRun, run_uuid)
        if paper is None:
            raise PaperAnalysisError("Paper does not exist")
        if run is None or run.paper_id != paper.id:
            raise PaperAnalysisError("Analysis run does not belong to this paper")
        if run.status == "completed" and not force:
            return {
                "paper_id": str(paper.id),
                "run_id": str(run.id),
                "status": "completed",
                "analysis_version": run.analysis_version,
                "skipped": True,
            }
        claimed = await claim_analysis_run(db, run.id, task_id=task_id)
        if claimed is None:
            current = await db.get(PaperAnalysisRun, run.id)
            return {
                "paper_id": str(paper.id),
                "run_id": str(run.id),
                "status": current.status if current else "failed",
                "analysis_version": current.analysis_version if current else None,
                "skipped": True,
            }
        await db.commit()
        analysis_version = claimed.analysis_version

    try:
        await _set_stage(run_uuid, "downloading")
        pdf_bytes = await download_pdf(paper.pdf_url, config=config, client=downloader)
        await _heartbeat(run_uuid)

        await _set_stage(run_uuid, "parsing")
        parsed = (parser or PDFParser()).parse(pdf_bytes)
        if not parsed.sections or not parsed.text.strip():
            raise OCRRequiredError("PDF text extraction returned no usable sections")
        await _heartbeat(run_uuid)

        await _set_stage(run_uuid, "chunking")
        chunks = SemanticChunker(
            target_tokens=config.analysis_chunk_target_tokens,
            max_tokens=config.analysis_chunk_max_tokens,
            overlap_tokens=config.analysis_chunk_overlap_tokens,
        ).chunk(parsed)
        if not chunks:
            raise PaperAnalysisError("PDF could not be divided into chunks")
        await _heartbeat(run_uuid)

        await _set_stage(run_uuid, "extracting")
        extraction = await StructuredExtractor(llm or get_llm_gateway(config), config).extract(
            title=paper.title,
            abstract=paper.abstract,
            chunks=chunks,
            progress_callback=lambda: _heartbeat(run_uuid),
        )
        await _heartbeat(run_uuid)

        await _set_stage(run_uuid, "embedding")
        embeddings = await (embedder or get_embedding_provider(config)).embed(
            [chunk.content for chunk in chunks]
        )
        if len(embeddings) != len(chunks):
            raise EmbeddingProviderError("Embedding provider returned an incomplete batch")
        for embedding in embeddings:
            if len(embedding) != config.embedding_dimension or len(embedding) != 1536:
                raise EmbeddingProviderError("Every paper chunk must have a 1536-dimensional vector")
        await _heartbeat(run_uuid)

        await _set_stage(run_uuid, "persisting")
        async with AsyncSessionLocal() as db:
            paper = await db.get(Paper, paper_uuid, with_for_update=True)
            run = await db.get(PaperAnalysisRun, run_uuid, with_for_update=True)
            if paper is None or run is None:
                raise PaperAnalysisError("Paper analysis state disappeared")
            if run.status in {"failed", "cancelled", "completed"}:
                raise PaperAnalysisError("Analysis run is no longer writable")
            final_metadata = {
                "analysis_version": analysis_version,
                "model": config.llm_model,
                "embedding_model": config.embedding_model,
                "prompt_version": config.analysis_prompt_version,
                "task_id": task_id or run.celery_task_id,
            }
            await persist_analysis(
                db,
                paper=paper,
                chunks=chunks,
                embeddings=embeddings,
                extraction=extraction,
                source_content=parsed.text,
                analysis_version=analysis_version,
                analysis_metadata=final_metadata,
                analysis_run_id=run.id,
            )
            await mark_analysis_completed(
                db,
                run.id,
                analysis_version=analysis_version,
                commit=False,
            )
            await db.commit()

        async with AsyncSessionLocal() as db:
            await backfill_unresolved_citations(db, paper_uuid)
        return {
            "paper_id": str(paper_uuid),
            "run_id": str(run_uuid),
            "status": "completed",
            "analysis_version": analysis_version,
            "chunk_count": len(chunks),
        }
    except (PDFInvalidError, OCRRequiredError):
        raise
    except Exception:
        raise


async def process_paper_async(
    paper_id: UUID | str,
    *,
    task_id: str | None = None,
    run_id: UUID | str | None = None,
    force: bool = False,
    **dependencies: Any,
) -> dict[str, Any]:
    return await run_paper_analysis(
        paper_id,
        task_id=task_id,
        run_id=run_id,
        force=force,
        **dependencies,
    )


async def record_failure(
    paper_id: UUID | str,
    error: Exception,
    *,
    task_id: str | None = None,
    run_id: UUID | str | None = None,
    error_code: str | None = None,
) -> None:
    info = classify_analysis_error(error)
    code = error_code or info.code
    async with AsyncSessionLocal() as db:
        target_run_id = UUID(str(run_id)) if run_id else None
        if target_run_id is None and task_id:
            target_run_id = await db.scalar(
                select(PaperAnalysisRun.id).where(PaperAnalysisRun.celery_task_id == task_id)
            )
        if target_run_id is None:
            paper = await db.get(Paper, UUID(str(paper_id)))
            if paper is not None:
                target_run_id = await db.scalar(
                    select(PaperAnalysisRun.id)
                    .where(PaperAnalysisRun.paper_id == paper.id)
                    .order_by(PaperAnalysisRun.created_at.desc())
                    .limit(1)
                )
        if target_run_id is None:
            return
        try:
            await mark_analysis_failed(
                db,
                target_run_id,
                error_code=code,
                error_message=str(error),
            )
        except LookupError:
            await db.rollback()


def run_paper_analysis_sync(paper_id: UUID | str, **kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_paper_analysis(paper_id, **kwargs))


__all__ = [
    "PDFDownloadError",
    "PaperAnalysisError",
    "download_pdf",
    "process_paper_async",
    "record_failure",
    "run_paper_analysis",
    "run_paper_analysis_sync",
]
