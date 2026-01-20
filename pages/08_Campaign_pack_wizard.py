import json
from io import BytesIO

import streamlit as st
from docx import Document

from engines.audience import focus_group_debate
from engines.creative import COUNTRY_RULES, LENGTH_RULES, generate_copy
from engines.personas import load_personas, persona_label
from engines.signals import collect_signals, summarise_daily_brief
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(page_title="Campaign pack wizard", page_icon="🧩", layout="wide")
apply_branding()

st.title("🧩 Campaign pack wizard")
st.caption("A guided flow: signals -> hook -> draft -> focus group -> packaged output.")

project_banner()
pid = require_project()

_, _, personas = load_personas()
uid_to_p = {p.uid: p for p in personas}

# Session state for wizard
st.session_state.setdefault("wiz_query", "ASX 200")
st.session_state.setdefault("wiz_brief", None)
st.session_state.setdefault("wiz_selected_opp", None)
st.session_state.setdefault("wiz_hook", "")
st.session_state.setdefault("wiz_details", "")
st.session_state.setdefault("wiz_draft", "")
st.session_state.setdefault("wiz_focus", None)
st.session_state.setdefault("wiz_pack", "")

TAB1, TAB2, TAB3, TAB4 = st.tabs(["1) Insight", "2) Draft", "3) Validate", "4) Pack"]) 

with TAB1:
    st.subheader("1) Generate an insight")
    colA, colB, colC = st.columns([2,2,1])
    with colA:
        st.session_state.wiz_query = st.text_input("Query", value=st.session_state.wiz_query)
    with colB:
        trends_q = st.text_input("Trends query/topic id (optional)", value=st.session_state.get("wiz_trends_q", ""))
        st.session_state.wiz_trends_q = trends_q
    with colC:
        model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0, key="wiz_signal_model")

    if st.button("Run signals", type="primary"):
        with st.status("Collecting signals and generating opportunities...", expanded=True) as status:
            d = collect_signals(query=st.session_state.wiz_query.strip(), trends_query_or_topic_id=(trends_q.strip() or None))
            brief = summarise_daily_brief(d, model=model)
            st.session_state.wiz_brief = brief
            status.update(label="Insight ready", state="complete", expanded=False)

    brief = st.session_state.get("wiz_brief")
    if isinstance(brief, dict) and brief.get("opportunities"):
        st.markdown("### Choose an opportunity")
        opps = brief.get("opportunities") or []
        labels = [f"{i+1}. {o.get('title','Opportunity')}" for i, o in enumerate(opps)]
        choice = st.selectbox("Opportunity", options=list(range(len(opps))), format_func=lambda i: labels[i])
        opp = opps[choice]
        st.session_state.wiz_selected_opp = opp

        st.write(opp.get("synopsis", ""))
        hooks = opp.get("suggested_hooks") or []
        st.session_state.wiz_hook = st.text_input("Hook", value=hooks[0] if hooks else opp.get("title", ""))
        st.session_state.wiz_details = st.text_area("Details", value=json.dumps(opp, ensure_ascii=False, indent=2), height=160)

        if st.button("Save insight to project"):
            save_artifact(
                pid,
                type="campaign_pack_insight",
                title=f"Pack insight: {st.session_state.wiz_query}",
                content_json={"brief": brief, "selected_opportunity": opp},
                content_text="",
                metadata={"query": st.session_state.wiz_query, "model": model},
            )
            st.success("Saved to Library.")

with TAB2:
    st.subheader("2) Draft")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        copy_type = st.selectbox("Format", options=["Email", "Ads", "Sales Page"], index=0, key="wiz_copy_type")
    with col2:
        country = st.selectbox("Country", options=list(COUNTRY_RULES.keys()), index=0, key="wiz_country")
    with col3:
        length_choice = st.selectbox("Length", options=list(LENGTH_RULES.keys()), index=1, key="wiz_length")

    hook = st.text_area("Hook", value=st.session_state.wiz_hook, height=70)
    details = st.text_area("Details", value=st.session_state.wiz_details, height=200)

    with st.expander("Traits", expanded=False):
        traits = {
            "Urgency": st.slider("Urgency", 1, 10, 8, key="wiz_t_urg"),
            "Data_Richness": st.slider("Data Richness", 1, 10, 7, key="wiz_t_data"),
            "Social_Proof": st.slider("Social Proof", 1, 10, 6, key="wiz_t_soc"),
            "Comparative_Framing": st.slider("Comparative Framing", 1, 10, 6, key="wiz_t_comp"),
            "Imagery": st.slider("Imagery", 1, 10, 7, key="wiz_t_img"),
            "Conversational_Tone": st.slider("Conversational Tone", 1, 10, 8, key="wiz_t_conv"),
            "FOMO": st.slider("FOMO", 1, 10, 7, key="wiz_t_fomo"),
            "Repetition": st.slider("Repetition", 1, 10, 5, key="wiz_t_rep"),
        }

    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0, key="wiz_copy_model")

    if st.button("Generate draft", type="primary"):
        with st.spinner("Writing..."):
            out = generate_copy(copy_type=copy_type, country=country, traits=traits, brief={"hook": hook, "details": details}, length_choice=length_choice, model=model)
            st.session_state.wiz_draft = out

            save_artifact(
                pid,
                type="campaign_pack_draft",
                title=f"Pack draft ({copy_type})",
                content_json={"hook": hook, "details": details, "copy_type": copy_type, "country": country},
                content_text=out,
                metadata={"model": model, "traits": traits},
            )

    st.session_state.wiz_hook = hook
    st.session_state.wiz_details = details

    if st.session_state.wiz_draft:
        st.markdown("### Draft")
        st.text_area("", value=st.session_state.wiz_draft, height=320, key="wiz_draft_editor")
        st.session_state.wiz_draft = st.session_state.wiz_draft_editor

