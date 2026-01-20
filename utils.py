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


def _get_from_secrets(path: str) -> Optional[Any]:
    """Get a value from st.secrets using dot-separated path."""
    try:
        cur: Any = st.secrets
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
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
