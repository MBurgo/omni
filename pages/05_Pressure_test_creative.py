import json

import streamlit as st

from engines.audience import focus_group_debate
from engines.personas import load_personas, persona_label
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(page_title="Pressure-test creative", page_icon="🔬", layout="wide")
apply_branding()

st.title("🔬 Pressure-test creative")
st.caption("Believer vs Skeptic debate + moderator rewrite. Use this for headlines, emails, sales pages, and ad copy.")

project_banner()
pid = require_project()

_, segments, personas = load_personas()
if not personas:
    st.error("No personas found.")
    st.stop()

uid_to_p = {p.uid: p for p in personas}

# Preload from other flows
default_creative = st.session_state.get("draft_for_validation") or st.session_state.get("seed_creative") or ""

col1, col2, col3 = st.columns([2,2,1])
with col1:
    believer_uid = st.selectbox(
        "Believer",
        options=[p.uid for p in personas],
        index=0,
        format_func=lambda uid: persona_label(uid_to_p[uid]),
    )
with col2:
    skeptic_uid = st.selectbox(
        "Skeptic",
        options=[p.uid for p in personas],
        index=1 if len(personas) > 1 else 0,
        format_func=lambda uid: persona_label(uid_to_p[uid]),
    )
with col3:
    copy_type = st.selectbox("Copy type", options=["Headline", "Email", "Sales Page", "Other"], index=1)

creative = st.text_area("Creative to test", value=default_creative, height=260)

risk_flags = []
from engines.audience import claim_risk_flags, word_count, estimate_tokens

wc = word_count(creative)
tok = estimate_tokens(creative)
if creative.strip():
    risk_flags = claim_risk_flags(creative)
    st.caption(f"Size: {wc} words (approx {tok} tokens)")
    if risk_flags:
        st.warning("Risk flags detected: " + ", ".join(risk_flags))

with st.expander("Long copy settings", expanded=False):
    participant_scope = st.selectbox("Participants see", options=["Full text (capped)", "First N words", "Custom excerpt"], index=1)
    participant_n_words = st.slider("First N words", min_value=150, max_value=1200, value=450, step=50)
    participant_custom_excerpt = st.text_area("Custom excerpt", height=120)
    extract_brief = st.checkbox("Auto-extract structured brief (recommended)", value=True)

colA, colB, colC = st.columns(3)
with colA:
    model = st.selectbox("Debate model", options=["gpt-4o", "gpt-4o-mini"], index=0)
with colB:
    brief_model = st.selectbox("Brief extraction model", options=["gpt-4o-mini", "gpt-4o"], index=0)
with colC:
    moderator_model = st.selectbox("Moderator model", options=["gemini-1.5-pro", "gemini-1.5-flash"], index=0)

if st.button("Run focus group", type="primary"):
    if not creative.strip():
        st.warning("Paste creative first.")
        st.stop()

    believer = uid_to_p[believer_uid]
    skeptic = uid_to_p[skeptic_uid]

    with st.status("Running debate + moderator analysis...", expanded=True) as status:
        out = focus_group_debate(
            believer=believer,
            skeptic=skeptic,
            creative_text=creative,
            copy_type=copy_type,
            participant_scope=participant_scope,
            participant_n_words=participant_n_words,
            participant_custom_excerpt=participant_custom_excerpt,
            extract_brief=extract_brief,
            brief_model=brief_model,
            model=model,
            moderator_model=moderator_model,
        )
        status.update(label="Complete", state="complete", expanded=False)

    save_artifact(
        pid,
        type="focus_group",
        title=f"Focus group: {copy_type}",
        content_json=out,
        content_text="",
        metadata={
            "believer": believer.name,
            "skeptic": skeptic.name,
            "copy_type": copy_type,
            "model": model,
            "brief_model": brief_model,
            "moderator_model": moderator_model,
        },
    )

    st.session_state["focus_group_last"] = out
    st.rerun()

out = st.session_state.get("focus_group_last")
if not out:
    st.stop()

if out.get("error"):
    st.error(out["error"])
    st.stop()

st.divider()

st.subheader("What the personas saw")
with st.expander("Excerpt", expanded=False):
    st.write(out.get("excerpt", ""))

if out.get("brief_json") or out.get("brief_raw"):
    with st.expander("Extracted brief", expanded=False):
        if out.get("brief_json"):
            st.code(json.dumps(out.get("brief_json"), ensure_ascii=False, indent=2), language="json")
        else:
            st.code(out.get("brief_raw"), language="text")

