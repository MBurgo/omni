from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from engines.llm import extract_json_object, query_gemini, query_openai
from model_registry import DEFAULT_GEMINI_MODEL
from engines.personas import Persona


DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def normalize_dashes(s: str) -> str:
    return re.sub(f"[{DASH_CHARS}]", "-", s or "")


def _ensure_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _ensure_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(re.findall(r"\S+", text))


def estimate_tokens(text: str) -> int:
    # heuristic: ~1 word ~= 1.45 tokens
    wc = word_count(text)
    return int(wc * 1.45)


def truncate_words(text: str, max_words: int) -> str:
    if not text:
        return ""
    words = re.findall(r"\S+", text)
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).strip()


def claim_risk_flags(text: str) -> List[str]:
    if not text or not text.strip():
        return []
    t = text.lower()
    patterns = {
        "Guaranteed / certainty language": [
            "guaranteed",
            "can't lose",
            "sure thing",
            "no risk",
            "risk-free",
            "100%",
        ],
        "Urgency pressure": [
            "urgent",
            "act now",
            "limited time",
            "today only",
            "last chance",
            "ends tonight",
            "flash sale",
            "expires",
        ],
        "Implied future performance": [
            "will double",
            "will triple",
            "can't miss",
            "next nvidia",
            "take off explosively",
        ],
        "Overly absolute claims": ["always", "never", "everyone", "no one"],
    }
    hits: List[str] = []
    for label, toks in patterns.items():
        if any(tok in t for tok in toks):
            hits.append(label)
    return hits


def build_persona_system_prompt(core: Dict[str, Any]) -> str:
    name = core.get("name", "Unknown")
    age = core.get("age", "")
    location = core.get("location", "")
    occupation = core.get("occupation", "")
    income = core.get("income", "")
    narrative = core.get("narrative", "")

    values = ", ".join(_ensure_list(core.get("values"))[:5])
    goals = "; ".join(_ensure_list(core.get("goals"))[:4])
    concerns = "; ".join(_ensure_list(core.get("concerns"))[:4])
    decision_making = core.get("decision_making", "")

    bt = _ensure_dict(core.get("behavioural_traits"))
    risk = bt.get("risk_tolerance", "Unknown")
    exp = bt.get("investment_experience", "Unknown")
    info_sources = ", ".join(_ensure_list(bt.get("information_sources"))[:6])
    preferred_channels = ", ".join(_ensure_list(bt.get("preferred_channels"))[:6])

    cc = _ensure_dict(core.get("content_consumption"))
    formats = ", ".join(_ensure_list(cc.get("preferred_formats"))[:6])

    return (
        f"You are {name}, a {age}-year-old {occupation} based in {location}. Income: ${income}.\n"
        f"Bio: {narrative}\n"
        f"Values: {values}\n"
        f"Goals: {goals}\n"
        f"Concerns: {concerns}\n"
        f"Decision style: {decision_making}\n"
        f"Investing: {exp}. Risk tolerance: {risk}.\n"
        f"Information sources: {info_sources}\n"
        f"Preferred channels: {preferred_channels}\n"
        f"Preferred formats: {formats}\n\n"
        "Rules: Respond in first person, in-character, and grounded in your constraints. "
        "Don't give financial advice; focus on reactions to marketing, credibility, and decision triggers. "
        "Keep answers under ~140 words unless asked for depth."
    )


def ask_persona(
    persona: Persona,
    question: str,
    history: Optional[List[Tuple[str, str]]] = None,
    model: str = "gpt-4.1",
    temperature: float = 0.7,
) -> str:
    history = history or []
    sys_msg = build_persona_system_prompt(persona.core)

    messages: List[Dict[str, str]] = [{"role": "system", "content": sys_msg}]
    for q, a in history[-3:]:
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": question})

    return query_openai(messages, model=model, temperature=temperature)


