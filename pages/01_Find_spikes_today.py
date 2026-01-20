import json

import streamlit as st

from engines.signals import collect_signals, summarise_daily_brief
from storage.store import latest_artifact, save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(page_title="Signals - What's spiking", page_icon="📰", layout="wide")
apply_branding()

st.title("📰 What's spiking today")
st.caption("Pulls fresh Google News + Google Trends signals (via SerpAPI) and turns them into campaign-ready opportunities.")

project_banner()
pid = require_project()

# --- Inputs ---
colA, colB, colC = st.columns([2,2,1])
with colA:
    query = st.text_input("Query", value=st.session_state.get("signals_query", "ASX 200"))
with colB:
    trends_q = st.text_input("Trends query or topic id (optional)", value=st.session_state.get("signals_trends_q", ""), placeholder="e.g. /m/0bl5c2 or 'ASX 200'")
with colC:
    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0)

cooldown_h = st.slider("Cooldown (hours)", min_value=0, max_value=12, value=3, help="Reuse the last run within this window to avoid hammering SerpAPI / OpenAI.")

# --- Load last run if available ---
last = latest_artifact(pid, "signals_daily")

if last and cooldown_h > 0:
    age_hours = (st.session_state.get("_now", None) or __import__("time").time()) - last.created_at
    age_hours /= 3600
    if age_hours <= cooldown_h:
        st.info(f"Using cached result from Library (ran {age_hours:.1f}h ago). Set cooldown=0 to force refresh.")
        cached = last.content_json or {}
    else:
        cached = None
else:
    cached = None

if "daily_brief_json" not in st.session_state:
    st.session_state.daily_brief_json = cached

# --- Run ---
run = st.button("Generate daily spikes briefing", type="primary")
if run:
    st.session_state["signals_query"] = query
    st.session_state["signals_trends_q"] = trends_q

    with st.status("Collecting signals and generating briefing...", expanded=True) as status:
        try:
            st.write("1) Fetching signals (news, top stories, trends)...")
            d = collect_signals(query=query.strip(), trends_query_or_topic_id=(trends_q.strip() or None))
            st.write("2) Summarising into opportunities...")
            brief = summarise_daily_brief(d, model=model)

            # Persist
            title = f"Daily spikes: {query.strip()}"
            save_artifact(
                pid,
                type="signals_daily",
                title=title,
                content_json=brief if isinstance(brief, dict) else None,
                content_text="",
                metadata={"query": query.strip(), "model": model},
            )

            st.session_state.daily_brief_json = brief
            status.update(label="Briefing ready", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Failed", state="error", expanded=True)
            st.error(str(e))

brief = st.session_state.get("daily_brief_json")
if not brief:
    st.stop()

if "error" in brief:
    st.error(brief.get("error"))
    with st.expander("Raw output"):
        st.code(brief.get("raw", ""))
    st.stop()

# --- Display ---
left, right = st.columns([2,3])

with left:
    st.subheader("Top trends")
    for t in (brief.get("top_trends") or []):
        st.markdown(f"- **{t.get('query','')}** ({t.get('value','')}) - {t.get('why_it_matters','')}")

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
                st.switch_page("pages/06_Write_campaign_assets.py")
