"""Central model lists + defaults.

This file exists to avoid hardcoding model ids across multiple pages/engines.
"""

from __future__ import annotations

from typing import List

# ---- OpenAI ----
OPENAI_CHAT_MODELS: List[str] = [
    "gpt-4.1",
    "o3",
    "gpt-4o",
    "gpt-4o-mini",
]

DEFAULT_OPENAI_MODEL: str = "gpt-4.1"
DEFAULT_OPENAI_FAST_MODEL: str = "gpt-4o-mini"

# ---- Gemini ----
#
# NOTE: gemini-1.5-* models were shut down on 2025-09-29 and should not be used.
# Keep this list to models that are expected to be available via the Gemini API.
GEMINI_MODELS_RECOMMENDED: List[str] = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

DEFAULT_GEMINI_MODEL: str = "gemini-2.5-pro"
DEFAULT_GEMINI_FAST_MODEL: str = "gemini-2.5-flash"
DEFAULT_GEMINI_CHEAP_MODEL: str = "gemini-2.5-flash-lite"


def coerce_openai_model(model: str | None) -> str:
    m = (model or "").strip()
    return m if m else DEFAULT_OPENAI_MODEL


def coerce_gemini_model(model: str | None) -> str:
    m = (model or "").strip()
    return m if m else DEFAULT_GEMINI_MODEL