st.subheader("Debate")
for turn in out.get("debate_turns") or []:
    st.markdown(f"**{turn.get('name')} ({turn.get('role')}):** {turn.get('text')}")
    st.divider()

st.subheader("Moderator analysis")
mod = out.get("moderator_json")
if isinstance(mod, dict):
    if mod.get("executive_summary"):
        st.success(mod.get("executive_summary"))
    cols = st.columns(3)
    with cols[0]:
        if mod.get("real_why"):
            st.markdown("**Real why**")
            st.write(mod.get("real_why"))
    with cols[1]:
        if mod.get("trust_gap"):
            st.markdown("**Trust gap**")
            st.write(mod.get("trust_gap"))
    with cols[2]:
        if mod.get("risk_flags"):
            st.markdown("**Risk flags**")
            st.markdown("- " + "\n- ".join(mod.get("risk_flags")))

    if mod.get("key_objections"):
        st.markdown("**Key objections**")
        st.markdown("- " + "\n- ".join(mod.get("key_objections")))
    if mod.get("proof_needed"):
        st.markdown("**Proof needed**")
        st.markdown("- " + "\n- ".join(mod.get("proof_needed")))
    if mod.get("actionable_fixes"):
        st.markdown("**Actionable fixes**")
        st.markdown("- " + "\n- ".join(mod.get("actionable_fixes")))

    st.divider()
    st.markdown("### ✍️ Suggested rewrite")
    rw = mod.get("rewrite") or {}
    if copy_type == "Headline":
        for h in (rw.get("headlines") or [])[:10]:
            st.markdown(f"- {h}")
    elif copy_type == "Email":
        if rw.get("subject"):
            st.markdown(f"**Subject:** {rw.get('subject')}")
        if rw.get("preheader"):
            st.markdown(f"**Preheader:** {rw.get('preheader')}")
        if rw.get("body"):
            st.markdown(rw.get("body"))
        if rw.get("cta"):
            st.markdown(f"**CTA:** {rw.get('cta')}")
        if rw.get("ps"):
            st.markdown(f"**P.S.:** {rw.get('ps')}")
    elif copy_type == "Sales Page":
        st.markdown(f"**Hero headline:** {rw.get('hero_headline','')}")
        st.markdown(f"**Hero subhead:** {rw.get('hero_subhead','')}")
        if rw.get("bullets"):
            st.markdown("**Bullets**")
            st.markdown("- " + "\n- ".join(rw.get("bullets")))
        if rw.get("proof_block"):
            st.markdown("**Proof block**")
            st.write(rw.get("proof_block"))
        if rw.get("offer_stack"):
            st.markdown("**Offer stack**")
            st.markdown("- " + "\n- ".join(rw.get("offer_stack")))
        if rw.get("cta_block"):
            st.markdown("**CTA block**")
            st.write(rw.get("cta_block"))
        if rw.get("cta_button"):
            st.markdown(f"**CTA button:** {rw.get('cta_button')}")
    else:
        st.write(rw)

    # Actions
    st.divider()
    colX, colY = st.columns(2)
    with colX:
        if st.button("Use rewrite as new draft"):
            # Convert rewrite to plain text for editing
            if copy_type == "Headline":
                new_text = (rw.get("headlines") or [""])[0]
            elif copy_type == "Email":
                parts = []
                if rw.get("subject"):
                    parts.append(f"Subject: {rw.get('subject')}")
                if rw.get("preheader"):
                    parts.append(f"Preheader: {rw.get('preheader')}")
                if rw.get("body"):
                    parts.append(rw.get("body"))
                if rw.get("cta"):
                    parts.append(f"CTA: {rw.get('cta')}")
                if rw.get("ps"):
                    parts.append(f"P.S.: {rw.get('ps')}")
                new_text = "\n\n".join([p for p in parts if p])
            else:
                new_text = json.dumps(rw, ensure_ascii=False, indent=2)

            st.session_state["seed_creative"] = new_text
            st.session_state["seed_source"] = "focus_group_rewrite"
            st.switch_page("pages/06_Write_campaign_assets.py")

    with colY:
        if st.button("Send original creative to Copywriter"):
            st.session_state["seed_creative"] = creative
            st.session_state["seed_source"] = "focus_group_original"
            st.switch_page("pages/06_Write_campaign_assets.py")

else:
    st.write(out.get("moderator_raw", ""))
