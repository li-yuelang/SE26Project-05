"""Tests for TrendService — phase detection and pure logic."""

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.trends import TrendService


def test_detect_phases_returns_emerging_when_all_zero_counts() -> None:
    service = TrendService()
    data = [{"month": f"2026-{str(m).zfill(2)}", "count": 0} for m in range(1, 13)]
    phases = service._detect_phases(data)
    assert len(phases) == 1
    assert phases[0]["phase"] == "emerging"
    assert "暂无显著论文" in phases[0]["description"]


def test_detect_phases_growing_detected() -> None:
    service = TrendService()
    # Counts clearly rising
    data = [
        {"month": "2026-01", "count": 1},
        {"month": "2026-02", "count": 2},
        {"month": "2026-03", "count": 3},
        {"month": "2026-04", "count": 10},
        {"month": "2026-05", "count": 15},
        {"month": "2026-06", "count": 20},
        {"month": "2026-07", "count": 25},
        {"month": "2026-08", "count": 30},
        {"month": "2026-09", "count": 35},
        {"month": "2026-10", "count": 40},
        {"month": "2026-11", "count": 45},
        {"month": "2026-12", "count": 50},
    ]
    phases = service._detect_phases(data)
    # At least one phase should be "growing" (second half > first half within window)
    assert any(p["phase"] == "growing" for p in phases)


def test_detect_phases_declining_detected() -> None:
    service = TrendService()
    data = [
        {"month": "2026-01", "count": 50},
        {"month": "2026-02", "count": 45},
        {"month": "2026-03", "count": 40},
        {"month": "2026-04", "count": 30},
        {"month": "2026-05", "count": 20},
        {"month": "2026-06", "count": 15},
        {"month": "2026-07", "count": 10},
        {"month": "2026-08", "count": 5},
        {"month": "2026-09", "count": 3},
        {"month": "2026-10", "count": 2},
        {"month": "2026-11", "count": 2},
        {"month": "2026-12", "count": 1},
    ]
    phases = service._detect_phases(data)
    assert any(p["phase"] == "declining" for p in phases)


def test_detect_phases_too_short_returns_empty() -> None:
    service = TrendService()
    data = [{"month": "2026-01", "count": 5} for _ in range(4)]
    assert service._detect_phases(data) == []


def test_detect_phases_mature_detected() -> None:
    service = TrendService()
    # Stably high counts
    data = [
        {"month": "2026-01", "count": 100},
        {"month": "2026-02", "count": 105},
        {"month": "2026-03", "count": 98},
        {"month": "2026-04", "count": 102},
        {"month": "2026-05", "count": 100},
        {"month": "2026-06", "count": 103},
        {"month": "2026-07", "count": 101},
        {"month": "2026-08", "count": 99},
        {"month": "2026-09", "count": 100},
        {"month": "2026-10", "count": 102},
        {"month": "2026-11", "count": 98},
        {"month": "2026-12", "count": 101},
    ]
    phases = service._detect_phases(data)
    assert any(p["phase"] == "mature" for p in phases)


def test_monthly_counts_uses_real_publication_dates() -> None:
    service = TrendService()
    now = datetime.now(timezone.utc)
    papers = [SimpleNamespace(published_at=now), SimpleNamespace(published_at=now)]

    points = service._monthly_counts(papers, months=6)

    assert len(points) == 6
    assert sum(point["count"] for point in points) == 2
    assert points[-1]["month"] == now.strftime("%Y-%m")


def test_milestones_keep_first_and_latest_papers() -> None:
    service = TrendService()
    papers = [
        {
            "paper_id": str(index),
            "published_at": f"20{index:02d}-01-01T00:00:00+00:00",
            "citation_count": 0,
        }
        for index in range(10, 20)
    ]

    milestones = service._milestones(papers)

    assert len(milestones) == 8
    assert milestones[0]["paper_id"] == "10"
    assert milestones[-1]["paper_id"] == "19"
    assert milestones[0]["significance"] == "foundation"
    assert milestones[-1]["significance"] == "frontier"
