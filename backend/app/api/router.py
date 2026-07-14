from fastapi import APIRouter

from app.api.v1 import auth, papers, tasks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(papers.router)
api_router.include_router(tasks.router)