def headline_test_prompt(persona: Persona, headlines: List[str], context: str = "") -> str:
    h_block = "\n".join([f"{i+1}. {h.strip()}" for i, h in enumerate(headlines) if h.strip()])
    return f"""
You are roleplaying this investor persona:
{build_persona_system_prompt(persona.core)}

Task:
- Evaluate the headlines as marketing headlines for an investing brand.
- Pick the top 3 you would click.
- Explain what each headline *implies* (promise/angle) and whether you trust it.
- Suggest improved rewrites for the weakest headlines.

Context (optional):
{context.strip()}

Headlines:
{h_block}

Return ONLY JSON (no markdown) in this schema:
{{
  "top_3": [{{"rank": 1, "headline_index": 3, "why": "..."}}],
  "headline_feedback": [{{"headline_index": 1, "click": true, "trust": "High|Medium|Low", "implied_promise": "...", "what_to_fix": "...", "rewrite": "..."}}],
  "overall_takeaways": ["..."],
  "best_angle": "..."
}}
""".strip()


def test_headlines(
    persona: Persona,
    headlines: List[str],
    context: str = "",
    model: str = "gpt-4.1",
) -> Dict[str, Any]:
    raw = query_openai(
        [{"role": "user", "content": headline_test_prompt(persona, headlines, context)}],
        model=model,
        temperature=0.4,
    )
    parsed = extract_json_object(raw)
    return parsed or {"error": "Could not parse JSON", "raw": raw}


def brief_extraction_prompt(copy_type: str, text: str) -> str:
    return f"""
You are a senior conversion strategist. Extract a structured brief from the marketing creative.

COPY TYPE: {copy_type}

CREATIVE (verbatim):
{text}

Return ONLY a single JSON object (no markdown, no commentary) with this structure:

{{
  "copy_type": "{copy_type}",
  "audience_assumed": "...",
  "primary_promise": "...",
  "mechanism_or_angle": "...",
  "offer_summary": "...",
  "cta": "...",
  "price_or_discount": "...",
  "key_claims": ["..."],
  "proof_elements_present": ["..."],
  "missing_proof": ["..."],
  "tone": ["..."],
  "sections_detected": ["..."],
  "confusing_or_unanswered": ["..."],
  "risk_flags": ["..."],
  "quick_fixes": ["..." ]
}}

Rules:
- If something is unknown, use an empty string or empty list.
- Keep strings concise.
""".strip()


def summarize_brief_for_personas(brief: Optional[Dict[str, Any]]) -> str:
    if not isinstance(brief, dict):
        return ""

    def _clip(s: str, n: int = 140) -> str:
        s = (s or "").strip()
        if len(s) <= n:
            return s
        return s[: n - 1].rstrip() + "..."

    lines: List[str] = []
    if brief.get("primary_promise"):
        lines.append(f"Promise: {_clip(str(brief.get('primary_promise')))}")
    if brief.get("mechanism_or_angle"):
        lines.append(f"Angle: {_clip(str(brief.get('mechanism_or_angle')))}")
    if brief.get("offer_summary"):
        lines.append(f"Offer: {_clip(str(brief.get('offer_summary')))}")
    if brief.get("cta"):
        lines.append(f"CTA: {_clip(str(brief.get('cta')))}")

    claims = _ensure_list(brief.get("key_claims"))[:4]
    if claims:
        lines.append("Claims: " + "; ".join([_clip(str(x), 90) for x in claims]))

    missing = _ensure_list(brief.get("missing_proof"))[:3]
    if missing:
        lines.append("Missing proof: " + "; ".join([_clip(str(x), 90) for x in missing]))

    if not lines:
        return ""

    return "\n".join([f"- {ln}" for ln in lines])


