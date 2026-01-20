from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import streamlit as st

from utils import get_gemini_client, get_openai_client


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from model output."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    blob = text[start : end + 1]
    try:
        return json.loads(blob)
    except Exception:
        return None


def query_openai(
    messages: List[Dict[str, str]],
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> str:
    client = get_openai_client()
    if client is None:
        return "Error: OpenAI client not configured. Add openai.api_key to Streamlit secrets or set OPENAI_API_KEY."

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"Error: {e}"


def query_gemini(prompt: str, model_name: str = "gemini-1.5-pro") -> str:
    gemini = get_gemini_client()
    if gemini is None:
        # Fallback to OpenAI
        return query_openai([{"role": "user", "content": prompt}], model="gpt-4o")

    try:
        model = gemini.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        st.warning(f"Gemini error: {e}. Falling back to OpenAI.")
        return query_openai([{"role": "user", "content": prompt}], model="gpt-4o")
