from pathlib import Path

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.local")
load_dotenv(ROOT / ".env")

AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY", "").strip()
AI_GATEWAY_BASE_URL = os.getenv(
    "AI_GATEWAY_BASE_URL",
    "https://aiapi-dev.stanford.edu/",
).strip()
SANS_BASE_URL = os.getenv(
    "SANS_BASE_URL",
    "https://www.sans.org/information-security-policy",
).strip()
