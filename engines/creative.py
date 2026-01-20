from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

from engines.llm import query_openai


LENGTH_RULES = {
    "Short (100-200 words)": (100, 220),
    "Medium (200-500 words)": (200, 550),
    "Long (500-1500 words)": (500, 1600),
    "Extra Long (1500-3000 words)": (1500, 3200),
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
    *Past performance is not a reliable indicator of future results.*
    """
).strip()


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
) -> str:
    # Structure
    if copy_type == "Email":
        struct = EMAIL_STRUCT
    elif copy_type == "Sales Page":
        struct = SALES_STRUCT
    else:
        struct = ADS_STRUCT

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

    return dedent(
        f"""
        Linguistic settings:
        {chr(10).join(trait_lines)}

        Structure to follow:
        {struct}

        {hard_block}

        Campaign brief:
        - Hook: {hook}
        - Details: {details}

        Length requirement:
        {length_block}

        IMPORTANT:
        - Do not invent fake names, fake doctors, or precise performance numbers unless explicitly provided.
        - If you need a number, use a placeholder like [Insert % Return].
        - Focus on persuasion psychology without overstating certainty.
        """
    ).strip()


def generate_copy(
    copy_type: str,
    country: str,
    traits: Dict[str, int],
    brief: Dict[str, str],
    length_choice: str,
    model: str = "gpt-4o",
) -> str:
    trait_cfg = load_trait_config()
    sys_msg = SYSTEM_PROMPT.format(country_rules=COUNTRY_RULES.get(country, "Use Australian English."))
    user_msg = build_user_prompt(copy_type, brief, traits, length_choice, trait_cfg)

    return query_openai(
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        model=model,
        temperature=0.7,
    )


def adapt_copy(
    source_country: str,
    target_country: str,
    copy_text: str,
    brief_notes: str = "",
    model: str = "gpt-4o",
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

    return query_openai(
        messages=[
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_msg},
        ],
        model=model,
        temperature=0.4,
    )
