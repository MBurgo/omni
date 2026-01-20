from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from serpapi import GoogleSearch

from engines.llm import extract_json_object, query_openai
from utils import get_serpapi_api_key


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
}


@dataclass(frozen=True)
class SignalsData:
    query: str
    generated_at: float
    news: List[Dict[str, Any]]
    top_stories: List[Dict[str, Any]]
    trends_rising: List[Dict[str, Any]]
    trends_top: List[Dict[str, Any]]


def _require_serpapi_key() -> str:
    key = get_serpapi_api_key()
    if not key:
        raise RuntimeError(
            "SerpAPI key not configured. Add serpapi.api_key to Streamlit secrets or set SERPAPI_API_KEY."
        )
    return key


def fetch_google_news(query: str, num: int = 40, gl: str = "au", hl: str = "en", google_domain: str = "google.com.au") -> List[Dict[str, Any]]:
    key = _require_serpapi_key()
    params = {
        "api_key": key,
        "engine": "google",
        "no_cache": "true",
        "q": query,
        "google_domain": google_domain,
        "tbs": "qdr:d",
        "gl": gl,
        "hl": hl,
        "location": "Australia",
        "tbm": "nws",
        "num": str(num),
    }
    return GoogleSearch(params).get_dict().get("news_results", []) or []


def fetch_google_top_stories(query: str, gl: str = "au", hl: str = "en") -> List[Dict[str, Any]]:
    key = _require_serpapi_key()
    params = {
        "api_key": key,
        "q": query,
        "hl": hl,
        "gl": gl,
    }
    return GoogleSearch(params).get_dict().get("top_stories", []) or []


