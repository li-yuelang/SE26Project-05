"""arXiv API 集成服务 — 拉取、去重、入库。"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

ARXIV_BASE_URL = "https://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
MAX_RESULTS_PER_PAGE = 100

logger = logging.getLogger(__name__)


class ArxivFetchError(Exception):
    """arXiv API 调用相关错误。"""


def _parse_arxiv_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt
    except (ValueError, TypeError):
        return None


def _parse_authors(entry: ET.Element) -> list[str]:
    authors: list[str] = []
    for author_el in entry.findall("atom:author", ARXIV_NS):
        name_el = author_el.find("atom:name", ARXIV_NS)
        if name_el is not None and name_el.text:
            authors.append(name_el.text)
    return authors


def _parse_categories(entry: ET.Element) -> list[str]:
    cats: list[str] = []
    for cat_el in entry.findall("atom:category", ARXIV_NS):
        term = cat_el.get("term", "")
        if term:
            cats.append(term)
    return cats


def _parse_links(entry: ET.Element) -> tuple[str, str]:
    pdf_url = ""
    arxiv_url = ""
    for link_el in entry.findall("atom:link", ARXIV_NS):
        href = link_el.get("href", "")
        title = link_el.get("title", "")
        if title == "pdf":
            pdf_url = href
        elif title == "abstract" or not arxiv_url:
            arxiv_url = href
    return arxiv_url, pdf_url


def _parse_entry(entry: ET.Element) -> dict[str, Any]:
    """将单条 arXiv Atom entry 解析为论文字典。"""
    id_el = entry.find("atom:id", ARXIV_NS)
    full_id = id_el.text.strip() if id_el is not None and id_el.text else ""
    arxiv_id = full_id.split("/")[-1].split("v")[0] if "abs/" in full_id else full_id

    title_el = entry.find("atom:title", ARXIV_NS)
    title = title_el.text.strip().replace("\n", " ").replace("  ", " ") if title_el is not None and title_el.text else ""

    summary_el = entry.find("atom:summary", ARXIV_NS)
    abstract = summary_el.text.strip() if summary_el is not None and summary_el.text else ""

    published_el = entry.find("atom:published", ARXIV_NS)
    published_at = _parse_arxiv_datetime(published_el.text) if published_el is not None else None

    updated_el = entry.find("atom:updated", ARXIV_NS)
    updated_at = _parse_arxiv_datetime(updated_el.text) if updated_el is not None else None

    authors = _parse_authors(entry)
    categories = _parse_categories(entry)
    primary_category = categories[0] if categories else None
    arxiv_url, pdf_url = _parse_links(entry)

    comment_el = entry.find("arxiv:comment", {"arxiv": "http://arxiv.org/schemas/atom"})
    comment = comment_el.text if comment_el is not None else None

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "categories": categories,
        "primary_category": primary_category,
        "published_at": published_at,
        "updated_at_source": updated_at,
        "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
        "arxiv_url": arxiv_url or f"https://arxiv.org/abs/{arxiv_id}",
        "metadata_extra": {"comment": comment} if comment else None,
    }


async def fetch_arxiv_papers(
    query: str,
    max_results: int = 50,
    start: int = 0,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
) -> list[dict[str, Any]]:
    """调用 arXiv API 查询论文。

    Args:
        query: arXiv 查询字符串（支持 AND/OR/ANDNOT, 字段限定如 ti:transformer）
        max_results: 返回条数（最大 100）
        start: 起始偏移
        sort_by: submittedDate | lastUpdatedDate | relevance
        sort_order: ascending | descending

    Returns:
        解析后的论文字典列表
    """
    params = {
        "search_query": query,
        "start": str(start),
        "max_results": str(min(max_results, MAX_RESULTS_PER_PAGE)),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_BASE_URL}?{urlencode(params, safe=':')}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ArxivFetchError(f"arXiv API returned {e.response.status_code}") from e
        except httpx.TimeoutException:
            raise ArxivFetchError("arXiv API timed out") from None

    root = ET.fromstring(resp.text)
    entries = root.findall("atom:entry", ARXIV_NS)
    return [_parse_entry(entry) for entry in entries]


def build_search_query(
    keywords: list[str] | None = None,
    categories: list[str] | None = None,
    author: str | None = None,
    title_words: list[str] | None = None,
) -> str:
    """构建 arXiv API 查询字符串。

    Examples:
        >>> build_search_query(keywords=["transformer", "attention"])
        'all:"transformer" AND all:"attention"'
        >>> build_search_query(categories=["cs.CL", "cs.AI"])
        'cat:cs.CL OR cat:cs.AI'
        >>> build_search_query(author="lecun")
        'au:"lecun"'
        >>> build_search_query(title_words=["retrieval", "augmented"])
        'ti:"retrieval" AND ti:"augmented"'
    """
    parts: list[str] = []

    if keywords:
        parts.extend(f'all:"{kw}"' for kw in keywords if kw)

    if categories:
        cat_part = " OR ".join(f"cat:{cat}" for cat in categories)
        if parts:
            cat_part = f"({cat_part})"
        parts.append(cat_part)

    if author:
        parts.append(f'au:"{author}"')

    if title_words:
        parts.extend(f'ti:"{tw}"' for tw in title_words if tw)

    if not parts:
        return "*"

    return " AND ".join(parts)
