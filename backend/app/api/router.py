from fastapi import APIRouter

from app.api.v1 import (
    auth,
    chat,
    compare,
    learning,
    papers,
    settings,
    subscriptions,
    tasks,
    trends,
    wiki,
)

api_router = APIRouter()
for router in (
    auth.router,
    papers.router,
    tasks.router,
    learning.router,
    compare.router,
    trends.router,
    subscriptions.router,
    settings.router,
    wiki.router,
    chat.router,
):
    api_router.include_router(router)
