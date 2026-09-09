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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv(
    "ANTHROPIC_BASE_URL",
    "https://api.anthropic.com",
).strip()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "stanford").strip().lower() or "stanford"
SANS_BASE_URL = os.getenv(
    "SANS_BASE_URL",
    "https://www.sans.org/information-security-policy",
).strip()
