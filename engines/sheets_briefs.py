"""Google Sheets-backed briefing retrieval.

This module lets the Streamlit app read the latest briefing text produced by
`step2_summarisation_with_easier_reading.py`.

The step2 script appends a single cell (column A) into the `Summaries` worksheet.
We fetch the latest non-empty value from that column and (optionally) parse it
into the "5 Detailed Briefs" blocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from utils import get_gspread_client, get_secret


DEFAULT_SPREADSHEET_ID = "1BzTJgX7OgaA0QNfzKs5AgAx2rvZZjDdorgAz0SD9NZg"
DEFAULT_WORKSHEET_TITLE = "Summaries"


@dataclass(frozen=True)
class SheetBrief:
    """A briefing fetched from Google Sheets."""

    text: str
    row_index: int  # 1-indexed row number in the worksheet
    spreadsheet_id: str
    worksheet_title: str


def _is_sep(line: str) -> bool:
    return re.fullmatch(r"\s*-{10,}\s*", line or "") is not None


def _is_star_title(line: str) -> bool:
    # e.g. *Brief Title* or **Brief Title**
    s = (line or "").strip()
    return len(s) >= 3 and s.startswith("*") and s.endswith("*") and s.count("*") >= 2


def convert_single_asterisk_to_bold(text: str) -> str:
    """Convert *single-asterisk wrapped* segments to markdown bold.

    The step2 script instructs the model to use single asterisks for "bold".
    Streamlit markdown treats single-asterisk as italics, so we convert to **bold**.

    This is intentionally conservative to avoid over-replacing.
    """

    if not text:
        return ""

    # Convert occurrences like *Synopsis* -> **Synopsis**
    # Avoid matching already-bolded **...** by requiring the asterisk not adjacent to another.
    pattern = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
    return pattern.sub(lambda m: f"**{m.group(1)}**", text)


def parse_step2_report(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Parse step2 report into summary text + brief blocks.

    Returns:
      - summary_text: everything before the '5 Detailed Briefs for Journalists' header
      - briefs: list of {title, body}

    Parsing is best-effort; if the expected structure isn't found, returns the
    whole text as summary_text and an empty briefs list.
    """

    if not text or not text.strip():
        return "", []

    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")

    # Find the header block for "5 Detailed Briefs for Journalists"
    hdr_start = None
    for i in range(0, max(0, len(lines) - 2)):
        if _is_sep(lines[i]) and _is_star_title(lines[i + 1]) and _is_sep(lines[i + 2]):
            title = lines[i + 1].strip("*").strip()
            if "detailed briefs" in title.lower():
                hdr_start = i
                break

    if hdr_start is None:
        return raw.strip(), []

    summary_text = "\n".join(lines[:hdr_start]).strip()

    # After the header triple, briefs begin.
    i = hdr_start + 3
    briefs: List[Dict[str, str]] = []

    while i < len(lines) - 2:
        if _is_sep(lines[i]) and _is_star_title(lines[i + 1]) and _is_sep(lines[i + 2]):
            title = lines[i + 1].strip("*").strip()

            # Skip accidental repeat of the header title if present.
            if "detailed briefs" in title.lower():
                i += 3
                continue

            body_start = i + 3

            # Find next brief header triple.
            j = body_start
            while j < len(lines) - 2:
                if _is_sep(lines[j]) and _is_star_title(lines[j + 1]) and _is_sep(lines[j + 2]):
                    break
                j += 1

            body = "\n".join(lines[body_start:j]).strip()
            if title:
                briefs.append({"title": title, "body": body})
            i = j
        else:
            i += 1

    return summary_text, briefs


@st.cache_resource(show_spinner=False)
def _gs_client():
    return get_gspread_client()


def fetch_latest_step2_brief(
    spreadsheet_id: Optional[str] = None,
    worksheet_title: str = DEFAULT_WORKSHEET_TITLE,
) -> Dict[str, Any]:
    """Fetch the latest step2 summary text from Google Sheets.

    Secrets supported (optional):
      - briefs.spreadsheet_id
      - briefs.worksheet_title
    """

    sid = (
        spreadsheet_id
        or get_secret("briefs.spreadsheet_id")
        or get_secret("briefings.spreadsheet_id")
        or DEFAULT_SPREADSHEET_ID
    )

    ws_title = (
        get_secret("briefs.worksheet_title")
        or get_secret("briefings.worksheet_title")
        or worksheet_title
        or DEFAULT_WORKSHEET_TITLE
    )

    client = _gs_client()
    if client is None:
        return {
            "error": (
                "Google Sheets access is not configured. Add a `service_account` block to "
                "Streamlit secrets so the app can read the Summaries worksheet."
            )
        }

    try:
        sh = client.open_by_key(sid)
        ws = sh.worksheet(ws_title)

        # Column A contains the appended summaries.
        col = ws.col_values(1)
        for idx in range(len(col) - 1, -1, -1):
            v = (col[idx] or "").strip()
            if v:
                return {
                    "brief": SheetBrief(
                        text=v,
                        row_index=idx + 1,
                        spreadsheet_id=sid,
                        worksheet_title=ws_title,
                    )
                }

        return {"error": f"No briefing rows found in worksheet '{ws_title}'."}
    except Exception as e:
        return {"error": str(e)}
