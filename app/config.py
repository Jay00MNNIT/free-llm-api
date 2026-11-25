import os 
from dotenv import load_dotenv

load_dotenv()

RATE_LIMIT, RATE_WINDOW = 20, 60    # 20 requests per 60 seconds
DAILY_LIMIT = 200                   # per user per day
GLOBAL_DAILY_CAP = 1000             # all users together per day
MAX_SIGNUPS_PER_IP_PER_DAY = 3

PROVIDERS = {
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key": os.getenv("GEMINI_API_KEY"),
        "model": "gemini-3.8-flash",    # check current model names
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": os.getenv("GROQ_API_KEY"),
        "model": "openai/gpt-oss-20b",
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "key": os.getenv("OPENAI_API_KEY"),
        "model": "gpt-4o-mini",
    },
}

# If the first provider fails, try these next (in this order)
FALLBACKS = {
    "gemini": ["groq", "openai"],
    "groq": ["gemini", "openai"],
    "openai": ["gemini", "groq"],
}