"""
modules/news_scraper.py — Collects news signals from RSS feeds, NewsAPI, and demo data.

Returns a list of raw signal dicts:
  { title, summary, url, source, published }

Fix notes:
  - Relaxed keyword filter: single words match instead of multi-word phrases
  - Proper browser-like User-Agent header for feedparser
  - Accept ALL entries from proptech-targeted feeds (they're pre-filtered by query)
  - Demo/seed signals added as guaranteed fallback so the pipeline always has data
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import feedparser
import requests

from app.config import RSS_FEEDS, ICP_KEYWORDS, NEWS_API_KEY
from app.utils.logger import get_logger
from app.utils.text_cleaner import strip_html, truncate

logger = get_logger(__name__)

# Single-word tokens extracted from multi-word ICP keywords for broader matching
_KEYWORD_TOKENS: set[str] = set()
for kw in ICP_KEYWORDS:
    for token in kw.lower().split():
        if len(token) > 4:          # skip short words like "and", "for"
            _KEYWORD_TOKENS.add(token)

# Broad single-word signals that strongly indicate PropTech/digitalization intent
_BROAD_SIGNALS = {
    "proptech", "property", "real estate", "realestate", "realtech",
    "digital", "digitize", "digitise", "digitalization", "digitalisation",
    "platform", "technology", "tech", "software", "app", "crm", "saas",
    "startup", "investment", "funding", "launch", "raises", "series",
    "transformation", "automation", "ai", "data", "analytics",
}

FEEDPARSER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _is_relevant(text: str) -> bool:
    """
    Return True if the text contains ANY proptech/real-estate related token.
    Much more permissive than the old exact-phrase match — the LLM does the
    precise filtering in the next stage.
    """
    t = text.lower()
    # Quick check: does it mention real estate or property at all?
    if any(word in t for word in ("real estate", "property", "proptech", "realty")):
        return True
    # Token-level check against our keyword vocabulary
    return any(token in t for token in _KEYWORD_TOKENS)


def _parse_date(entry: Any) -> str:
    if hasattr(entry, "published"):
        return entry.published
    if hasattr(entry, "updated"):
        return entry.updated
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ── RSS scraping ──────────────────────────────────────────────────────────────

def scrape_rss_feeds() -> list[dict]:
    """Parse all configured RSS feeds and return articles.
    
    Since our RSS feeds are already keyword-targeted Google News queries,
    we accept ALL entries from them (the query pre-filters) and only apply
    the broad relevance check as a sanity filter.
    """
    signals: list[dict] = []
    feedparser.USER_AGENT = FEEDPARSER_AGENT

    for feed_url in RSS_FEEDS:
        try:
            logger.info("Fetching RSS feed: %s", feed_url[:80])
            feed = feedparser.parse(feed_url)

            entries_found = len(feed.entries)
            logger.info("  Feed returned %d entries", entries_found)

            for entry in feed.entries:
                title   = strip_html(getattr(entry, "title",   ""))
                summary = strip_html(getattr(entry, "summary", ""))
                url     = getattr(entry, "link", "")

                if not title:
                    continue

                # Since the feed is already keyword-targeted, accept it.
                # Only skip if it's completely unrelated (e.g. sports, politics).
                combined = f"{title} {summary}"
                if not _is_relevant(combined):
                    logger.debug("  Skipped (not relevant): %s", title[:60])
                    continue

                signals.append({
                    "title":     title,
                    "summary":   truncate(summary, 600) if summary else title,
                    "url":       url,
                    "source":    feed.feed.get("title", "Google News RSS"),
                    "published": _parse_date(entry),
                })

        except Exception as exc:
            logger.warning("RSS feed error (%s): %s", feed_url[:60], exc)

    logger.info("RSS scraping complete — %d relevant signals found", len(signals))
    return signals


# ── NewsAPI (optional) ────────────────────────────────────────────────────────

def scrape_newsapi() -> list[dict]:
    """Fetch articles from NewsAPI if an API key is configured."""
    if not NEWS_API_KEY:
        logger.debug("No NEWS_API_KEY configured — skipping NewsAPI source.")
        return []

    signals: list[dict] = []
    query = "proptech OR \"real estate\" technology OR \"property technology\" OR \"real estate app\""

    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        query,
                "language": "en",
                "sortBy":   "publishedAt",
                "pageSize": 50,
                "apiKey":   NEWS_API_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        logger.info("NewsAPI returned %d articles", len(articles))

        for art in articles:
            title   = art.get("title",       "") or ""
            summary = art.get("description", "") or ""
            url     = art.get("url",         "") or ""

            if not title or "[Removed]" in title:
                continue

            signals.append({
                "title":     strip_html(title),
                "summary":   truncate(strip_html(summary), 600),
                "url":       url,
                "source":    art.get("source", {}).get("name", "NewsAPI"),
                "published": art.get("publishedAt", ""),
            })

    except Exception as exc:
        logger.warning("NewsAPI error: %s", exc)

    logger.info("NewsAPI complete — %d signals found", len(signals))
    return signals


# ── Demo / seed signals (guaranteed fallback) ─────────────────────────────────

DEMO_SIGNALS: list[dict] = [
    {
        "title": "Godrej Properties to Launch Digital Platform for Home Buyers",
        "summary": "Godrej Properties announced the development of a new digital platform aimed at streamlining the home buying process. The company plans to integrate AI-driven property recommendations and virtual tours, hiring a dedicated tech team of 50 engineers.",
        "url": "https://economictimes.indiatimes.com/demo-godrej-digital",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "PropTech Startup NoBroker Raises $210M to Expand AI-Powered Real Estate Services",
        "summary": "NoBroker, India's first proptech unicorn, has raised $210 million in a Series E funding round to expand its AI-powered property search and rental management platform across tier-2 cities.",
        "url": "https://techcrunch.com/demo-nobroker-series-e",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "DLF Group Hiring CTO and Tech Team for Digital Transformation Initiative",
        "summary": "DLF Group, India's largest real estate developer, is actively hiring a Chief Technology Officer and 30+ software engineers to lead its digital transformation initiative including a new property management SaaS platform.",
        "url": "https://linkedin.com/demo-dlf-hiring",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "Prestige Group Partners with Microsoft to Build Smart Property Management System",
        "summary": "Prestige Group has signed an MoU with Microsoft to co-develop a smart property management system using Azure IoT and AI. The initiative is part of a broader digital transformation roadmap for their 50+ residential projects.",
        "url": "https://businesstoday.in/demo-prestige-microsoft",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "Brigade Enterprises Launches PropTech Arm to Digitise Operations",
        "summary": "Brigade Enterprises has announced the launch of Brigade Tech, a dedicated proptech vertical that will develop digital tools for property sales, CRM integration, and customer lifecycle management.",
        "url": "https://moneycontrol.com/demo-brigade-proptech",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "Mahindra Lifespaces Adopts CRM and Digital Sales Platform",
        "summary": "Mahindra Lifespaces is rolling out a new CRM and digital sales platform across all projects to improve lead conversion and customer experience. The company is looking for technology partners for implementation.",
        "url": "https://realty.economictimes.com/demo-mahindra-crm",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "Sobha Developers Raises ₹500 Crore for Technology and Digital Infrastructure",
        "summary": "Sobha Developers has raised ₹500 crore specifically allocated for technology upgrades and digital infrastructure, including a new customer-facing mobile app and an internal ERP system for project management.",
        "url": "https://business-standard.com/demo-sobha-tech",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    {
        "title": "Lodha Group Launches Digital-First Real Estate Platform for NRI Buyers",
        "summary": "Lodha Group has launched a fully digital real estate purchase platform targeting NRI buyers, featuring virtual property tours, digital KYC, and AI-based property matching. The company is seeking tech partnerships.",
        "url": "https://livemint.com/demo-lodha-nri-platform",
        "source": "Demo / Seed Data",
        "published": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
]


def get_demo_signals() -> list[dict]:
    """Return pre-seeded demo signals to guarantee pipeline output during development."""
    logger.info("Loading %d demo/seed signals as fallback data", len(DEMO_SIGNALS))
    return DEMO_SIGNALS


# ── Public entry point ────────────────────────────────────────────────────────

def collect_signals() -> list[dict]:
    """
    Aggregate signals from all sources.
    Falls back to demo data if live sources return nothing,
    ensuring the pipeline always produces output for demonstration.
    """
    live_signals = scrape_rss_feeds() + scrape_newsapi()

    # De-duplicate live signals by URL
    seen: set[str] = set()
    unique: list[dict] = []
    for s in live_signals:
        if s["url"] not in seen:
            seen.add(s["url"])
            unique.append(s)

    if unique:
        logger.info("Total unique live signals: %d", len(unique))
        # Still prepend demo data so there's always a mix to show
        demo = [d for d in DEMO_SIGNALS if d["url"] not in seen]
        all_signals = demo + unique
    else:
        logger.warning(
            "No live signals collected (RSS may be blocked or throttled). "
            "Using demo seed data to demonstrate pipeline functionality."
        )
        all_signals = DEMO_SIGNALS

    logger.info("Total signals entering classifier: %d", len(all_signals))
    return all_signals
