from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Async Execution System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database — set DATABASE_URL directly to override the PostgreSQL default.
    # For local dev with SQLite:  DATABASE_URL=sqlite+aiosqlite:///./test.db
    # For production:             DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
    #
    # NOTE: When deploying the backend and database on different hosts (Render,
    # Railway, EC2, managed Postgres, etc.) you MUST provide DATABASE_URL as an
    # environment variable pointing at the real DB host. The "localhost" pieces
    # below are only a convenience default for running everything on one machine
    # — inside a deployed container "localhost" refers to the container itself
    # and cannot reach an external database.
    DATABASE_URL: Optional[str] = None

    # PostgreSQL credentials (used only when DATABASE_URL is not set)
    POSTGRES_USER: str = "executor_user"
    POSTGRES_PASSWORD: str = "executor_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "executor_db"

    def model_post_init(self, __context) -> None:
        """Build DATABASE_URL from components if not explicitly set."""
        if self.DATABASE_URL is None:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

    # Redis
    # As with the database, set REDIS_URL (or REDIS_HOST) to the real Redis host
    # when deploying. "localhost" only works when Redis runs in the same place.
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.REDIS_URL is None:
            self.REDIS_URL = f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # CORS
    # Comma-separated list of allowed origins. Use "*" (default) for development.
    # For production set an explicit list, e.g.:
    #   CORS_ORIGINS=https://integrated-work.vercel.app,https://www.example.com
    CORS_ORIGINS: str = "*"
    # Regex applied in addition to CORS_ORIGINS, so preview deployments work
    # without enumerating every ephemeral subdomain.
    CORS_ORIGIN_REGEX: str = r"https://.*\.(netlify\.app|vercel\.app)|http://localhost:\d+"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Worker Configuration
    WORKER_CONCURRENCY: int = 100
    WORKER_HEARTBEAT_INTERVAL: int = 5
    WORKER_TIMEOUT: int = 30

    # Worker execution mode.
    # When Redis is NOT available the API always runs an in-process worker pool
    # (in-memory dev mode). When Redis IS available the API does NOT start
    # workers by default — you must run them separately via `python run_worker.py`,
    # otherwise enqueued tasks stay QUEUED forever. Set RUN_WORKER_IN_API=true to
    # force the API to also run an in-process worker pool even with Redis
    # (convenient for single-instance deployments where you don't want a
    # separate worker process). For horizontally-scaled deployments keep this
    # False and run dedicated worker processes.
    RUN_WORKER_IN_API: bool = False

    # Rate Limiting & Retry
    DEFAULT_MAX_RETRIES: int = 3
    DEFAULT_RETRY_BACKOFF: float = 2.0

    # ---- Authentication (JWT) ----
    # JWT_SECRET MUST be set to a strong random value in production. The default
    # is for local dev only; tokens signed with it are not secure.
    JWT_SECRET: str = "dev-insecure-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # When True, business endpoints require a valid access token. Kept False by
    # default so existing flows keep working; flip to True to lock the API down.
    AUTH_REQUIRED: bool = False

    # Optional bootstrap admin created on startup if no users exist.
    BOOTSTRAP_ADMIN_EMAIL: Optional[str] = None
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None

    # ---- HTTP hardening (middleware) ----
    # Per-client-IP request rate limit. Returns 429 when exceeded.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 120

    # Server-side request timeout. Long requests are aborted with 504 so the
    # frontend gets a clear error instead of a hanging connection. Streaming
    # (SSE) endpoints are exempt.
    REQUEST_TIMEOUT_SECONDS: int = 30

    # Structured access logging (method, path, status, latency).
    REQUEST_LOGGING_ENABLED: bool = True

    # Security response headers.
    SECURITY_HEADERS_ENABLED: bool = True
    # Strict-Transport-Security — only enable when always served over HTTPS.
    ENABLE_HSTS: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")


settings = Settings()
