"""Step 2: Summarise Signals sheet data into a human-friendly briefing.

This module is used by the Streamlit portal (pages/01_Find_spikes_today.py).

Key changes vs the original script:
- No secrets are read at import time (so the app can load without hard-crashing)
- Google Sheets + OpenAI clients are resolved lazily inside functions
- Missing configuration raises clear RuntimeError messages
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Optional

import pandas as pd
import pytz

from utils import get_gspread_client, get_openai_client, get_secret

DEFAULT_SPREADSHEET_ID = "1BzTJgX7OgaA0QNfzKs5AgAx2rvZZjDdorgAz0SD9NZg"
DEFAULT_MODEL = "gpt-4o"


def get_spreadsheet_id() -> str:
    """Return the spreadsheet id used by the Signals pipeline.

    Allows overriding via:
      - secrets: [signals] spreadsheet_id
      - env: SIGNALS_SPREADSHEET_ID
    """

    return (
        get_secret("signals.spreadsheet_id")
        or get_secret("SIGNALS_SPREADSHEET_ID")
        or DEFAULT_SPREADSHEET_ID
    )


def get_sheet():
    """Return an open gspread Spreadsheet instance (or raise with a friendly message)."""

    client = get_gspread_client()
    if client is None:
        raise RuntimeError(
            "Google Sheets client not configured. Add a service_account block to Streamlit secrets "
            "(see .streamlit/secrets.toml.example)."
        )

    sid = get_spreadsheet_id()
    try:
        return client.open_by_key(sid)
    except Exception as e:
        raise RuntimeError(f"Could not open Google Sheet: {sid}. {e}")


def get_openai():
    """Return a configured OpenAI client (or raise with a friendly message)."""

    client = get_openai_client()
    if client is None:
        raise RuntimeError(
            "OpenAI client not configured. Add openai.api_key to Streamlit secrets or set OPENAI_API_KEY."
        )
    return client


def read_data(sheet, title: str) -> pd.DataFrame:
    """Reads data from a specified Google Sheet worksheet into a pandas DataFrame."""

    try:
        worksheet = sheet.worksheet(title)
    except Exception as e:
        raise RuntimeError(f"Worksheet not found (or not accessible): '{title}'. {e}")

    data = worksheet.get_all_records()
    return pd.DataFrame(data)


def format_data_for_prompt(
    news_data: pd.DataFrame,
    top_stories_data: pd.DataFrame,
    rising_data: pd.DataFrame,
    top_data: pd.DataFrame,
) -> str:
    """Format Signals sheet data into a single prompt string."""

    formatted_data = "Google News Data:\n"
    for _, row in news_data.iterrows():
        formatted_data += (
            f"- Title: {row.get('Title', '')}, Link: {row.get('Link', '')}, "
            f"Snippet: {row.get('Snippet', '')}\n"
        )

    formatted_data += "\nTop Stories Data:\n"
    for _, row in top_stories_data.iterrows():
        formatted_data += (
            f"- Title: {row.get('Title', '')}, Link: {row.get('Link', '')}, "
            f"Snippet: {row.get('Snippet', '')}\n"
        )

    formatted_data += "\nGoogle Trends Rising Data:\n"
    for _, row in rising_data.iterrows():
        formatted_data += f"- Query: {row.get('Query', '')}, Value: {row.get('Value', '')}\n"

    formatted_data += "\nGoogle Trends Top Data:\n"
    for _, row in top_data.iterrows():
        formatted_data += f"- Query: {row.get('Query', '')}, Value: {row.get('Value', '')}\n"

    return formatted_data


def summarize_data(formatted_data: str, model: str = DEFAULT_MODEL) -> str:
    """Summarise data using OpenAI."""

    local_tz = pytz.timezone("Australia/Sydney")
    now_local = dt.datetime.now(local_tz)
    current_date = now_local.strftime("%Y-%m-%d")

    system_like_context = (
        "You are a seasoned financial news editor for an Australian financial news publisher. "
        "Your responsibilities include analyzing financial data and news sources to identify "
        "key trends, notable events, and opportunities for in-depth reporting. "
        "You provide insightful summaries and detailed briefs to help financial journalists "
        "craft stories that inform and engage retail investors and industry professionals. "
        "Your communication style is clear, concise, and analytical, with a focus on accuracy "
        "and relevance. You use industry-specific terminology appropriately and maintain an "
        "objective tone.\n\n"
    )

    instructions = (
        f"As a news editor for an Australian financial news publisher, your task is to analyze "
        f"and summarize the latest data from various sources related to the Australian stock market. "
        f"Your goal is to identify key trends, recurring themes, and interesting opportunities for "
        f"our financial journalists to cover.\n\n"
        f"Using the provided data, please perform the following tasks:\n"
        f"1. Analyze the \"Google Trends Rising\" data to identify the top 10 rising search queries, "
        f"paying special attention to high-volume queries and those marked as 'Breakout'.\n"
        f"2. Analyze the \"Google Trends Top\" data to identify the top search queries.\n"
        f"3. Review the articles from \"Google News\" to identify recurring themes and notable entities.\n"
        f"4. Review the articles from \"Top Stories\" for the query \"ASX 200\" to identify significant news stories.\n\n"
        f"Please include the following sections in your report using plain text with single asterisks (*) "
        f"for bold text. Use lines of hyphens (\"-\" repeated) to create horizontal lines as separators "
        f"before and after major sections and brief titles. Do not use Markdown headers or `###`.\n\n"
        f"Include the date of summarization ({current_date}) in your report.\n\n"
        f"The report should have the following structure:\n\n"
        f"--------------------------------------------------\n"
        f"*Summary of Findings [{current_date}]*\n"
        f"--------------------------------------------------\n"
        f"*Google Trends Insights*: List the top 10 trends from the \"Google Trends Rising\" data, along with their volumes.\n\n"
        f"*Key Trends & Recurring Themes*: Identify the top 5 trends with brief descriptions and their volumes.\n\n"
        f"*Notable Entities*: List key companies, institutions, and market insights discussed in the data.\n\n"
        f"--------------------------------------------------\n"
        f"*5 Detailed Briefs for Journalists*\n"
        f"--------------------------------------------------\n\n"
        f"For each brief, use the following structure, separated by horizontal lines:\n\n"
        f"--------------------------------------------------\n"
        f"*Brief Title*\n"
        f"--------------------------------------------------\n"
        f"1. *Synopsis*: Brief summary of the findings.\n"
        f"2. *Key Themes*: Main themes identified in the data.\n"
        f"3. *Entities*: Relevant companies, indexes, or key individuals.\n"
        f"4. *Source Insights*: Data sources these insights come from.\n"
        f"5. *Suggested Angles*: Recommended angles for journalists to pursue.\n\n"
        f"Include emojis at the beginning of important sections to visually highlight them. "
        f"Do not use Markdown headers or `###`.\n"
    )

    big_prompt = (
        f"{system_like_context}"
        f"{instructions}\n"
        f"Here is the data to analyze:\n\n"
        f"{formatted_data}"
    )

    messages = [{"role": "user", "content": big_prompt}]

    client = get_openai()
    try:
        resp = client.chat.completions.create(
            model=model or DEFAULT_MODEL,
            messages=messages,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        raise RuntimeError(f"OpenAI error: {e}")


def store_summary_in_google_sheets(sheet, summary: str) -> None:
    """Append the summary to a 'Summaries' worksheet (creating it if needed)."""

    if not summary or not str(summary).strip():
        raise RuntimeError("Cannot store empty summary.")

    try:
        summary_sheet = sheet.worksheet("Summaries")
    except Exception:
        # Create on demand
        summary_sheet = sheet.add_worksheet(title="Summaries", rows="2000", cols="2")

    summary_sheet.append_row([summary])
    time.sleep(1)  # Delay to prevent exceeding quota


def generate_summary(model: str = DEFAULT_MODEL) -> str:
    """Pull data from Google Sheets, summarise, store it, and return the summary text."""

    sheet = get_sheet()

    news_data = read_data(sheet, "Google News")
    top_stories_data = read_data(sheet, "Top Stories")
    rising_data = read_data(sheet, "Google Trends Rising")
    top_data = read_data(sheet, "Google Trends Top")

    formatted_data = format_data_for_prompt(news_data, top_stories_data, rising_data, top_data)

    summary = summarize_data(formatted_data, model=model)

    store_summary_in_google_sheets(sheet, summary)

    return summary


def main() -> None:
    generate_summary()


if __name__ == "__main__":
    main()
