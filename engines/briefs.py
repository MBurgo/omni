from __future__ import annotations

from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

from engines.llm import parse_json_object, query_gemini_chat, query_openai
from model_registry import DEFAULT_GEMINI_MODEL, DEFAULT_OPENAI_FAST_MODEL


BRIEF_KEYS: Tuple[str, ...] = (
    "hook",
    "details",
    "offer_price",
    "retail_price",
    "offer_term",
    "reports",
    "stocks_to_tease",
    "quotes_news",
)


def _ensure_str(x: Any) -> str:
    return str(x).strip() if x is not None else ""


def coerce_brief(obj: Any) -> Dict[str, str]:
    """Coerce arbitrary object into a brief dict with stable keys."""
    d = obj if isinstance(obj, dict) else {}
    out: Dict[str, str] = {}
    for k in BRIEF_KEYS:
        out[k] = _ensure_str(d.get(k))
    return out


def _provider_call_json(
    *,
    provider: str,
    openai_model: str,
    gemini_model: str,
    system_instruction: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Call the selected provider and attempt to parse JSON.

    Returns (parsed_json_or_none, raw_text).
    """
    provider = (provider or "OpenAI").strip()
    raw = ""

    if provider.lower() == "gemini":
        raw = query_gemini_chat(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            model_name=gemini_model or DEFAULT_GEMINI_MODEL,
            temperature=temperature,
            max_output_tokens=max_tokens,
            expect_json=True,
        )
        return parse_json_object(raw), raw

    raw = query_openai(
        [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt},
        ],
        model=openai_model or DEFAULT_OPENAI_FAST_MODEL,
        temperature=temperature,
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
    )
    return parse_json_object(raw), raw


def extract_campaign_brief_from_text(
    *,
    text: str,
    provider: str = "OpenAI",
    openai_model: str = DEFAULT_OPENAI_FAST_MODEL,
    gemini_model: str = DEFAULT_GEMINI_MODEL,
) -> Dict[str, Any]:
    """Extract a structured campaign brief from messy input text."""

    src = (text or "").strip()
    if not src:
        return {"error": "No input text provided.", "brief": coerce_brief({}), "raw": ""}

    system = dedent(
        """
        You convert messy campaign notes into a structured direct-response marketing brief.

        Return ONLY valid JSON.

        Rules:
        - Do not invent facts.
        - If information is missing, use an empty string.
        - Keep fields concise but usable by a copywriter.
        """
    ).strip()

    user = dedent(
        f"""
        Extract these fields from the input:

        {", ".join(BRIEF_KEYS)}

        Input:
        ---
        {src}
        ---

        Return a single JSON object with exactly those keys.
        """
    ).strip()

    obj, raw = _provider_call_json(
        provider=provider,
        openai_model=openai_model,
        gemini_model=gemini_model,
        system_instruction=system,
        user_prompt=user,
        temperature=0.1,
        max_tokens=1400,
    )

    if not isinstance(obj, dict):
        return {
            "error": "Could not parse JSON from the model response.",
            "brief": coerce_brief({}),
            "raw": raw,
        }

    return {"brief": coerce_brief(obj), "raw": raw}


def brief_builder_turn(
    *,
    chat_history: List[Dict[str, str]],
    current_brief: Dict[str, str],
    provider: str = "OpenAI",
    openai_model: str = DEFAULT_OPENAI_FAST_MODEL,
    gemini_model: str = DEFAULT_GEMINI_MODEL,
    copy_type: str = "Email",
    length_choice: str = "Medium (200-500 words)",
    country: str = "Australia",
) -> Dict[str, Any]:
    """Single turn of the dialogue-first brief builder.

    The model:
      - updates the brief
      - asks ONE next question (or says "Ready")
      - sets is_ready when enough to generate copy

    Returns:
      {brief: {...}, next_question: str, is_ready: bool, raw: str, error?: str}
    """

    brief = coerce_brief(current_brief)

    system = dedent(
        """
        You are a senior direct-response marketing strategist helping a marketer build a campaign brief.
        Your job is to meet them halfway.

        Return ONLY valid JSON with this schema:
        {
          "brief": { ... },
          "next_question": "string",
          "is_ready": true|false
        }

        Constraints:
        - Ask at most ONE question at a time.
        - Keep questions short and specific.
        - Do not ask for everything; focus on the 3–6 most important missing pieces.
        - Do not invent facts; keep unknown fields as empty strings.
        - Avoid financial advice.
        """
    ).strip()

    # Keep history short to avoid token blowouts.
    history = chat_history[-12:] if isinstance(chat_history, list) else []

    hist_text = "\n".join([f"{m.get('role','user')}: {m.get('content','')}" for m in history]).strip()

    user = dedent(
        f"""
        Context:
        - copy_type: {copy_type}
        - length_choice: {length_choice}
        - country: {country}

        Current brief JSON:
        {brief}

        Conversation so far:
        {hist_text}

        Task:
        1) Update the brief using the latest user message.
        2) Decide if we have enough to generate copy (is_ready).
        3) If not ready, ask the single next best question.
           If ready, set next_question to "Ready".
        """
    ).strip()

    obj, raw = _provider_call_json(
        provider=provider,
        openai_model=openai_model,
        gemini_model=gemini_model,
        system_instruction=system,
        user_prompt=user,
        temperature=0.2,
        max_tokens=1200,
    )

    if not isinstance(obj, dict):
        return {
            "error": "Could not parse JSON from the model response.",
            "brief": brief,
            "next_question": "Could you rephrase that in one sentence?",
            "is_ready": False,
            "raw": raw,
        }

    new_brief = coerce_brief(obj.get("brief"))
    next_q = _ensure_str(obj.get("next_question")) or "What are you promoting, and who is it for?"
    is_ready = bool(obj.get("is_ready"))

    return {"brief": new_brief, "next_question": next_q, "is_ready": is_ready, "raw": raw}