def participant_task(copy_type: str) -> str:
    if copy_type == "Headline":
        return (
            "Answer in 4 short bullets:\n"
            "1) Click or ignore (and why)\n"
            "2) What you think this really means (implied promise)\n"
            "3) Trust reaction (what feels credible / not)\n"
            "4) One rewrite suggestion (<= 12 words)"
        )
    if copy_type == "Email":
        return (
            "Answer in 4 short bullets:\n"
            "1) Open or ignore (and why)\n"
            "2) Trust/credibility reaction\n"
            "3) Biggest question holding you back\n"
            "4) One change that improves it"
        )
    if copy_type == "Sales Page":
        return (
            "Answer in 5 short bullets:\n"
            "1) Would you keep reading or bounce (and where)\n"
            "2) Strongest section (and why)\n"
            "3) Weakest section (and why)\n"
            "4) Proof you need before believing\n"
            "5) One concrete fix"
        )
    return (
        "Answer in 4 short bullets:\n"
        "1) What grabs you (if anything)\n"
        "2) What feels off / unclear\n"
        "3) What proof you need\n"
        "4) One improvement"
    )


def moderator_prompt(copy_type: str, transcript: str, creative_for_moderator: str, brief_json: Optional[Dict[str, Any]]) -> str:
    base_fields = (
        '  "executive_summary": "...",\n'
        '  "real_why": "...",\n'
        '  "trust_gap": "...",\n'
        '  "key_objections": ["..."],\n'
        '  "proof_needed": ["..."],\n'
        '  "risk_flags": ["..."],\n'
        '  "actionable_fixes": ["..."],\n'
    )

    if copy_type == "Headline":
        rewrite_schema = (
            '  "rewrite": {\n'
            '    "headlines": ["..."],\n'
            '    "angle_notes": "..."\n'
            '  },\n'
            '  "notes": "..."\n'
        )
        constraints = (
            "Constraints:\n"
            "- Provide 10 headlines. Each <= 12 words.\n"
            "- Make the angle specific early (avoid pure mystery).\n"
            "- Avoid guarantees or performance promises.\n"
        )
    elif copy_type == "Email":
        rewrite_schema = (
            '  "rewrite": {\n'
            '    "subject": "...",\n'
            '    "preheader": "...",\n'
            '    "body": "...",\n'
            '    "cta": "...",\n'
            '    "ps": "..."\n'
            '  },\n'
            '  "alt_subjects": ["..."],\n'
            '  "notes": "..."\n'
        )
        constraints = (
            "Constraints:\n"
            "- Subject <= 70 characters.\n"
            "- Preheader <= 110 characters.\n"
            "- Body 150-250 words, clear and credible (AU tone).\n"
            "- Avoid guarantees or performance promises.\n"
        )
    elif copy_type == "Sales Page":
        rewrite_schema = (
            '  "section_feedback": [\n'
            '    {"section": "Hero", "what_works": "...", "what_hurts": "...", "fix": "..."}\n'
            '  ],\n'
            '  "rewrite": {\n'
            '    "hero_headline": "...",\n'
            '    "hero_subhead": "...",\n'
            '    "bullets": ["..."],\n'
            '    "proof_block": "...",\n'
            '    "offer_stack": ["..."],\n'
            '    "cta_block": "...",\n'
            '    "cta_button": "..."\n'
            '  },\n'
            '  "notes": "..."\n'
        )
        constraints = (
            "Constraints:\n"
            "- Focus on rewriting key blocks (not the entire page).\n"
            "- Bullets: 5-7. Offer stack: 3-6 items.\n"
            "- Avoid guarantees or performance promises.\n"
        )
    else:
        rewrite_schema = (
            '  "rewrite": {\n'
            '    "headline": "...",\n'
            '    "body": "..."\n'
            '  },\n'
            '  "notes": "..."\n'
        )
        constraints = (
            "Constraints:\n"
            "- Keep rewrite concise and concrete.\n"
            "- Avoid guarantees or performance promises.\n"
        )

    brief_block = ""
    if isinstance(brief_json, dict) and brief_json:
        brief_block = "\n\nEXTRACTED BRIEF (JSON):\n" + json.dumps(brief_json, ensure_ascii=False)

    return f"""
You are a legendary Direct Response Copywriter (Motley Fool style) acting as a focus-group moderator.
You are strict, practical, and credibility-first.

COPY TYPE: {copy_type}

TRANSCRIPT:
{transcript}

CREATIVE:
{creative_for_moderator}
{brief_block}

OUTPUT:
Return ONLY a single JSON object (no markdown, no commentary) with this structure:

{{
{base_fields}{rewrite_schema}}}

{constraints}
""".strip()


