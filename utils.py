"""Shared utilities for the Goal-First AI Portal.

Keep this module small and stable to avoid circular imports.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import streamlit as st

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None

from ui.branding import apply_branding

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:  # pragma: no cover
    gspread = None
    Credentials = None


def _get_from_secrets(path: str) -> Optional[Any]:
    """Get a value from st.secrets using dot-separated path.

    Important: `st.secrets` is a Streamlit "Secrets" object, not always a plain
    `dict`. On Streamlit Cloud in particular, checking `isinstance(..., dict)`
    can fail even though the object is subscriptable. We therefore walk the path
    using `__getitem__` with exception handling.
    """
    try:
        cur: Any = st.secrets
        for part in path.split("."):
            try:
                cur = cur[part]  # type: ignore[index]
            except Exception:
                return None
        return cur
    except Exception:
        return None


def get_secret(path: str, default: Optional[str] = None) -> Optional[str]:
    """Fetch a secret from st.secrets or environment variables.

    Supports dot-paths like:
      - openai.api_key
      - serpapi.api_key

    Environment variable fallback:
      - OPENAI_API_KEY
      - SERPAPI_API_KEY
    """

    v = _get_from_secrets(path)
    if v is not None and str(v).strip():
        return str(v).strip()

    env_key = path.upper().replace(".", "_")
    v2 = os.getenv(env_key)
    if v2 and v2.strip():
        return v2.strip()

    return default


def get_openai_client() -> Optional[OpenAI]:
    """Return an OpenAI client if configured, else None."""
    if OpenAI is None:
        return None

    api_key = get_secret("openai.api_key") or get_secret("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def get_gemini_client() -> Optional[Any]:
    """Return a configured google.generativeai module if available."""
    if genai is None:
        return None

    api_key = get_secret("google.api_key") or get_secret("GOOGLE_API_KEY")
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        return genai
    except Exception:
        return None


def get_serpapi_api_key() -> Optional[str]:
    return get_secret("serpapi.api_key") or get_secret("SERPAPI_API_KEY")


def get_gspread_client() -> Optional[Any]:
    """Return an authorised gspread client if configured, else None.

    Expects a `service_account` object in Streamlit secrets that contains the
    JSON fields for a Google service account.
    """

    if gspread is None or Credentials is None:
        return None

    sa = _get_from_secrets("service_account")
    if not sa:
        return None

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        creds = Credentials.from_service_account_info(sa, scopes=scope)
        return gspread.authorize(creds)
    except Exception:
        return None
