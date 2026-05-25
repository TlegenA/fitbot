from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Telegram
    bot_token: str

    # Database
    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Claude API
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-5"
    claude_max_tokens: int = 1024

    # App
    environment: str = "production"
    log_level: str = "INFO"
    webhook_url: str = ""
    webhook_secret: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
