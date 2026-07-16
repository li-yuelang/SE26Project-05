"""arXiv Atom API client with query construction, pagination and rate limiting."""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from urllib.parse import urlencode
from weakref import WeakKeyDictionary

import httpx

from app.config import settings

ARXIV_BASE_URL = "https://export.arxiv.org/api/query"
ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_NS_ARXIV = {"arxiv": "http://arxiv.org/schemas/atom"}
MAX_RESULTS_PER_PAGE = 100

logger = logging.getLogger(__name__)
_local_rate_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()
_local_last_request = 0.0


class ArxivFetchError(Exception):
    """An arXiv API or Atom parsing failure."""

    def __init__(self, message: str, *, retryable: bool = True, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def _parse_arxiv_datetime(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_authors(entry: ET.Element) -> list[str]:
    authors: list[str] = []
    for author_el in entry.findall("atom:author", ARXIV_NS):
        name_el = author_el.find("atom:name", ARXIV_NS)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())
    return authors


def _parse_categories(entry: ET.Element) -> list[str]:
    return [
        term
        for element in entry.findall("atom:category", ARXIV_NS)
        if (term := element.get("term", "").strip())
    ]


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
    """Convert one Atom entry into the metadata shape used by ``Paper``."""

    id_el = entry.find("atom:id", ARXIV_NS)
    full_id = id_el.text.strip() if id_el is not None and id_el.text else ""
    arxiv_id = full_id.split("/")[-1] if full_id else ""
    if "v" in arxiv_id:
        arxiv_id = arxiv_id.split("v", 1)[0]
    if not arxiv_id:
        raise ArxivFetchError("arXiv entry is missing an id", retryable=False)

    title_el = entry.find("atom:title", ARXIV_NS)
    title = " ".join(title_el.text.split()) if title_el is not None and title_el.text else ""
    summary_el = entry.find("atom:summary", ARXIV_NS)
    abstract = " ".join(summary_el.text.split()) if summary_el is not None and summary_el.text else ""
    published_el = entry.find("atom:published", ARXIV_NS)
    updated_el = entry.find("atom:updated", ARXIV_NS)
    published_at = _parse_arxiv_datetime(published_el.text if published_el is not None else None)
    updated_at = _parse_arxiv_datetime(updated_el.text if updated_el is not None else None)
    if published_at is None:
        raise ArxivFetchError(f"arXiv entry {arxiv_id} has an invalid published date", retryable=False)

    categories = _parse_categories(entry)
    arxiv_url, pdf_url = _parse_links(entry)
    comment_el = entry.find("arxiv:comment", ARXIV_NS_ARXIV)
    comment = comment_el.text.strip() if comment_el is not None and comment_el.text else None
    return {
        "arxiv_id": arxiv_id,
        "title": title or arxiv_id,
        "authors": _parse_authors(entry),
        "abstract": abstract,
        "categories": categories,
        "primary_category": categories[0] if categories else None,
        "published_at": published_at,
        "updated_at_source": updated_at,
        "pdf_url": pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
        "arxiv_url": arxiv_url or f"https://arxiv.org/abs/{arxiv_id}",
        "metadata_extra": {"comment": comment} if comment else None,
    }


def _escape_phrase(value: str) -> str:
    # arXiv accepts quoted field values.  Escape the two characters that can
    # break a quoted value and collapse line breaks from form input.
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", " ").strip()


def build_search_query(
    keywords: list[str] | None = None,
    categories: list[str] | None = None,
    author: str | None = None,
    title_words: list[str] | None = None,
    # Keep the helper's historical default for existing callers.  Durable
    # fetch-task snapshots always pass their explicit default of ``or``.
    keyword_match_mode: str = "and",
) -> str:
    """Build an arXiv query with safe quoting and explicit keyword semantics."""

    normalized_keywords = [_escape_phrase(value) for value in keywords or [] if str(value).strip()]
    keyword_joiner = " AND " if keyword_match_mode == "and" else " OR "
    parts: list[str] = []
    if normalized_keywords:
        keyword_part = keyword_joiner.join(f'all:"{value}"' for value in normalized_keywords)
        parts.append(f"({keyword_part})" if len(normalized_keywords) > 1 else keyword_part)
    if categories:
        category_part = " OR ".join(f"cat:{_escape_phrase(category)}" for category in categories)
        parts.append(f"({category_part})" if len(categories) > 1 else category_part)
    if author and author.strip():
        parts.append(f'au:"{_escape_phrase(author)}"')
    if title_words:
        parts.extend(f'ti:"{_escape_phrase(word)}"' for word in title_words if str(word).strip())
    return " AND ".join(parts) if parts else "*"


def build_window_query(query: str, window_start: datetime, window_end: datetime) -> str:
    start = _format_submitted_date(window_start)
    end = _format_submitted_date(window_end)
    return f"({query}) AND submittedDate:[{start} TO {end}]"


def _format_submitted_date(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%d%H%M")


@asynccontextmanager
async def _global_request_slot() -> AsyncIterator[None]:
    """Serialize arXiv requests across workers using Redis when available."""

    global _local_last_request
    # The local lock is also useful as a safe fallback when Redis is starting.
    event_loop = asyncio.get_running_loop()
    local_rate_lock = _local_rate_locks.get(event_loop)
    if local_rate_lock is None:
        local_rate_lock = asyncio.Lock()
        _local_rate_locks[event_loop] = local_rate_lock
    async with local_rate_lock:
        redis_client = None
        redis_lock = None
        try:
            from redis.asyncio import Redis

            redis_client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=2,
            )
            redis_lock = redis_client.lock(
                "papermate:arxiv:request",
                timeout=settings.arxiv_redis_lock_timeout_seconds,
                blocking_timeout=settings.arxiv_redis_lock_timeout_seconds,
            )
            if not await redis_lock.acquire():
                raise RuntimeError("could not acquire arXiv Redis lock")
            last_value = await redis_client.get("papermate:arxiv:last-request")
            elapsed = time.time() - float(last_value) if last_value else 999.0
            delay = settings.arxiv_request_interval_seconds - elapsed
            if delay > 0:
                await asyncio.sleep(delay)
        except Exception as exc:
            if redis_lock is not None:
                try:
                    await redis_lock.release()
                except Exception:
                    logger.debug("unable to release arXiv Redis lock", exc_info=True)
            if redis_client is not None:
                await redis_client.aclose()
            redis_client = None
            redis_lock = None
            delay = settings.arxiv_request_interval_seconds - (
                time.monotonic() - _local_last_request
            )
            if delay > 0:
                await asyncio.sleep(delay)
            logger.debug("using local arXiv limiter because Redis is unavailable: %s", exc)

        try:
            yield
        finally:
            _local_last_request = time.monotonic()
            if redis_client is not None:
                try:
                    await redis_client.set("papermate:arxiv:last-request", str(time.time()), ex=3600)
                    if redis_lock is not None:
                        await redis_lock.release()
                except Exception:
                    logger.debug("unable to update arXiv Redis limiter", exc_info=True)
                finally:
                    await redis_client.aclose()


def _request_headers() -> dict[str, str]:
    headers = {"User-Agent": settings.arxiv_user_agent, "Accept": "application/atom+xml"}
    if settings.arxiv_contact_email:
        headers["From"] = settings.arxiv_contact_email
    return headers


async def fetch_arxiv_papers(
    query: str,
    max_results: int = 50,
    start: int = 0,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch one page, never requesting more than arXiv's 100-item limit."""

    params = {
        "search_query": query,
        "start": str(max(start, 0)),
        "max_results": str(min(max(max_results, 1), MAX_RESULTS_PER_PAGE)),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_BASE_URL}?{urlencode(params, safe=':()[]')}"
    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(settings.arxiv_timeout_seconds),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )
    try:
        async with _global_request_slot():
            response = await http_client.get(url, headers=_request_headers())
        if response.status_code == 429 or response.status_code >= 500:
            raise ArxivFetchError(
                f"arXiv API returned HTTP {response.status_code}",
                retryable=True,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ArxivFetchError(
                f"arXiv API returned HTTP {response.status_code}",
                retryable=False,
                status_code=response.status_code,
            )
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError as exc:
            raise ArxivFetchError("arXiv API returned invalid XML", retryable=True) from exc
        return [_parse_entry(entry) for entry in root.findall("atom:entry", ARXIV_NS)]
    except ArxivFetchError:
        raise
    except httpx.TimeoutException as exc:
        raise ArxivFetchError("arXiv API timed out", retryable=True) from exc
    except httpx.HTTPError as exc:
        raise ArxivFetchError(f"arXiv API request failed: {exc}", retryable=True) from exc
    finally:
        if owns_client:
            await http_client.aclose()


async def fetch_arxiv_window(
    query: str,
    *,
    window_start: datetime,
    window_end: datetime,
    max_results: int,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
) -> tuple[list[dict[str, Any]], int]:
    """Fetch pages until the task cap or the API's result set is exhausted."""

    window_query = build_window_query(query, window_start, window_end)
    results: list[dict[str, Any]] = []
    page_count = 0
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.arxiv_timeout_seconds),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    ) as client:
        start = 0
        while len(results) < max_results:
            page_limit = min(MAX_RESULTS_PER_PAGE, max_results - len(results))
            page = await fetch_arxiv_papers(
                window_query,
                max_results=page_limit,
                start=start,
                sort_by=sort_by,
                sort_order=sort_order,
                client=client,
            )
            page_count += 1
            results.extend(page)
            if len(page) < page_limit:
                break
            start += len(page)
    return results[:max_results], page_count


__all__ = [
    "ARXIV_BASE_URL",
    "ArxivFetchError",
    "MAX_RESULTS_PER_PAGE",
    "build_search_query",
    "build_window_query",
    "fetch_arxiv_papers",
    "fetch_arxiv_window",
]
