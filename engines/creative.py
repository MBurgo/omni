from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

from engines.llm import parse_json_object, query_gemini_chat, query_openai, sanitize_json_text
from model_registry import (
    DEFAULT_GEMINI_CHEAP_MODEL,
    DEFAULT_GEMINI_FAST_MODEL,
    DEFAULT_GEMINI_MODEL,
)


MAX_OUTPUT_TOKENS = 4096

DISCLAIMER_LINE = "*Past performance is not a reliable indicator of future results.*"


LENGTH_RULES = {
    "Short (100-200 words)": (100, 220),
    "Medium (200-500 words)": (200, 550),
    "Long (500-1500 words)": (500, 1600),
    "Extra Long (1500-3000 words)": (1500, 3200),
    "Scrolling Monster (3000+ words)": (3000, None),
}

COUNTRY_RULES = {
    "Australia": "Use Australian English, prices in AUD, reference the ASX.",
    "United Kingdom": "Use British English, prices in GBP, reference the FTSE.",
    "Canada": "Use Canadian English, prices in CAD, reference the TSX.",
    "United States": "Use American English, prices in USD, reference the S&P 500.",
}

EMAIL_STRUCT = """
### Subject Line
### Greeting
### Body (benefits, urgency, proofs)
### Call-to-Action
### Sign-off
""".strip()

SALES_STRUCT = """
## Headline
### Introduction
### Key Benefit Paragraphs
### Detailed Body
### Call-to-Action
""".strip()

ADS_STRUCT = """
### Ad Headline
### Primary Text
### CTA
""".strip()

SYSTEM_PROMPT = dedent(
    """
    You are The Motley Fool's senior direct-response copy chief.

    - Voice: plain English, optimistic, inclusive, lightly playful but always expert.
    - Use Markdown headings (##, ###) and standard '-' bullets for lists.
    - Never promise guaranteed returns; keep compliance in mind.
    - Return ONLY the requested copy - no meta commentary.

    {country_rules}

    At the very end of the piece, append this italic line (no quotes):
    {disclaimer_line}
    """
).strip()


def _line(label: str, value: str) -> str:
    v = (value or "").strip()
    return f"- {label}: {v}\n" if v else ""


def _offer_line(brief: Dict[str, str]) -> str:
    offer_price = (brief.get("offer_price") or "").strip()
    retail_price = (brief.get("retail_price") or "").strip()
    term = (brief.get("offer_term") or "").strip()

    if not (offer_price or retail_price or term):
        return ""

    parts = []
    if offer_price:
        parts.append(f"Special {offer_price}")
    if retail_price:
        parts.append(f"Retail {retail_price}")
    if term:
        parts.append(f"Term {term}")
    return _line("Offer", ", ".join(parts))


def _structure_for_copy_type(copy_type: str) -> str:
    if copy_type == "Email":
        return EMAIL_STRUCT
    if copy_type == "Sales Page":
        return SALES_STRUCT
    return ADS_STRUCT


