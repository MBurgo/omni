import json
import time

import streamlit as st

from engines.signals import collect_signals, summarise_daily_brief
from storage.store import latest_artifact, save_artifact
from ui.branding import apply_branding, render_footer
from ui.layout import project_banner, require_project

st.set_page_config(
    page_title="Market signals",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

# --- Sidebar: project + controls (keeps the main page clean like the screenshots) ---
with st.sidebar:
    project_banner()

    st.divider()
    st.markdown("## Settings")

    st.session_state.setdefault("signals_model", "gpt-4o")
    st.session_state.setdefault("signals_cooldown_h", 3)

    model = st.selectbox(
        "Model",
        options=["gpt-4o", "gpt-4o-mini"],
        index=(0 if st.session_state.get("signals_model") == "gpt-4o" else 1),
        key="signals_model",
    )

    cooldown_h = st.slider(
        "Cooldown (hours)",
        min_value=0,
        max_value=12,
        value=int(st.session_state.get("signals_cooldown_h", 3)),
        key="signals_cooldown_h",
        help="Reuse the last run within this window to avoid hammering SerpAPI / OpenAI.",
    )

# Fixed defaults (no user input on this page)
DEFAULT_QUERY = "ASX 200"
DEFAULT_TRENDS_TOPIC_ID = "/m/0bl5c2"

# Backwards compatibility: if older sessions have values set, force them back to defaults.
st.session_state["signals_query"] = DEFAULT_QUERY
st.session_state["signals_trends_q"] = DEFAULT_TRENDS_TOPIC_ID

query = DEFAULT_QUERY
trends_q = DEFAULT_TRENDS_TOPIC_ID

pid = require_project()

# --- Hero (matches screenshot copy) ---
st.markdown(
    "<div class='page-title'>Find out what’s making news in the financial markets</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='page-subtitle'>This tool pulls live data from Google News and Google Trends to see what is making news in the financial markets right now.</div>",
    unsafe_allow_html=True,
)

# CTA button (gold)
run = st.button("Start Run", type="primary")

# Session cache
st.session_state.setdefault("daily_brief_json", None)

if run:
    # Attempt to reuse cached artifact if within cooldown and inputs match
    last = latest_artifact(pid, "signals_daily")

    def _now() -> float:
        # Allows tests to inject time via session_state
        return float(st.session_state.get("_now", time.time()))

    cached = None
    cache_msg = None
    if last and cooldown_h and cooldown_h > 0:
        age_h = (_now() - float(last.created_at)) / 3600.0
        meta = last.metadata or {}
        same_query = (meta.get("query") or "").strip().lower() == query.strip().lower()
        same_trends = (meta.get("trends_query_or_topic_id") or "").strip().lower() == trends_q.strip().lower()

        if age_h <= float(cooldown_h) and same_query and same_trends and last.content_json:
            cached = last.content_json
            cache_msg = f"Using cached result from Library (ran {age_h:.1f}h ago). Set cooldown=0 to force refresh."

    if cached is not None:
        st.info(cache_msg)
        st.session_state.daily_brief_json = cached
    else:
        with st.status("Collecting signals and generating briefing...", expanded=True) as status:
            try:
                st.write("1) Fetching signals (news, top stories, trends)...")
                d = collect_signals(query=query.strip(), trends_query_or_topic_id=(trends_q.strip() or None))
                st.write("2) Summarising into opportunities...")
                brief = summarise_daily_brief(d, model=model)

                title = f"Daily spikes: {query.strip()}"
                save_artifact(
                    pid,
                    type="signals_daily",
                    title=title,
                    content_json=brief if isinstance(brief, dict) else None,
                    content_text="",
                    metadata={
                        "query": query.strip(),
                        "trends_query_or_topic_id": trends_q.strip(),
                        "model": model,
                    },
                )

                st.session_state.daily_brief_json = brief
                status.update(label="Briefing ready", state="complete", expanded=False)
            except Exception as e:
                status.update(label="Failed", state="error", expanded=True)
                st.error(str(e))

brief = st.session_state.get("daily_brief_json")
if brief:
    st.divider()

    if isinstance(brief, dict) and "error" in brief:
        st.error(brief.get("error"))
        with st.expander("Raw output"):
            st.code(brief.get("raw", ""))
    elif isinstance(brief, dict):
        # --- Display (unchanged functionality) ---
        left, right = st.columns([2, 3], gap="large")

        with left:
            st.subheader("Top trends")
            for t in (brief.get("top_trends") or []):
                st.markdown(
                    f"- **{t.get('query','')}** ({t.get('value','')}) - {t.get('why_it_matters','')}"
                )

            st.subheader("Themes")
            for th in (brief.get("themes") or []):
                st.markdown(f"**{th.get('theme','')}**")
                if th.get("why_it_matters"):
                    st.caption(th.get("why_it_matters"))
                if th.get("suggested_angles"):
                    st.markdown("- " + "\n- ".join(th.get("suggested_angles")))
                st.divider()

        with right:
            st.subheader("Opportunities")
            opps = brief.get("opportunities") or []
            if not opps:
                st.info("No opportunities returned.")

            for i, opp in enumerate(opps, 1):
                title = opp.get("title") or f"Opportunity {i}"
                with st.expander(f"{i}. {title}"):
                    st.write(opp.get("synopsis", ""))

                    cols = st.columns(2)
                    with cols[0]:
                        if opp.get("key_entities"):
                            st.markdown("**Entities**")
                            st.markdown("- " + "\n- ".join(opp.get("key_entities")))
                    with cols[1]:
                        if opp.get("recommended_channels"):
                            st.markdown("**Recommended channels**")
                            st.markdown("- " + "\n- ".join(opp.get("recommended_channels")))

                    if opp.get("source_links"):
                        st.markdown("**Sources**")
                        for url in opp.get("source_links"):
                            st.markdown(f"- {url}")

                    if opp.get("risk_notes"):
                        st.warning("Risk notes: " + "; ".join(opp.get("risk_notes")))

                    hooks = opp.get("suggested_hooks") or []
                    if hooks:
                        st.markdown("**Suggested hooks**")
                        for h in hooks[:6]:
                            st.markdown(f"- {h}")

                    # Golden thread to Copywriter
                    if st.button("Send to Copywriter", key=f"send_copy_{i}"):
                        st.session_state["seed_hook"] = hooks[0] if hooks else title
                        st.session_state["seed_details"] = json.dumps(opp, ensure_ascii=False, indent=2)
                        st.session_state["seed_source"] = "signals_daily"
                        st.session_state["copywriter_mode"] = "generate"
                        st.switch_page("pages/06_Write_campaign_assets.py")

render_footer()
