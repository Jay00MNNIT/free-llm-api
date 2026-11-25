import sqlite3
from datetime import datetime, timezone

db = sqlite3.connect("keys.db", check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS keys (
key TEXT PRIMARY KEY,
email TEXT UNIQUE,
ip TEXT,
day TEXT
)""")
db.execute("""
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
    return db.execute("SELECT 1 FROM keys WHERE key=?", (api_key,)).fetchone() is not None


def email_exists(email: str) -> bool:
    return db.execute("SELECT 1 FROM keys WHERE email=?", (email,)).fetchone() is not None


def signups_from_ip(ip: str, day: str) -> int:
    return db.execute("SELECT COUNT(*) FROM keys WHERE ip=? AND day=?", (ip, day)).fetchone()[0]


def create_key(key: str, email: str, ip: str, day: str) -> bool:
    """Returns False if the email already exists."""
    try:
        db.execute("INSERT INTO keys (key, email, ip, day) VALUES (?, ?, ?, ?)", (key, email, ip, day))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    

def get_requests(key: str, day: str) -> int:
    row = db.execute(
        "SELECT requests FROM usage WHERE key=? AND day=?", (key, day)
    ).fetchone()
    return row[0] if row else 0


def add_usage(key: str, day: str, requests: int = 0, tokens: int = 0):
    db.execute("""
    INSERT INTO usage (key, day, requests, tokens) VALUES (?, ?, ?, ?)
    ON CONFLICT(key, day) DO UPDATE SET
        requests = requests + excluded.requests,
        tokens = tokens + excluded.tokens
""", (key, day, requests, tokens))
db.commit()