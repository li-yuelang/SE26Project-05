from types import SimpleNamespace
from uuid import uuid4

from app.services.rag import (
    RetrievedChunk,
    build_prompt,
    detect_scenario,
    fallback_answer,
    lexical_score,
)


def make_chunk(content: str = "Self-attention maps queries and key-value pairs to an output."):
    paper = SimpleNamespace(id=uuid4(), title="Attention Is All You Need", arxiv_id="1706.03762")
    chunk = SimpleNamespace(
        id=uuid4(),
        content=content,
        chunk_index=2,
        section_title="Model Architecture",
    )
    return RetrievedChunk(chunk=chunk, paper=paper, score=0.9)


def test_detects_prompt_scenarios():
    assert detect_scenario("BERT 和 GPT 有什么区别？") == "comparison"
    assert detect_scenario("请梳理 RAG 的发展脉络") == "lineage"
    assert detect_scenario("解释什么是自注意力") == "concept"
    assert detect_scenario("任意问题", "comparison") == "comparison"


def test_prompt_contains_traceable_chunk_metadata():
    system, prompt = build_prompt("什么是自注意力？", [make_chunk()], "concept")
    assert "只能依据" in system
    assert "arXiv:1706.03762" in prompt
    assert "片段：2" in prompt
    assert "[1]" in prompt


def test_fallback_answer_keeps_citation_and_evidence_boundary():
    answer = fallback_answer("什么是自注意力？", [make_chunk()], "concept")
    assert "[1]" in answer
    assert "证据边界" in answer


def test_lexical_reranking_prefers_matching_evidence():
    relevant = lexical_score("self attention query", "self attention uses a query and key")
    irrelevant = lexical_score("self attention query", "image convolution kernels")
    assert relevant > irrelevant
