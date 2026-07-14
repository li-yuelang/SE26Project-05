from fastapi import APIRouter

from app.api.v1 import auth, compare, learning, papers, settings, subscriptions, tasks, trends

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(papers.router)
api_router.include_router(tasks.router)
api_router.include_router(learning.router)
api_router.include_router(compare.router)
api_router.include_router(trends.router)
api_router.include_router(subscriptions.router)
api_router.include_router(settings.router)
