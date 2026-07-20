"""Tests for analysis state machine helpers."""

from datetime import datetime, timezone
from uuid import uuid4

from app.services.analysis_state import (
    get_analysis_metadata,
    new_analysis_version,
    utc_now,
)


def test_utc_now_returns_iso_format() -> None:
    result = utc_now()
    # Should be valid ISO 8601
    parsed = datetime.fromisoformat(result)
    assert parsed.tzinfo is not None


def test_new_analysis_version_contains_config_version_and_uuid() -> None:
    version = new_analysis_version()
    assert "-" in version
    prefix, suffix = version.rsplit("-", 1)
    assert len(suffix) == 12  # hex part of uuid4


def test_get_analysis_metadata_returns_empty_dict_when_none() -> None:
    class FakePaper:
        metadata_extra = None
    result = get_analysis_metadata(FakePaper())
    assert result == {}


def test_get_analysis_metadata_returns_empty_dict_when_no_analysis_key() -> None:
    class FakePaper:
        metadata_extra = {"other": "data"}
    result = get_analysis_metadata(FakePaper())
    assert result == {}


def test_get_analysis_metadata_returns_analysis_dict() -> None:
    class FakePaper:
        metadata_extra = {"analysis": {"status": "completed", "stage": "done"}}
    result = get_analysis_metadata(FakePaper())
    assert result == {"status": "completed", "stage": "done"}


def test_get_analysis_metadata_coerces_non_dict_analysis_to_dict() -> None:
    class FakePaper:
        metadata_extra = {"analysis": "not-a-dict"}
    result = get_analysis_metadata(FakePaper())
    assert result == {}
