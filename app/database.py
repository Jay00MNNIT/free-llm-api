import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import pg8000.dbapi
else:
    _sqlite = sqlite3.connect("keys.db", check_same_thread=False)

print("DATABASE:", "Postgres (Neon)" if USE_POSTGRES else "SQLite (keys.db)")


def _pg_connect():
    u = urlparse(DATABASE_URL)
    conn = pg8000.dbapi.connect(
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        host=u.hostname,
        port=u.port or 5432,
        database=(u.path or "/").lstrip("/"),
        ssl_context=True,
        timeout=15,
    )
    conn.autocommit = True
    return conn

 
def _run(sql: str, params: tuple = (), fetch_one: bool = False):
    """Run one SQL statement on whichever database is active."""
    if USE_POSTGRES:
        conn = _pg_connect()    # new connection each time: Neon closes idle ones
        try:
            cur = conn.cursor()
            cur.execute(sql.replace("?", "%s"), params)
            return cur.fetchone() if fetch_one else None
        finally:
            conn.close()
    cur = _sqlite.execute(sql, params)
    row = cur.fetchone() if fetch_one else None
    _sqlite.commit()
    return row
       

_run("""
CREATE TABLE IF NOT EXISTS keys (
    key TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    ip TEXT,
    day TEXT
)""")
_run("""
CREATE TABLE IF NOT EXISTS usage (
    key TEXT,
    day TEXT,
    requests INTEGER DEFAULT 0,
    tokens INTEGER DEFAULT 0,
    PRIMARY KEY (key, day)
    )""")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def key_exists(api_key: str) -> bool:
    return _run("SELECT 1 FROM keys WHERE key=?", (api_key,), fetch_one=True) is not None


def email_exists(email: str) -> bool:
    return _run("SELECT 1 FROM keys WHERE email=?", (email,), fetch_one=True) is not None


def signups_from_ip(ip: str, day: str) -> int:
    return _run("SELECT COUNT(*) FROM keys WHERE ip=? AND day=?", (ip, day), fetch_one=True)[0]


def create_key(key: str, email: str, ip: str, day: str) -> bool:
    """Returns False if the email already exists."""
    row = _run(
        "INSERT INTO keys (key, email, ip, day) VALUES (?, ?, ?, ?)"
        "ON CONFLICT DO NOTHING RETURNING key", 
        (key, email, ip, day),
        fetch_one=True,
    )
    return row is not None   


def get_requests(key: str, day: str) -> int:
    row = _run("SELECT requests FROM usage WHERE key=? AND day=?", (key, day),fetch_one=True)
    return row[0] if row else 0


def add_usage(key: str, day: str, requests: int = 0, tokens: int = 0):
    prefix = "usage." if USE_POSTGRES else ""   # Postgres needs the table name here
    _run(f"""
        INSERT INTO usage (key, day, requests, tokens) VALUES (?, ?, ?, ?)
        ON CONFLICT(key, day) DO UPDATE SET
            requests = {prefix}requests + excluded.requests,
            tokens = {prefix}tokens + excluded.tokens
    """, (key, day, requests, tokens))