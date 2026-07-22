"""Canonicalisation, citation matching and atomic persistence for analysis."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.concept import Concept, ConceptRelation, ConceptRelationEvidence, PaperConcept
from app.models.paper import Paper, PaperAnalysisRun, PaperChunk, PaperCitation
from app.schemas.analysis import (
    ExtractedConcept,
    ExtractedReference,
    ExtractedRelation,
    FinalExtraction,
)
from app.services.analysis_extractor import ExtractionResult
from app.services.chunking import PaperTextChunk


def normalize_concept_name(value: str) -> str:
    """Return a stable, case-insensitive graph key for an English concept name."""

    value = unicodedata.normalize("NFKC", value or "").strip().casefold()
    value = re.sub(r"[^\w\u3400-\u9fff]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[^\w\u3400-\u9fff]+", " ", value, flags=re.UNICODE).strip()


def normalize_arxiv_id(value: str) -> str:
    value = (value or "").strip().casefold()
    value = re.sub(r"^https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/", "", value)
    value = re.sub(r"^arxiv:", "", value)
    value = re.sub(r"\.pdf$", "", value)
    value = re.sub(r"v\d+$", "", value)
    return value.strip()


def normalize_relation_type(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", (value or "RELATED_TO").upper()).strip("_")
    return value or "RELATED_TO"


def clamp_confidence(value: float | int | None, default: float = 1.0) -> float:
    try:
        number = float(value if value is not None else default)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


@dataclass(slots=True)
class ConceptRecord:
    key: str
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    category: str = ""
    evidence: str = ""
    relevance: float = 1.0


@dataclass(slots=True)
class RelationRecord:
    source_key: str
    target_key: str
    relation_type: str
    evidence: str
    confidence: float


def _concept_key(value: str) -> str:
    return normalize_concept_name(value)


def collect_concepts(
    final: FinalExtraction, local: Iterable[Any] = ()
) -> tuple[dict[str, ConceptRecord], list[RelationRecord]]:
    records: dict[str, ConceptRecord] = {}
    alias_to_key: dict[str, str] = {}
    # Reduce output comes first so its descriptions are preferred over local notes.
    all_concepts: list[ExtractedConcept] = list(final.concepts)
    all_relations: list[ExtractedRelation] = list(final.relations)
    for result in local:
        all_concepts.extend(result.concepts)
        all_relations.extend(result.relations)

    for concept in all_concepts:
        raw_name = concept.name_en.strip() or concept.name_zh.strip()
        key = _concept_key(raw_name)
        if not key:
            continue
        record = records.setdefault(key, ConceptRecord(key=key, name=key))
        for alias in (concept.name_zh.strip(),):
            if alias:
                alias_to_key[_concept_key(alias)] = key
            if alias and alias.casefold() != record.name.casefold() and alias not in record.aliases:
                record.aliases.append(alias)
        if concept.description.strip() and not record.description:
            record.description = concept.description.strip()
        if concept.category.strip() and not record.category:
            record.category = concept.category.strip()
        if concept.evidence.strip() and not record.evidence:
            record.evidence = concept.evidence.strip()
        record.relevance = max(record.relevance, clamp_confidence(concept.relevance))

    relations: list[RelationRecord] = []
    seen_relations: set[tuple[str, str, str]] = set()
    for relation in all_relations:
        source_key = alias_to_key.get(_concept_key(relation.source), _concept_key(relation.source))
        target_key = alias_to_key.get(_concept_key(relation.target), _concept_key(relation.target))
        if not source_key or not target_key or source_key == target_key:
            continue
        # A relation may introduce a concept that the LLM omitted from its concept list.
        records.setdefault(source_key, ConceptRecord(key=source_key, name=source_key))
        records.setdefault(target_key, ConceptRecord(key=target_key, name=target_key))
        relation_key = (source_key, target_key, normalize_relation_type(relation.relation_type))
        if relation_key in seen_relations:
            continue
        seen_relations.add(relation_key)
        relations.append(
            RelationRecord(
                source_key=source_key,
                target_key=target_key,
                relation_type=relation_key[2],
                evidence=relation.evidence.strip(),
                confidence=clamp_confidence(relation.confidence),
            )
        )
    return records, relations


def collect_references(final: FinalExtraction, local: Iterable[Any] = ()) -> list[ExtractedReference]:
    references: list[ExtractedReference] = []
    seen: set[tuple[str, str]] = set()
    for reference in [*final.references, *(reference for result in local for reference in result.references)]:
        key = (normalize_arxiv_id(reference.arxiv_id), normalize_title(reference.title))
        if not key[0] and not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        references.append(reference)
    return references


async def match_references(
    db: AsyncSession, references: list[ExtractedReference], source_paper_id: UUID
) -> list[dict[str, Any]]:
    """Match references by arXiv ID first, then by normalised title."""

    arxiv_ids = {normalize_arxiv_id(reference.arxiv_id) for reference in references if reference.arxiv_id}
    conditions = []
    if arxiv_ids:
        conditions.append(Paper.arxiv_id.in_(list(arxiv_ids)))
    # Exact title filtering is only a candidate reduction; normalisation below
    # handles punctuation and whitespace differences.
    if reference_titles := [reference.title for reference in references if reference.title]:
        conditions.append(Paper.title.in_(reference_titles))
    candidates: list[Paper] = []
    if conditions:
        candidates = list((await db.scalars(select(Paper).where(or_(*conditions)))).all())
    # SQL equality cannot express the punctuation/whitespace normalisation
    # used by the matcher.  A small fallback scan preserves title matching for
    # references such as "A Study: ..." versus "A Study ...".
    if references and not candidates:
        candidates = list((await db.scalars(select(Paper))).all())

    by_arxiv: dict[str, Paper] = {}
    by_title: dict[str, Paper] = {}
    for candidate in candidates:
        if candidate.id == source_paper_id:
            continue
        if candidate.arxiv_id:
            by_arxiv.setdefault(normalize_arxiv_id(candidate.arxiv_id), candidate)
        if candidate.title:
            by_title.setdefault(normalize_title(candidate.title), candidate)

    needs_normalised_scan = any(
        (reference.arxiv_id and normalize_arxiv_id(reference.arxiv_id) not in by_arxiv)
        or (reference.title and normalize_title(reference.title) not in by_title)
        for reference in references
    )
    if references and needs_normalised_scan:
        candidates = list((await db.scalars(select(Paper))).all())
        by_arxiv.clear()
        by_title.clear()
        for candidate in candidates:
            if candidate.id == source_paper_id:
                continue
            if candidate.arxiv_id:
                by_arxiv.setdefault(normalize_arxiv_id(candidate.arxiv_id), candidate)
            if candidate.title:
                by_title.setdefault(normalize_title(candidate.title), candidate)

    result: list[dict[str, Any]] = []
    for reference in references:
        matched = by_arxiv.get(normalize_arxiv_id(reference.arxiv_id)) if reference.arxiv_id else None
        if matched is None and reference.title:
            matched = by_title.get(normalize_title(reference.title))
        item = reference.model_dump(mode="json")
        item["confidence"] = clamp_confidence(reference.confidence)
        item["matchedPaperId"] = str(matched.id) if matched else None
        if matched:
            item["matchedArxivId"] = matched.arxiv_id
            item["matchedTitle"] = matched.title
        result.append(item)
    return result


async def persist_analysis(
    db: AsyncSession,
    *,
    paper: Paper,
    chunks: list[PaperTextChunk],
    embeddings: list[list[float]],
    extraction: ExtractionResult,
    source_content: str,
    analysis_version: str,
    analysis_metadata: dict[str, Any],
    analysis_run_id: UUID | None = None,
) -> None:
    """Persist one immutable result version in the caller's transaction.

    New runs never delete a previous successful version.  The legacy delete
    path remains available only for callers that have not supplied a run id.
    """

    if len(chunks) != len(embeddings):
        raise ValueError("The number of embeddings must equal the number of chunks")
    concepts, relations = collect_concepts(extraction.final, extraction.local)
    references = await match_references(db, collect_references(extraction.final, extraction.local), paper.id)

    if analysis_run_id is not None:
        run = await db.get(PaperAnalysisRun, analysis_run_id, with_for_update=True)
        if run is None or run.paper_id != paper.id:
            raise ValueError("Analysis run does not belong to this paper")
        if run.status in {"failed", "cancelled", "completed"}:
            raise RuntimeError(f"Analysis run {analysis_run_id} is no longer writable")

    # The legacy path is retained for old callers and one-time compatibility
    # scripts.  The production worker always supplies ``analysis_run_id``.
    if analysis_run_id is None:
        await db.execute(delete(PaperChunk).where(PaperChunk.paper_id == paper.id))
        await db.execute(delete(PaperConcept).where(PaperConcept.paper_id == paper.id))
        await db.execute(delete(PaperCitation).where(PaperCitation.source_paper_id == paper.id))
    # Relation evidence is intentionally retained across reruns.  The current
    # paper links/chunks are replaced, while each evidence row records its
    # analysis version for auditability.

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        if len(embedding) != 1536:
            raise ValueError(f"Embedding dimension mismatch: expected 1536, got {len(embedding)}")
        db.add(
            PaperChunk(
                paper_id=paper.id,
                analysis_run_id=analysis_run_id,
                analysis_version=analysis_version,
                chunk_index=chunk.chunk_index,
                section_title=chunk.section_title,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=embedding,
            )
        )

    concept_rows: dict[str, Concept] = {}
    if concepts:
        existing = list((await db.scalars(select(Concept).where(Concept.name.in_(list(concepts))))).all())
        concept_rows.update({row.name: row for row in existing})
    for key, record in concepts.items():
        row = concept_rows.get(key)
        if row is None:
            row = Concept(
                name=record.name,
                aliases=record.aliases,
                description=record.description or None,
                category=record.category or None,
            )
            db.add(row)
            concept_rows[key] = row
        # Concept rows are shared extraction facts.  Do not let a later
        # user's analysis overwrite descriptions, aliases, or categories
        # already visible to other users; user-authored Wiki data belongs in
        # UserConcept instead.
    await db.flush()

    for key, record in concepts.items():
        db.add(
            PaperConcept(
                paper_id=paper.id,
                concept_id=concept_rows[key].id,
                analysis_run_id=analysis_run_id,
                analysis_version=analysis_version,
                relevance=record.relevance,
                evidence=record.evidence or None,
            )
        )

    for relation in relations:
        source = concept_rows[relation.source_key]
        target = concept_rows[relation.target_key]
        graph_relation = await db.scalar(
            select(ConceptRelation).where(
                and_(
                    ConceptRelation.source_concept_id == source.id,
                    ConceptRelation.target_concept_id == target.id,
                    ConceptRelation.relation_type == relation.relation_type,
                )
            )
        )
        if graph_relation is None:
            graph_relation = ConceptRelation(
                source_concept_id=source.id,
                target_concept_id=target.id,
                relation_type=relation.relation_type,
                weight=relation.confidence,
            )
            db.add(graph_relation)
            await db.flush()
        # Relation strength is immutable at the shared-graph level.  A user's
        # Wiki view derives its strength from evidence in that user's library.
        db.add(
            ConceptRelationEvidence(
                relation_id=graph_relation.id,
                paper_id=paper.id,
                evidence=relation.evidence or "该关系由论文分析结果推断。",
                confidence=relation.confidence,
                analysis_version=analysis_version,
                analysis_run_id=analysis_run_id,
            )
        )

    for reference in references:
        target_id = reference.get("matchedPaperId")
        if not target_id or UUID(target_id) == paper.id:
            continue
        db.add(
            PaperCitation(
                source_paper_id=paper.id,
                target_paper_id=UUID(target_id),
                analysis_run_id=analysis_run_id,
                analysis_version=analysis_version,
                context=reference.get("context") or None,
                confidence=clamp_confidence(reference.get("confidence")),
            )
        )

    structured_content = dict(extraction.structured_content)
    structured_content["references"] = references
    structured_content["analysisVersion"] = analysis_version
    paper.source_content = source_content.replace("\x00", "")
    paper.structured_content = structured_content
    if analysis_run_id is None:
        paper.parsed_status = "completed"
        paper.metadata_extra = {
            **(paper.metadata_extra or {}),
            "analysis": {**analysis_metadata, "status": "completed", "stage": "completed"},
        }


async def backfill_unresolved_citations(db: AsyncSession, target_paper_id: UUID) -> int:
    """Resolve references in older analyses after a new target paper is added."""

    target = await db.get(Paper, target_paper_id)
    if target is None:
        return 0
    target_arxiv = normalize_arxiv_id(target.arxiv_id)
    target_title = normalize_title(target.title)
    papers = list((await db.scalars(select(Paper).where(Paper.id != target.id))).all())
    created = 0
    updated = False
    for paper in papers:
        content = dict(paper.structured_content or {})
        references = content.get("references")
        if not isinstance(references, list):
            continue
        changed = False
        for reference in references:
            if not isinstance(reference, dict) or reference.get("matchedPaperId"):
                continue
            if normalize_arxiv_id(str(reference.get("arxiv_id", ""))) == target_arxiv or (
                reference.get("title") and normalize_title(str(reference["title"])) == target_title
            ):
                reference["matchedPaperId"] = str(target.id)
                reference["matchedArxivId"] = target.arxiv_id
                reference["matchedTitle"] = target.title
                exists = await db.scalar(
                    select(PaperCitation.id).where(
                        PaperCitation.source_paper_id == paper.id,
                        PaperCitation.target_paper_id == target.id,
                    )
                )
                if exists is None:
                    db.add(
                        PaperCitation(
                            source_paper_id=paper.id,
                            target_paper_id=target.id,
                            analysis_run_id=paper.active_analysis_run_id,
                            analysis_version=content.get("analysisVersion"),
                            context=reference.get("context"),
                            confidence=clamp_confidence(reference.get("confidence")),
                        )
                    )
                    created += 1
                changed = True
        if changed:
            paper.structured_content = content
            updated = True
    if updated:
        await db.commit()
    return created
