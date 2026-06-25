import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from prometheus_client import make_asgi_app

from executor.configs.settings import settings
from executor.api.routes import router
from executor.persistence.database import engine
from executor.task_queue.redis_client import RedisClient
from executor.queue.redis_client import RedisClient

# Configure Logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Async Execution System for API Security Scanner"
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# Reverse-proxy support: when running behind Nginx / Render / Railway, honour
# X-Forwarded-* headers so request.url, scheme and client host are correct.
try:
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
except Exception as e:  # pragma: no cover - defensive, uvicorn always present
    logger.warning(f"Could not enable ProxyHeadersMiddleware: {e}")

# CORS. Defaults to "*" for development; set CORS_ORIGINS to an explicit,
# comma-separated list of frontend domains in production. When the wildcard is
# used, credentials must be disabled (browsers reject "*" + credentials).
_cors_origins = settings.cors_origins
_allow_all = "*" in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_credentials=not _allow_all,  # credentials not allowed with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Access-Control-Allow-Origin", "Access-Control-Allow-Headers"],
)

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include Routers
app.include_router(router)
from executor.api.copilot_routes import router as copilot_router
app.include_router(copilot_router)
from executor.api.sse_routes import router as sse_router
app.include_router(sse_router)
from executor.api.auth_routes import router as auth_router
app.include_router(auth_router)


# ---------------------------------------------------------------------------
# Hardening middleware: access logging, security headers, rate limiting,
# and a server-side request timeout. These run for every request and make the
# API safer and easier to debug in production.
# ---------------------------------------------------------------------------

# Paths that must NOT be rate-limited or timed out (probes, metrics, docs,
# and long-lived Server-Sent-Events streams).
_INFRA_PATHS = ("/health", "/metrics", "/docs", "/redoc", "/openapi.json")


def _is_infra_path(path: str) -> bool:
    return path.startswith(_INFRA_PATHS) or path == "/"


def _is_stream_path(path: str) -> bool:
    return "/stream/" in path


# In-memory sliding-window rate limiter keyed by client IP. Suitable for a
# single instance / dev; for multi-instance production back it with Redis.
_rate_buckets: dict = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS" or _is_infra_path(request.url.path):
        return await call_next(request)

    ip = _client_ip(request)
    now = time.monotonic()
    window = 60.0
    bucket = _rate_buckets.setdefault(ip, deque())
    while bucket and now - bucket[0] > window:
        bucket.popleft()

    if len(bucket) >= settings.RATE_LIMIT_PER_MINUTE:
        retry_after = int(window - (now - bucket[0])) + 1
        logger.warning(f"Rate limit exceeded for {ip} on {request.url.path}")
        return JSONResponse(
            status_code=429,
            content={"success": False, "message": "Too many requests. Please slow down and retry.",
                     "error": {"type": "rate_limited", "retry_after_seconds": retry_after}},
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
    return await call_next(request)


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    # Never time out streaming endpoints (SSE) or infra/metrics paths.
    if settings.REQUEST_TIMEOUT_SECONDS <= 0 or _is_stream_path(request.url.path) or request.url.path.startswith("/metrics"):
        return await call_next(request)
    try:
        return await asyncio.wait_for(call_next(request), timeout=settings.REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.error(f"Request timed out after {settings.REQUEST_TIMEOUT_SECONDS}s: {request.method} {request.url.path}")
        return JSONResponse(
            status_code=504,
            content={"success": False, "message": "The server took too long to process the request.",
                     "error": {"type": "timeout"}},
        )


@app.middleware("http")
async def access_log_and_headers_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000

    if settings.REQUEST_LOGGING_ENABLED:
        logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.1f}ms) ip={_client_ip(request)}")
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"

    if settings.SECURITY_HEADERS_ENABLED:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        # Don't apply a restrictive CSP to the interactive API docs (Swagger UI
        # loads assets from a CDN); apply it to API/JSON responses only.
        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if settings.ENABLE_HSTS:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")

    return response


