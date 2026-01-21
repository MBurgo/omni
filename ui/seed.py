"""Session-state seed helpers.

These helpers centralise how one tool hands context to another.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st


def set_copywriter_seed(
    *,
    mode: str = "generate",
    hook: str = "",
    details: str = "",
    creative: str = "",
    source: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Seed the Copywriter page.

    Keys used by pages/06_Write_campaign_assets.py:
      - seed_hook
      - seed_details
      - seed_creative
      - copywriter_mode  (generate|revise|adapt)

    This function intentionally overwrites the seed fields to keep handoffs clean.
    """

    st.session_state["seed_hook"] = (hook or "").strip()
    st.session_state["seed_details"] = (details or "").strip()
    st.session_state["seed_creative"] = (creative or "").strip()

    m = (mode or "generate").strip().lower()
    if m not in {"generate", "revise", "adapt"}:
        m = "generate"
    st.session_state["copywriter_mode"] = m

    if source:
        st.session_state["seed_source"] = str(source)

    if metadata is not None:
        st.session_state["seed_metadata"] = metadata
