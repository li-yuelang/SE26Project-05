"""Persistent asyncio-loop bridge shared by Celery tasks."""

from __future__ import annotations

import asyncio
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

_LOOP_LOCK = threading.Lock()
_LOOP: asyncio.AbstractEventLoop | None = None
_LOOP_THREAD: threading.Thread | None = None


def _get_or_start_loop() -> asyncio.AbstractEventLoop:
    global _LOOP, _LOOP_THREAD
    if _LOOP is None or _LOOP.is_closed():
        with _LOOP_LOCK:
            if _LOOP is None or _LOOP.is_closed():
                if sys.platform == "win32":
                    _LOOP = asyncio.SelectorEventLoop()
                else:
                    _LOOP = asyncio.new_event_loop()
                asyncio.set_event_loop(_LOOP)
                _LOOP_THREAD = threading.Thread(
                    target=_LOOP.run_forever,
                    daemon=True,
                    name="celery-async-loop",
                )
                _LOOP_THREAD.start()
    return _LOOP


def run_async(coroutine: Any, *, timeout_seconds: int = 600) -> Any:
    """Run an async Celery workload on the shared persistent event loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = _get_or_start_loop()
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        return future.result(timeout=timeout_seconds)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


__all__ = ["run_async"]
