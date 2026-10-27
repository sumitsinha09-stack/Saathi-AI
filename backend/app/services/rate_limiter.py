import logging
import time
from typing import Callable, Dict, List, Optional, Tuple
from fastapi import HTTPException, Request, status

from backend.app.config import settings

logger = logging.getLogger(__name__)


def parse_rate_limit(rate_str: str) -> Tuple[int, float]:
    """
    Parses rate limit string such as '15/minute', '10/second', '120/hour', or '10'.
    Returns (max_requests, window_seconds).
    """
    if not rate_str or not rate_str.strip():
        return (60, 60.0)

    clean = rate_str.strip().lower()
    if "/" not in clean:
        try:
            return (int(clean), 60.0)
        except ValueError:
            return (60, 60.0)

    parts = clean.split("/", 1)
    try:
        count = int(parts[0])
    except ValueError:
        count = 60

    unit = parts[1].strip()
    if unit in ("s", "sec", "second"):
        window = 1.0
    elif unit in ("m", "min", "minute"):
        window = 60.0
    elif unit in ("h", "hr", "hour"):
        window = 3600.0
    elif unit in ("d", "day"):
        window = 86400.0
    else:
        window = 60.0

    return (count, window)


class RateLimiter:
    """
    In-memory sliding window rate limiter.
    Safely resolves client IP and enforces configurable limits.
    """

    _buckets: Dict[str, List[float]] = {}
    _last_prune_time: float = 0.0

    @classmethod
    def get_client_ip(cls, request: Request) -> str:
        """
        Resolves client IP securely.
        Only trusts X-Forwarded-For if request.client.host is in TRUSTED_PROXIES.
        """
        direct_ip = request.client.host if request.client else "127.0.0.1"

        trusted_list = [
            ip.strip() for ip in settings.TRUSTED_PROXIES.split(",") if ip.strip()
        ]
        if trusted_list and direct_ip in trusted_list:
            xff = request.headers.get("x-forwarded-for")
            if xff:
                # First IP in X-Forwarded-For represents the original client
                first_ip = xff.split(",")[0].strip()
                if first_ip:
                    return first_ip
            x_real_ip = request.headers.get("x-real-ip")
            if x_real_ip and x_real_ip.strip():
                return x_real_ip.strip()

        return direct_ip

    @classmethod
    def check_limit(
        cls,
        key: str,
        max_requests: int,
        window_seconds: float,
    ) -> None:
        """
        Enforces rate limit on a specific composite key (e.g. 'voice_upload:127.0.0.1').
        Raises HTTP 429 if the limit is exceeded.
        """
        now = time.time()
        cls._maybe_prune(now)

        timestamps = cls._buckets.setdefault(key, [])
        cutoff = now - window_seconds
        # Filter timestamps within current sliding window
        valid_timestamps = [ts for ts in timestamps if ts > cutoff]
        cls._buckets[key] = valid_timestamps

        if len(valid_timestamps) >= max_requests:
            oldest = valid_timestamps[0]
            retry_after = max(1, int(oldest + window_seconds - now))
            logger.warning(
                f"Rate limit exceeded for key='{key}': {len(valid_timestamps)}/{max_requests} in {window_seconds}s. Retry-After: {retry_after}s"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)},
            )

        valid_timestamps.append(now)

    @classmethod
    def _maybe_prune(cls, now: float) -> None:
        """Periodically cleans up dead bucket entries every 60 seconds."""
        if now - cls._last_prune_time < 60.0:
            return
        cls._last_prune_time = now
        dead_keys = []
        for k, timestamps in cls._buckets.items():
            if not timestamps or now - timestamps[-1] > 3600.0:
                dead_keys.append(k)
        for k in dead_keys:
            cls._buckets.pop(k, None)

    @classmethod
    def reset(cls) -> None:
        """Resets all rate limit tracking (useful for test suites)."""
        cls._buckets.clear()
        cls._last_prune_time = 0.0


def rate_limit(endpoint_name: str, config_attr: str) -> Callable:
    """
    FastAPI dependency factory enforcing rate limits configured via Settings.
    """
    async def dependency(request: Request) -> None:
        raw_limit = getattr(settings, config_attr, "60/minute")
        max_reqs, window_sec = parse_rate_limit(raw_limit)
        client_ip = RateLimiter.get_client_ip(request)
        composite_key = f"{endpoint_name}:{client_ip}"
        RateLimiter.check_limit(composite_key, max_reqs, window_sec)

    return dependency
