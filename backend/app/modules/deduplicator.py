"""
modules/deduplicator.py — Ensures the same company isn't stored more than once.

Checks existing DB records and in-batch duplicates using fuzzy company name matching.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import Lead
from app.utils.text_cleaner import clean_company_name
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _normalise(name: str) -> str:
    return clean_company_name(name)


def company_already_exists(company: str, db: Session) -> bool:
    """Return True if a lead for this company already exists in the database."""
    norm = _normalise(company)
    existing = db.query(Lead.company).all()
    for (existing_name,) in existing:
        if _normalise(existing_name) == norm:
            logger.debug("Duplicate found — '%s' matches existing '%s'", company, existing_name)
            return True
    return False


def deduplicate_batch(leads: list[dict]) -> list[dict]:
    """
    Remove duplicate companies within a single batch (before DB write).
    Keeps the highest-scored entry when duplicates exist.
    """
    seen: dict[str, dict] = {}
    for lead in leads:
        key = _normalise(lead.get("company", ""))
        if not key:
            continue
        existing = seen.get(key)
        if existing is None or lead.get("score", 0) > existing.get("score", 0):
            seen[key] = lead

    result = list(seen.values())
    dropped = len(leads) - len(result)
    if dropped:
        logger.info("Deduplication removed %d in-batch duplicate(s)", dropped)
    return result
