"""
data_retrieval_storage_news_engine.py
------------------------------------
Refactored for Portal Integration
"""

import asyncio
import datetime as dt
import time
from typing import List
import gspread
import httpx
from bs4 import BeautifulSoup
import streamlit as st
from google.oauth2.service_account import Credentials
# NOTE: We use the google-search-results library, but the import is 'serpapi'
from serpapi import GoogleSearch 
from utils import get_gspread_client 

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
CAP_NEWS         = 40   
CAP_TOP_STORIES  = 40   
CAP_TRENDS       = 20   
DEBUG_COUNTS     = False  

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SPREADSHEET_ID = "1BzTJgX7OgaA0QNfzKs5AgAx2rvZZjDdorgAz0SD9NZg"

# ---------------------------------------------------------------------
# 1. SerpAPI Fetch Helpers (Lazy Loaded)
# ---------------------------------------------------------------------
def get_api_key():
    """Safely get the API key only when needed."""
    return st.secrets["serpapi"]["api_key"]

def fetch_google_news() -> List[dict]:
    params = {
        "api_key": get_api_key(),
        "engine": "google",
        "no_cache": "true",
        "q": "asx 200",
        "google_domain": "google.com.au",
        "tbs": "qdr:d",
        "gl": "au",
        "hl": "en",
        "location": "Australia",
        "tbm": "nws",
        "num": "40",
    }
    return GoogleSearch(params).get_dict().get("news_results", [])

def fetch_google_top_stories() -> List[dict]:
    params = {
        "api_key": get_api_key(),
        "q": "asx+200",
        "hl": "en",
        "gl": "au",
    }
    return GoogleSearch(params).get_dict().get("top_stories", [])

def fetch_google_trends():
    params = {
        "api_key": get_api_key(),
        "engine": "google_trends",
        "q": "/m/0bl5c2",
        "geo": "AU",
        "data_type": "RELATED_QUERIES",
        "tz": "-600",
        "date": "now 4-H",
    }

    attempts = 0
    # Use the lazy import here to avoid top-level dependency issues if installed late
    from pytrends.exceptions import TooManyRequestsError
    
    while attempts < 5:
        try:
            results = GoogleSearch(params).get_dict()
            rising = results.get("related_queries", {}).get("rising", [])
            top    = results.get("related_queries", {}).get("top",    [])
            return rising, top
        except TooManyRequestsError:
            wait = (2 ** attempts) * 10
            print(f"Google Trends rate-limited – sleeping {wait}s")
            time.sleep(wait)
            attempts += 1
        except Exception as e:
            # Fallback for generic errors to prevent hard crash
            print(f"Trend fetch error: {e}")
            return [], []
            
    return [], [] # Return empty if failed

# ---------------------------------------------------------------------
# 2. Worksheet Utilities
# ---------------------------------------------------------------------
def ensure_worksheet_exists(sheet_obj, title: str):
    try:
        return sheet_obj.worksheet(title)
    except gspread.exceptions.WorksheetNotFound:
        return sheet_obj.add_worksheet(title=title, rows="100", cols="20")

def overwrite_worksheet(ws, header: List[str], rows: List[List]):
    ws.resize(rows=len(rows) + 1, cols=len(header))
    ws.update(
        range_name="A1",
        values=[header] + rows,
        value_input_option="USER_ENTERED",
    )

# ---------------------------------------------------------------------
# 3. Data Hygiene Helpers
# ---------------------------------------------------------------------
def dedupe_rows(rows: List[List], key_index: int, keep_n: int) -> List[List]:
    seen, out = set(), []
    for row in rows:
        key = row[key_index]
        if key not in seen:
            seen.add(key)
            out.append(row)
        if len(out) >= keep_n:
            break
    return out

# ---------------------------------------------------------------------
# 4. Async Meta Fetch
# ---------------------------------------------------------------------
async def _grab_desc(session: httpx.AsyncClient, url: str) -> str:
    if not url or not url.startswith("http"):
        return "Invalid URL"
    try:
        r = await session.get(url, timeout=10, headers=BROWSER_HEADERS)
        if r.status_code != 200:
            return f"HTTP {r.status_code}"
        soup = BeautifulSoup(r.content, "lxml")
        tag  = soup.find("meta", attrs={"name": "description"})
        return (
            tag["content"].strip()
            if tag and "content" in tag.attrs and tag["content"].strip()
            else "No Meta Description"
        )
    except Exception:
        return "Error Fetching Description"

