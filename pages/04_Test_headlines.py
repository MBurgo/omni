import re

import streamlit as st

from engines.audience import test_headlines
from engines.llm import extract_json_object, query_openai
from engines.personas import load_personas, persona_label
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import hub_nav
from ui.seed import set_copywriter_seed

st.set_page_config(
    page_title="Test headlines",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()


def _clean_headline(s: str) -> str:
    s = (s or "").strip()
    # Remove common list prefixes: "1) ", "1. ", "- ", "• "
    s = re.sub(r"^\s*(?:[-•*]|\d+\s*[\.\)])\s*", "", s).strip()
    # Strip wrapping quotes
    s = s.strip().strip('"').strip("'").strip()
    return s


def _dedupe_preserve_order(items):
    seen = set()
    out = []
    for x in items:
        k = x.lower().strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x.strip())
    return out


def generate_headline_variants(
    base_headline: str,
    context: str,
    n: int,
    model: str = "gpt-4o-mini",
):
    """Generate headline variants for comparison. Returns a list of strings (may be empty on failure)."""
    base = _clean_headline(base_headline)
    if not base:
        return []

    ctx = (context or "").strip()
    prompt = f"""
You are a senior acquisition copywriter for an Australian investing publisher.

Goal:
Generate {n} alternative headline variants to test *alongside* the original headline.

Original headline:
{base}

Optional context about the offer / product / constraints:
{ctx if ctx else "(none)"}

Rules:
- Keep each variant concise and headline-like (ideally <= 12 words).
- Do NOT promise or guarantee returns. Avoid words like "guaranteed", "sure thing", "risk-free", "can't lose".
- Avoid giving financial advice or telling the reader what to buy/sell.
- Maintain the core intent/angle of the original, but vary framing (curiosity, specificity, credibility, benefit).
- Australian English tone.

Return ONLY JSON (no markdown, no commentary) in this schema:
{{
  "variants": ["...", "..."]
}}
""".strip()

    raw = query_openai([{"role": "user", "content": prompt}], model=model, temperature=0.8)
    parsed = extract_json_object(raw) or {}
    variants = parsed.get("variants") if isinstance(parsed, dict) else None
    if not isinstance(variants, list):
        return []

    cleaned = [_clean_headline(str(v)) for v in variants if str(v).strip()]
    cleaned = [v for v in cleaned if v and v.lower() != base.lower()]
    cleaned = _dedupe_preserve_order(cleaned)
    return cleaned[: max(0, n)]


pid = hub_nav()

# ---- Data ----
_, segments, personas = load_personas()
if not personas:
    st.error("No personas found.")
    st.stop()

# Settings (kept on main page; sidebar is hidden)
segment_opts = ["All"] + [s.get("id") or s.get("label") for s in segments]
segment_label = {s.get("id") or s.get("label"): s.get("label", "Unknown") for s in segments}

st.session_state.setdefault("headline_test_model", "gpt-4o-mini")
st.session_state.setdefault("headline_test_segment", "All")
st.session_state.setdefault("headline_test_personas", [p.uid for p in personas[:2]])

seg_state = st.session_state.get("headline_test_segment", "All")
if seg_state not in segment_opts:
    seg_state = "All"
    st.session_state["headline_test_segment"] = "All"

with st.expander("Settings", expanded=False):
    model = st.selectbox(
        "Model",
        options=["gpt-4o", "gpt-4o-mini"],
        index=1,
        key="headline_test_model",
    )

    seg = st.selectbox(
        "Segment",
        options=segment_opts,
        format_func=lambda x: "All" if x == "All" else segment_label.get(x, x),
        key="headline_test_segment",
    )

    if seg == "All":
        visible = personas
    else:
        visible = [p for p in personas if p.segment_id == seg or p.segment_label == segment_label.get(seg)]

    uid_to_p = {p.uid: p for p in visible}
    visible_uids = [p.uid for p in visible]

    # Keep the persona selection valid when segment changes.
    prev = st.session_state.get("headline_test_personas")
    prev = prev if isinstance(prev, list) else []
    valid_default = [uid for uid in prev if uid in visible_uids]
    if not valid_default:
        valid_default = visible_uids[:2]
    st.session_state["headline_test_personas"] = valid_default

    selected_uids = st.multiselect(
        "Personas to test",
        options=visible_uids,
        default=valid_default,
        format_func=lambda uid: persona_label(uid_to_p[uid]),
        key="headline_test_personas",
    )

    st.caption("Tip: start with 2 personas, then expand.")


# ---- Hero ----
st.markdown("<div class='page-title'>Test headlines with AI personas</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='page-subtitle'>Get synthetic investor reactions to headlines (click intent, trust, implied promise). Add 1 headline for a qualitative review, or enable auto-variants to create a comparison set.</div>",
    unsafe_allow_html=True,
)

# Inputs
# Support seeding from other tools (e.g., Copywriter variants)
if "seed_headlines_raw" in st.session_state and st.session_state.get("seed_headlines_raw"):
    st.session_state["headlines_raw"] = st.session_state.pop("seed_headlines_raw")
