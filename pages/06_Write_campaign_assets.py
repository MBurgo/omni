import json
from io import BytesIO

import streamlit as st
from docx import Document

from engines.creative import COUNTRY_RULES, LENGTH_RULES, adapt_copy, generate_copy
from engines.llm import query_openai
from ui.branding import apply_branding
from ui.layout import project_banner, require_project
from storage.store import save_artifact

st.set_page_config(page_title="Copywriter", page_icon="✍️", layout="wide", initial_sidebar_state="collapsed")
apply_branding()

st.title("✍️ Copywriter")
st.caption("Generate campaign copy from a hook + brief, or revise an existing draft.")

project_banner()
pid = require_project()

# Seed from other tools
seed_hook = st.session_state.get("seed_hook", "")
seed_details = st.session_state.get("seed_details", "")
seed_creative = st.session_state.get("seed_creative", "")

st.session_state.setdefault("generated_copy", "")
st.session_state.setdefault("revised_copy", "")
st.session_state.setdefault("adapted_copy", "")

# Sidebar settings
with st.sidebar:
    st.subheader("Tone / traits")
    traits = {
        "Urgency": st.slider("Urgency", 1, 10, 8),
        "Data_Richness": st.slider("Data Richness", 1, 10, 7),
        "Social_Proof": st.slider("Social Proof", 1, 10, 6),
        "Comparative_Framing": st.slider("Comparative Framing", 1, 10, 6),
        "Imagery": st.slider("Imagery", 1, 10, 7),
        "Conversational_Tone": st.slider("Conversational Tone", 1, 10, 8),
        "FOMO": st.slider("FOMO", 1, 10, 7),
        "Repetition": st.slider("Repetition", 1, 10, 5),
    }

    st.divider()
    country = st.selectbox("Target country", list(COUNTRY_RULES.keys()), index=0)
    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0)

# Tabs
#
# Home tiles can set st.session_state["copywriter_mode"] to choose the first visible tab.
# (Streamlit tabs always default to the first tab.)
mode = (st.session_state.get("copywriter_mode") or "generate").lower().strip()

if mode == "adapt":
    TAB_ADAPT, TAB_GEN, TAB_REVISE = st.tabs(["Localise", "Generate", "Revise"])
else:
    TAB_GEN, TAB_REVISE, TAB_ADAPT = st.tabs(["Generate", "Revise", "Localise"])

# --- Generate ---
with TAB_GEN:
    st.subheader("Campaign brief")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        copy_type = st.selectbox("Format", options=["Email", "Ads", "Sales Page"], index=0)
    with col2:
        length_choice = st.selectbox("Length", options=list(LENGTH_RULES.keys()), index=1)
    with col3:
        st.write("")

    hook = st.text_area("Hook", value=seed_hook, height=80, placeholder="e.g., The ASX theme investors are missing...")
    details = st.text_area("Offer / context / notes", value=seed_details, height=220)

    if st.button("Generate copy", type="primary"):
        if not hook.strip() and not details.strip():
            st.warning("Add a hook or some details.")
        else:
            with st.spinner("Writing..."):
                out = generate_copy(
                    copy_type=copy_type,
                    country=country,
                    traits=traits,
                    brief={"hook": hook, "details": details},
                    length_choice=length_choice,
                    model=model,
                )
                st.session_state.generated_copy = out

                save_artifact(
                    pid,
                    type="draft",
                    title=f"Draft ({copy_type}) - {hook.strip()[:40] or 'untitled'}",
                    content_json={"copy_type": copy_type, "country": country, "hook": hook, "details": details},
                    content_text=out,
                    metadata={"model": model, "traits": traits},
                )

    if st.session_state.generated_copy:
        st.divider()
        st.markdown("### Output")
        st.markdown(st.session_state.generated_copy)

        # Download docx
        doc = Document()
        for line in st.session_state.generated_copy.splitlines():
            doc.add_paragraph(line)
        buf = BytesIO()
        doc.save(buf)
        st.download_button(
            "Download as .docx",
            data=buf.getvalue(),
            file_name="copy.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        colA, colB = st.columns(2)
        with colA:
            if st.button("Pressure-test this draft"):
                st.session_state["draft_for_validation"] = st.session_state.generated_copy
                st.switch_page("pages/05_Pressure_test_creative.py")
        with colB:
            if st.button("Use this as starting point in Revise tab"):
                st.session_state["seed_creative"] = st.session_state.generated_copy
                st.rerun()

# --- Revise ---
with TAB_REVISE:
    st.subheader("Revise an existing draft")
    existing = st.text_area("Paste draft", value=seed_creative, height=240)

    goal = st.selectbox(
        "Revision goal",
        options=[
            "Tighten and clarify (more credible)",
            "Add proof and specificity (without inventing facts)",
            "Increase urgency (compliant)",
            "Make tone calmer (less hype)",
            "Rewrite to fit AU investor tone",
        ],
        index=0,
    )

    extra = st.text_area("Additional instructions (optional)", height=90)

    if st.button("Revise copy", type="primary"):
        if not existing.strip():
            st.warning("Paste a draft to revise.")
        else:
            sys_msg = (
                "You are a senior direct-response editor at The Motley Fool. "
                "Rewrite the copy to achieve the goal, while staying compliant: no guaranteed outcomes, "
                "no invented performance numbers, no invented authorities. Return only the revised copy."
            )
            user_msg = f"GOAL: {goal}\n\nTARGET COUNTRY: {country}\n\nEXTRA NOTES: {extra}\n\nCOPY:\n{existing}"

            with st.spinner("Rewriting..."):
                out = query_openai(
                    [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                    model=model,
                    temperature=0.5,
                )
                st.session_state.revised_copy = out

                save_artifact(
                    pid,
                    type="draft_revision",
                    title=f"Revision - {goal[:30]}",
                    content_json={"goal": goal, "country": country, "extra": extra},
                    content_text=out,
                    metadata={"model": model},
                )

    if st.session_state.revised_copy:
        st.divider()
        st.markdown("### Revised output")
        st.markdown(st.session_state.revised_copy)

        if st.button("Pressure-test revised draft"):
            st.session_state["draft_for_validation"] = st.session_state.revised_copy
            st.switch_page("pages/05_Pressure_test_creative.py")

# --- Localise ---
with TAB_ADAPT:
    st.subheader("Adapt copy from another market")
    c1, c2 = st.columns(2)
    with c1:
        src = st.selectbox("Source", options=list(COUNTRY_RULES.keys()), index=3)
    with c2:
        tgt = st.selectbox("Target", options=list(COUNTRY_RULES.keys()), index=0)

    original = st.text_area("Copy to adapt", height=240)
    notes = st.text_area("Notes (optional)", height=90)

    if st.button("Adapt", type="primary"):
        if not original.strip():
            st.warning("Paste some copy.")
        else:
            with st.spinner("Adapting..."):
                out = adapt_copy(source_country=src, target_country=tgt, copy_text=original, brief_notes=notes, model=model)
                st.session_state.adapted_copy = out

                save_artifact(
                    pid,
                    type="draft_adapted",
                    title=f"Adapted {src} -> {tgt}",
                    content_json={"source": src, "target": tgt, "notes": notes},
                    content_text=out,
                    metadata={"model": model},
                )

    if st.session_state.adapted_copy:
        st.divider()
        st.markdown("### Adapted output")
        st.markdown(st.session_state.adapted_copy)

        if st.button("Pressure-test adapted draft"):
            st.session_state["draft_for_validation"] = st.session_state.adapted_copy
            st.switch_page("pages/05_Pressure_test_creative.py")
