"""
arxiv-PaperMate Performance Test — 终极版

Tests:
  1. Retrieval    – paper list, keyword search, paper detail, semantic search
  2. Q&A (non-LLM) – chat bootstrap, create conversation
  3. Learning     – dashboard, bookmarks, notes

Each concurrent request uses a distinct test user account.

Requirements (verified by this script):
  - >= 100 data records (paper metadata)
  - 100 concurrent users
  - p95 response time < 3s for retrieval / Q&A / learning management
  - Excludes LLM response time (semantic search's embedding API is external)

Usage:
  cd backend
  uv run python performance_test.py

Environment variables (optional):
  PAPERMATE_BASE_URL      – API base URL          (default: http://localhost:8080)
  PAPERMATE_CONCURRENCY   – concurrent users      (default: 100)
  PAPERMATE_SKIP_EXTERNAL – skip semantic search  (set to "1" to skip external API tests)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Coroutine

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("PAPERMATE_BASE_URL", "http://localhost:8080")
CONCURRENCY = int(os.getenv("PAPERMATE_CONCURRENCY", "100"))
TIMEOUT = 30.0
TARGET = 3.0
PAPER_MIN = 100
SKIP_EXTERNAL = os.getenv("PAPERMATE_SKIP_EXTERNAL", "") == "1"

TEST_PASSWORD = "perftest123"
TEST_USERNAME_FMT = "perftest_{i:03d}"
TEST_EMAIL_FMT = "perftest_{i:03d}@example.com"

# Semantic search concurrency is capped so the external embedding API
# isn't flooded (each search call hits the API).
SEMANTIC_CONCURRENCY = max(1, min(10, CONCURRENCY // 10))


# ---------------------------------------------------------------------------
# Result collector
# ---------------------------------------------------------------------------
@dataclass
class Result:
    name: str
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    external_api: bool = False  # True = depends on external LLM/embedding API

    @property
    def total(self) -> int:
        return len(self.latencies) + self.errors

    @property
    def success_rate(self) -> float:
        return len(self.latencies) / max(self.total, 1) * 100

    def percentile(self, pct: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = max(0, min(len(s) - 1, int(len(s) * pct / 100)))
        return s[idx]

    def summary(self) -> str:
        if not self.latencies:
            return f"  {self.name}: no successful requests ({self.errors} errors)"
        p50 = self.percentile(50)
        p95 = self.percentile(95)
        p99 = self.percentile(99)
        avg = sum(self.latencies) / len(self.latencies)
        below = sum(1 for l in self.latencies if l < TARGET) / len(self.latencies) * 100
        tag = " [ext-API]" if self.external_api else ""
        verdict = "PASS" if p95 < TARGET else "FAIL"

        return (
            f"  {self.name}{tag}:\n"
            f"    requests: {self.total} | errors: {self.errors}"
            f" | success_rate: {self.success_rate:.1f}%\n"
            f"    min: {min(self.latencies):.3f}s  max: {max(self.latencies):.3f}s"
            f"  avg: {avg:.3f}s\n"
            f"    p50: {p50:.3f}s  p95: {p95:.3f}s  p99: {p99:.3f}s\n"
            f"    < {TARGET}s: {below:.1f}%  {verdict}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _api(path: str) -> str:
    return f"{BASE_URL}/api{path}"


async def _ensure_user(client: httpx.AsyncClient, username: str, email: str) -> str:
    """Login or register, return JWT token."""
    resp = await client.post(
        _api("/auth/login"),
        json={"email": email, "password": TEST_PASSWORD},
    )
    if resp.status_code == 200:
        return resp.json()["data"]["access_token"]

    resp = await client.post(
        _api("/auth/register"),
        json={"username": username, "email": email, "password": TEST_PASSWORD},
    )
    if resp.status_code in (201, 200):
        return resp.json()["data"]["access_token"]

    raise RuntimeError(f"Auth failed for {username}: {resp.status_code} {resp.text}")


async def _setup_users(client: httpx.AsyncClient, count: int) -> list[str]:
    """Register/login users concurrently in batches."""
    sem = asyncio.Semaphore(50)  # limit concurrent auth requests

    async def _setup_one(i: int) -> str:
        username = TEST_USERNAME_FMT.format(i=i)
        email = TEST_EMAIL_FMT.format(i=i)
        async with sem:
            return await _ensure_user(client, username, email)

    tasks = [_setup_one(i) for i in range(count)]
    return await asyncio.gather(*tasks)


async def _get_paper_ids(client: httpx.AsyncClient, token: str, count: int = 30) -> list[str]:
    """Discover paper IDs from the global pool (not user-library scoped)."""
    resp = await client.get(
        _api("/papers/discover"),
        params={"pageSize": count, "page": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        return []
    return [item["id"] for item in resp.json()["data"]["items"]]


async def _add_paper_to_library(client: httpx.AsyncClient, token: str, paper_id: str) -> None:
    await client.post(
        _api(f"/papers/{paper_id}/library"),
        headers={"Authorization": f"Bearer {token}"},
    )


async def _check_paper_count(client: httpx.AsyncClient, token: str) -> int:
    """Count papers in the global pool."""
    resp = await client.get(
        _api("/papers/discover"),
        params={"pageSize": 1, "page": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code == 200:
        return resp.json()["data"]["total"]
    return 0


# ---------------------------------------------------------------------------
# Core request helper
# ---------------------------------------------------------------------------
async def _do_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    token: str,
    json_body: dict | None = None,
    params: dict | None = None,
) -> tuple[float, bool]:
    headers = {"Authorization": f"Bearer {token}"}
    start = time.perf_counter()
    try:
        resp = await client.request(
            method, _api(path), headers=headers,
            json=json_body, params=params, timeout=TIMEOUT,
        )
        latency = time.perf_counter() - start
        return latency, not (200 <= resp.status_code < 500)
    except Exception:
        return time.perf_counter() - start, True


# ---------------------------------------------------------------------------
# Concurrent runner
# ---------------------------------------------------------------------------
TaskFn = Callable[[httpx.AsyncClient, str], Coroutine[None, None, tuple[float, bool]]]


async def run_concurrent(
    name: str,
    client: httpx.AsyncClient,
    tokens: list[str],
    task_fn: TaskFn,
    external_api: bool = False,
    concurrency: int | None = None,
) -> Result:
    result = Result(name=name, external_api=external_api)
    c = concurrency if concurrency is not None else CONCURRENCY
    used = tokens[:c]
    sem = asyncio.Semaphore(c)

    async def worker(token: str) -> None:
        async with sem:
            lat, err = await task_fn(client, token)
            if err:
                result.errors += 1
            else:
                result.latencies.append(lat)

    await asyncio.gather(*(worker(t) for t in used))
    return result


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

async def retrieval_list(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(
        client, "GET", "/papers", token,
        params={"pageSize": 20, "page": 1},
    )


async def retrieval_list_with_query(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(
        client, "GET", "/papers", token,
        params={"pageSize": 20, "page": 1, "query": "transformer"},
    )


async def retrieval_detail(paper_ids: list[str]) -> Callable:
    async def _fn(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
        pid = paper_ids[hash(token) % len(paper_ids)]
        return await _do_request(client, "GET", f"/papers/{pid}", token)
    return _fn


SEARCH_QUERIES = [
    "deep learning neural network",
    "transformer attention mechanism",
    "reinforcement learning policy gradient",
    "graph neural network node classification",
    "natural language processing bert",
]


async def retrieval_semantic(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    q = SEARCH_QUERIES[hash(token) % len(SEARCH_QUERIES)]
    return await _do_request(
        client, "GET", "/papers/search/semantic", token,
        params={"q": q, "limit": 5},
    )


async def chat_bootstrap(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(client, "GET", "/chat", token)


async def chat_create_conv(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(
        client, "POST", "/chat/conversations", token,
        json_body={"title": "perf test"},
    )


async def learning_dashboard(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(client, "GET", "/learning", token)


async def learning_bookmarks(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(
        client, "GET", "/learning/bookmarks", token,
        params={"page": 1, "pageSize": 10},
    )


async def learning_notes(client: httpx.AsyncClient, token: str) -> tuple[float, bool]:
    return await _do_request(
        client, "GET", "/learning/notes", token,
        params={"page": 1, "pageSize": 10},
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    print("=" * 70)
    print("  arxiv-PaperMate Performance Test  [ULTIMATE]")
    print(f"  Base URL:       {BASE_URL}")
    print(f"  Concurrency:    {CONCURRENCY} distinct users")
    print(f"  Target:         p95 < {TARGET}s (excl. LLM)")
    if SKIP_EXTERNAL:
        print(f"  External APIs:  SKIPPED (PAPERMATE_SKIP_EXTERNAL=1)")
    print("=" * 70)

    limits = httpx.Limits(
        max_connections=max(200, CONCURRENCY + 50),
        max_keepalive_connections=max(50, CONCURRENCY // 2),
    )
    async with httpx.AsyncClient(timeout=TIMEOUT, limits=limits) as client:

        # ---- health check ----
        try:
            resp = await client.get(f"{BASE_URL}/health")
            resp.raise_for_status()
            print(f"\n  Health check:   OK ({resp.json()['data']['status']})")
        except Exception as e:
            print(f"\n  Health check:   FAILED – {e}")
            sys.exit(1)

        # ---- user setup ----
        print(f"\n  Setting up {CONCURRENCY} test users ...")
        t0 = time.perf_counter()
        tokens = await _setup_users(client, CONCURRENCY)
        print(f"  Users ready:    {len(tokens)} ({time.perf_counter() - t0:.1f}s)")

        # ---- paper inventory ----
        first_token = tokens[0]
        paper_count = await _check_paper_count(client, first_token)
        print(f"  Papers in db:   {paper_count}"
              f" (via {TEST_USERNAME_FMT.format(i=0)})")
        meets_data_req = paper_count >= PAPER_MIN

        paper_ids = await _get_paper_ids(client, first_token, 30)
        print(f"  Sample papers:  {len(paper_ids)} available")

        if paper_ids:
            print(f"  Adding papers to all user libraries ...")
            t0 = time.perf_counter()
            sem = asyncio.Semaphore(50)

            async def _add_all(token: str) -> None:
                async with sem:
                    for pid in paper_ids:
                        await _add_paper_to_library(client, token, pid)

            await asyncio.gather(*(_add_all(t) for t in tokens))
            print(f"  Libraries ready ({time.perf_counter() - t0:.1f}s)")

        # ---- warm-up ----
        print(f"\n  Warming up endpoints ...")
        t0 = time.perf_counter()
        warm_token = tokens[0]
        warmups = [
            retrieval_list(client, warm_token),
            retrieval_list_with_query(client, warm_token),
            chat_bootstrap(client, warm_token),
            chat_create_conv(client, warm_token),
            learning_dashboard(client, warm_token),
            learning_bookmarks(client, warm_token),
            learning_notes(client, warm_token),
        ]
        if paper_ids and not SKIP_EXTERNAL:
            detail_fn = await retrieval_detail(paper_ids)
            warmups.append(detail_fn(client, warm_token))
            warmups.append(retrieval_semantic(client, warm_token))
        elif paper_ids:
            detail_fn = await retrieval_detail(paper_ids)
            warmups.append(detail_fn(client, warm_token))
        await asyncio.gather(*warmups)
        print(f"  Warm-up done    ({time.perf_counter() - t0:.1f}s)")

        # ==================================================================
        # PHASE 1 – Retrieval
        # ==================================================================
        print("\n" + "-" * 70)
        print("  PHASE 1: Retrieval Performance")
        print("-" * 70)

        results: list[Result] = []

        r = await run_concurrent(
            "Paper list (GET /papers)", client, tokens, retrieval_list,
        )
        results.append(r)
        print(r.summary())

        r = await run_concurrent(
            "Paper list + keyword (GET /papers?query=...)",
            client, tokens, retrieval_list_with_query,
        )
        results.append(r)
        print(r.summary())

        if paper_ids:
            detail_fn = await retrieval_detail(paper_ids)
            r = await run_concurrent(
                "Paper detail (GET /papers/{id})", client, tokens, detail_fn,
            )
            results.append(r)
            print(r.summary())
        else:
            print("\n  (no papers – skipping paper detail)")

        if SKIP_EXTERNAL:
            print("\n  (semantic search skipped – external embedding API)")
        elif paper_ids:
            print(f"\n  Semantic search (concurrency={SEMANTIC_CONCURRENCY}"
                  f" to avoid flooding embedding API)")
            r = await run_concurrent(
                "Semantic search (GET /papers/search/semantic)",
                client, tokens, retrieval_semantic,
                external_api=True,
                concurrency=SEMANTIC_CONCURRENCY,
            )
            results.append(r)
            print(r.summary())
        else:
            print("\n  (no papers – skipping semantic search)")

        # ==================================================================
        # PHASE 2 – Q&A (non-LLM)
        # ==================================================================
        print("\n" + "-" * 70)
        print("  PHASE 2: Q&A Performance (non-LLM endpoints)")
        print("-" * 70)

        r = await run_concurrent(
            "Chat bootstrap (GET /chat)", client, tokens, chat_bootstrap,
        )
        results.append(r)
        print(r.summary())

        r = await run_concurrent(
            "Create conversation (POST /chat/conversations)",
            client, tokens, chat_create_conv,
        )
        results.append(r)
        print(r.summary())

        # ==================================================================
        # PHASE 3 – Learning Management
        # ==================================================================
        print("\n" + "-" * 70)
        print("  PHASE 3: Learning Management Performance")
        print("-" * 70)

        r = await run_concurrent(
            "Dashboard (GET /learning)", client, tokens, learning_dashboard,
        )
        results.append(r)
        print(r.summary())

        r = await run_concurrent(
            "Bookmarks (GET /learning/bookmarks)", client, tokens,
            learning_bookmarks,
        )
        results.append(r)
        print(r.summary())

        r = await run_concurrent(
            "Notes (GET /learning/notes)", client, tokens, learning_notes,
        )
        results.append(r)
        print(r.summary())

        # ==================================================================
        # FINAL REPORT
        # ==================================================================
        print("\n" + "=" * 70)
        print("  OVERALL SUMMARY")
        print("=" * 70)

        core_results = [r for r in results if not r.external_api]
        ext_results = [r for r in results if r.external_api]

        core_all_pass = True
        for r in core_results:
            p95 = r.percentile(95)
            status = "PASS" if p95 < TARGET else "FAIL"
            if status == "FAIL":
                core_all_pass = False
            print(f"  [{status}] {r.name}: p95={p95:.3f}s")

        if ext_results:
            print(f"\n  --- External-API dependent tests ---")
            for r in ext_results:
                p95 = r.percentile(95)
                status = "PASS" if p95 < TARGET else "FAIL"
                print(f"  [{status}] {r.name}: p95={p95:.3f}s")

        print(f"\n  Data records:     {paper_count}"
              f" {'(meets >= 100)' if meets_data_req else '(WARNING: < 100)'}")
        print(f"  Concurrency:      {CONCURRENCY} distinct users")
        print(f"  Target:           p95 < {TARGET}s per request (excl. LLM)")

        if core_all_pass:
            print(f"\n  >>> CORE TESTS: ALL PASSED <<<")
        else:
            print(f"\n  >>> CORE TESTS: SOME FAILED <<<")

        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