# ---------------------------------------------------------------------------
# Exception handlers — standardized JSON so the frontend never receives an
# opaque body for a 500. Known HTTP/validation errors keep their status codes;
# anything unexpected is wrapped in {"success": false, "message": ...}.
# ---------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.detail, "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # exc.errors() can contain non-JSON-serializable objects (e.g. the original
    # ValueError in "ctx"); keep only the safe, serializable fields.
    clean = [
        {"type": e.get("type"), "loc": [str(p) for p in e.get("loc", [])], "msg": e.get("msg")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "Validation error", "detail": clean},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error processing {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": str(exc) or "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing API and checking Redis status...")
    # Trigger connection check
    redis_alive = RedisClient.check_redis_alive()

    # Ensure the database schema exists. This is idempotent (only missing tables
    # are created) and makes the backend self-sufficient regardless of how it is
    # launched, so data endpoints never 500 due to a missing schema (the common
    # cause of "internal error" / "relation does not exist" on /api/v1/scans in
    # fresh environments).
    try:
        from executor.persistence.database import engine, Base
        import executor.persistence.models  # noqa: F401  (register ORM models)
        async with engine.begin() as conn:
            # Fail-fast validation: confirm the database is actually reachable
            # before serving traffic, instead of crashing later on the first
            # frontend request.
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database connection verified and schema created/validated.")

        # Optional: bootstrap an admin account from env on first run.
        if settings.BOOTSTRAP_ADMIN_EMAIL and settings.BOOTSTRAP_ADMIN_PASSWORD:
            try:
                from sqlalchemy import select
                from executor.persistence.database import AsyncSessionLocal
                from executor.persistence.models import User, UserRole
                from executor.api.auth import hash_password
                async with AsyncSessionLocal() as session:
                    existing = await session.execute(
                        select(User).where(User.email == settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower())
                    )
                    if existing.scalar_one_or_none() is None:
                        session.add(User(
                            email=settings.BOOTSTRAP_ADMIN_EMAIL.strip().lower(),
                            full_name="Administrator",
                            hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                            role=UserRole.ADMIN.value,
                            is_active=True,
                        ))
                        await session.commit()
                        logger.info(f"Bootstrapped admin user: {settings.BOOTSTRAP_ADMIN_EMAIL}")
            except Exception as be:
                logger.error(f"Failed to bootstrap admin user: {be}")
    except Exception as e:
        # Surface the failure loudly. In production a deployment should treat an
        # unreachable database as fatal; we log clearly so it is obvious why
        # data endpoints would fail.
        logger.error(f"DATABASE STARTUP CHECK FAILED — backend cannot reach the database: {e}")

    # Trigger connection check. Guard against check_redis_alive raising so a
    # flaky Redis probe can never block startup; treat any error as "no Redis".
    try:
        redis_alive = RedisClient.check_redis_alive()
    except Exception as e:
        logger.warning(f"Redis availability check raised, assuming unavailable: {e}")
        redis_alive = False

    if not redis_alive:
        logger.info("Starting WorkerPoolManager as a background task inside FastAPI process (in-memory dev mode)...")
        from executor.worker_manager.manager import WorkerPoolManager
        import asyncio
        manager = WorkerPoolManager(
            queue_base_name="tasks:default",
            min_workers=2,  # Keep it light for in-process local dev
            max_workers=5,
            idle_timeout=30
        )
        app.state.worker_manager = manager
        # Start worker manager in background task
        app.state.worker_task = asyncio.create_task(manager.start())
    else:
        logger.info("Production Redis detected. Worker execution must be started externally via run_worker.py")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down API...")
    if hasattr(app.state, "worker_manager") and app.state.worker_manager:
        logger.info("Stopping in-process WorkerPoolManager...")
        await app.state.worker_manager.stop()
    await RedisClient.close()


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    try:
        redis_alive = RedisClient.check_redis_alive()
    except Exception:
        redis_alive = False
    return {
        "status": "ok",
    }
    try:
        redis_alive = RedisClient.check_redis_alive()
    except Exception:
        redis_alive = False
    return {
        "status": "ok",
        "success": True,
        "version": settings.APP_VERSION,
        "mode": "standalone_in_memory" if not redis_alive else "distributed",
        "redis_connected": redis_alive
    }

@app.get("/health/database")
async def health_database():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

@app.get("/health/redis")
async def health_redis():
    redis_alive = RedisClient.check_redis_alive()
    return {
        "status": "ok" if redis_alive else "warning",
        "redis_connected": redis_alive,
        "mode": "redis" if redis_alive else "in_memory"
    }

@app.get("/health/workers")
async def health_workers():
    try:
        redis = RedisClient.get_client()
        worker_ids = []
        async for key in redis.scan_iter(match="worker:heartbeat:*"):
            if isinstance(key, bytes):
                key = key.decode("utf-8", errors="replace")
            worker_ids.append(str(key).replace("worker:heartbeat:", ""))
        return {"status": "ok", "active_workers": len(worker_ids), "workers": worker_ids}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Worker health unavailable: {e}")

@app.get("/health/external")
async def health_external(url: str = "https://petstore3.swagger.io/api/v3/openapi.json"):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            return {
                "status": "ok" if response.status_code < 400 else "failed",
                "url": url,
                "status_code": response.status_code,
                "reason": response.reason_phrase
            }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"External connectivity failed: {e}")

@app.get("/health/websocket")
async def health_websocket():
    return {
        "status": "ok",
        "sse_endpoint": "/api/v1/stream/scan/{scan_id}",
        "note": "SSE streaming is available via /api/v1/stream/scan/{scan_id}."
    }