async def fetch_meta_descriptions(urls: List[str], limit: int = 10) -> List[str]:
    sem = asyncio.Semaphore(limit)
    async with httpx.AsyncClient(follow_redirects=True) as session:
        async def bound(u):
            async with sem:
                return await _grab_desc(session, u)
        return await asyncio.gather(*(bound(u) for u in urls))

# ---------------------------------------------------------------------
# 5. Storage Orchestrator
# ---------------------------------------------------------------------
def store_data_in_google_sheets(sheet, news_data, top_stories_data, rising_data, top_data):
    # ---------- Google News ----------
    news_rows = [
        [a.get("title") or "No Title",
         a.get("link")  or "No Link",
         a.get("snippet") or "No Snippet"]
        for a in news_data
    ]
    
    news_rows = dedupe_rows(news_rows, key_index=1, keep_n=CAP_NEWS)
    snippet_lookup_news = {r[1]: r[2] for r in news_rows}

    # Use a new loop just for metadata to ensure async loop is managed correctly
    try:
        news_meta = asyncio.run(fetch_meta_descriptions([r[1] for r in news_rows]))
    except RuntimeError:
        # If an event loop is already running (Streamlit sometimes does this), fallback
        news_meta = ["No Meta (Async Error)"] * len(news_rows)

    for row, meta in zip(news_rows, news_meta):
        row.append(meta if meta else "No Meta Description")
        if meta.startswith("HTTP") or meta.startswith("Error"):
            row[-1] = snippet_lookup_news.get(row[1], "No Meta Description")

    overwrite_worksheet(
        ensure_worksheet_exists(sheet, "Google News"),
        ["Title", "Link", "Snippet", "Meta Description"],
        news_rows,
    )

    # ---------- Top Stories ----------
    top_rows = [
        [s.get("title") or "No Title",
         s.get("link")  or "No Link",
         s.get("snippet") or "No Snippet"]
        for s in top_stories_data
    ]
    
    top_rows = dedupe_rows(top_rows, key_index=1, keep_n=CAP_TOP_STORIES)
    snippet_lookup_top = {r[1]: r[2] for r in top_rows}

    try:
        top_meta = asyncio.run(fetch_meta_descriptions([r[1] for r in top_rows]))
    except RuntimeError:
        top_meta = ["No Meta (Async Error)"] * len(top_rows)
        
    for row, meta in zip(top_rows, top_meta):
        row.append(meta if meta else "No Meta Description")
        if meta.startswith("HTTP") or meta.startswith("Error"):
            row[-1] = snippet_lookup_top.get(row[1], "No Meta Description")

    overwrite_worksheet(
        ensure_worksheet_exists(sheet, "Top Stories"),
        ["Title", "Link", "Snippet", "Meta Description"],
        top_rows,
    )

    # ---------- Google Trends Rising ----------
    rising_rows = [[q.get("query"), q.get("value")] for q in rising_data][:CAP_TRENDS]
    overwrite_worksheet(
        ensure_worksheet_exists(sheet, "Google Trends Rising"),
        ["Query", "Value"],
        rising_rows,
    )

    # ---------- Google Trends Top ----------
    top_rows_q = [[q.get("query"), q.get("value")] for q in top_data][:CAP_TRENDS]
    overwrite_worksheet(
        ensure_worksheet_exists(sheet, "Google Trends Top"),
        ["Query", "Value"],
        top_rows_q,
    )

# ---------------------------------------------------------------------
# 6. Main Entry Point
# ---------------------------------------------------------------------
def main():
    # Initialize connection ONLY when function is called
    client = get_gspread_client()
    sheet = client.open_by_key(SPREADSHEET_ID)
    
    now_utc = dt.datetime.now(dt.timezone.utc)
    print(f"=== Data scrape started {now_utc.isoformat(timespec='seconds')}Z ===")

    news_data        = fetch_google_news()
    top_stories_data = fetch_google_top_stories()
    rising_data, top_data = fetch_google_trends()

    store_data_in_google_sheets(sheet, news_data, top_stories_data, rising_data, top_data)
    print("=== Data scrape finished ===")

if __name__ == "__main__":
    main()
