import json

import streamlit as st

from engines.audience import ask_persona
from engines.personas import load_personas, persona_label
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(page_title="Ask a persona", page_icon="🧠", layout="wide")
apply_branding()

st.title("🧠 Ask a persona")
st.caption("Interview synthetic Australian investor personas. Use this for copy reactions, trust triggers, and objections.")

project_banner()
pid = require_project()

path, segments, personas = load_personas()
if not personas:
    st.error("No personas file found. Expected personas.json in the app root.")
    st.stop()

# State
st.session_state.setdefault("persona_chat", {})  # uid -> [(q,a),...]

# Segment selection
segment_opts = ["All"] + [s.get("id") or s.get("label") for s in segments]
segment_label = {s.get("id") or s.get("label"): s.get("label", "Unknown") for s in segments}

seg = st.selectbox("Segment", options=segment_opts, format_func=lambda x: "All" if x == "All" else segment_label.get(x, x))
if seg == "All":
    visible = personas
else:
    visible = [p for p in personas if p.segment_id == seg or p.segment_label == segment_label.get(seg)]

mode = st.radio("Mode", options=["Single persona", "Batch (segment)"], horizontal=True)

if mode == "Single persona":
    # Persona select
    uid_list = [p.uid for p in visible]
    sel_uid = st.selectbox("Persona", options=uid_list, format_func=lambda uid: persona_label(next(p for p in visible if p.uid == uid)))
    persona = next(p for p in visible if p.uid == sel_uid)

    with st.expander("Persona details", expanded=False):
        core = persona.core
        st.markdown(f"**{core.get('name','')}** ({persona.segment_label})")
        st.write(core.get("narrative", ""))
        st.caption(
            f"Age: {core.get('age','')} | Location: {core.get('location','')} | Occupation: {core.get('occupation','')}"
        )
        bt = core.get("behavioural_traits") or {}
        st.caption(
            f"Risk: {bt.get('risk_tolerance','')} | Experience: {bt.get('investment_experience','')}"
        )

    question = st.text_area("Question", placeholder="e.g., What would make this offer feel credible to you?", height=120)
    col1, col2 = st.columns([1,2])
    with col1:
        model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=1)
    with col2:
        temperature = st.slider("Temperature", min_value=0.0, max_value=1.2, value=0.7, step=0.1)

    if st.button("Ask", type="primary"):
        if not question.strip():
            st.warning("Enter a question.")
        else:
            history = st.session_state.persona_chat.get(persona.uid, [])
            ans = ask_persona(persona, question.strip(), history=history, model=model, temperature=temperature)

            st.session_state.persona_chat.setdefault(persona.uid, []).append((question.strip(), ans))

            # Persist as artifact
            save_artifact(
                pid,
                type="persona_interview",
                title=f"{persona.name}: {question.strip()[:60]}",
                content_json={"persona_uid": persona.uid, "persona": persona.name, "question": question.strip(), "answer": ans},
                content_text=f"**Q:** {question.strip()}\n\n**A ({persona.name}):** {ans}",
                metadata={"persona_uid": persona.uid, "segment": persona.segment_label, "model": model},
            )

            st.rerun()

    # History
    hist = st.session_state.persona_chat.get(persona.uid, [])
    if hist:
        st.subheader("Conversation")
        for q, a in reversed(hist[-10:]):
            st.markdown(f"**You:** {q}")
            st.markdown(f"**{persona.name}:** {a}")
            st.divider()

else:
    st.info("Batch mode asks the same question to multiple personas. Keep batches small to control cost.")
    max_n = st.slider("Max personas to ask", min_value=2, max_value=15, value=8)
    question = st.text_area("Question", placeholder="e.g., What objections do you have to this headline?", height=120)
    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=1)

    if st.button("Run batch", type="primary"):
        if not question.strip():
            st.warning("Enter a question.")
        else:
            batch = visible[:max_n]
            results = []
            with st.status(f"Interviewing {len(batch)} personas...", expanded=True) as status:
                for p in batch:
                    ans = ask_persona(p, question.strip(), history=None, model=model, temperature=0.7)
                    results.append({"persona": p.name, "uid": p.uid, "segment": p.segment_label, "answer": ans})
                    st.write(f"- {p.name}: done")
                status.update(label="Batch complete", state="complete", expanded=False)

            # Persist
            save_artifact(
                pid,
                type="persona_batch",
                title=f"Batch: {question.strip()[:60]}",
                content_json={"question": question.strip(), "results": results},
                content_text="\n\n".join([f"**{r['persona']} ({r['segment']}):** {r['answer']}" for r in results]),
                metadata={"segment": seg, "model": model, "n": len(results)},
            )

            st.subheader("Results")
            for r in results:
                st.markdown(f"**{r['persona']} ({r['segment']}):** {r['answer']}")
                st.divider()