if "seed_headline_context" in st.session_state and st.session_state.get("seed_headline_context"):
    st.session_state["headline_context"] = st.session_state.pop("seed_headline_context")

headlines_raw = st.text_area(
    "Headlines (one per line)",
    height=200,
    placeholder="1) ...\n2) ...\n3) ...",
    key="headlines_raw",
)

context = st.text_area(
    "Context (optional)",
    height=120,
    placeholder="What is the offer / product? Any constraints or must-say details?",
    key="headline_context",
)

# Preview parsed headlines to drive UI
_headlines_preview = [_clean_headline(h) for h in headlines_raw.splitlines() if _clean_headline(h)]
single_headline_entered = len(_headlines_preview) == 1

auto_generate_variants = False
num_variants = 3

if single_headline_entered:
    with st.expander("Single-headline options", expanded=True):
        auto_generate_variants = st.checkbox(
            "Generate variants so you can compare and pick a winner",
            value=True,
            help=(
                "If enabled, the portal will generate a few alternatives and run the normal leaderboard. "
                "If disabled, you’ll get a qualitative review of your single headline."
            ),
        )
        num_variants = st.slider("How many variants?", min_value=2, max_value=6, value=3, step=1)

run = st.button("Run headline test", type="primary")
if run:
    headlines = [_clean_headline(h) for h in headlines_raw.splitlines() if _clean_headline(h)]
    headlines = _dedupe_preserve_order(headlines)

    if len(headlines) < 1:
        st.warning("Add at least one headline.")
        st.stop()
    if not selected_uids:
        st.warning("Select at least one persona.")
        st.stop()

    headline_sources = ["user"] * len(headlines)

    # If only one headline, optionally generate variants and switch into compare mode.
    if len(headlines) == 1 and auto_generate_variants:
        base = headlines[0]
        variant_model = "gpt-4o-mini"  # keep variant generation cheap/fast by default
        variants = generate_headline_variants(base, context=context, n=int(num_variants), model=variant_model)

        if variants:
            headlines = [base] + variants
            headline_sources = ["user"] + ["generated"] * len(variants)
            mode = "compare"
        else:
            st.warning("Could not generate variants (or none were valid). Running single-headline review instead.")
            mode = "review"
    else:
        mode = "review" if len(headlines) == 1 else "compare"

    # Help the underlying prompt behave sensibly when there's only 1 headline and we're in review mode.
    llm_context = context or ""
    if mode == "review":
        note = (
            "Note: Only ONE headline is provided. Treat this as a qualitative review of that single headline. "
            "In `top_3`, include only one item with headline_index=1. Focus on trust, clarity, implied promise, "
            "objections, and 3–5 improved rewrite options."
        )
        llm_context = (llm_context.strip() + "\n\n" + note) if llm_context.strip() else note

    results = []
    if mode == "compare":
        status_label = f"Testing {len(headlines)} headlines across {len(selected_uids)} persona(s)..."
        if auto_generate_variants and headline_sources.count("generated") > 0:
            status_label = (
                f"Generated {headline_sources.count('generated')} variant(s). "
                f"Testing {len(headlines)} headlines across {len(selected_uids)} persona(s)..."
            )
    else:
        status_label = f"Reviewing 1 headline across {len(selected_uids)} persona(s)..."

    with st.status(status_label, expanded=True) as status:
        for uid in selected_uids:
            p = uid_to_p[uid]
            out = test_headlines(p, headlines=headlines, context=llm_context, model=model)
            results.append({"persona_uid": uid, "persona": p.name, "segment": p.segment_label, "output": out})
            st.write(f"- {p.name}: done")
        status.update(label="Complete", state="complete", expanded=False)

    scores = None
    ranked = None

    if mode == "compare":
        # Aggregate a simple score from top_3 ranks
        scores = {i + 1: 0 for i in range(len(headlines))}
        for r in results:
            top_3 = (r.get("output") or {}).get("top_3") or []
            for item in top_3:
                try:
                    idx = int(item.get("headline_index"))
                    rank = int(item.get("rank"))
                    if 1 <= idx <= len(headlines):
                        scores[idx] += max(0, 4 - rank)  # rank1=3, rank2=2, rank3=1
                except Exception:
                    continue
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    # Persist
    title = (
        f"Headline review (1x{len(selected_uids)})"
        if mode == "review"
        else f"Headline test ({len(headlines)}x{len(selected_uids)})"
    )

    content_json = {
        "mode": mode,
        "headlines": headlines,
        "headline_sources": headline_sources,
        "context": context,
        "results": results,
    }
    if scores is not None:
        content_json["scores"] = scores
    if ranked is not None:
        content_json["ranked"] = ranked

    save_artifact(
        pid,
        type="headline_test",
        title=title,
        content_json=content_json,
        content_text="",
        metadata={
            "segment": seg,
            "model": model,
            "mode": mode,
            "auto_generated_variants": bool(auto_generate_variants and len(headline_sources) > 1),
            "variants_count": int(headline_sources.count("generated")),
        },
    )

    st.session_state["headline_test_last"] = {
        "mode": mode,
        "headlines": headlines,
        "headline_sources": headline_sources,
        "context": context,
        "results": results,
        "scores": scores,
        "ranked": ranked,
    }
    st.rerun()

