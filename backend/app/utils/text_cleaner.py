"""
utils/text_cleaner.py — HTML / text sanitisation helpers.
"""

import re
import html


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalise(text)


def _normalise(text: str) -> str:
    """Collapse whitespace and strip leading/trailing space."""
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, max_chars: int = 500) -> str:
    """Truncate text to max_chars, appending '…' if needed."""
    text = text or ""
    return text if len(text) <= max_chars else text[:max_chars].rstrip() + "…"


def clean_company_name(name: str) -> str:
    """Normalise a company name for deduplication comparisons."""
    name = (name or "").lower()
    # Remove common suffixes
    for suffix in [" inc", " llc", " ltd", " corp", " co", " group", "."]:
        name = name.replace(suffix, "")
    return _normalise(name)
