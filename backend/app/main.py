import json
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.config import settings
from app.core.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    validation_exception_handler,
)
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.logging import configure_logging
from app.core.metrics import RedMetricsMiddleware
from app.schemas.common import success


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.debug)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RedMetricsMiddleware, api_prefix=settings.api_v1_prefix)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return success({"status": "ok", "environment": settings.environment})


@app.get("/version", tags=["system"])
async def version_info() -> dict:
    content = files("app").joinpath("build_info.json").read_text(encoding="utf-8")
    return success(json.loads(content))


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
