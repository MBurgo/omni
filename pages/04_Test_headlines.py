import json

import streamlit as st

from engines.audience import test_headlines
from engines.personas import load_personas, persona_label
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(page_title="Test headlines", page_icon="🧪", layout="wide")
apply_branding()

st.title("🧪 Test headlines")
st.caption("Get synthetic investor reactions to headline variations (click intent, trust, implied promise).")

project_banner()
pid = require_project()

_, segments, personas = load_personas()
if not personas:
    st.error("No personas found.")
    st.stop()

segment_opts = ["All"] + [s.get("id") or s.get("label") for s in segments]
segment_label = {s.get("id") or s.get("label"): s.get("label", "Unknown") for s in segments}
seg = st.selectbox("Segment", options=segment_opts, format_func=lambda x: "All" if x == "All" else segment_label.get(x, x))

if seg == "All":
    visible = personas
else:
    visible = [p for p in personas if p.segment_id == seg or p.segment_label == segment_label.get(seg)]

headlines_raw = st.text_area(
    "Headlines (one per line)",
    height=200,
    placeholder="1) ...\n2) ...\n3) ...",
)

context = st.text_area(
    "Context (optional)",
    height=120,
    placeholder="What is the offer / product? Any constraints or must-say details?",
)

uid_to_p = {p.uid: p for p in visible}
selected_uids = st.multiselect(
    "Personas to test",
    options=[p.uid for p in visible],
    default=[p.uid for p in visible[:2]],
    format_func=lambda uid: persona_label(uid_to_p[uid]),
)

colA, colB = st.columns([1,2])
with colA:
    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=1)
with colB:
    st.caption("Tip: start with 2 personas, then expand.")

if st.button("Run headline test", type="primary"):
    headlines = [h.strip() for h in headlines_raw.splitlines() if h.strip()]
    if len(headlines) < 2:
        st.warning("Add at least two headlines.")
        st.stop()
    if not selected_uids:
        st.warning("Select at least one persona.")
        st.stop()

    results = []
    with st.status(f"Testing {len(headlines)} headlines across {len(selected_uids)} persona(s)...", expanded=True) as status:
        for uid in selected_uids:
            p = uid_to_p[uid]
            out = test_headlines(p, headlines=headlines, context=context, model=model)
            results.append({"persona_uid": uid, "persona": p.name, "segment": p.segment_label, "output": out})
            st.write(f"- {p.name}: done")
        status.update(label="Complete", state="complete", expanded=False)

    # Aggregate a simple score from top_3 ranks
    scores = {i+1: 0 for i in range(len(headlines))}
    for r in results:
        top_3 = (r.get("output") or {}).get("top_3") or []
        for item in top_3:
            try:
                idx = int(item.get("headline_index"))
                rank = int(item.get("rank"))
                scores[idx] += max(0, 4 - rank)  # rank1=3, rank2=2, rank3=1
            except Exception:
                continue

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

    # Persist
    save_artifact(
        pid,
        type="headline_test",
        title=f"Headline test ({len(headlines)}x{len(selected_uids)})",
        content_json={"headlines": headlines, "context": context, "results": results, "scores": scores},
        content_text="",
        metadata={"segment": seg, "model": model},
    )

    st.session_state["headline_test_last"] = {"headlines": headlines, "context": context, "results": results, "scores": scores, "ranked": ranked}
    st.rerun()

last = st.session_state.get("headline_test_last")
if not last:
    st.stop()

headlines = last["headlines"]
results = last["results"]
ranked = last["ranked"]

st.subheader("Leaderboard")
for idx, score in ranked:
    st.markdown(f"- **{idx}. {headlines[idx-1]}**  _(score: {score})_")

# Select winner to send to Copywriter
st.divider()
winning_idx = st.radio(
    "Choose a headline to use as the campaign hook",
    options=[i+1 for i in range(len(headlines))],
    format_func=lambda i: f"{i}. {headlines[i-1]}",
    index=ranked[0][0]-1 if ranked else 0,
)

if st.button("Send selected headline to Copywriter"):
    st.session_state["seed_hook"] = headlines[winning_idx-1]
    st.session_state["seed_details"] = context
    st.session_state["seed_source"] = "headline_test"
    st.switch_page("pages/06_Write_campaign_assets.py")

st.divider()
st.subheader("Persona breakdown")
for r in results:
    out = r.get("output") or {}
    with st.expander(f"{r['persona']} ({r['segment']})"):
        if "error" in out:
            st.error(out.get("error"))
            st.code(out.get("raw", ""))
            continue
        st.markdown("**Top 3**")
        for item in out.get("top_3") or []:
            hi = int(item.get("headline_index", 0))
            if hi and hi <= len(headlines):
                st.markdown(f"- #{item.get('rank')}: ({hi}) {headlines[hi-1]} - {item.get('why','')}")

        fb = out.get("headline_feedback") or []
        if fb:
            st.markdown("**Feedback**")
            for f in fb:
                hi = int(f.get("headline_index", 0))
                if not hi or hi > len(headlines):
                    continue
                st.markdown(f"**{hi}. {headlines[hi-1]}**")
                st.caption(f"Click: {f.get('click')} | Trust: {f.get('trust','')} | Promise: {f.get('implied_promise','')}")
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
