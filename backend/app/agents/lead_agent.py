"""
agents/lead_agent.py — Core pipeline orchestrator.

Pipeline:
  1. Collect signals (news scraper)
  2. Classify signals with LLM (intent classifier)
  3. Deduplicate within batch
  4. Find contacts for each qualified lead
  5. Check against DB duplicates
  6. Persist new leads to SQLite
  7. Generate Excel report
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.news_scraper import collect_signals
from app.modules.intent_classifier import classify_signals
from app.modules.contact_finder import find_contact
from app.modules.deduplicator import deduplicate_batch, company_already_exists
from app.database.models import Lead
from app.services.excel_exporter import export_leads
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LeadAgentResult:
    def __init__(self):
        self.signals_collected: int = 0
        self.signals_qualified: int = 0
        self.new_leads_saved: int = 0
        self.duplicates_skipped: int = 0
        self.report_path: str = ""
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "signals_collected":  self.signals_collected,
            "signals_qualified":  self.signals_qualified,
            "new_leads_saved":    self.new_leads_saved,
            "duplicates_skipped": self.duplicates_skipped,
            "report_path":        self.report_path,
            "errors":             self.errors,
        }


def run_pipeline(db: Session) -> LeadAgentResult:
    """Execute the full lead generation pipeline and return a result summary."""
    result = LeadAgentResult()
    logger.info("═══ Lead Agent Pipeline START ═══")

    # Step 1 — Collect signals
    try:
        raw_signals = collect_signals()
        result.signals_collected = len(raw_signals)
        logger.info("Step 1 ✓  Collected %d signals", result.signals_collected)
    except Exception as exc:
        msg = f"Signal collection failed: {exc}"
        logger.error(msg)
        result.errors.append(msg)
        return result

    if not raw_signals:
        logger.warning("No signals collected — aborting pipeline.")
        return result

    # Step 2 — Classify with LLM (cap at 50 to respect free-tier rate limits)
    MAX_TO_CLASSIFY = 10
    if len(raw_signals) > MAX_TO_CLASSIFY:
        logger.info("Capping signals from %d to %d to respect API rate limits", len(raw_signals), MAX_TO_CLASSIFY)
        raw_signals = raw_signals[:MAX_TO_CLASSIFY]
    try:
        qualified = classify_signals(raw_signals)
        result.signals_qualified = len(qualified)
        logger.info("Step 2 ✓  %d signals qualified as buying signals", result.signals_qualified)
    except Exception as exc:
        msg = f"Signal classification failed: {exc}"
        logger.error(msg)
        result.errors.append(msg)
        return result

    if not qualified:
        logger.info("No qualified signals — generating report with existing leads.")
        _generate_report(db, result)
        return result

    # Step 3 — Deduplicate within batch
    qualified = deduplicate_batch(qualified)
    logger.info("Step 3 ✓  %d unique companies after batch deduplication", len(qualified))

    # Step 4 & 5 — Contact discovery + DB deduplication + persist
    for lead_data in qualified:
        company = lead_data["company"]

        # Skip if already in DB
        if company_already_exists(company, db):
            result.duplicates_skipped += 1
            logger.info("Skipped (duplicate): %s", company)
            continue

        # Find contact
        try:
            contact_info = find_contact(company)
        except Exception as exc:
            logger.warning("Contact finder failed for '%s': %s", company, exc)
            contact_info = {"contact": "", "title": "", "linkedin": "", "website": ""}

        # Persist to DB
        try:
            lead = Lead(
                company    = company,
                contact    = contact_info.get("contact",  ""),
                title      = contact_info.get("title",    ""),
                linkedin   = contact_info.get("linkedin", ""),
                website    = contact_info.get("website",  ""),
                signal     = lead_data.get("signal",      ""),
                signal_url = lead_data.get("signal_url",  ""),
                score      = lead_data.get("score",       0.0),
                reasoning  = lead_data.get("reasoning",   ""),
                date_found = datetime.utcnow(),
            )
            db.add(lead)
            db.commit()
            result.new_leads_saved += 1
            logger.info("Saved lead: %s (score %.1f)", company, lead_data.get("score", 0))
        except Exception as exc:
            db.rollback()
            msg = f"DB save failed for '{company}': {exc}"
            logger.error(msg)
            result.errors.append(msg)

    logger.info("Step 4-5 ✓  Saved %d new leads, skipped %d duplicates",
                result.new_leads_saved, result.duplicates_skipped)

    # Step 6 — Generate Excel report
    _generate_report(db, result)

    logger.info("═══ Lead Agent Pipeline END ═══")
    logger.info("Summary: %s", result.to_dict())
    return result


def _generate_report(db: Session, result: LeadAgentResult) -> None:
    try:
        path = export_leads(db)
        result.report_path = str(path)
        logger.info("Step 6 ✓  Excel report generated: %s", path)
    except Exception as exc:
        msg = f"Excel export failed: {exc}"
        logger.error(msg)
        result.errors.append(msg)