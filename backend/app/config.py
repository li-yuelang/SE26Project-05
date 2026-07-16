from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "arxiv-PaperMate API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api"
    database_url: str = "postgresql+asyncpg://papermate:papermate@localhost:5432/papermate"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Paper analysis pipeline.  The provider settings intentionally use the
    # OpenAI-compatible API shape so they also work with local gateways.
    llm_api_key: str | None = None
    llm_base_url: str = "https://models.sjtu.edu.cn/api/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 90.0
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "qwen3.7-text-embedding"
    embedding_timeout_seconds: float = 60.0
    embedding_batch_size: int = 64
    embedding_dimension: int = 1536
    analysis_prompt_version: str = "paper-analysis-v1"
    analysis_version: str = "v1"
    analysis_pdf_timeout_seconds: float = 45.0
    analysis_pdf_max_bytes: int = 50 * 1024 * 1024
    analysis_chunk_target_tokens: int = 500
    analysis_chunk_max_tokens: int = 600
    analysis_chunk_overlap_tokens: int = 50
    analysis_max_retries: int = 3
    celery_task_always_eager: bool = False
    celery_task_eager_propagates: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
