# ⚡ AI Lead Generation Agent
### Strikin Internship Assignment — Task 02 | Intent-Based Outreach

An autonomous AI agent that monitors online sources for **PropTech / real estate digital transformation** buying signals, classifies them with an LLM, discovers CEO/CTO contacts, stores structured leads in SQLite, and exports a formatted Excel report — all accessible through a clean frontend dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Frontend Dashboard                      │
│         index.html  ·  script.js  ·  style.css          │
└────────────────────┬────────────────────────────────────┘
                     │  HTTP (REST)
┌────────────────────▼────────────────────────────────────┐
│                FastAPI Backend  (main.py)                │
│  /run-agent  /leads  /stats  /download-report           │
└──┬───────────────┬──────────────────────────────────────┘
   │               │
   ▼               ▼
APScheduler    Lead Agent Pipeline (lead_agent.py)
(daily runs)        │
              ┌─────▼──────────────────────────────────┐
              │  1. news_scraper.py  — RSS + NewsAPI    │
              │  2. intent_classifier.py — LLM (GPT/   │
              │     Gemini) scores buying signals       │
              │  3. contact_finder.py — CEO/CTO search  │
              │  4. deduplicator.py — no repeat leads   │
              │  5. db.py / models.py — SQLite persist  │
              │  6. excel_exporter.py — .xlsx report    │
              └─────────────────────────────────────────┘
```

---

## Features

| # | Feature | Details |
|---|---------|---------|
| D1 | **Signal Monitoring** | Google News RSS (5 feeds) + NewsAPI (optional) filtered by 15 PropTech keywords |
| D2 | **LLM Intent Classifier** | GPT-4o-mini or Gemini 1.5 Flash — Yes/No/Maybe + urgency score 1–10 + reasoning |
| D3 | **Contact Discovery** | Google search → BeautifulSoup scrape → LLM extracts name, title, LinkedIn URL |
| D4 | **Excel Lead Output** | Formatted 2-sheet workbook with score-coloured rows and summary stats |
| D5 | **Scheduler / Trigger** | APScheduler (configurable interval) + manual `/run-agent` endpoint |
| D6 | **Frontend Dashboard** | Run agent, view leads table, search/filter, delete, download report |

---

## Quick Start

### 1. Clone & enter the project

```bash
git clone https://github.com/YOUR_USERNAME/ai-lead-generation-agent.git
cd ai-lead-generation-agent
```

### 2. Create a virtual environment

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
LLM_PROVIDER=openai                     # or gemini
OPENAI_API_KEY=sk-...                   # required if using openai
GEMINI_API_KEY=AIza...                  # required if using gemini
NEWS_API_KEY=your_key_here              # optional — enhances sources
SCHEDULER_INTERVAL_HOURS=24
```

### 5. Start the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs auto-generated at: http://localhost:8000/docs

### 6. Open the dashboard

Open `frontend/index.html` directly in your browser — no server needed.

> If you get CORS errors, serve the frontend with:
> ```bash
> cd ../frontend && python -m http.server 3000
> ```
> Then open http://localhost:3000

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run-agent` | Trigger pipeline in background |
| `GET`  | `/run-status` | Poll agent progress |
| `GET`  | `/leads` | Fetch all leads as JSON |
| `GET`  | `/stats` | Summary statistics |
| `GET`  | `/download-report` | Download Excel report |
| `DELETE` | `/leads/{id}` | Delete a lead |
| `GET`  | `/health` | Health check |

---

## Project Structure

```
ai-lead-generation-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point
│   │   ├── config.py               # API keys & settings
│   │   ├── agents/
│   │   │   └── lead_agent.py       # Pipeline orchestrator
│   │   ├── modules/
│   │   │   ├── news_scraper.py     # RSS + NewsAPI signals
│   │   │   ├── intent_classifier.py# LLM classification
│   │   │   ├── contact_finder.py   # CEO/CTO discovery
│   │   │   └── deduplicator.py     # No duplicate companies
│   │   ├── database/
│   │   │   ├── db.py               # SQLite connection
│   │   │   └── models.py           # Lead schema
│   │   ├── services/
│   │   │   └── excel_exporter.py   # Excel generation
│   │   ├── scheduler/
│   │   │   └── scheduler.py        # Automated runs
│   │   └── utils/
│   │       ├── logger.py
│   │       └── text_cleaner.py
│   ├── requirements.txt
│   ├── .env                        # Your keys (not committed)
│   └── .env.example
├── frontend/
│   ├── index.html                  # Dashboard
│   ├── script.js                   # API integration
│   └── style.css                   # Dark UI styling
├── data/
│   ├── leads.db                    # SQLite (auto-created)
│   └── reports/
│       └── lead_report.xlsx        # Generated report
├── .gitignore
└── README.md
```

---

## ICP Configuration

To change the target customer profile, edit `backend/app/config.py`:

```python
ICP_KEYWORDS = [
    "real estate digital transformation",
    "proptech launch",
    # … add your own keywords
]

RSS_FEEDS = [
    "https://news.google.com/rss/search?q=proptech&...",
    # … add more RSS feeds
]
```

---

## Excel Report

The generated `lead_report.xlsx` contains:

- **Sheet 1 — Lead List**: All leads with score-coloured rows (🟢 ≥7 · 🟡 4–6 · 🔴 <4), auto-filter, and frozen headers
- **Sheet 2 — Summary**: Total leads, high/med/low intent counts, avg score, contacts found

---

## Known Limitations & Improvements

| Limitation | Potential Improvement |
|---|---|
| Google search scraping can be rate-limited | Use SerpAPI or ScraperAPI for reliable search |
| LinkedIn scraping is restricted | Integrate LinkedIn API or Proxycurl for accurate contacts |
| Contact discovery depends on Google snippet quality | Add Hunter.io / Apollo.io API for email enrichment |
| No authentication on API | Add API key middleware for production deployment |
| SQLite not suitable for concurrent writes | Migrate to PostgreSQL for production scale |

---

## Tech Stack

- **Python 3.11+** — core language
- **FastAPI + Uvicorn** — async REST API
- **SQLAlchemy + SQLite** — lead storage
- **feedparser + BeautifulSoup + requests** — signal scraping
- **OpenAI GPT-4o-mini / Google Gemini 1.5 Flash** — intent classification & contact extraction
- **openpyxl** — Excel report generation
- **APScheduler** — automated scheduling
- **Vanilla JS + CSS** — lightweight zero-dependency frontend

---

*Built for Strikin Internship Assignment — Task 02*  
*Submit to: deepesh.j@strikin.com*