last = st.session_state.get("headline_test_last")
if not last:
    st.stop()

mode = last.get("mode") or ("review" if len(last.get("headlines", [])) == 1 else "compare")
headlines = last.get("headlines") or []
headline_sources = last.get("headline_sources") or ["user"] * len(headlines)
results = last.get("results") or []
ranked = last.get("ranked")
context_used = last.get("context", "") or ""

if not headlines:
    st.stop()


def _headline_display(i: int) -> str:
    """1-indexed headline label with source tag."""
    src = ""
    if 0 <= (i - 1) < len(headline_sources):
        if headline_sources[i - 1] == "generated":
            src = " (generated)"
    return f"{i}. {headlines[i-1]}{src}"


st.divider()
st.subheader("Headlines under test")
for i in range(1, len(headlines) + 1):
    st.markdown(f"- {_headline_display(i)}")

# -----------------------
# Compare mode UI
# -----------------------
if mode == "compare":
    st.divider()
    st.subheader("Leaderboard")
    if ranked:
        for idx, score in ranked:
            st.markdown(f"- **{_headline_display(idx)}**  _(score: {score})_")
    else:
        st.info("No leaderboard available (could not compute scores).")

    # Select winner to send to Copywriter
    st.divider()
    default_index = 0
    if ranked and len(ranked) > 0:
        try:
            default_index = int(ranked[0][0]) - 1
        except Exception:
            default_index = 0

    winning_idx = st.radio(
        "Choose a headline to use as the campaign hook",
        options=[i + 1 for i in range(len(headlines))],
        format_func=_headline_display,
        index=default_index,
    )

    if st.button("Send selected headline to Copywriter", type="primary"):
        set_copywriter_seed(
            mode="generate",
            hook=headlines[winning_idx - 1],
            details=context_used,
            source="headline_test",
        )
        st.switch_page("pages/06_Write_campaign_assets.py")

# -----------------------
# Review mode UI
# -----------------------
else:
    st.divider()
    st.subheader("Headline review")
    st.markdown(f"**{_headline_display(1)}**")

    # Simple summary across personas (if feedback is available)
    click_yes = 0
    click_total = 0
    trust_counts = {"High": 0, "Medium": 0, "Low": 0}

    for r in results:
        out = r.get("output") or {}
        fb = out.get("headline_feedback") or []
        for f in fb:
            try:
                hi = int(f.get("headline_index", 0))
            except Exception:
                hi = 0
            if hi != 1:
                continue
            click_total += 1
            if bool(f.get("click")):
                click_yes += 1
            t = str(f.get("trust", "")).strip()
            if t in trust_counts:
                trust_counts[t] += 1

    cols = st.columns(4)
    cols[0].metric("Personas tested", value=str(len(results)))
    if click_total:
        cols[1].metric("Would click", value=f"{click_yes}/{click_total}")
    if sum(trust_counts.values()) > 0:
        cols[2].metric("Trust: High", value=str(trust_counts["High"]))
        cols[3].metric("Trust: Low", value=str(trust_counts["Low"]))

    st.divider()
    if st.button("Send this headline to Copywriter", type="primary"):
        set_copywriter_seed(
            mode="generate",
            hook=headlines[0],
            details=context_used,
            source="headline_review",
        )
        st.switch_page("pages/06_Write_campaign_assets.py")

# -----------------------
# Persona breakdown (both modes)
# -----------------------
st.divider()
st.subheader("Persona breakdown")
for r in results:
    out = r.get("output") or {}
    with st.expander(f"{r.get('persona','Unknown')} ({r.get('segment','')})"):
        if "error" in out:
            st.error(out.get("error"))
            st.code(out.get("raw", ""))
            continue

        if mode == "compare":
            st.markdown("**Top 3**")
            for item in out.get("top_3") or []:
                try:
                    hi = int(item.get("headline_index", 0))
                except Exception:
                    hi = 0
                if hi and hi <= len(headlines):
                    st.markdown(f"- #{item.get('rank')}: {_headline_display(hi)} - {item.get('why','')}")

        fb = out.get("headline_feedback") or []
        if fb:
            st.markdown("**Feedback**")
            for f in fb:
                try:
                    hi = int(f.get("headline_index", 0))
                except Exception:
                    hi = 0
                if not hi or hi > len(headlines):
                    continue
                if mode == "review" and hi != 1:
                    continue

                st.markdown(f"**{_headline_display(hi)}**")
                st.caption(
                    f"Click: {f.get('click')} | Trust: {f.get('trust','')} | Promise: {f.get('implied_promise','')}"
                )
                if f.get("what_to_fix"):
                    st.markdown(f"- Fix: {f.get('what_to_fix')}")
                if f.get("rewrite"):
                    st.markdown(f"- Rewrite: {f.get('rewrite')}")
                st.divider()

        if out.get("overall_takeaways"):
            st.markdown("**Overall takeaways**")
            st.markdown("- " + "\n- ".join(out.get("overall_takeaways")))

        if out.get("best_angle"):
            st.markdown(f"**Best angle:** {out.get('best_angle')}")
