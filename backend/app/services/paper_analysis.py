"""Orchestration for downloading, parsing, extracting and indexing a paper."""

from __future__ import annotations

import asyncio
import tempfile
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import Settings, settings
from app.core.embedding import EmbeddingProvider, EmbeddingProviderError, get_embedding_provider
from app.core.llm_gateway import LLMGateway, get_llm_gateway
from app.database import AsyncSessionLocal
from app.models.paper import Paper
from app.services.analysis_extractor import StructuredExtractor
from app.services.analysis_persistence import backfill_unresolved_citations, persist_analysis
from app.services.analysis_state import (
    get_analysis_metadata,
    mark_analysis_failed,
    new_analysis_version,
    set_analysis_state,
)
from app.services.chunking import SemanticChunker
from app.services.pdf_parser import PDFParser


class PaperAnalysisError(RuntimeError):
    """Base exception for failures that should be visible in analysis state."""


class PDFDownloadError(PaperAnalysisError):
    pass


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
    except (httpx.HTTPError, OSError) as exc:
        raise PDFDownloadError(f"Unable to download PDF: {exc}") from exc

    status_code = getattr(response, "status_code", 200)
    if status_code >= 400:
        raise PDFDownloadError(f"PDF download returned HTTP {status_code}")
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", "")).split(";", 1)[0].strip().casefold()
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise PDFDownloadError(f"Unexpected PDF Content-Type: {content_type}")
    content_length = headers.get("content-length")
    try:
        if content_length and int(content_length) > config.analysis_pdf_max_bytes:
            raise PDFDownloadError("PDF exceeds the configured size limit")
    except ValueError:
        pass
    content = bytes(getattr(response, "content", b""))
    if len(content) > config.analysis_pdf_max_bytes:
        raise PDFDownloadError("PDF exceeds the configured size limit")
    if not content.startswith(b"%PDF"):
        raise PDFDownloadError("Downloaded content is not a PDF")
    return content


def _materialise_pdf(pdf_bytes: bytes) -> bytes:
    """Use a short-lived file so oversized/failed parser work never leaves artifacts."""

    with tempfile.NamedTemporaryFile(prefix="papermate-", suffix=".pdf", delete=True) as handle:
        handle.write(pdf_bytes)
        handle.flush()
        handle.seek(0)
        return handle.read()


async def run_paper_analysis(
    paper_id: UUID | str,
    *,
    task_id: str | None = None,
    force: bool = False,
    config: Settings = settings,
    llm: LLMGateway | None = None,
    embedder: EmbeddingProvider | None = None,
    parser: PDFParser | None = None,
    downloader: Any | None = None,
) -> dict[str, Any]:
    paper_uuid = UUID(str(paper_id))
    async with AsyncSessionLocal() as db:
        paper = await db.scalar(select(Paper).where(Paper.id == paper_uuid))
        if paper is None:
            raise PaperAnalysisError("Paper does not exist")
        current = get_analysis_metadata(paper)
        if paper.parsed_status == "completed" and not force:
            return {"paper_id": str(paper.id), "status": "completed", "skipped": True}
        analysis_version = current.get("analysis_version") or new_analysis_version()
        await set_analysis_state(
            db,
            paper.id,
            status="processing",
            stage="downloading",
            task_id=task_id,
            analysis_version=analysis_version,
            model=config.llm_model,
            embedding_model=config.embedding_model,
            prompt_version=config.analysis_prompt_version,
        )
        try:
            pdf_bytes = await download_pdf(paper.pdf_url, config=config, client=downloader)
            pdf_bytes = _materialise_pdf(pdf_bytes)
            await set_analysis_state(db, paper.id, status="processing", stage="parsing", commit=True)
            parsed = (parser or PDFParser()).parse(pdf_bytes)
            if not parsed.sections or not parsed.text.strip():
                raise PaperAnalysisError("PDF text extraction returned no usable sections")

            chunks = SemanticChunker(
                target_tokens=config.analysis_chunk_target_tokens,
                max_tokens=config.analysis_chunk_max_tokens,
                overlap_tokens=config.analysis_chunk_overlap_tokens,
            ).chunk(parsed)
            if not chunks:
                raise PaperAnalysisError("PDF could not be divided into chunks")
            await set_analysis_state(db, paper.id, status="processing", stage="extracting", commit=True)
            extraction = await StructuredExtractor(llm or get_llm_gateway(config), config).extract(
                title=paper.title,
                abstract=paper.abstract,
                chunks=chunks,
            )

            await set_analysis_state(db, paper.id, status="processing", stage="embedding", commit=True)
            embeddings = await (embedder or get_embedding_provider(config)).embed(
                [chunk.content for chunk in chunks]
            )
            if len(embeddings) != len(chunks):
                raise EmbeddingProviderError("Embedding provider returned an incomplete batch")
            for embedding in embeddings:
                if len(embedding) != config.embedding_dimension or len(embedding) != 1536:
                    raise EmbeddingProviderError("Every paper chunk must have a 1536-dimensional vector")

            await set_analysis_state(db, paper.id, status="processing", stage="persisting", commit=True)
            final_metadata = {
                **get_analysis_metadata(paper),
                "analysis_version": analysis_version,
                "model": config.llm_model,
                "embedding_model": config.embedding_model,
                "prompt_version": config.analysis_prompt_version,
                "task_id": task_id or get_analysis_metadata(paper).get("task_id"),
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
            )
            await db.commit()
            await db.refresh(paper)
            await backfill_unresolved_citations(db, paper.id)
            return {
                "paper_id": str(paper.id),
                "status": "completed",
                "analysis_version": analysis_version,
                "chunk_count": len(chunks),
            }
        except Exception:
            await db.rollback()
            raise


async def process_paper_async(
    paper_id: UUID | str,
    *,
    task_id: str | None = None,
    force: bool = False,
    **dependencies: Any,
) -> dict[str, Any]:
    return await run_paper_analysis(paper_id, task_id=task_id, force=force, **dependencies)


async def record_failure(paper_id: UUID | str, error: Exception, *, task_id: str | None = None) -> None:
    async with AsyncSessionLocal() as db:
        await mark_analysis_failed(db, UUID(str(paper_id)), str(error), task_id=task_id)


def run_paper_analysis_sync(paper_id: UUID | str, **kwargs: Any) -> dict[str, Any]:
    return asyncio.run(run_paper_analysis(paper_id, **kwargs))


__all__ = [
    "PDFDownloadError",
    "PaperAnalysisError",
    "download_pdf",
    "process_paper_async",
    "run_paper_analysis",
    "run_paper_analysis_sync",
]
