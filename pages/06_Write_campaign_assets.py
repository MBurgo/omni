import streamlit as st

from engines.creative import (
    COUNTRY_RULES,
    LENGTH_RULES,
    adapt_copy,
    generate_copy_with_plan,
    generate_variants,
    qa_and_patch_copy,
    revise_copy_goal,
    rewrite_with_traits_preserve_structure,
)
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.export import create_docx_from_markdown
from ui.layout import project_banner, require_project
from ui.seed import set_headline_test_seed

st.set_page_config(
    page_title="Copywriter",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

pid = require_project()

# Seed from other tools
seed_hook = st.session_state.get("seed_hook", "")
seed_details = st.session_state.get("seed_details", "")
seed_creative = st.session_state.get("seed_creative", "")
seed_source = st.session_state.get("seed_source", "")

st.session_state.setdefault("generated_copy", "")
st.session_state.setdefault("generated_plan", "")
st.session_state.setdefault("last_generate_settings", {})
st.session_state.setdefault("copywriter_variants", None)
st.session_state.setdefault("revised_copy", "")
st.session_state.setdefault("revised_plan", "")
st.session_state.setdefault("adapted_copy", "")
st.session_state.setdefault("adapted_plan", "")
# Default copywriter settings (main-page widgets)
st.session_state.setdefault("cw_trait_urgency", 8)
st.session_state.setdefault("cw_trait_data", 7)
st.session_state.setdefault("cw_trait_social", 6)
st.session_state.setdefault("cw_trait_compare", 6)
st.session_state.setdefault("cw_trait_imagery", 7)
st.session_state.setdefault("cw_trait_convo", 8)
st.session_state.setdefault("cw_trait_fomo", 7)
st.session_state.setdefault("cw_trait_repetition", 5)
st.session_state.setdefault("cw_country", "Australia")
st.session_state.setdefault("cw_provider", "OpenAI")
st.session_state.setdefault("cw_openai_model", "gpt-4o")
st.session_state.setdefault("cw_gemini_model", "gemini-1.5-pro")
st.session_state.setdefault("cw_auto_qa", True)


# Sidebar (project selector only)
with st.sidebar:
    project_banner(compact=True)

# Hero
st.markdown("<div class='page-title'>Brief our AI copywriter to deliver campaign assets</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='page-subtitle'>Generate campaign copy from a hook + brief, revise an existing draft, or localise copy from another market.</div>",
    unsafe_allow_html=True,
)

if seed_source:
    st.caption(f"Seed loaded from: `{seed_source}`")

# Copy settings (kept on the main page so the sidebar can stay collapsed)
with st.expander("Copy settings", expanded=False):
    left, right = st.columns([2, 1])

    with left:
        st.markdown("### Tone / traits")
        t1, t2 = st.columns(2)

        with t1:
            urgency = st.slider("Urgency", 1, 10, 8, key="cw_trait_urgency")
            data = st.slider("Data Richness", 1, 10, 7, key="cw_trait_data")
            social = st.slider("Social Proof", 1, 10, 6, key="cw_trait_social")
            compare = st.slider("Comparative Framing", 1, 10, 6, key="cw_trait_compare")

        with t2:
            imagery = st.slider("Imagery", 1, 10, 7, key="cw_trait_imagery")
            convo = st.slider("Conversational Tone", 1, 10, 8, key="cw_trait_convo")
            fomo = st.slider("FOMO", 1, 10, 7, key="cw_trait_fomo")
            repetition = st.slider("Repetition", 1, 10, 5, key="cw_trait_repetition")

        traits = {
            "Urgency": urgency,
            "Data_Richness": data,
            "Social_Proof": social,
            "Comparative_Framing": compare,
            "Imagery": imagery,
            "Conversational_Tone": convo,
            "FOMO": fomo,
            "Repetition": repetition,
        }

    with right:
        st.markdown("### Target")
        country = st.selectbox("Target country", list(COUNTRY_RULES.keys()), index=0, key="cw_country")

        st.markdown("### AI provider")
        provider = st.radio("Provider", options=["OpenAI", "Gemini"], index=0, horizontal=True, key="cw_provider")

        # Keep model selections stable even when the other provider is selected.
        openai_model = st.session_state.get("cw_openai_model", "gpt-4o")
        gemini_model = st.session_state.get("cw_gemini_model", "gemini-1.5-pro")

        if provider == "OpenAI":
            openai_model = st.selectbox("OpenAI model", options=["gpt-4o", "gpt-4o-mini"], index=0, key="cw_openai_model")
        else:
            gemini_model = st.selectbox(
                "Gemini model",
                options=["gemini-1.5-pro", "gemini-1.5-flash"],
                index=0,
                key="cw_gemini_model",
                help="Requires google.api_key in Streamlit secrets (falls back to OpenAI if missing).",
            )

        st.markdown("### Quality")
        auto_qa = st.checkbox(
            "Run QA pass (recommended)",
            value=True,
            key="cw_auto_qa",
            help="Checks structure, disclaimer, length, and compliance; auto-fixes if needed.",
        )


# Tabs
#
# Other pages set st.session_state["copywriter_mode"] to choose the first visible tab.
mode = (st.session_state.get("copywriter_mode") or "generate").lower().strip()

if mode == "adapt":
    TAB_ADAPT, TAB_GEN, TAB_REVISE = st.tabs(["Localise", "Generate", "Revise"])
elif mode == "revise":
    TAB_REVISE, TAB_GEN, TAB_ADAPT = st.tabs(["Revise", "Generate", "Localise"])
else:
    TAB_GEN, TAB_REVISE, TAB_ADAPT = st.tabs(["Generate", "Revise", "Localise"])

# --- Generate ---
with TAB_GEN:
    st.subheader("Campaign brief")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        copy_type = st.selectbox("Format", options=["Email", "Ads", "Sales Page"], index=0)
    with col2:
        length_choice = st.selectbox("Length", options=list(LENGTH_RULES.keys()), index=1)
    with col3:
        st.write("")

    seed_md = st.session_state.get("seed_metadata")
    seed_md = seed_md if isinstance(seed_md, dict) else {}

    hook = st.text_area(
        "Hook",
        value=seed_hook,
        height=80,
        placeholder="e.g., The ASX theme investors are missing...",
    )

    details = st.text_area(
        "Offer / context / notes",
        value=seed_details,
        height=180,
        placeholder="Product / offer details, audience context, must-say info...",
    )

    with st.expander("Advanced brief (optional)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            offer_price = st.text_input("Special offer price", value=str(seed_md.get("offer_price") or ""))
        with c2:
            retail_price = st.text_input("Retail price", value=str(seed_md.get("retail_price") or ""))
        with c3:
            offer_term = st.text_input("Subscription term", value=str(seed_md.get("offer_term") or ""))

        reports = st.text_area("Included reports", value=str(seed_md.get("reports") or ""), height=100)
        stocks_to_tease = st.text_input("Stocks to tease (optional)", value=str(seed_md.get("stocks_to_tease") or ""))
        quotes_news = st.text_area("Quotes / timely news (optional)", value=str(seed_md.get("quotes_news") or ""), height=110)

    if st.button("Generate copy", type="primary"):
        if not hook.strip() and not details.strip():
            st.warning("Add a hook or some details.")
        else:
            with st.spinner("Writing..."):
                brief = {
                    "hook": hook,
                    "details": details,
                    "offer_price": offer_price,
                    "retail_price": retail_price,
                    "offer_term": offer_term,
                    "reports": reports,
                    "stocks_to_tease": stocks_to_tease,
                    "quotes_news": quotes_news,
                }

                out = generate_copy_with_plan(
                    copy_type=copy_type,
                    country=country,
                    traits=traits,
                    brief=brief,
                    length_choice=length_choice,
                    provider=provider,
                    openai_model=openai_model,
                    gemini_model=gemini_model,
                )

                draft = (out.get("copy") or "").strip()
                plan = (out.get("plan") or "").strip()

                qa_meta = {}
                if auto_qa:
                    qa = qa_and_patch_copy(
                        draft=draft,
                        copy_type=copy_type,
                        country=country,
                        length_choice=length_choice,
                        traits=traits,
                        provider=provider,
                        openai_model="gpt-4o-mini",
                        gemini_model="gemini-1.5-flash",
                    )
                    draft = qa.get("copy") or draft
                    qa_meta = {"qa_status": qa.get("status"), "qa_critique": qa.get("critique")}

                st.session_state.generated_copy = draft
                st.session_state.generated_plan = plan
                st.session_state.last_generate_settings = {
                    "copy_type": copy_type,
                    "country": country,
                    "length_choice": length_choice,
                    "brief": brief,
                }
                st.session_state.copywriter_variants = None

                save_artifact(
                    pid,
                    type="draft",
                    title=f"Draft ({copy_type}) - {hook.strip()[:40] or 'untitled'}",
                    content_json={
                        "copy_type": copy_type,
                        "country": country,
                        "length_choice": length_choice,
                        "brief": brief,
                        "plan": plan,
                    },
                    content_text=draft,
                    metadata={
                        "provider": provider,
                        "openai_model": openai_model,
                        "gemini_model": gemini_model,
                        "traits": traits,
                        **qa_meta,
                    },
                )

    if st.session_state.generated_copy:
        st.divider()
        st.markdown("### Output")
        st.markdown(st.session_state.generated_copy)

        with st.expander("Show internal plan (AI outline)"):
            st.markdown(st.session_state.generated_plan or "_No plan captured._")

        # Download docx (markdown-aware)
        buf = create_docx_from_markdown(st.session_state.generated_copy)
        st.download_button(
            "Download as .docx",
            data=buf.getvalue(),
            file_name="copy.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        st.divider()
        st.markdown("### Variants")
        cvar1, cvar2 = st.columns([1, 1])
        with cvar1:
            if st.button("Generate 5 headline/subject + CTA variants"):
                with st.spinner("Brainstorming variants..."):
                    v = generate_variants(
                        base_copy=st.session_state.generated_copy,
                        n=5,
                        provider=provider,
                        openai_model="gpt-4o-mini",
                        gemini_model="gemini-1.5-flash",
                    )
                    st.session_state.copywriter_variants = v
        with cvar2:
            if st.session_state.copywriter_variants and st.button("Send headline variants to Headline Test"):
                hs = st.session_state.copywriter_variants.get("headlines") or []
                ctx = "\n".join(
                    [
                        f"Hook: {(st.session_state.last_generate_settings or {}).get('brief', {}).get('hook', '')}",
                        f"Details: {(st.session_state.last_generate_settings or {}).get('brief', {}).get('details', '')}",
                    ]
                ).strip()
                set_headline_test_seed(headlines=hs, context=ctx, source="copywriter:variants")
                st.switch_page("pages/04_Test_headlines.py")

        v = st.session_state.copywriter_variants
        if isinstance(v, dict) and (v.get("headlines") or v.get("ctas")):
            st.markdown("**Headline / subject ideas**")
            hs = v.get("headlines") or []
            if hs:
                cols = st.columns(min(5, len(hs)))
                for i, t in enumerate(hs[:5]):
                    with cols[i]:
                        st.markdown(f"**{i+1}.** {t}")
            else:
                st.caption("No headlines returned.")

            st.markdown("**CTA button ideas**")
            cs = v.get("ctas") or []
            if cs:
                cols = st.columns(min(5, len(cs)))
                for i, t in enumerate(cs[:5]):
                    with cols[i]:
                        st.markdown(f"**{i+1}.** {t}")
            else:
                st.caption("No CTAs returned.")

        st.divider()
        st.markdown("### Trait-based rewrite")
        if st.button("Rewrite this draft using current trait sliders (preserve structure)"):
            settings = st.session_state.last_generate_settings or {}
            copy_type0 = settings.get("copy_type") or "Email"
            length0 = settings.get("length_choice") or "Medium (200-500 words)"
            brief0 = settings.get("brief") or {}
            country0 = settings.get("country") or country

            with st.spinner("Rewriting with traits..."):
                out2 = rewrite_with_traits_preserve_structure(
                    copy_type=copy_type0,
                    country=country0,
                    traits=traits,
                    length_choice=length0,
                    original_copy=st.session_state.generated_copy,
                    brief=brief0,
                    provider=provider,
                    openai_model=openai_model,
                    gemini_model=gemini_model,
                )
                revised = (out2.get("copy") or "").strip()
                plan2 = (out2.get("plan") or "").strip()

                qa_meta = {}
                if auto_qa:
                    qa = qa_and_patch_copy(
                        draft=revised,
                        copy_type=copy_type0,
                        country=country0,
                        length_choice=length0,
                        traits=traits,
                        provider=provider,
                        openai_model="gpt-4o-mini",
                        gemini_model="gemini-1.5-flash",
                    )
                    revised = qa.get("copy") or revised
                    qa_meta = {"qa_status": qa.get("status"), "qa_critique": qa.get("critique")}

                st.session_state.generated_copy = revised
                st.session_state.generated_plan = plan2
                st.session_state.copywriter_variants = None

                save_artifact(
                    pid,
                    type="draft_revision_traits",
                    title=f"Trait rewrite ({copy_type0})",
                    content_json={
                        "copy_type": copy_type0,
                        "country": country0,
                        "length_choice": length0,
                        "brief": brief0,
                        "plan": plan2,
                    },
                    content_text=revised,
                    metadata={
                        "provider": provider,
                        "openai_model": openai_model,
                        "gemini_model": gemini_model,
                        "traits": traits,
                        **qa_meta,
                    },
                )

        colA, colB = st.columns(2)
        with colA:
            if st.button("Pressure-test this draft"):
                st.session_state["draft_for_validation"] = st.session_state.generated_copy
                st.switch_page("pages/05_Pressure_test_creative.py")
        with colB:
            if st.button("Use this as starting point in Revise tab"):
                st.session_state["seed_creative"] = st.session_state.generated_copy
                st.session_state["copywriter_mode"] = "revise"
                st.rerun()

# --- Revise ---
with TAB_REVISE:
    st.subheader("Revise an existing draft")
    existing = st.text_area("Paste draft", value=seed_creative, height=240)

    method = st.selectbox(
        "Revision method",
        options=[
            "Goal-based edit",
            "Rewrite using current trait sliders (preserve structure)",
        ],
        index=0,
    )

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
        disabled=(method != "Goal-based edit"),
    )

    extra = st.text_area("Additional instructions (optional)", height=90)

    if method == "Rewrite using current trait sliders (preserve structure)":
        c1, c2 = st.columns(2)
        with c1:
            r_copy_type = st.selectbox("Format", options=["Email", "Ads", "Sales Page"], index=0)
        with c2:
            r_length = st.selectbox("Length", options=list(LENGTH_RULES.keys()), index=1)
    else:
        r_copy_type = "Email"
        r_length = "Medium (200-500 words)"

    if st.button("Revise copy", type="primary"):
        if not existing.strip():
            st.warning("Paste a draft to revise.")
        else:
            with st.spinner("Rewriting..."):
                if method == "Goal-based edit":
                    out = revise_copy_goal(
                        target_country=country,
                        goal=goal,
                        existing_copy=existing,
                        extra_notes=extra,
                        provider=provider,
                        openai_model=openai_model,
                        gemini_model=gemini_model,
                    )
                    plan = ""
                else:
                    out2 = rewrite_with_traits_preserve_structure(
                        copy_type=r_copy_type,
                        country=country,
                        traits=traits,
                        length_choice=r_length,
                        original_copy=existing,
                        brief=None,
                        extra_instructions=extra,
                        provider=provider,
                        openai_model=openai_model,
                        gemini_model=gemini_model,
                    )
                    out = (out2.get("copy") or "").strip()
                    plan = (out2.get("plan") or "").strip()

                qa_meta = {}
                if auto_qa and method != "Goal-based edit":
                    qa = qa_and_patch_copy(
                        draft=out,
                        copy_type=r_copy_type,
                        country=country,
                        length_choice=r_length,
                        traits=traits,
                        provider=provider,
                        openai_model="gpt-4o-mini",
                        gemini_model="gemini-1.5-flash",
                    )
                    out = qa.get("copy") or out
                    qa_meta = {"qa_status": qa.get("status"), "qa_critique": qa.get("critique")}

                st.session_state.revised_copy = out
                st.session_state.revised_plan = plan

                save_artifact(
                    pid,
                    type="draft_revision",
                    title=f"Revision - {method[:18]}",
                    content_json={
                        "method": method,
                        "goal": goal,
                        "country": country,
                        "extra": extra,
                        "copy_type": r_copy_type,
                        "length_choice": r_length,
                        "plan": plan,
                    },
                    content_text=out,
                    metadata={
                        "provider": provider,
                        "openai_model": openai_model,
                        "gemini_model": gemini_model,
                        "traits": traits,
                        **qa_meta,
                    },
                )

    if st.session_state.revised_copy:
        st.divider()
        st.markdown("### Revised output")
        st.markdown(st.session_state.revised_copy)

        if st.session_state.revised_plan:
            with st.expander("Show internal plan (AI outline)"):
                st.markdown(st.session_state.revised_plan)

        buf = create_docx_from_markdown(st.session_state.revised_copy)
        st.download_button(
            "Download revised draft as .docx",
            data=buf.getvalue(),
            file_name="copy_revised.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

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

    original = st.text_area("Copy to adapt", value=seed_creative if mode == "adapt" else "", height=240)
    notes = st.text_area("Notes (optional)", height=90)

    if st.button("Adapt", type="primary"):
        if not original.strip():
            st.warning("Paste some copy.")
        else:
            with st.spinner("Adapting..."):
                out = adapt_copy(
                    source_country=src,
                    target_country=tgt,
                    copy_text=original,
                    brief_notes=notes,
                    provider=provider,
                    openai_model=openai_model,
                    gemini_model=gemini_model,
                )

                if auto_qa:
                    qa = qa_and_patch_copy(
                        draft=out,
                        copy_type="Sales Page" if "##" in out else "Email",
                        country=tgt,
                        length_choice="Long (500-1500 words)",
                        traits=traits,
                        provider=provider,
                        openai_model="gpt-4o-mini",
                        gemini_model="gemini-1.5-flash",
                    )
                    out = qa.get("copy") or out

                st.session_state.adapted_copy = out

                save_artifact(
                    pid,
                    type="draft_adapted",
                    title=f"Adapted {src} -> {tgt}",
                    content_json={"source": src, "target": tgt, "notes": notes},
                    content_text=out,
                    metadata={"provider": provider, "openai_model": openai_model, "gemini_model": gemini_model},
                )

    if st.session_state.adapted_copy:
        st.divider()
        st.markdown("### Adapted output")
        st.markdown(st.session_state.adapted_copy)

        buf = create_docx_from_markdown(st.session_state.adapted_copy)
        st.download_button(
            "Download adapted draft as .docx",
            data=buf.getvalue(),
            file_name="copy_adapted.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        if st.button("Pressure-test adapted draft"):
            st.session_state["draft_for_validation"] = st.session_state.adapted_copy
            st.switch_page("pages/05_Pressure_test_creative.py")
