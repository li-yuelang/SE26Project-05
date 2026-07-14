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

    # LLM / OpenAI
    openai_api_key: str = ""
    openai_base_url: str = ""           # 留空用官方 API，也可填代理地址
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 4096

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