def fetch_google_trends_related_queries(
    q: str,
    geo: str = "AU",
    date: str = "now 4-H",
    tz: str = "-600",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (rising, top) related queries for a trends query or topic id."""
    key = _require_serpapi_key()
    params = {
        "api_key": key,
        "engine": "google_trends",
        "q": q,
        "geo": geo,
        "data_type": "RELATED_QUERIES",
        "tz": tz,
        "date": date,
    }

    # Simple retry to survive rate limiting
    attempts = 0
    while attempts < 3:
        try:
            results = GoogleSearch(params).get_dict()
            related = results.get("related_queries", {}) or {}
            rising = related.get("rising", []) or []
            top = related.get("top", []) or []
            return rising, top
        except Exception:
            wait = (2**attempts) * 4
            time.sleep(wait)
            attempts += 1

    return [], []


async def _grab_desc(session: httpx.AsyncClient, url: str) -> str:
    if not url or not url.startswith("http"):
        return ""
    try:
        r = await session.get(url, timeout=10, headers=BROWSER_HEADERS)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.content, "html.parser")
        tag = soup.find("meta", attrs={"name": "description"})
        if tag and tag.get("content"):
            return str(tag.get("content")).strip()
        return ""
    except Exception:
        return ""


async def fetch_meta_descriptions(urls: List[str], concurrency: int = 10) -> List[str]:
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(follow_redirects=True) as session:
        async def bound(u: str) -> str:
            async with sem:
                return await _grab_desc(session, u)
        return await asyncio.gather(*(bound(u) for u in urls))


def collect_signals(
    query: str,
    trends_query_or_topic_id: Optional[str] = None,
    limits: Optional[Dict[str, int]] = None,
) -> SignalsData:
    """Fetch signals from SerpAPI and return a normalized bundle."""
    limits = limits or {}
    news_n = int(limits.get("news", 40))
    top_n = int(limits.get("top_stories", 40))
    trends_n = int(limits.get("trends", 20))

    news = fetch_google_news(query=query, num=news_n)
    top_stories = fetch_google_top_stories(query=query)

    # trends q: allow override; fall back to query
    trends_q = (trends_query_or_topic_id or query).strip()
    rising, top = fetch_google_trends_related_queries(q=trends_q)

    # Normalize trends to a common format and cap
    def _norm_trend(x: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "query": x.get("query") or x.get("topic") or "",
            "value": x.get("value") or x.get("extracted_value") or "",
        }

    trends_rising = [_norm_trend(x) for x in rising][:trends_n]
    trends_top = [_norm_trend(x) for x in top][:trends_n]

    return SignalsData(
        query=query,
        generated_at=time.time(),
        news=news[:news_n],
        top_stories=top_stories[:top_n],
        trends_rising=trends_rising,
        trends_top=trends_top,
    )


def _format_signals_for_prompt(d: SignalsData, include_links: bool = True, max_items: int = 40) -> str:
    def _fmt_news(items: List[Dict[str, Any]], title: str) -> str:
        lines = [f"{title}:"]
        for it in items[:max_items]:
            t = it.get("title") or ""
            link = it.get("link") or ""
            snippet = it.get("snippet") or it.get("source") or ""
            if include_links:
                lines.append(f"- {t} | {link} | {snippet}")
            else:
                lines.append(f"- {t} | {snippet}")
        return "\n".join(lines)

    def _fmt_trends(items: List[Dict[str, Any]], title: str) -> str:
        lines = [f"{title}:"]
        for it in items[:max_items]:
            q = it.get("query") or ""
            v = it.get("value") or ""
            lines.append(f"- {q} | {v}")
        return "\n".join(lines)

    blocks = [
        _fmt_trends(d.trends_rising, "Google Trends (Rising related queries)"),
        _fmt_trends(d.trends_top, "Google Trends (Top related queries)"),
        _fmt_news(d.news, "Google News"),
        _fmt_news(d.top_stories, "Google Top Stories"),
    ]
    return "\n\n".join(blocks)


def summarise_daily_brief(
    d: SignalsData,
    model: str = "gpt-4o",
) -> Dict[str, Any]:
    """Return a structured daily briefing as JSON."""
    au_date = dt.datetime.now(dt.timezone(dt.timedelta(hours=10))).strftime("%Y-%m-%d")

    prompt = f"""
You are a senior marketing + editorial strategist for an Australian investing brand.

Task:
- Analyze the signals and identify what is spiking *today* for Australian investors.
- Produce a structured briefing that a marketer can turn into campaigns.

Output:
Return ONLY valid JSON (no markdown, no commentary) that matches this schema:

{{
  "run_date": "{au_date}",
  "query": "{d.query}",
  "top_trends": [{{"query": "...", "value": "...", "why_it_matters": "..."}}],
  "themes": [{{"theme": "...", "why_it_matters": "...", "evidence": ["..."], "suggested_angles": ["..."], "segments": ["..."]}}],
  "opportunities": [
    {{
      "title": "...",
      "synopsis": "...",
      "key_entities": ["..."],
      "source_links": ["..."],
      "suggested_hooks": ["..."],
      "recommended_channels": ["Email", "Paid Social", "Editorial", "Landing Page"],
      "risk_notes": ["..."]
    }}
  ],
  "notes": "..."
}}

Constraints:
- Provide exactly 10 items in top_trends (mix rising/top; if insufficient, provide as many as possible).
- Provide 5 themes maximum.
- Provide exactly 6 opportunities.
- Avoid financial advice. Avoid guarantees. Flag compliance/claim risk in risk_notes.
- Source_links must only include URLs present in the data.

Signals:
{_format_signals_for_prompt(d)}
""".strip()

    raw = query_openai([{"role": "user", "content": prompt}], model=model, temperature=0.2)
    parsed = extract_json_object(raw)
    if parsed:
        return parsed
    return {"error": "Could not parse JSON from model output", "raw": raw, "query": d.query, "run_date": au_date}


def summarise_horizon_scan(
    d: SignalsData,
    model: str = "gpt-4o",
) -> Dict[str, Any]:
    """Return a structured horizon scan: emerging themes + campaign ideas."""
    au_date = dt.datetime.now(dt.timezone(dt.timedelta(hours=10))).strftime("%Y-%m-%d")

    prompt = f"""
You are a futurist strategist for an Australian investing brand.

Task:
- Use the current signals as weak indicators.
- Predict 5 emerging investor themes (next 3-12 months) and propose campaign ideas.
- The goal is originality + plausibility, not certainty.

Return ONLY valid JSON with this schema:

{{
  "run_date": "{au_date}",
  "query": "{d.query}",
  "emerging_themes": [
    {{
      "theme": "...",
      "time_horizon": "3-12 months",
      "why_now": "...",
      "what_to_watch": ["..."],
      "investor_questions": ["..."],
      "campaign_ideas": [{{"hook": "...", "angle": "...", "channels": ["..."]}}],
      "risks": ["..."]
    }}
  ],
  "notes": "..."
}}

Constraints:
- Provide exactly 5 themes.
- Provide 3 campaign_ideas per theme.
- Avoid hype and guaranteed outcomes. Note uncertainty where appropriate.

Signals:
{_format_signals_for_prompt(d)}
""".strip()

    raw = query_openai([{"role": "user", "content": prompt}], model=model, temperature=0.25)
    parsed = extract_json_object(raw)
    if parsed:
        return parsed
    return {"error": "Could not parse JSON from model output", "raw": raw, "query": d.query, "run_date": au_date}
