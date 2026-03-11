"""
main.py — FastAPI application entry point.

Endpoints:
  POST /run-agent           — Trigger the lead pipeline manually
  GET  /leads               — Return all stored leads as JSON
  GET  /download-report     — Download the latest Excel report
  GET  /health              — Health check
  GET  /stats               — Quick statistics
"""

from __future__ import annotations

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.db import init_db, get_db
from app.database.models import Lead
from app.agents.lead_agent import run_pipeline, LeadAgentResult
from app.scheduler.scheduler import start_scheduler, stop_scheduler
from app.services.excel_exporter import export_leads
from app.config import REPORT_OUTPUT_PATH
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Lead Generation Agent …")
    init_db()
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("AI Lead Generation Agent shut down.")


app = FastAPI(
    title="AI Lead Generation Agent",
    description="Autonomous B2B lead discovery for PropTech / Digital Transformation",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run-state (for UI progress feedback) ────────────────────────────
_run_state: dict = {"running": False, "last_result": None}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "agent": "AI Lead Generation Agent v1.0"}


@app.post("/run-agent")
async def run_agent(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger the lead pipeline. Runs in the background so the HTTP response is immediate."""
    if _run_state["running"]:
        return {"message": "Agent is already running. Please wait.", "running": True}

    def _run():
        _run_state["running"] = True
        try:
            from app.database.db import SessionLocal
            with SessionLocal() as session:
                result = run_pipeline(session)
                _run_state["last_result"] = result.to_dict()
        except Exception as exc:
            logger.error("Background pipeline error: %s", exc)
            _run_state["last_result"] = {"error": str(exc)}
        finally:
            _run_state["running"] = False

    background_tasks.add_task(_run)
    return {"message": "Lead agent started in background.", "running": True}


@app.get("/run-status")
def run_status():
    """Poll this to check if the agent is still running."""
    return {
        "running":     _run_state["running"],
        "last_result": _run_state["last_result"],
    }


@app.get("/leads")
def get_leads(db: Session = Depends(get_db)):
    """Return all leads ordered by intent score descending."""
    leads: list[Lead] = db.query(Lead).order_by(Lead.score.desc()).all()
    return [l.to_dict() for l in leads]


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Return quick summary statistics."""
    leads: list[Lead] = db.query(Lead).all()
    total = len(leads)
    return {
        "total_leads":           total,
        "high_intent":           sum(1 for l in leads if (l.score or 0) >= 7),
        "medium_intent":         sum(1 for l in leads if 4 <= (l.score or 0) < 7),
        "low_intent":            sum(1 for l in leads if (l.score or 0) < 4),
        "avg_score":             round(sum(l.score or 0 for l in leads) / max(total, 1), 2),
        "contacts_found":        sum(1 for l in leads if l.contact),
        "linkedin_found":        sum(1 for l in leads if l.linkedin),
    }


@app.get("/download-report")
def download_report(db: Session = Depends(get_db)):
    """Generate (or regenerate) and return the Excel report as a download."""
    path = export_leads(db)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(
        path=str(path),
        filename="lead_report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.delete("/leads/{lead_id}")
def delete_lead(lead_id: int, db: Session = Depends(get_db)):
    """Delete a specific lead by ID."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")
    db.delete(lead)
    db.commit()
    return {"message": f"Lead {lead_id} deleted."}
