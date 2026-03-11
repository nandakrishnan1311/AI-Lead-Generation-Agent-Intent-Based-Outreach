"""
modules/contact_finder.py — Discovers CEO/CTO contact information for a company.

Strategy (no paid API required):
  1. Google search "{company} CEO site:linkedin.com"
  2. Parse result snippets for name + LinkedIn URL
  3. Fallback: search company website for leadership page
  4. Use LLM to extract structured contact info from snippets

Supports: openai | gemini | huggingface
"""

from __future__ import annotations

import json
import re
import time

import requests
from bs4 import BeautifulSoup

from app.config import LLM_PROVIDER, OPENAI_API_KEY, GEMINI_API_KEY, HUGGINGFACE_API_KEY, TARGET_TITLES
from app.utils.logger import get_logger
from app.utils.text_cleaner import strip_html, truncate

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── Web search helpers ────────────────────────────────────────────────────────

def _google_search_snippets(query: str, num: int = 5) -> list[str]:
    url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num}"
    snippets: list[str] = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for div in soup.select("div.BNeawe, div.VwiC3b, span.st"):
            text = strip_html(div.get_text())
            if text:
                snippets.append(truncate(text, 300))
        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = re.search(r"https://[a-z]+\.linkedin\.com/in/[^\s&\"]+", href)
            if match:
                snippets.append(match.group(0))
    except Exception as exc:
        logger.warning("Google search error for '%s': %s", query, exc)
    return snippets


def _extract_linkedin_urls(texts: list[str]) -> list[str]:
    urls: list[str] = []
    pattern = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[^\s\"'<>]+")
    for t in texts:
        urls.extend(pattern.findall(t))
    return list(dict.fromkeys(urls))


def _find_company_website(company: str) -> str:
    snippets = _google_search_snippets(f"{company} official website")
    pattern = re.compile(
        r"https?://(?:www\.)?(?!" + re.escape("linkedin") + r")"
        r"(?!" + re.escape("google") + r")"
        r"[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[^\s\"'<>]*)?"
    )
    for s in snippets:
        m = pattern.search(s)
        if m:
            return m.group(0).split("?")[0]
    return ""


# ── LLM contact extraction ────────────────────────────────────────────────────

_CONTACT_SYSTEM = """You are a contact extraction assistant.
Given search snippets about a company's leadership, extract the most likely CEO or CTO.
Respond ONLY with valid JSON — no preamble, no markdown fences.
Schema:
{
  "name": "<full name or empty string>",
  "title": "<CEO | CTO | Co-Founder | Head of Technology | empty string>",
  "linkedin": "<LinkedIn profile URL or empty string>"
}"""


def _llm_extract_contact(company: str, snippets: list[str]) -> dict:
    text = "\n".join(snippets[:8])
    prompt = f"Company: {company}\n\nSearch snippets:\n{text}\n\nExtract the top executive contact."

    try:
        raw = "{}"

        if LLM_PROVIDER == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.0-flash")
            raw = model.generate_content(f"{_CONTACT_SYSTEM}\n\n{prompt}").text or "{}"

        elif LLM_PROVIDER == "huggingface":
            resp = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "meta-llama/Llama-3.1-8B-Instruct",
                    "messages": [
                        {"role": "system", "content": _CONTACT_SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.1,
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")

        else:  # openai
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _CONTACT_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content or "{}"

        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        return json.loads(raw)

    except Exception as exc:
        logger.warning("LLM contact extraction failed: %s", exc)
        return {}


# ── Public entry point ────────────────────────────────────────────────────────

def find_contact(company: str) -> dict:
    """
    Find CEO/CTO contact for a company.
    Returns: { name, title, linkedin, website }
    """
    logger.info("Finding contact for: %s", company)
    time.sleep(1)

    snippets: list[str] = []
    for title_kw in ["CEO", "CTO", "Co-Founder"]:
        q = f'{company} {title_kw} site:linkedin.com'
        snippets.extend(_google_search_snippets(q, num=3))
        time.sleep(0.5)

    snippets.extend(_google_search_snippets(f"{company} leadership team"))

    linkedin_urls = _extract_linkedin_urls(snippets)
    contact = _llm_extract_contact(company, snippets)
    website = _find_company_website(company)

    return {
        "contact":  contact.get("name",     ""),
        "title":    contact.get("title",    ""),
        "linkedin": contact.get("linkedin", "") or (linkedin_urls[0] if linkedin_urls else ""),
        "website":  website,
    }