"""
config.py — Centralised configuration loader.
Reads .env and exposes typed settings to the rest of the app.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve .env relative to this file's parent (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()          # "openai" | "gemini" | "huggingface"
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")

# ── External APIs ─────────────────────────────────────────────────────────────
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

# ── Storage ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = BASE_DIR.parent
DATABASE_PATH: Path = PROJECT_ROOT / os.getenv("DATABASE_PATH", "data/leads.db")
REPORT_OUTPUT_PATH: Path = PROJECT_ROOT / os.getenv("REPORT_OUTPUT_PATH", "data/reports/lead_report.xlsx")

# Ensure directories exist
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULER_INTERVAL_HOURS: int = int(os.getenv("SCHEDULER_INTERVAL_HOURS", "24"))

# ── ICP & Signal Keywords ─────────────────────────────────────────────────────
ICP_KEYWORDS: list[str] = [
    "real estate digital transformation",
    "proptech launch",
    "property tech investment",
    "real estate app",
    "real estate CRM",
    "property management software",
    "real estate technology",
    "proptech startup",
    "real estate digitalization",
    "real estate platform",
    "real estate hiring tech",
    "property technology",
    "real estate SaaS",
    "smart property management",
    "real estate data analytics",
]

# ── RSS Feed Sources ──────────────────────────────────────────────────────────
RSS_FEEDS: list[str] = [
    "https://news.google.com/rss/search?q=proptech&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=real+estate+digital+transformation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=real+estate+technology+investment&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=property+tech+startup&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=real+estate+app+launch&hl=en-US&gl=US&ceid=US:en",
]

# ── Contact Discovery ─────────────────────────────────────────────────────────
TARGET_TITLES: list[str] = ["CEO", "CTO", "Co-Founder", "Head of Technology", "Chief Technology Officer", "Chief Executive Officer"]