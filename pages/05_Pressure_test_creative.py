import json

import streamlit as st

from engines.audience import focus_group_debate
from engines.personas import Persona, load_personas
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import hub_nav
from ui.seed import set_copywriter_seed


def _short_persona_label(p: Persona) -> str:
    """Compact persona label for dropdowns (matches screenshot style)."""
    return f"{p.name} ({p.segment_label})"


st.set_page_config(
    page_title="Pressure test creative",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

# Page-specific tweaks to better match the provided screenshot.
st.markdown(
    """
<style>
/* Make the expander look like a full-width pill row */
div[data-testid="stExpander"] details {
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: 16px;
  background: rgba(255,255,255,0.02);
}
div[data-testid="stExpander"] summary {
  padding: 0.85rem 1.05rem;
  font-family: 'Poppins', sans-serif;
  font-weight: 700;
  color: rgba(255,255,255,0.92);
}
div[data-testid="stExpander"] summary:hover {
  background: rgba(255,255,255,0.03);
  border-radius: 16px;
}

/* Slightly bigger textarea to match screenshot proportions */
[data-testid="stTextArea"] textarea {
  min-height: 285px;
}
</style>
""",
    unsafe_allow_html=True,
)


pid = hub_nav()

_, segments, personas = load_personas()
if not personas:
    st.error("No personas found.")
    st.stop()

uid_to_p = {p.uid: p for p in personas}

# Preload from other flows
default_creative = st.session_state.get("draft_for_validation") or st.session_state.get("seed_creative") or ""


# --- Hero ---
st.markdown(
    "<div class='hero-title'>Pressure test your creatives using our AI personas</div>",
    unsafe_allow_html=True,
)
st.markdown(
    """
<div class='page-subtitle'>
Our AI personas are built using real Australian investor demographics and traits. Ask them any questions regarding their
feelings, motivations or opinions. Our AI personas will take a “Believer vs Skeptic” debate approach, and our moderator will
scan their arguments for insights.. Use this to pressure test headlines, emails, sales pages, and ad copy.
</div>
""",
    unsafe_allow_html=True,
)


# --- Inputs ---
col1, col2, col3 = st.columns([2, 2, 1], gap="large")
with col1:
    believer_uid = st.selectbox(
        "Believer",
        options=[p.uid for p in personas],
        index=0,
        format_func=lambda uid: _short_persona_label(uid_to_p[uid]),
    )
with col2:
    skeptic_uid = st.selectbox(
        "Skeptic",
        options=[p.uid for p in personas],
        index=1 if len(personas) > 1 else 0,
        format_func=lambda uid: _short_persona_label(uid_to_p[uid]),
    )
with col3:
    copy_type = st.selectbox(
        "Copy type",
        options=["Email", "Headline", "Sales Page", "Ad copy", "Other"],
        index=0,
    )

creative = st.text_area(
    "Creative to test",
    value=default_creative,
    height=300,
    placeholder="Paste your headline/email/sales page/ad copy here…",
)


# --- Long copy settings ---
with st.expander("Long copy settings", expanded=False):
    st.caption(
        "If you’re testing long creative, you can limit what participants see while still giving the moderator a structured brief."
    )
    participant_scope = st.selectbox(
        "Participants see",
        options=["Full text (capped)", "First N words", "Custom excerpt"],
        index=1,
    )
    participant_n_words = st.slider("First N words", min_value=150, max_value=1200, value=450, step=50)
    participant_custom_excerpt = st.text_area("Custom excerpt", height=120)
    extract_brief = st.checkbox("Auto-extract structured brief (recommended)", value=True)


# --- Models ---
colA, colB, colC, colD = st.columns([1, 1, 1, 0.35], gap="large")
with colA:
    model = st.selectbox("Debate model", options=["gpt-4o", "gpt-4o-mini"], index=0)
with colB:
    brief_model = st.selectbox("Brief extraction model", options=["gpt-4o-mini", "gpt-4o"], index=0)
with colC:
    _moderator_choice = st.selectbox(
        "Moderator model",
        options=[
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "Custom…",
        ],
        index=0,
        help="Gemini is preferred for the moderator. If Gemini isn't configured, the app falls back to OpenAI.",
    )

    if _moderator_choice == "Custom…":
        moderator_model = st.text_input(
            "Custom Gemini model id",
            value=st.session_state.get("moderator_model_custom", "gemini-2.5-pro"),
            help="Paste the exact model id your Google API key has access to.",
        ).strip() or "gemini-2.5-pro"
        st.session_state["moderator_model_custom"] = moderator_model
    else:
        moderator_model = _moderator_choice

with colD:
    # Unlabeled toggle (matches the screenshot’s bottom-right control). It currently controls
    # whether the debate transcript is shown in full.
    show_full_debate = st.toggle("Show full debate", value=True, label_visibility="collapsed")


run = st.button("Run focus group", type="primary")
if run:
    if not creative.strip():
        st.warning("Paste creative first.")
        st.stop()

    believer = uid_to_p[believer_uid]
    skeptic = uid_to_p[skeptic_uid]

    with st.status("Running debate + moderator analysis…", expanded=True) as status:
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
    st.session_state["focus_group_show_full_debate"] = show_full_debate
    st.rerun()


out = st.session_state.get("focus_group_last")
if not out:
    st.stop()

if out.get("error"):
    st.error(out["error"])
    st.stop()


st.divider()

tabs = st.tabs(["What the personas saw", "Debate", "Moderator analysis", "Rewrite actions"])

with tabs[0]:
    with st.expander("Excerpt", expanded=False):
        st.write(out.get("excerpt", ""))

    if out.get("brief_json") or out.get("brief_raw"):
        with st.expander("Extracted brief", expanded=False):
            if out.get("brief_json"):
                st.code(json.dumps(out.get("brief_json"), ensure_ascii=False, indent=2), language="json")
            else:
                st.code(out.get("brief_raw"), language="text")

with tabs[1]:
    debate_turns = out.get("debate_turns") or []
    if not debate_turns:
        st.info("No debate turns found.")
    else:
        full = st.session_state.get("focus_group_show_full_debate", True)
        turns_to_show = debate_turns if full else debate_turns[:6]
        for turn in turns_to_show:
            st.markdown(f"**{turn.get('name')} ({turn.get('role')}):** {turn.get('text')}")
            st.divider()

        if not full and len(debate_turns) > len(turns_to_show):
            st.caption("Debate truncated. Enable the bottom-right toggle and rerun to show the full transcript.")

with tabs[2]:
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
    else:
        st.write(out.get("moderator_raw", ""))

with tabs[3]:
    mod = out.get("moderator_json") or {}
    rw = mod.get("rewrite") or {}

    st.markdown("### Suggested rewrite")
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

    st.divider()
    colX, colY = st.columns(2)
    with colX:
        if st.button("Use rewrite as new draft"):
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

            set_copywriter_seed(
                mode="revise",
                creative=new_text,
                source="focus_group_rewrite",
            )
            st.switch_page("pages/06_Write_campaign_assets.py")

    with colY:
        if st.button("Send original creative to Copywriter"):
            set_copywriter_seed(
                mode="revise",
                creative=creative,
                source="focus_group_original",
            )
            st.switch_page("pages/06_Write_campaign_assets.py")