def focus_group_debate(
    believer: Persona,
    skeptic: Persona,
    creative_text: str,
    copy_type: str = "Email",
    participant_scope: str = "First N words",
    participant_n_words: int = 450,
    participant_custom_excerpt: str = "",
    extract_brief: bool = True,
    brief_model: str = "gpt-4o-mini",
    model: str = "gpt-4.1",
    moderator_model: str = DEFAULT_GEMINI_MODEL,
) -> Dict[str, Any]:
    """Run a Believer vs Skeptic debate and return structured outputs."""

    creative_text = (creative_text or "").strip()
    if not creative_text:
        return {"error": "No creative provided"}

    # caps
    PARTICIPANT_CAP_WORDS = 1500
    MODERATOR_CAP_WORDS = 4500

    def _excerpt(full_text: str) -> str:
        if participant_scope == "Custom excerpt" and participant_custom_excerpt.strip():
            return truncate_words(participant_custom_excerpt.strip(), PARTICIPANT_CAP_WORDS)
        if participant_scope == "Full text (capped)":
            return truncate_words(full_text, PARTICIPANT_CAP_WORDS)
        return truncate_words(full_text, int(participant_n_words))

    excerpt = _excerpt(creative_text)
    creative_for_moderator = truncate_words(creative_text, MODERATOR_CAP_WORDS)

    # optional brief extraction
    brief_raw = ""
    brief_json: Optional[Dict[str, Any]] = None
    if extract_brief:
        brief_raw = query_openai(
            [{"role": "user", "content": brief_extraction_prompt(copy_type, creative_for_moderator)}],
            model=brief_model,
            temperature=0.2,
        )
        brief_json = extract_json_object(brief_raw)

    brief_summary = summarize_brief_for_personas(brief_json)

    base_instruction = (
        "IMPORTANT: This is a simulation for marketing research. "
        "You are roleplaying a specific persona. Do NOT sound like a generic AI. "
        "Do not give financial advice; focus on reactions to marketing, credibility, and decision triggers. "
        "Be specific. Avoid repeating the same template in every turn."
    )

    def _role_prompt(p: Persona, stance: str) -> str:
        core = p.core
        bt = _ensure_dict(core.get("behavioural_traits"))
        values = ", ".join(_ensure_list(core.get("values"))[:5])
        goals = "; ".join(_ensure_list(core.get("goals"))[:4])
        concerns = "; ".join(_ensure_list(core.get("concerns"))[:4])

        stance_block = (
            "You WANT the message to be true. You focus on upside, possibility, and emotional appeal. "
            "You defend the message against skepticism, but you still sound like a real person."
            if stance == "Believer"
            else "You are allergic to hype. You look for missing specifics, credibility gaps, and implied claims. "
            "You call out anything that sounds too good to be true."
        )

        return (
            f"ROLE: You are {core.get('name')}, a {core.get('age')}-year-old {core.get('occupation')}.\n"
            f"BIO: {core.get('narrative','')}\n"
            f"VALUES: {values}\n"
            f"GOALS: {goals}\n"
            f"CONCERNS: {concerns}\n"
            f"RISK TOLERANCE: {bt.get('risk_tolerance','Unknown')}\n\n"
            f"STANCE: {stance}\n{stance_block}"
        )

    role_a = _role_prompt(believer, "Believer")
    role_b = _role_prompt(skeptic, "Skeptic")

    persona_brief = f"\n\nBRIEF SUMMARY (for context):\n{brief_summary}" if brief_summary else ""
    task = participant_task(copy_type)

    # 1) Believer
    msg_a = query_openai(
        [
            {"role": "system", "content": base_instruction + "\n\n" + role_a},
            {
                "role": "user",
                "content": (
                    f"You are reacting to {copy_type} creative.\n\n"
                    f"CREATIVE (excerpt):\n{excerpt}{persona_brief}\n\n"
                    f"TASK:\n{task}"
                ),
            },
        ],
        model=model,
        temperature=0.8,
    )
    time.sleep(0.15)

    # 2) Skeptic
    msg_b = query_openai(
        [
            {"role": "system", "content": base_instruction + "\n\n" + role_b},
            {
                "role": "user",
                "content": (
                    f"You are reacting to the same {copy_type} creative.\n\n"
                    f"CREATIVE (excerpt):\n{excerpt}{persona_brief}\n\n"
                    f"The Believer said:\n{msg_a}\n\n"
                    "Respond directly to their points. Don't restate the creative. "
                    "Call out what feels manipulative or unclear.\n\n"
                    f"TASK:\n{task}"
                ),
            },
        ],
        model=model,
        temperature=0.8,
    )
    time.sleep(0.15)

    # 3) Believer rebuttal
    msg_a2 = query_openai(
        [
            {"role": "system", "content": base_instruction + "\n\n" + role_a},
            {
                "role": "user",
                "content": (
                    "Reply to the Skeptic in 5-6 sentences max.\n"
                    "- Acknowledge 1 fair critique\n"
                    "- Defend 1 element that still excites you\n"
                    "- Suggest 1 specific improvement that would keep the upside but build trust\n\n"
                    f"Skeptic said:\n{msg_b}"
                ),
            },
        ],
        model=model,
        temperature=0.7,
    )
    time.sleep(0.15)

    # 4) Skeptic counter
    msg_b2 = query_openai(
        [
            {"role": "system", "content": base_instruction + "\n\n" + role_b},
            {
                "role": "user",
                "content": (
                    "Counter the Believer in 5-6 sentences max.\n"
                    "- Say what specific proof/detail would convert you\n"
                    "- Name the single most damaging phrase or move in the creative\n"
                    "- Provide one rewrite principle (not a full rewrite)\n\n"
                    f"Believer said:\n{msg_a2}"
                ),
            },
        ],
        model=model,
        temperature=0.7,
    )

    debate_turns = [
        {"name": believer.name, "uid": believer.uid, "role": "Believer", "text": msg_a},
        {"name": skeptic.name, "uid": skeptic.uid, "role": "Skeptic", "text": msg_b},
        {"name": believer.name, "uid": believer.uid, "role": "Believer", "text": msg_a2},
        {"name": skeptic.name, "uid": skeptic.uid, "role": "Skeptic", "text": msg_b2},
    ]

    transcript = "\n".join([f"{x['name']} ({x['role']}): {x['text']}" for x in debate_turns])

    # Moderator analysis: Gemini preferred, OpenAI fallback inside query_gemini
    mod_raw = query_gemini(moderator_prompt(copy_type, transcript, creative_for_moderator, brief_json), model_name=moderator_model)
    mod_json = extract_json_object(mod_raw)

    return {
        "created_at": time.time(),
        "copy_type": copy_type,
        "creative_full": creative_text,
        "excerpt": excerpt,
        "brief_raw": brief_raw,
        "brief_json": brief_json,
        "debate_turns": debate_turns,
        "transcript": transcript,
        "moderator_raw": mod_raw,
        "moderator_json": mod_json,
        "risk_flags_detected": claim_risk_flags(creative_text),
        "token_estimate": estimate_tokens(creative_text),
    }
