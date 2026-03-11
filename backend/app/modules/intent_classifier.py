"""
modules/intent_classifier.py — Uses an LLM to classify signals and extract company info.

Supports:
  - gemini   (Google Gemini API)
  - openai   (OpenAI API)
  - huggingface (HuggingFace Inference API — no download, runs on HF servers)
"""

from __future__ import annotations

import json
import re
import time

from app.config import LLM_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY, HUGGINGFACE_API_KEY
from app.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a B2B sales analyst. Classify if this news signal is a buying signal for PropTech/real estate digital transformation services.

ICP (Ideal Customer Profile):
- Real estate companies, property developers, realty groups
- Companies launching apps/platforms, hiring tech teams, adopting CRM/SaaS, raising funds for tech
- PropTech startups building products

Classification:
- "yes"   -> Clear buying signal
- "maybe" -> Indirect signal
- "no"    -> Not relevant

Be GENEROUS. Any real estate company doing ANYTHING technology-related = yes or maybe.
Extract the PRIMARY company name. Never leave blank for yes/maybe.

Respond ONLY with valid JSON, no markdown, no extra text:
{"is_buying_signal":"yes","company_name":"Example Corp","signal_summary":"Summary.","intent_score":8,"reasoning":"One sentence."}"""

USER_TEMPLATE = "Title: {title}\n\nSummary: {summary}\n\nClassify now. JSON only."


# ── OpenAI ────────────────────────────────────────────────────────────────────
def _call_openai(title: str, summary: str, url: str) -> dict:
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_TEMPLATE.format(title=title, summary=summary, url=url)},
        ],
        temperature=0.1,
        max_tokens=300,
    )
    return _parse_json(response.choices[0].message.content or "{}")


# ── Gemini ────────────────────────────────────────────────────────────────────
def _call_gemini(title: str, summary: str, url: str) -> dict:
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = f"{SYSTEM_PROMPT}\n\n{USER_TEMPLATE.format(title=title, summary=summary, url=url)}"

    for attempt in range(4):
        try:
            result = model.generate_content(prompt)
            time.sleep(4)
            return _parse_json(result.text or "{}")
        except Exception as exc:
            err = str(exc)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                wait = 60 * (attempt + 1)
                logger.warning("Gemini rate limited — waiting %ds (attempt %d/4)…", wait, attempt + 1)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini rate limit: exhausted retries")


# ── HuggingFace Inference API ─────────────────────────────────────────────────
def _call_huggingface(title: str, summary: str, url: str) -> dict:
    import requests

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(title=title, summary=summary, url=url)},
        ],
        "max_tokens": 300,
        "temperature": 0.1,
    }

    for attempt in range(4):
        try:
            resp = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            if resp.status_code == 503:
                wait = 20 * (attempt + 1)
                logger.warning("HuggingFace model loading — waiting %ds (attempt %d/4)…", wait, attempt + 1)
                time.sleep(wait)
                continue

            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                logger.warning("HuggingFace rate limited — waiting %ds (attempt %d/4)…", wait, attempt + 1)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            # OpenAI-compatible response format
            raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            time.sleep(1)
            return _parse_json(raw)

        except Exception as exc:
            logger.warning("HuggingFace error (attempt %d/4): %s", attempt + 1, exc)
            if attempt < 3:
                time.sleep(10)

    logger.error("HuggingFace: exhausted all retries")
    return {}


# ── JSON parser ───────────────────────────────────────────────────────────────
def _parse_json(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r'\{.*?"is_buying_signal".*?\}', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning("JSON parse failed: %s", raw[:200])
    return {}


# ── Main classifier ───────────────────────────────────────────────────────────
def classify_signal(signal: dict) -> dict | None:
    title   = signal.get("title",   "")
    summary = signal.get("summary", "") or title
    url     = signal.get("url",     "")

    try:
        if LLM_PROVIDER == "gemini":
            result = _call_gemini(title, summary, url)
        elif LLM_PROVIDER == "huggingface":
            result = _call_huggingface(title, summary, url)
        else:
            result = _call_openai(title, summary, url)
    except Exception as exc:
        logger.error("LLM error for '%s': %s", title[:60], exc)
        return None

    if not result:
        return None

    is_signal = str(result.get("is_buying_signal", "no")).lower().strip()
    if is_signal == "no":
        logger.debug("  ✗ Rejected: %s", title[:60])
        return None

    try:
        score = float(result.get("intent_score", 5))
    except (TypeError, ValueError):
        score = 5.0
    score = max(1.0, min(10.0, score))
    if is_signal == "maybe":
        score = min(score, 6.0)

    company = str(result.get("company_name") or "").strip()
    if not company or company.lower() in ("unknown", "n/a", "none", ""):
        logger.debug("  ✗ No company extracted: %s", title[:60])
        return None

    return {
        "company":    company,
        "signal":     str(result.get("signal_summary") or summary),
        "signal_url": url,
        "score":      score,
        "reasoning":  str(result.get("reasoning") or ""),
        "is_maybe":   is_signal == "maybe",
        "source":     signal.get("source", ""),
        "published":  signal.get("published", ""),
    }


def classify_signals(signals: list[dict]) -> list[dict]:
    qualified: list[dict] = []
    total = len(signals)
    for i, sig in enumerate(signals, 1):
        logger.info("Classifying %d/%d: %s", i, total, sig.get("title", "")[:70])
        result = classify_signal(sig)
        if result:
            qualified.append(result)
            logger.info("  ✓ QUALIFIED [%.1f]: %s", result["score"], result["company"])
    logger.info("Classification: %d/%d qualified", len(qualified), total)
    return qualified