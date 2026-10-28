"""Celery tasks for recommendation computation."""
from __future__ import annotations

from app.tasks.celery_app import celery_app


@celery_app.task(name="recommendation.compute_global")
def compute_global_recommendations() -> None:
    """Periodically compute content-similarity matrix for all papers.

    In a production scenario this would:
    1. Load all paper concept vectors
    2. Compute pairwise cosine similarity
    3. Store the top-N similar papers per paper in a cache/DB table
    4. Used by the content-based recommendation endpoint for fast lookup

    Currently the recommendation endpoint does on-the-fly computation
    which is fine for the scale of this project (< 10000 papers).
    """
    pass


@celery_app.task(name="recommendation.refresh_user_embeddings")
def refresh_user_embeddings() -> None:
    """Periodically refresh user interest embeddings based on saved research interests.

    Combines concept vectors of papers the user has bookmarked into
    a weighted user profile vector for faster content-based recommendations.
    """
    pass
