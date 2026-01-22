from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import streamlit as st

from model_registry import DEFAULT_GEMINI_MODEL, DEFAULT_OPENAI_MODEL
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
        obj = json.loads(blob)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def query_openai(
    messages: List[Dict[str, str]],
    model: str = DEFAULT_OPENAI_MODEL,
    temperature: float = 0.7,
    response_format: Optional[Dict[str, Any]] = None,
    max_tokens: Optional[int] = None,
) -> str:
    client = get_openai_client()
    if client is None:
        return (
            "Error: OpenAI client not configured. Add openai.api_key to Streamlit secrets or set OPENAI_API_KEY."
        )

    try:
        kwargs: Dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if response_format is not None:
            kwargs["response_format"] = response_format
        if max_tokens is not None:
            kwargs["max_tokens"] = int(max_tokens)

        resp = client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"Error: {e}"


def sanitize_json_text(text: str) -> str:
    """Strip common markdown wrappers around JSON."""
    t = (text or "").strip()
    if not t:
        return ""
    t = t.replace("```json", "").replace("```", "").strip()
    return t


def parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON object from model output.

    Tries strict parsing first, then falls back to best-effort extraction.
    """
    cleaned = sanitize_json_text(text)
    if not cleaned:
        return None
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return extract_json_object(cleaned)


def query_gemini(prompt: str, model_name: str = DEFAULT_GEMINI_MODEL) -> str:
    """Simple Gemini helper (single prompt)."""
    return query_gemini_chat(
        system_instruction="",
        user_prompt=prompt,
        model_name=model_name,
        temperature=0.7,
        max_output_tokens=4096,
        expect_json=False,
    )


def query_gemini_chat(
    *,
    system_instruction: str,
    user_prompt: str,
    model_name: str = DEFAULT_GEMINI_MODEL,
    temperature: float = 0.7,
    max_output_tokens: int = 4096,
    expect_json: bool = False,
) -> str:
    """Gemini chat helper with optional JSON-mode.

    If Gemini is not configured, this falls back to OpenAI.
    """

    gemini = get_gemini_client()
    if gemini is None:
        # Fallback to OpenAI
        return query_openai(
            [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}],
            model=DEFAULT_OPENAI_MODEL,
        )

    # Safety settings (avoid overly aggressive blocks for marketing copy)
    safety_settings = None
    try:
        from google.generativeai.types import HarmBlockThreshold, HarmCategory

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
    except Exception:
        safety_settings = None

    try:
        gen_config = gemini.GenerationConfig(
            temperature=float(temperature),
            max_output_tokens=int(max_output_tokens),
            response_mime_type="application/json" if expect_json else "text/plain",
        )

        model = gemini.GenerativeModel(model_name, system_instruction=system_instruction or "")
        resp = model.generate_content(user_prompt, generation_config=gen_config, safety_settings=safety_settings)
        return (getattr(resp, "text", "") or "").strip()
    except Exception as e:
        st.warning(f"Gemini error: {e}. Falling back to OpenAI.")
        return query_openai(
            [{"role": "system", "content": system_instruction}, {"role": "user", "content": user_prompt}],
            model=DEFAULT_OPENAI_MODEL,
        )
