from __future__ import annotations

import io
from typing import Any, Dict

import streamlit as st
from bs4 import BeautifulSoup
from docx import Document

from engines.briefs import brief_builder_turn, extract_campaign_brief_from_text
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
from model_registry import (
    DEFAULT_GEMINI_CHEAP_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OPENAI_FAST_MODEL,
    GEMINI_MODELS_RECOMMENDED,
    OPENAI_CHAT_MODELS,
)
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.export import create_docx_from_markdown
from ui.layout import hub_nav
from ui.seed import set_headline_test_seed

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore


# -------------------------
# Helpers
# -------------------------

def _safe_str(x: Any) -> str:
    return str(x).strip() if x is not None else ""


def extract_text_from_upload(upload: Any) -> str:
    """Extract text from a Streamlit UploadedFile (txt/docx/html/pdf)."""
    if upload is None:
        return ""

    name = (getattr(upload, "name", "") or "").lower()
    data = upload.getvalue() if hasattr(upload, "getvalue") else b""

    if name.endswith(".txt"):
        try:
            return data.decode("utf-8")
        except Exception:
            return data.decode("latin-1", errors="ignore")

    if name.endswith(".docx"):
        try:
            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs if (p.text or "").strip()]
            return "\n".join(parts).strip()
        except Exception:
            return ""

    if name.endswith((".html", ".htm")):
        try:
            html = data.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text("\n").strip()
        except Exception:
            return ""

    if name.endswith(".pdf") and PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(data))
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
            return "\n".join([p for p in parts if p.strip()]).strip()
        except Exception:
            return ""

    return ""


def _apply_extracted_brief_to_state(brief: Dict[str, str]) -> None:
    """Map extracted brief keys into Streamlit widget keys."""
    st.session_state["cw_brief_hook"] = _safe_str(brief.get("hook"))
    st.session_state["cw_brief_details"] = _safe_str(brief.get("details"))
    st.session_state["cw_brief_offer_price"] = _safe_str(brief.get("offer_price"))
    st.session_state["cw_brief_retail_price"] = _safe_str(brief.get("retail_price"))
    st.session_state["cw_brief_offer_term"] = _safe_str(brief.get("offer_term"))
    st.session_state["cw_brief_reports"] = _safe_str(brief.get("reports"))
    st.session_state["cw_brief_stocks"] = _safe_str(brief.get("stocks_to_tease"))
    st.session_state["cw_brief_quotes_news"] = _safe_str(brief.get("quotes_news"))


def get_traits() -> Dict[str, int]:
    return {
        "Urgency": int(st.session_state.get("cw_trait_urgency", 8)),
        "Data_Richness": int(st.session_state.get("cw_trait_data", 7)),
        "Social_Proof": int(st.session_state.get("cw_trait_social", 6)),
        "Comparative_Framing": int(st.session_state.get("cw_trait_compare", 6)),
        "Imagery": int(st.session_state.get("cw_trait_imagery", 7)),
        "Conversational_Tone": int(st.session_state.get("cw_trait_convo", 8)),
        "FOMO": int(st.session_state.get("cw_trait_fomo", 7)),
        "Repetition": int(st.session_state.get("cw_trait_repetition", 5)),
    }


