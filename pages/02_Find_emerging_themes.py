import json

import streamlit as st

from engines.signals import collect_signals, summarise_horizon_scan
from storage.store import latest_artifact, save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(page_title="Futurist - Emerging themes", page_icon="🔮", layout="wide")
apply_branding()

st.title("🔮 Emerging themes")
st.caption("A horizon scan: turns current signals into plausible 3-12 month investor themes + campaign ideas.")

project_banner()
pid = require_project()

# --- Inputs ---
colA, colB, colC = st.columns([2,2,1])
with colA:
    query = st.text_input("Query", value=st.session_state.get("futurist_query", "ASX 200"))
with colB:
    trends_q = st.text_input("Trends query or topic id (optional)", value=st.session_state.get("futurist_trends_q", ""), placeholder="e.g. /m/0bl5c2")
with colC:
    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0)

cooldown_h = st.slider("Cooldown (hours)", min_value=0, max_value=48, value=12)

last = latest_artifact(pid, "signals_horizon")
if last and cooldown_h > 0:
    import time
    age_h = (time.time() - last.created_at) / 3600
    cached = last.content_json if age_h <= cooldown_h else None
else:
    cached = None

if "horizon_json" not in st.session_state:
    st.session_state.horizon_json = cached

if st.button("Generate horizon scan", type="primary"):
    st.session_state["futurist_query"] = query
    st.session_state["futurist_trends_q"] = trends_q
    with st.status("Collecting signals and generating horizon scan...", expanded=True) as status:
        try:
            st.write("1) Fetching signals...")
            d = collect_signals(query=query.strip(), trends_query_or_topic_id=(trends_q.strip() or None))
            st.write("2) Synthesising emerging themes...")
            out = summarise_horizon_scan(d, model=model)
            save_artifact(
                pid,
                type="signals_horizon",
                title=f"Horizon scan: {query.strip()}",
                content_json=out if isinstance(out, dict) else None,
                content_text="",
                metadata={"query": query.strip(), "model": model},
            )
            st.session_state.horizon_json = out
            status.update(label="Horizon scan ready", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Failed", state="error", expanded=True)
            st.error(str(e))

out = st.session_state.get("horizon_json")
if not out:
    st.stop()
if "error" in out:
    st.error(out.get("error"))
    with st.expander("Raw output"):
        st.code(out.get("raw", ""))
    st.stop()

st.subheader("Themes")
for idx, th in enumerate(out.get("emerging_themes") or [], 1):
    with st.expander(f"{idx}. {th.get('theme','Theme')}"):
        st.write(th.get("why_now", ""))
        st.caption(f"Time horizon: {th.get('time_horizon','')}")

        cols = st.columns(2)
        with cols[0]:
            if th.get("what_to_watch"):
                st.markdown("**What to watch**")
                st.markdown("- " + "\n- ".join(th.get("what_to_watch")))
        with cols[1]:
            if th.get("investor_questions"):
                st.markdown("**Investor questions**")
                st.markdown("- " + "\n- ".join(th.get("investor_questions")))

        st.markdown("**Campaign ideas**")
        ideas = th.get("campaign_ideas") or []
        for j, idea in enumerate(ideas, 1):
            hook = idea.get("hook", "")
            angle = idea.get("angle", "")
            ch = ", ".join(idea.get("channels") or [])
            st.markdown(f"{j}. **{hook}**\n\n- Angle: {angle}\n- Channels: {ch}")

            if st.button("Send idea to Copywriter", key=f"send_idea_{idx}_{j}"):
                st.session_state["seed_hook"] = hook or th.get("theme", "")
                st.session_state["seed_details"] = json.dumps({"theme": th, "idea": idea}, ensure_ascii=False, indent=2)
                st.session_state["seed_source"] = "signals_horizon"
                st.switch_page("pages/06_Write_campaign_assets.py")

        if th.get("risks"):
            st.warning("Risks: " + "; ".join(th.get("risks")))
