import secrets
from pathlib import Path

import httpx
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .config import PROVIDERS, DAILY_LIMIT, FALLBACKS, MAX_SIGNUPS_PER_IP_PER_DAY
from .database import (today, key_exists, email_exists, signups_from_ip, create_key, get_requests, add_usage)
from .limits import check_rate, check_daily_limits

app = FastAPI(title="My Free LLM API")
bearer = HTTPBearer()

PROVIDER_TIMEOUT = 60   # seconds to wait for each provider
INDEX_FILE = Path(__file__).resolve().parent.parent / "static" / "index.html"


class SignupBody(BaseModel):
    email: str


class ChatBody(BaseModel):
    provider: str = "gemini"
    messages: list[dict]
    max_tokens: int = 500


def authenticate(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    api_key = creds.credentials
    if not key_exists(api_key):
        raise HTTPException(401, "Invalid API key")
    return api_key


def client_ip(request: Request) -> str:
    # Behind a hosting proxy, the real IP is in X-Forwarded-For (last entry = added by the proxy)
    forwarded = request.headers.get("X-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


async def call_provider(name: str, messages: list, max_tokens: int):
    """Returns the provider's answer (dict), or None if it failed."""
    p = PROVIDERS[name]
    payload = {
        "model": p["model"],
        "messages": messages,
        "max_tokens": min(max_tokens, 500),
    }
    try:
        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
            r = await client.post(
                p["url"], json=payload,
                headers={"Authorization": f"Bearer {p['key']}"},
            )
    except httpx.HTTPError as e:    # timeout, no internet, etc.
        print(f"[{name}] NETWORK/TIMEOUT ERROR:", repr(e))
        return None
    if r.status_code != 200:
        print(f"[{name}] PROVIDER ERROR:", r.status_code, r.text)
        return None
    return r.json()

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def home():
    return INDEX_FILE.read_text(encoding="utf-8")


@app.post("/signup")
def signup(body: SignupBody, request: Request):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email or len(email) > 254:
        raise HTTPException(400, "Please enter a valid email.")

    ip, day = client_ip(request), today()
    if signups_from_ip(ip, day) >= MAX_SIGNUPS_PER_IP_PER_DAY:
        raise HTTPException(429, "Too many keys created from your network today. Try again tomorrow.")
    if email_exists(email):
        raise HTTPException(409, "This email already has a key.")

    key = "sk-" + secrets.token_urlsafe(24)
    if not create_key(key, email, ip, day):
        raise HTTPException(409, "This email already has a key.")
    return {"api_key": key}


@app.post("/v1/chat")
async def chat(body: ChatBody, api_key: str = Depends(authenticate)):
    check_rate(api_key)
    check_daily_limits(api_key)

    first = body.provider
    if first not in PROVIDERS or not PROVIDERS[first]["key"]:
        raise HTTPException(400, "Unknown or unavailable provider")

    # requested provider first, then the fallbacks that have a key
    order = [first] + FALLBACKS.get(first, [])
    order = [n for n in order if PROVIDERS[n]["key"]]

    data, used_provider = None, None
    for name in order:
        data = await call_provider(name, body.messages, body.max_tokens)
        if data is not None:
            used_provider = name
            break

    if data is None:
        raise HTTPException(502, "All providers failed. Please try again later.")

    tokens = data.get("usage", {}).get("total_tokens", 0)
    day = today()
    add_usage(api_key, day, requests=1, tokens=tokens)      # counted once, even with fallback
    add_usage("__global__", day, requests=1, tokens=tokens)

    data["served_by"] = used_provider
    return data


@app.get("/v1/usage")
def usage(api_key: str = Depends(authenticate)):
    used = get_requests(api_key, today())
    return {"used_today": used, "daily_limit": DAILY_LIMIT, "remaining": DAILY_LIMIT - used}