def get_selected_models() -> tuple[str, str, str]:
    """Return (provider, openai_model, gemini_model) from session state."""
    provider = st.session_state.get("cw_provider", "OpenAI")

    openai_model = (st.session_state.get("cw_openai_model") or OPENAI_CHAT_MODELS[0]).strip()

    gemini_choice = st.session_state.get("cw_gemini_model", DEFAULT_GEMINI_MODEL)
    if gemini_choice == "Custom…":
        gemini_model = (
            (st.session_state.get("cw_gemini_model_custom") or DEFAULT_GEMINI_MODEL).strip()
            or DEFAULT_GEMINI_MODEL
        )
    else:
        gemini_model = (gemini_choice or DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL

    return provider, openai_model, gemini_model


def render_copy_settings(*, show_country: bool, expanded: bool = False) -> None:
    """Render the existing Copy settings accordion.

    Kept as an accordion (per requirement), but placed near the primary action buttons.
    """

    with st.expander("Copy settings", expanded=expanded):
        left, right = st.columns([2, 1])

        with left:
            st.markdown("### Tone / traits")
            t1, t2 = st.columns(2)

            with t1:
                st.slider("Urgency", 1, 10, 8, key="cw_trait_urgency")
                st.slider("Data Richness", 1, 10, 7, key="cw_trait_data")
                st.slider("Social Proof", 1, 10, 6, key="cw_trait_social")
                st.slider("Comparative Framing", 1, 10, 6, key="cw_trait_compare")

            with t2:
                st.slider("Imagery", 1, 10, 7, key="cw_trait_imagery")
                st.slider("Conversational Tone", 1, 10, 8, key="cw_trait_convo")
                st.slider("FOMO", 1, 10, 7, key="cw_trait_fomo")
                st.slider("Repetition", 1, 10, 5, key="cw_trait_repetition")

        with right:
            if show_country:
                st.markdown("### Target")
                st.selectbox("Target country", list(COUNTRY_RULES.keys()), index=0, key="cw_country")

            st.markdown("### AI provider")
            st.radio("Provider", options=["OpenAI", "Gemini"], index=0, horizontal=True, key="cw_provider")

            provider, _, _ = get_selected_models()

            if provider == "OpenAI":
                st.selectbox(
                    "OpenAI model",
                    options=OPENAI_CHAT_MODELS,
                    index=0,
                    key="cw_openai_model",
                )
            else:
                sel = st.selectbox(
                    "Gemini model",
                    options=[*GEMINI_MODELS_RECOMMENDED, "Custom…"],
                    index=0,
                    key="cw_gemini_model",
                    help="Requires google.api_key in Streamlit secrets (falls back to OpenAI if missing).",
                )

                if sel == "Custom…":
                    st.text_input(
                        "Custom Gemini model id",
                        value=st.session_state.get("cw_gemini_model_custom", DEFAULT_GEMINI_MODEL),
                        key="cw_gemini_model_custom",
                        help="Paste the exact model id your Google API key has access to.",
                    )

            st.markdown("### Quality")
            st.checkbox(
                "Run QA pass (recommended)",
                value=True,
                key="cw_auto_qa",
                help="Checks structure, disclaimer, length, and compliance; auto-fixes if needed.",
            )


def _incoming_mode_to_task_label(mode: str) -> str:
    m = (mode or "generate").lower().strip()
    if m == "revise":
        return "Improve existing draft"
    if m in ("adapt", "localise", "localize"):
        return "Adapt for another market"
    return "Create new assets"


def _task_label_to_mode(label: str) -> str:
    l = (label or "").lower().strip()
    if "improve" in l or "revise" in l:
        return "revise"
    if "adapt" in l or "market" in l or "local" in l:
        return "adapt"
    return "generate"


# -------------------------
# Page setup
# -------------------------

st.set_page_config(
    page_title="Copywriter",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

pid = hub_nav()

# Seed from other tools
seed_hook = st.session_state.get("seed_hook", "")
seed_details = st.session_state.get("seed_details", "")
seed_creative = st.session_state.get("seed_creative", "")
seed_source = st.session_state.get("seed_source", "")

seed_md = st.session_state.get("seed_metadata")
seed_md = seed_md if isinstance(seed_md, dict) else {}

# Output/session scaffolding
st.session_state.setdefault("generated_copy", "")
st.session_state.setdefault("generated_plan", "")
st.session_state.setdefault("last_generate_settings", {})
st.session_state.setdefault("copywriter_variants", None)
st.session_state.setdefault("revised_copy", "")
st.session_state.setdefault("revised_plan", "")
st.session_state.setdefault("adapted_copy", "")

# Default copywriter settings (widgets)
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
st.session_state.setdefault("cw_openai_model", OPENAI_CHAT_MODELS[0])
st.session_state.setdefault("cw_gemini_model", DEFAULT_GEMINI_MODEL)
st.session_state.setdefault("cw_auto_qa", True)

# Generate options
st.session_state.setdefault("cw_copy_type", "Email")
st.session_state.setdefault("cw_length_choice", list(LENGTH_RULES.keys())[1] if LENGTH_RULES else "Medium (200-500 words)")

# Brief fields (explicit keys so they can be populated by upload/extraction/dialogue)
st.session_state.setdefault("cw_brief_hook", "")
st.session_state.setdefault("cw_brief_details", "")
st.session_state.setdefault("cw_brief_offer_price", "")
st.session_state.setdefault("cw_brief_retail_price", "")
st.session_state.setdefault("cw_brief_offer_term", "")
st.session_state.setdefault("cw_brief_reports", "")
st.session_state.setdefault("cw_brief_stocks", "")
st.session_state.setdefault("cw_brief_quotes_news", "")

# Only apply seeds if the current brief fields are empty (avoid overwriting work-in-progress).
if seed_hook and not st.session_state.get("cw_brief_hook"):
    st.session_state["cw_brief_hook"] = seed_hook
if seed_details and not st.session_state.get("cw_brief_details"):
    st.session_state["cw_brief_details"] = seed_details

# Apply seed metadata if advanced fields empty
if seed_md and not any(
    [
        st.session_state.get("cw_brief_offer_price"),
        st.session_state.get("cw_brief_retail_price"),
        st.session_state.get("cw_brief_offer_term"),
        st.session_state.get("cw_brief_reports"),
        st.session_state.get("cw_brief_stocks"),
        st.session_state.get("cw_brief_quotes_news"),
    ]
):
    st.session_state["cw_brief_offer_price"] = _safe_str(seed_md.get("offer_price"))
    st.session_state["cw_brief_retail_price"] = _safe_str(seed_md.get("retail_price"))
    st.session_state["cw_brief_offer_term"] = _safe_str(seed_md.get("offer_term"))
    st.session_state["cw_brief_reports"] = _safe_str(seed_md.get("reports"))
    st.session_state["cw_brief_stocks"] = _safe_str(seed_md.get("stocks_to_tease"))
    st.session_state["cw_brief_quotes_news"] = _safe_str(seed_md.get("quotes_news"))

# Dialogue + paste/upload state
st.session_state.setdefault("cw_brief_mode", "Guided brief (form)")
st.session_state.setdefault("cw_unstructured_input", "")
st.session_state.setdefault("cw_last_extract_raw", "")
st.session_state.setdefault("cw_brief_chat", [])
st.session_state.setdefault("cw_brief_chat_ready", False)
st.session_state.setdefault("cw_last_upload_name", "")
st.session_state.setdefault("cw_brief_fields_expanded", False)


# -------------------------
# Hero
# -------------------------

st.markdown("<div class='page-title'>Brief our AI copywriter to deliver campaign assets</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='page-subtitle'>Generate campaign copy from a hook + brief, revise an existing draft, or localise copy from another market.</div>",
    unsafe_allow_html=True,
)

if seed_source:
    st.caption(f"Seed loaded from: `{seed_source}`")


# -------------------------
# Step 1: Choose task
# -------------------------

incoming_mode = (st.session_state.get("copywriter_mode") or "generate").lower().strip()

# If another page set copywriter_mode (seed navigation), update the task selector once.
if st.session_state.get("cw_last_incoming_mode") != incoming_mode:
    st.session_state["cw_last_incoming_mode"] = incoming_mode
    st.session_state["cw_task"] = _incoming_mode_to_task_label(incoming_mode)

st.session_state.setdefault("cw_task", "Create new assets")

st.markdown("### What would you like to do today?")

TASK_OPTIONS = [
    "Create new assets",
    "Improve existing draft",
    "Adapt for another market",
]

cw_task_label = st.radio(
    "Task",
    options=TASK_OPTIONS,
    horizontal=True,
    key="cw_task",
    label_visibility="collapsed",
)

selected_mode = _task_label_to_mode(cw_task_label)
# Keep legacy state in sync so other parts of the hub can still deep-link into the right mode.
st.session_state["copywriter_mode"] = selected_mode


# -------------------------
# Sections
# -------------------------

def render_generate() -> None:
    st.subheader("Campaign brief")

    # Output choices
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        copy_type = st.selectbox(
            "Format",
            options=["Email", "Ads", "Sales Page"],
            index=0,
            key="cw_copy_type",
        )
    with col2:
        length_choice = st.selectbox(
            "Length",
            options=list(LENGTH_RULES.keys()),
            index=1,
            key="cw_length_choice",
        )
    with col3:
        st.write("")

    st.markdown("#### How would you like to brief in our copywriter?")

    brief_mode_label = st.radio(
        "Brief mode",
        options=[
            "Answer a few questions",
            "Paste notes or upload a brief",
            "Guided brief (form)",
        ],
        horizontal=True,
        key="cw_brief_mode",
        label_visibility="collapsed",
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("**Recommended.** Answer 3–6 questions and the brief will fill itself.")
    with c2:
        st.caption("Paste a ticket/Slack thread/bullets, or upload a file, then extract.")
    with c3:
        st.caption("Fill in the brief fields directly (fastest for experienced users).")

    # Map user-facing labels to internal mode keys
    if brief_mode_label == "Answer a few questions":
        brief_mode = "Conversation"
    elif brief_mode_label == "Paste notes or upload a brief":
        brief_mode = "Paste/Upload"
    else:
        brief_mode = "Form"

    # ---- Conversation mode ----
    if brief_mode == "Conversation":
        top = st.columns([1, 1, 2])
        with top[0]:
            if st.button("Reset chat", type="secondary"):
                st.session_state["cw_brief_chat"] = []
                st.session_state["cw_brief_chat_ready"] = False
                st.session_state["cw_brief_fields_expanded"] = False
                st.rerun()
        with top[1]:
            if st.button("Clear brief fields", type="secondary"):
                _apply_extracted_brief_to_state(
                    {
                        "hook": "",
                        "details": "",
                        "offer_price": "",
                        "retail_price": "",
                        "offer_term": "",
                        "reports": "",
                        "stocks_to_tease": "",
                        "quotes_news": "",
                    }
                )
                st.session_state["cw_brief_fields_expanded"] = False
                st.rerun()
        with top[2]:
            st.caption("Answer a few quick questions. We’ll build the brief for you.")

        # Initialise with an opening assistant prompt if empty
        if not st.session_state.get("cw_brief_chat"):
            st.session_state["cw_brief_chat"] = [
                {
                    "role": "assistant",
                    "content": "Tell me what you’re promoting and who it’s for. (One sentence is fine.)",
                }
            ]

        for m in st.session_state.get("cw_brief_chat") or []:
            role = m.get("role") or "user"
            content = m.get("content") or ""
            with st.chat_message(role):
                st.markdown(content)

        user_msg = st.chat_input("Type your answer…")
        if user_msg:
            st.session_state["cw_brief_chat"].append({"role": "user", "content": user_msg})

            provider, _, gemini_model = get_selected_models()
            country = st.session_state.get("cw_country", "Australia")

            current_brief = {
                "hook": st.session_state.get("cw_brief_hook", ""),
                "details": st.session_state.get("cw_brief_details", ""),
                "offer_price": st.session_state.get("cw_brief_offer_price", ""),
                "retail_price": st.session_state.get("cw_brief_retail_price", ""),
                "offer_term": st.session_state.get("cw_brief_offer_term", ""),
                "reports": st.session_state.get("cw_brief_reports", ""),
                "stocks_to_tease": st.session_state.get("cw_brief_stocks", ""),
                "quotes_news": st.session_state.get("cw_brief_quotes_news", ""),
            }

            with st.spinner("Updating brief…"):
                turn = brief_builder_turn(
                    chat_history=st.session_state.get("cw_brief_chat") or [],
                    current_brief=current_brief,
                    provider=provider,
                    openai_model=DEFAULT_OPENAI_FAST_MODEL,
                    gemini_model=gemini_model or DEFAULT_GEMINI_MODEL,
                    copy_type=copy_type,
                    length_choice=length_choice,
                    country=country,
                )

            if turn.get("error"):
                st.warning(turn.get("error"))
                if turn.get("raw"):
                    with st.expander("Debug: raw model output", expanded=False):
                        st.code(turn.get("raw"), language="text")
            else:
                brief = turn.get("brief") or {}
                _apply_extracted_brief_to_state(brief)

                next_q = (turn.get("next_question") or "").strip() or "Anything else that must be included?"
                st.session_state["cw_brief_chat_ready"] = bool(turn.get("is_ready"))

                if (next_q or "").lower() != "ready":
                    st.session_state["cw_brief_chat"].append({"role": "assistant", "content": next_q})
                else:
                    st.session_state["cw_brief_chat"].append(
                        {
                            "role": "assistant",
                            "content": "Ready. You can generate copy now, or review/edit the brief below.",
                        }
                    )

                # When we have a usable brief, expand the review section automatically.
                st.session_state["cw_brief_fields_expanded"] = True

            st.rerun()

        if st.session_state.get("cw_brief_chat_ready"):
            st.success("Brief looks ready. Generate copy whenever you’re happy with it.")

    # ---- Paste/Upload mode ----
    elif brief_mode == "Paste/Upload":
        st.caption("Paste anything you have or upload a file — we’ll extract a usable brief.")

        upload = st.file_uploader(
            "Upload (optional)",
            type=["txt", "docx", "html", "htm", "pdf"],
            key="cw_brief_upload",
        )

        if upload is not None:
            extracted = extract_text_from_upload(upload)
            if extracted and st.session_state.get("cw_last_upload_name") != getattr(upload, "name", ""):
                st.session_state["cw_last_upload_name"] = getattr(upload, "name", "")
                st.session_state["cw_unstructured_input"] = extracted

        st.text_area(
            "Brief / notes",
            key="cw_unstructured_input",
            height=180,
            placeholder="Paste notes here…",
        )

        cols = st.columns([1, 1, 2])
        with cols[0]:
            do_extract = st.button("Extract brief", type="primary")
        with cols[1]:
            if st.button("Clear input", type="secondary"):
                st.session_state["cw_unstructured_input"] = ""
                st.session_state["cw_brief_fields_expanded"] = False
                st.rerun()
        with cols[2]:
            st.write("")

        if do_extract:
            src = (st.session_state.get("cw_unstructured_input") or "").strip()
            if not src:
                st.warning("Add some notes or upload a file first.")
            else:
                provider, _, gemini_model = get_selected_models()

                with st.spinner("Extracting…"):
                    res = extract_campaign_brief_from_text(
                        text=src,
                        provider=provider,
                        openai_model=DEFAULT_OPENAI_FAST_MODEL,
                        gemini_model=gemini_model or DEFAULT_GEMINI_MODEL,
                    )

                st.session_state["cw_last_extract_raw"] = res.get("raw") or ""

                if res.get("error"):
                    st.warning(res.get("error"))
                else:
                    _apply_extracted_brief_to_state(res.get("brief") or {})
                    st.session_state["cw_brief_fields_expanded"] = True
                    st.success("Brief updated. Review/edit below if needed.")

                if st.session_state.get("cw_last_extract_raw"):
                    with st.expander("Show extraction raw output", expanded=False):
                        st.code(st.session_state.get("cw_last_extract_raw"), language="text")

    # ---- Guided form mode ----
    else:
        st.caption("Fill out the brief fields below. Best results come from including both fields.")

    # ---- Brief fields ----
    show_fields_in_expander = brief_mode in {"Conversation", "Paste/Upload"}

    if show_fields_in_expander:
        fields_container = st.expander(
            "Review & edit brief fields (optional)",
            expanded=bool(st.session_state.get("cw_brief_fields_expanded")),
        )
    else:
        fields_container = st.container()

    with fields_container:
        st.text_area(
            "Hook / angle (optional)",
            key="cw_brief_hook",
            height=80,
            placeholder="e.g., The ASX theme investors are missing…",
        )

        st.text_area(
            "What are we promoting? Include key details",
            key="cw_brief_details",
            height=180,
            placeholder="Product/offer details, who it’s for, must-say info, proof points you can use…",
        )

        with st.expander("Add specifics (optional)", expanded=False):
            cA, cB, cC = st.columns(3)
            with cA:
                st.text_input("Special offer price", key="cw_brief_offer_price")
            with cB:
                st.text_input("Retail price", key="cw_brief_retail_price")
            with cC:
                st.text_input("Subscription term", key="cw_brief_offer_term")

            st.text_area("Included reports", key="cw_brief_reports", height=100)
            st.text_input("Stocks to tease (optional)", key="cw_brief_stocks")
            st.text_area("Quotes / timely news (optional)", key="cw_brief_quotes_news", height=110)

    st.markdown("#### Final step")
    st.caption("Optional: adjust copy settings (tone, target country, model).")
    render_copy_settings(show_country=True, expanded=False)

    if st.button("Generate copy", type="primary"):
        hook = (st.session_state.get("cw_brief_hook") or "").strip()
        details = (st.session_state.get("cw_brief_details") or "").strip()

        if not (hook or details):
            st.warning("Add a hook/angle or some details about what you’re promoting.")
            return

        traits = get_traits()
        country = st.session_state.get("cw_country", "Australia")
        provider, openai_model, gemini_model = get_selected_models()
        auto_qa = bool(st.session_state.get("cw_auto_qa", True))

        with st.spinner("Writing…"):
            brief = {
                "hook": hook,
                "details": details,
                "offer_price": st.session_state.get("cw_brief_offer_price", ""),
                "retail_price": st.session_state.get("cw_brief_retail_price", ""),
                "offer_term": st.session_state.get("cw_brief_offer_term", ""),
                "reports": st.session_state.get("cw_brief_reports", ""),
                "stocks_to_tease": st.session_state.get("cw_brief_stocks", ""),
                "quotes_news": st.session_state.get("cw_brief_quotes_news", ""),
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

            qa_meta: Dict[str, Any] = {}
            if auto_qa:
                qa = qa_and_patch_copy(
                    draft=draft,
                    copy_type=copy_type,
                    country=country,
                    length_choice=length_choice,
                    traits=traits,
                    provider=provider,
                    openai_model=DEFAULT_OPENAI_FAST_MODEL,
                    gemini_model=DEFAULT_GEMINI_CHEAP_MODEL,
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
                title=f"Draft ({copy_type}) - {hook[:40] or 'untitled'}",
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

    if st.session_state.get("generated_copy"):
        st.divider()
        st.markdown("### Output")
        st.markdown(st.session_state.generated_copy)

        with st.expander("Show internal plan (AI outline)"):
            st.markdown(st.session_state.generated_plan or "_No plan captured._")

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
                provider, _, gemini_model = get_selected_models()
                with st.spinner("Brainstorming variants…"):
                    v = generate_variants(
                        base_copy=st.session_state.generated_copy,
                        n=5,
                        provider=provider,
                        openai_model=DEFAULT_OPENAI_FAST_MODEL,
                        gemini_model=DEFAULT_GEMINI_CHEAP_MODEL,
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
            country0 = settings.get("country") or st.session_state.get("cw_country", "Australia")

            traits = get_traits()
            provider, openai_model, gemini_model = get_selected_models()
            auto_qa = bool(st.session_state.get("cw_auto_qa", True))

            with st.spinner("Rewriting with traits…"):
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

                qa_meta2: Dict[str, Any] = {}
                if auto_qa:
                    qa = qa_and_patch_copy(
                        draft=revised,
                        copy_type=copy_type0,
                        country=country0,
                        length_choice=length0,
                        traits=traits,
                        provider=provider,
                        openai_model=DEFAULT_OPENAI_FAST_MODEL,
                        gemini_model=DEFAULT_GEMINI_CHEAP_MODEL,
                    )
                    revised = qa.get("copy") or revised
                    qa_meta2 = {"qa_status": qa.get("status"), "qa_critique": qa.get("critique")}

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
                        **qa_meta2,
                    },
                )

        colA, colB = st.columns(2)
        with colA:
            if st.button("Pressure-test this draft"):
                st.session_state["draft_for_validation"] = st.session_state.generated_copy
                st.switch_page("pages/05_Pressure_test_creative.py")
        with colB:
            if st.button("Improve this in the revise tool"):
                st.session_state["seed_creative"] = st.session_state.generated_copy
                st.session_state["copywriter_mode"] = "revise"
                st.session_state["cw_task"] = "Improve existing draft"
                st.rerun()


def render_revise() -> None:
    st.subheader("Revise an existing draft")

    existing = st.text_area(
        "Paste the draft you want to improve",
        value=seed_creative,
        height=240,
    )

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
            r_copy_type = st.selectbox("Format", options=["Email", "Ads", "Sales Page"], index=0, key="cw_revise_copy_type")
        with c2:
            r_length = st.selectbox("Length", options=list(LENGTH_RULES.keys()), index=1, key="cw_revise_length")
    else:
        r_copy_type = "Email"
        r_length = "Medium (200-500 words)"

    st.markdown("#### Final step")
    st.caption("Optional: adjust copy settings (tone, target country, model).")
    render_copy_settings(show_country=True, expanded=False)

    if st.button("Revise copy", type="primary"):
        if not existing.strip():
            st.warning("Paste a draft to revise.")
            return

        traits = get_traits()
        country = st.session_state.get("cw_country", "Australia")
        provider, openai_model, gemini_model = get_selected_models()
        auto_qa = bool(st.session_state.get("cw_auto_qa", True))

        with st.spinner("Rewriting…"):
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
                revised_text = out
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
                revised_text = (out2.get("copy") or "").strip()
                plan = (out2.get("plan") or "").strip()

            qa_meta: Dict[str, Any] = {}
            if auto_qa and method != "Goal-based edit":
                qa = qa_and_patch_copy(
                    draft=revised_text,
                    copy_type=r_copy_type,
                    country=country,
                    length_choice=r_length,
                    traits=traits,
                    provider=provider,
                    openai_model=DEFAULT_OPENAI_FAST_MODEL,
                    gemini_model=DEFAULT_GEMINI_CHEAP_MODEL,
                )
                revised_text = qa.get("copy") or revised_text
                qa_meta = {"qa_status": qa.get("status"), "qa_critique": qa.get("critique")}

            st.session_state.revised_copy = revised_text
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
                content_text=revised_text,
                metadata={
                    "provider": provider,
                    "openai_model": openai_model,
                    "gemini_model": gemini_model,
                    "traits": traits,
                    **qa_meta,
                },
            )

    if st.session_state.get("revised_copy"):
        st.divider()
        st.markdown("### Revised output")
        st.markdown(st.session_state.revised_copy)

        if st.session_state.get("revised_plan"):
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


def render_adapt() -> None:
    st.subheader("Adapt copy from another market")

    c1, c2 = st.columns(2)
    with c1:
        src = st.selectbox("Source", options=list(COUNTRY_RULES.keys()), index=3, key="cw_adapt_src")
    with c2:
        tgt = st.selectbox("Target", options=list(COUNTRY_RULES.keys()), index=0, key="cw_adapt_tgt")

    original = st.text_area(
        "Copy to adapt",
        value=seed_creative if selected_mode == "adapt" else "",
        height=240,
    )
    notes = st.text_area("Notes (optional)", height=90)

    st.markdown("#### Final step")
    st.caption("Optional: adjust copy settings (tone, model). Target is set above.")
    render_copy_settings(show_country=False, expanded=False)

    if st.button("Adapt", type="primary"):
        if not original.strip():
            st.warning("Paste some copy to adapt.")
            return

        traits = get_traits()
        provider, openai_model, gemini_model = get_selected_models()
        auto_qa = bool(st.session_state.get("cw_auto_qa", True))

        with st.spinner("Adapting…"):
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
                    openai_model=DEFAULT_OPENAI_FAST_MODEL,
                    gemini_model=DEFAULT_GEMINI_CHEAP_MODEL,
                )
                out = qa.get("copy") or out

            st.session_state.adapted_copy = out

            save_artifact(
                pid,
                type="draft_adapted",
                title=f"Adapted {src} -> {tgt}",
                content_json={"source": src, "target": tgt, "notes": notes},
                content_text=out,
                metadata={
                    "provider": provider,
                    "openai_model": openai_model,
                    "gemini_model": gemini_model,
                    "traits": traits,
                },
            )

    if st.session_state.get("adapted_copy"):
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


if selected_mode == "generate":
    render_generate()
elif selected_mode == "revise":
    render_revise()
else:
    render_adapt()