def load_trait_config(path: str = "traits_config.json") -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def trait_rules(traits: Dict[str, int], trait_cfg: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for name, score in traits.items():
        cfg = trait_cfg.get(name)
        if not cfg:
            continue
        if score >= cfg.get("high_threshold", 8):
            out.append(cfg.get("high_rule", ""))
        elif score <= cfg.get("low_threshold", 3):
            out.append(cfg.get("low_rule", ""))
        else:
            mid = cfg.get("mid_rule")
            if mid:
                out.append(mid)
    return [x for x in out if str(x).strip()]


def build_user_prompt(
    copy_type: str,
    brief: Dict[str, str],
    traits: Dict[str, int],
    length_choice: str,
    trait_cfg: Dict[str, Any],
    original_copy: Optional[str] = None,
    extra_instructions: str = "",
) -> str:
    struct = _structure_for_copy_type(copy_type)

    # Hard requirements
    hard_list = trait_rules(traits, trait_cfg)
    hard_block = "\n".join(hard_list)
    if hard_block:
        hard_block = "Hard Requirements:\n" + hard_block

    # Length requirement
    min_len, max_len = LENGTH_RULES.get(length_choice, LENGTH_RULES["Medium (200-500 words)"])
    length_block = f"Write between {min_len} and {max_len} words." if max_len else f"Write at least {min_len} words."

    # Traits guide (short)
    trait_lines = [f"- {k}: {v}/10" for k, v in traits.items()]

    hook = (brief.get("hook") or "").strip()
    details = (brief.get("details") or "").strip()

    reports = (brief.get("reports") or "").strip()
    stocks_to_tease = (brief.get("stocks_to_tease") or "").strip()
    quotes_news = (brief.get("quotes_news") or "").strip()

    brief_block = (
        _line("Hook", hook)
        + _line("Details", details)
        + _offer_line(brief)
        + _line("Reports", reports)
        + _line("Stocks to Tease", stocks_to_tease)
        + _line("Quotes/News", quotes_news)
    ).strip()
    if not brief_block:
        brief_block = "- (none provided)"

    edit_block = ""
    if original_copy is not None and str(original_copy).strip():
        extra = (extra_instructions or "").strip()
        extra = f"\n\nAdditional revision instructions:\n{extra}\n" if extra else ""
        edit_block = dedent(
            f"""

            ### ORIGINAL COPY TO REVISE
            {str(original_copy).strip()}

            ### INSTRUCTION
            Rewrite the copy above using the trait requirements and the structure rules.
            IMPORTANT: You MUST preserve the Markdown structure (headings, bullets) used in the original.
            {extra}
            """
        ).strip()

    return dedent(
        f"""
        Linguistic settings:
        {chr(10).join(trait_lines)}

        Structure to follow:
        {struct}

        {hard_block}

        Campaign brief:
        {brief_block}

        Length requirement:
        {length_block}

        IMPORTANT:
        - Do not invent fake names, fake doctors, or precise performance numbers unless explicitly provided.
        - If you need a number, use a placeholder like [Insert % Return].
        - Focus on persuasion psychology without overstating certainty.

        Please limit bullet lists to three or fewer and favour full-sentence paragraphs elsewhere.

        {edit_block}
        """
    ).strip()


def _call_provider(
    *,
    provider: str,
    system: str,
    user: str,
    openai_model: str,
    gemini_model: str,
    temperature: float,
    expect_json: bool,
    max_tokens: int,
) -> str:
    p = (provider or "OpenAI").strip().lower()
    if p in {"gemini", "google", "google (gemini)"}:
        return query_gemini_chat(
            system_instruction=system,
            user_prompt=user,
            model_name=gemini_model,
            temperature=temperature,
            max_output_tokens=max_tokens,
            expect_json=expect_json,
        )

    return query_openai(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=openai_model,
        temperature=temperature,
        response_format={"type": "json_object"} if expect_json else None,
        max_tokens=max_tokens,
    )


def generate_copy_with_plan(
    *,
    copy_type: str,
    country: str,
    traits: Dict[str, int],
    brief: Dict[str, str],
    length_choice: str,
    provider: str = "OpenAI",
    openai_model: str = "gpt-4.1",
    gemini_model: str = DEFAULT_GEMINI_MODEL,
) -> Dict[str, str]:
    """Generate copy and an internal plan (outline).

    Returns dict with keys: plan, copy, raw
    """

    trait_cfg = load_trait_config()
    sys_msg = SYSTEM_PROMPT.format(
        country_rules=COUNTRY_RULES.get(country, "Use Australian English."),
        disclaimer_line=DISCLAIMER_LINE,
    )
    prompt_core = build_user_prompt(copy_type, brief, traits, length_choice, trait_cfg)

    user_instr = dedent(
        """
        TASK
        1) Create a concise INTERNAL bullet plan covering:
           - Hook & opening flow
           - Placement of proof, urgency, CTA
           - Structure checkpoints (headings)
        2) Then write the final copy.

        Respond ONLY as valid JSON with exactly two keys:
        {
          "plan": "<the bullet outline>",
          "copy": "<the finished marketing copy>"
        }
        """
    ).strip()

    raw = _call_provider(
        provider=provider,
        system=sys_msg,
        user=user_instr + "\n\n" + prompt_core,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=0.7,
        expect_json=True,
        max_tokens=MAX_OUTPUT_TOKENS,
    )

    cleaned = sanitize_json_text(raw)
    obj = parse_json_object(cleaned) or {}
    plan = str(obj.get("plan") or "").strip()
    copy = str(obj.get("copy") or "").strip()
    if not copy:
        # Fallback: treat entire response as the copy
        copy = (cleaned or raw or "").strip()

    # Gemini sometimes returns literal "\\n" strings
    if "\\n" in copy:
        copy = copy.replace("\\n", "\n")

    return {"plan": plan, "copy": copy, "raw": raw}


def generate_copy(
    copy_type: str,
    country: str,
    traits: Dict[str, int],
    brief: Dict[str, str],
    length_choice: str,
    model: str = "gpt-4.1",
) -> str:
    out = generate_copy_with_plan(
        copy_type=copy_type,
        country=country,
        traits=traits,
        brief=brief,
        length_choice=length_choice,
        provider="OpenAI",
        openai_model=model,
        gemini_model=DEFAULT_GEMINI_MODEL,
    )
    return (out.get("copy") or "").strip()


def rewrite_with_traits_preserve_structure(
    *,
    copy_type: str,
    country: str,
    traits: Dict[str, int],
    length_choice: str,
    original_copy: str,
    brief: Optional[Dict[str, str]] = None,
    extra_instructions: str = "",
    provider: str = "OpenAI",
    openai_model: str = "gpt-4.1",
    gemini_model: str = DEFAULT_GEMINI_MODEL,
) -> Dict[str, str]:
    """Rewrite an existing draft using the current trait rules.

    Preserves the original Markdown structure.
    Returns dict with keys: plan, copy, raw
    """

    trait_cfg = load_trait_config()
    sys_msg = SYSTEM_PROMPT.format(
        country_rules=COUNTRY_RULES.get(country, "Use Australian English."),
        disclaimer_line=DISCLAIMER_LINE,
    )
    prompt_core = build_user_prompt(
        copy_type,
        brief or {},
        traits,
        length_choice,
        trait_cfg,
        original_copy=original_copy,
        extra_instructions=extra_instructions,
    )

    user_instr = dedent(
        """
        TASK
        1) Create a concise INTERNAL bullet plan for the revision.
        2) Then output the revised copy.

        Respond ONLY as valid JSON with exactly two keys:
        {
          "plan": "<the bullet outline>",
          "copy": "<the revised marketing copy>"
        }
        """
    ).strip()

    raw = _call_provider(
        provider=provider,
        system=sys_msg,
        user=user_instr + "\n\n" + prompt_core,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=0.6,
        expect_json=True,
        max_tokens=MAX_OUTPUT_TOKENS,
    )

    cleaned = sanitize_json_text(raw)
    obj = parse_json_object(cleaned) or {}
    plan = str(obj.get("plan") or "").strip()
    copy = str(obj.get("copy") or "").strip() or cleaned

    if "\\n" in copy:
        copy = copy.replace("\\n", "\n")

    return {"plan": plan, "copy": copy, "raw": raw}


def revise_copy_goal(
    *,
    target_country: str,
    goal: str,
    existing_copy: str,
    extra_notes: str = "",
    provider: str = "OpenAI",
    openai_model: str = "gpt-4.1",
    gemini_model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    sys_msg = dedent(
        f"""
        You are a senior direct-response editor at The Motley Fool.

        Rewrite the copy to achieve the goal, while staying compliant:
        - no guaranteed outcomes
        - no invented performance numbers
        - no invented authorities

        IMPORTANT:
        - Preserve Markdown structure (headings, bullets) where possible.
        - Ensure the piece ends with the exact italic disclaimer line:
          {DISCLAIMER_LINE}

        Return ONLY the revised copy.
        """
    ).strip()

    user_msg = dedent(
        f"""
        GOAL:
        {goal}

        TARGET COUNTRY:
        {target_country}

        EXTRA NOTES:
        {extra_notes.strip() or "(none)"}

        COPY:
        {existing_copy.strip()}
        """
    ).strip()

    return _call_provider(
        provider=provider,
        system=sys_msg,
        user=user_msg,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=0.5,
        expect_json=False,
        max_tokens=MAX_OUTPUT_TOKENS,
    )


def qa_and_patch_copy(
    *,
    draft: str,
    copy_type: str,
    country: str,
    length_choice: str,
    traits: Dict[str, int],
    provider: str = "OpenAI",
    openai_model: str = "gpt-4o-mini",
    gemini_model: str = DEFAULT_GEMINI_CHEAP_MODEL,
) -> Dict[str, str]:
    """Run a short QA loop.

    Returns dict with keys:
      - status: PASS|PATCHED|ERROR
      - critique: model critique or automatic reason
      - copy: final copy (maybe patched)
    """

    text = (draft or "").strip()
    if not text:
        return {"status": "ERROR", "critique": "Empty draft", "copy": ""}

    min_len, max_len = LENGTH_RULES.get(length_choice, (0, None))
    word_count = len(text.split())

    # Fast checks (cheap)
    issues: List[str] = []
    if min_len and word_count < int(min_len * 0.5):
        issues.append(f"Draft is only {word_count} words (target min: {min_len}). Expand significantly.")
    if DISCLAIMER_LINE not in text:
        issues.append("Disclaimer line is missing or not exact. Append the italic disclaimer at the end.")
    if max_len and word_count > int(max_len * 1.25):
        issues.append(f"Draft is {word_count} words (target max: {max_len}). Tighten to fit the length bucket.")

    critique = ""
    if issues:
        critique = "\n".join([f"- {x}" for x in issues])
    else:
        # Model critique
        trait_cfg = load_trait_config()
        hard_list = trait_rules(traits, trait_cfg)
        hard_block = "\n".join(hard_list)

        sys_msg = "You are an obsessive editorial QA bot for direct-response copy."
        user_msg = dedent(
            f"""
            Check the copy for:
            - Structure matches {copy_type}
            - Hard requirements are satisfied
            - Length fits: {length_choice}
            - Disclaimer line present exactly: {DISCLAIMER_LINE}
            - Compliance: no guaranteed outcomes, no invented performance numbers

            Hard requirements:
            {hard_block if hard_block else "(none)"}

            TARGET COUNTRY:
            {country}

            Return ONLY:
            - "PASS" if everything is acceptable
            - Otherwise, a short bullet list of fixes (no more than 8 bullets)

            --- COPY ---
            {text}
            """
        ).strip()

        critique = _call_provider(
            provider=provider,
            system=sys_msg,
            user=user_msg,
            openai_model=openai_model,
            gemini_model=gemini_model,
            temperature=0.2,
            expect_json=False,
            max_tokens=1200,
        )

    if "PASS" in (critique or "").upper() and not issues:
        return {"status": "PASS", "critique": "PASS", "copy": text}

    # Patch
    sys_fix = "Revise copy to address QA feedback. Output the full revised copy ONLY.".strip()
    user_fix = dedent(
        f"""
        Apply the fixes below while preserving the overall intent.
        - Keep compliance in mind.
        - Do not invent performance numbers.

        FIXES:
        {critique.strip()}

        ORIGINAL:
        {text}
        """
    ).strip()

    patched = _call_provider(
        provider=provider,
        system=sys_fix,
        user=user_fix,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=0.4,
        expect_json=False,
        max_tokens=MAX_OUTPUT_TOKENS,
    )

    patched = (patched or "").strip()
    if patched:
        return {"status": "PATCHED", "critique": critique.strip(), "copy": patched}

    return {"status": "ERROR", "critique": critique.strip(), "copy": text}


def generate_variants(
    *,
    base_copy: str,
    n: int = 5,
    provider: str = "OpenAI",
    openai_model: str = "gpt-4o-mini",
    gemini_model: str = DEFAULT_GEMINI_CHEAP_MODEL,
) -> Dict[str, Any]:
    """Generate headline/subject + CTA variants.

    Returns dict: {"headlines": [...], "ctas": [...]} (empty lists on failure)
    """

    prompt = dedent(
        f"""
        Write {n} alternative subject-line/headline ideas AND {n} alternative CTA button labels
        for the copy below, preserving tone and urgency.

        Rules:
        - Keep headlines short and punchy (ideally <= 12 words)
        - Keep CTAs short (ideally <= 6 words)
        - Avoid guaranteed outcomes and financial advice phrasing

        Return ONLY JSON:
        {{
          "headlines": ["..."],
          "ctas": ["..."]
        }}

        --- COPY ---
        {base_copy.strip()}
        --- END COPY ---
        """
    ).strip()

    raw = _call_provider(
        provider=provider,
        system="You are a world-class direct-response copywriter.",
        user=prompt,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=0.8,
        expect_json=True,
        max_tokens=1200,
    )

    obj = parse_json_object(raw) or {}
    headlines = obj.get("headlines") if isinstance(obj, dict) else None
    ctas = obj.get("ctas") if isinstance(obj, dict) else None
    if not isinstance(headlines, list):
        headlines = []
    if not isinstance(ctas, list):
        ctas = []

    headlines = [str(x).strip() for x in headlines if str(x).strip()]
    ctas = [str(x).strip() for x in ctas if str(x).strip()]
    return {"headlines": headlines[:n], "ctas": ctas[:n], "raw": raw}


def adapt_copy(
    source_country: str,
    target_country: str,
    copy_text: str,
    brief_notes: str = "",
    provider: str = "OpenAI",
    openai_model: str = "gpt-4.1",
    gemini_model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    sys_msg = dedent(
        f"""
        You are a senior direct-response editor at The Motley Fool.

        Task:
        - Adapt marketing copy written for {source_country} so it works for {target_country}.
        - Keep the underlying offer and persuasive structure, but localise language, references, spelling, and cultural cues.
        - Do not add new factual claims or performance numbers.

        Target country rules:
        {COUNTRY_RULES.get(target_country, "Use Australian English.")}

        Output:
        - Return the adapted copy only.
        - Keep Markdown formatting if present.

        Compliance:
        - Avoid guaranteed outcomes.
        - If the original contains risky claims, soften them.
        """
    ).strip()

    user_msg = dedent(
        f"""
        Optional brief notes (context):
        {brief_notes.strip()}

        Copy to adapt (verbatim):
        {copy_text.strip()}
        """
    ).strip()

    return _call_provider(
        provider=provider,
        system=sys_msg,
        user=user_msg,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=0.4,
        expect_json=False,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
