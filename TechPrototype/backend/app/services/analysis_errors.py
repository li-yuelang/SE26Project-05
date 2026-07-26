"""Stable error-code and retry classification for the analysis worker."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError


@dataclass(frozen=True, slots=True)
class AnalysisErrorInfo:
    code: str
    retryable: bool


def classify_analysis_error(error: Exception) -> AnalysisErrorInfo:
    code = getattr(error, "error_code", None)
    retryable = getattr(error, "retryable", None)
    if isinstance(code, str):
        return AnalysisErrorInfo(code=code, retryable=bool(retryable))

    if isinstance(error, IntegrityError):
        return AnalysisErrorInfo("PERSISTENCE_ERROR", False)
    if isinstance(error, (DBAPIError, SQLAlchemyError)):
        return AnalysisErrorInfo("PERSISTENCE_ERROR", True)
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code if error.response is not None else 0
        if status == 429:
            return AnalysisErrorInfo("LLM_RATE_LIMIT", True)
        return AnalysisErrorInfo("LLM_SERVER_ERROR" if status >= 500 else "LLM_ERROR", status >= 500)
    if isinstance(error, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError, OSError)):
        return AnalysisErrorInfo("DOWNLOAD_ERROR", True)
    return AnalysisErrorInfo("PARSER_ERROR", False)


__all__ = ["AnalysisErrorInfo", "classify_analysis_error"]
