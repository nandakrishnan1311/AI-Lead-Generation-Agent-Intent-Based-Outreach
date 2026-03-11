"""
database/models.py — SQLAlchemy ORM model for the leads table.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Lead(Base):
    """One row per qualified lead company."""
    __tablename__ = "leads"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    company      = Column(String(255), nullable=False, index=True)
    contact      = Column(String(255), default="")        # Contact person name
    title        = Column(String(100), default="")        # CEO / CTO / …
    linkedin     = Column(String(500), default="")        # LinkedIn profile URL
    website      = Column(String(500), default="")        # Company website
    signal       = Column(Text, default="")               # Signal summary
    signal_url   = Column(String(500), default="")        # Source article URL
    score        = Column(Float, default=0.0)             # Intent score 1–10
    reasoning    = Column(Text, default="")               # LLM reasoning
    date_found   = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "company":     self.company,
            "contact":     self.contact,
            "title":       self.title,
            "linkedin":    self.linkedin,
            "website":     self.website,
            "signal":      self.signal,
            "signal_url":  self.signal_url,
            "score":       self.score,
            "reasoning":   self.reasoning,
            "date_found":  self.date_found.strftime("%Y-%m-%d %H:%M") if self.date_found else "",
        }
