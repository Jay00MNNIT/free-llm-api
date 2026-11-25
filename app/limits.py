import time
from fastapi import HTTPException
from .config import RATE_LIMIT, RATE_WINDOW, DAILY_LIMIT, GLOBAL_DAILY_CAP
from .database import get_requests, today

hits: dict[str, list[float]] = {}


def check_rate(api_key: str):
    now = time.time()
    recent = [t for t in hits.get(api_key, []) if now - t < RATE_WINDOW]
    if len(recent) >= RATE_LIMIT:
        raise HTTPException(429, f"Rate limit: {RATE_LIMIT} requests per minute")
    recent.append(now)
    hits[api_key] = recent


def check_daily_limits(api_key: str):
    day = today()
    if get_requests("__global__", day) >= GLOBAL_DAILY_CAP:
        raise HTTPException(503, "Service is busy today. Please try again tomorrow.")
    if get_requests(api_key, day) >= DAILY_LIMIT:
        raise HTTPException(429, f"Daily limit reached ({DAILY_LIMIT} requests). Resets at 00:00 UTC.")