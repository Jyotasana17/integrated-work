import time
import asyncio
import logging
from urllib.parse import urlparse
from executor.task_queue.redis_client import RedisClient
from executor.rate_limiter.config import RateLimiterConfigLoader

logger = logging.getLogger(__name__)

# Redis Lua Script for Atomic Token Bucket
# ARGV[1] = capacity, ARGV[2] = refill_rate, ARGV[3] = now, ARGV[4] = requested
TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call("HMGET", key, "tokens", "last_refill", "adaptive_multiplier")
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])
local multiplier = tonumber(bucket[3]) or 1.0

if not tokens then
    tokens = capacity
    last_refill = now
end

-- Apply adaptive multiplier to refill rate (if 429 was detected)
local effective_rate = refill_rate * multiplier
local time_passed = math.max(0, now - last_refill)
local new_tokens = time_passed * effective_rate

tokens = math.min(capacity, tokens + new_tokens)

if tokens >= requested then
    tokens = tokens - requested
    redis.call("HMSET", key, "tokens", tokens, "last_refill", now, "adaptive_multiplier", multiplier)
    redis.call("EXPIRE", key, math.ceil(capacity / effective_rate) * 2)
    return 1
else
    redis.call("HMSET", key, "tokens", tokens, "last_refill", now, "adaptive_multiplier", multiplier)
    return 0
end
"""


class _LocalTokenBucket:
    """In-process token bucket fallback used when the Redis backend does not
    support server-side Lua scripting (e.g. FakeRedis in local/dev mode).

    This keeps rate limiting functional in single-process deployments. In a
    real distributed deployment a scripting-capable Redis is used instead and
    this fallback is never exercised.
    """

    def __init__(self):
        # key -> {tokens, last_refill, multiplier}
        self._buckets = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, capacity: float, refill_rate: float, requested: float) -> bool:
        async with self._lock:
            now = time.time()
            b = self._buckets.get(key)
            if b is None:
                b = {"tokens": capacity, "last_refill": now, "multiplier": 1.0}
                self._buckets[key] = b

            effective_rate = refill_rate * b["multiplier"]
            time_passed = max(0.0, now - b["last_refill"])
            b["tokens"] = min(capacity, b["tokens"] + time_passed * effective_rate)
            b["last_refill"] = now

            if b["tokens"] >= requested:
                b["tokens"] -= requested
                return True
            return False

    async def report_429(self, key: str):
        async with self._lock:
            b = self._buckets.setdefault(key, {"tokens": 0.0, "last_refill": time.time(), "multiplier": 1.0})
            b["multiplier"] = max(0.1, b["multiplier"] * 0.5)
            return b["multiplier"]


# Shared across all RateLimiter instances in this process so buckets are
# consistent regardless of how many worker engines are spawned.
_LOCAL_BUCKETS = _LocalTokenBucket()


class RateLimiter:
    def __init__(self):
        self.redis = RedisClient.get_client()
        self.config_loader = RateLimiterConfigLoader()
        self.script_sha = None
        # None = unknown, True = redis Lua, False = local fallback
        self._scripting_supported = None
        self._local = _LOCAL_BUCKETS

    async def _ensure_backend(self):
        """Detect (once) whether the Redis backend supports Lua scripting and
        cache the result. Falls back to an in-process token bucket otherwise."""
        if self._scripting_supported is not None:
            return
        try:
            self.script_sha = await self.redis.script_load(TOKEN_BUCKET_SCRIPT)
            self._scripting_supported = True
            logger.info("RateLimiter using atomic Redis Lua token bucket.")
        except Exception as e:
            self._scripting_supported = False
            logger.warning(
                "Redis server-side scripting unavailable (%s). "
                "RateLimiter falling back to in-process token bucket.", e
            )

    async def acquire(self, url: str, scan_id: str, tokens: int = 1, timeout: int = 30) -> bool:
        """Wait until tokens are available for global, domain, and scan buckets."""
        await self._ensure_backend()

        domain = urlparse(url).netloc
        config = self.config_loader.config

        domain_rate = config.domains.get(domain, None)
        global_rate = config.global_limit

        # capacity equals the rate (1 second burst) for each bucket
        keys_and_args = []
        keys_and_args.append(("rl:global", global_rate, global_rate, tokens))
        if domain_rate:
            keys_and_args.append((f"rl:domain:{domain}", domain_rate, domain_rate, tokens))
        scan_rate = 100.0
        keys_and_args.append((f"rl:scan:{scan_id}", scan_rate, scan_rate, tokens))

        start_time = time.time()
        while time.time() - start_time < timeout:
            all_acquired = True
            for key, cap, rate, req in keys_and_args:
                if not await self._acquire_one(key, cap, rate, req):
                    all_acquired = False
                    break
            if all_acquired:
                return True
            await asyncio.sleep(0.1)

        logger.warning(f"RateLimiter timed out after {timeout}s for URL: {url}")
        return False

    async def _acquire_one(self, key: str, cap: float, rate: float, req: float) -> bool:
        if self._scripting_supported:
            try:
                res = await self.redis.evalsha(self.script_sha, 1, key, cap, rate, time.time(), req)
                return res == 1 or res == "1"
            except Exception as e:
                # If scripting breaks at runtime, degrade gracefully instead of
                # leaving tasks stuck. Switch permanently to the local bucket.
                logger.warning("Redis EVALSHA failed (%s); switching to in-process rate limiter.", e)
                self._scripting_supported = False
        return await self._local.acquire(key, cap, rate, req)

    async def report_429(self, url: str):
        """Adaptive Rate Limiting: reduce the domain's multiplier on 429 response."""
        domain = urlparse(url).netloc
        key = f"rl:domain:{domain}"

        if self._scripting_supported:
            try:
                bucket = await self.redis.hmget(key, "adaptive_multiplier")
                multiplier = float(bucket[0]) if bucket and bucket[0] else 1.0
                new_multiplier = max(0.1, multiplier * 0.5)
                await self.redis.hset(key, "adaptive_multiplier", new_multiplier)
                logger.warning(f"Detected 429 for {domain}. Halved multiplier to {new_multiplier}")
                return
            except Exception as e:
                logger.warning("Redis report_429 failed (%s); using in-process limiter.", e)
                self._scripting_supported = False

        new_multiplier = await self._local.report_429(key)
        logger.warning(f"Detected 429 for {domain}. Halved multiplier to {new_multiplier}")