with TAB3:
    st.subheader("3) Validate")
    if not personas:
        st.error("No personas available.")
        st.stop()

    colA, colB, colC = st.columns([2,2,1])
    with colA:
        believer_uid = st.selectbox("Believer", options=[p.uid for p in personas], index=0, format_func=lambda uid: persona_label(uid_to_p[uid]), key="wiz_bel")
    with colB:
        skeptic_uid = st.selectbox("Skeptic", options=[p.uid for p in personas], index=1 if len(personas) > 1 else 0, format_func=lambda uid: persona_label(uid_to_p[uid]), key="wiz_ske")
    with colC:
        copy_type = st.selectbox("Copy type", options=["Headline", "Email", "Sales Page", "Other"], index=1, key="wiz_val_type")

    creative = st.text_area("Draft to test", value=st.session_state.wiz_draft, height=260)

    if st.button("Run focus group", type="primary"):
        if not creative.strip():
            st.warning("Generate or paste a draft first.")
        else:
            with st.status("Running focus group...", expanded=True) as status:
                out = focus_group_debate(
                    believer=uid_to_p[believer_uid],
                    skeptic=uid_to_p[skeptic_uid],
                    creative_text=creative,
                    copy_type=copy_type,
                    participant_scope="First N words",
                    participant_n_words=450,
                    extract_brief=True,
                    model="gpt-4o",
                    moderator_model="gemini-1.5-pro",
                )
                st.session_state.wiz_focus = out
                status.update(label="Validation complete", state="complete", expanded=False)

            save_artifact(
                pid,
                type="campaign_pack_focus_group",
                title=f"Pack focus group ({copy_type})",
                content_json=out,
                content_text="",
                metadata={"believer": uid_to_p[believer_uid].name, "skeptic": uid_to_p[skeptic_uid].name},
            )

    if st.session_state.wiz_focus and isinstance(st.session_state.wiz_focus.get("moderator_json"), dict):
        mod = st.session_state.wiz_focus["moderator_json"]
        st.markdown("### Moderator summary")
        st.success(mod.get("executive_summary", ""))
        if mod.get("actionable_fixes"):
            st.markdown("**Fixes**")
            st.markdown("- " + "\n- ".join(mod.get("actionable_fixes")))

with TAB4:
    st.subheader("4) Pack")

    brief = st.session_state.get("wiz_selected_opp")
    draft = st.session_state.get("wiz_draft")
    focus = st.session_state.get("wiz_focus")

    def build_pack() -> str:
        lines = []
        lines.append(f"# Campaign Pack")
        lines.append("")
        lines.append(f"## Insight")
        if isinstance(brief, dict):
            lines.append(f"**Title:** {brief.get('title','')}")
            lines.append(f"**Synopsis:** {brief.get('synopsis','')}")
            if brief.get("suggested_hooks"):
                lines.append("**Hooks:**")
                for h in (brief.get("suggested_hooks") or [])[:6]:
                    lines.append(f"- {h}")
        else:
            lines.append("(No insight selected)")

        lines.append("")
        lines.append("## Draft")
        lines.append(draft or "(No draft)")

        lines.append("")
        lines.append("## Focus group")
        if isinstance(focus, dict) and isinstance(focus.get("moderator_json"), dict):
            m = focus["moderator_json"]
            lines.append(f"**Executive summary:** {m.get('executive_summary','')}")
            if m.get("key_objections"):
                lines.append("**Key objections:**")
                for o in m.get("key_objections"):
                    lines.append(f"- {o}")
            if m.get("proof_needed"):
                lines.append("**Proof needed:**")
                for o in m.get("proof_needed"):
                    lines.append(f"- {o}")
            if m.get("actionable_fixes"):
                lines.append("**Actionable fixes:**")
                for o in m.get("actionable_fixes"):
                    lines.append(f"- {o}")
            lines.append("")
            lines.append("### Suggested rewrite")
            lines.append(json.dumps(m.get("rewrite") or {}, ensure_ascii=False, indent=2))
        else:
            lines.append("(No focus group run)")

        return "\n".join(lines)

    if st.button("Build pack", type="primary"):
        pack_text = build_pack()
        st.session_state.wiz_pack = pack_text
        save_artifact(pid, type="campaign_pack", title="Campaign pack", content_json=None, content_text=pack_text, metadata={})

    if st.session_state.wiz_pack:
        st.markdown("### Output")
        st.text_area("", value=st.session_state.wiz_pack, height=360)

        # Docx
        doc = Document()
        for line in st.session_state.wiz_pack.splitlines():
            doc.add_paragraph(line)
        buf = BytesIO()
        doc.save(buf)
        st.download_button(
            "Download pack as .docx",
            data=buf.getvalue(),
            file_name="campaign_pack.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
