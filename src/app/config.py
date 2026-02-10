from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "StatusPing"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./statusping.db"

    # JWT
    secret_key: str = "change-me-in-production-use-a-real-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Email (SMTP)
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "alerts@statusping.app"
    smtp_use_tls: bool = True

    # Monitoring defaults
    default_check_interval: int = 300  # 5 minutes in seconds
    default_timeout: int = 30  # HTTP request timeout in seconds
    consecutive_failures_threshold: int = 3  # failures before marking down

    # Base URL
    base_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
