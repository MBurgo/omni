import json

import streamlit as st

from engines.sheets_briefs import parse_step2_report
from storage.store import get_artifact, list_artifacts
from ui.branding import apply_branding
from ui.layout import hub_nav, human_time
from ui.seed import set_copywriter_seed

st.set_page_config(
    page_title="Library",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

pid = hub_nav()

def _clip(s: str, n: int = 160) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


def _fmt_rewrite(copy_type: str, rewrite: dict) -> str:
    """Convert moderator rewrite JSON into a copy-pastable text draft."""
    copy_type = (copy_type or "").strip()
    rw = rewrite or {}

    if copy_type == "Headline":
        headlines = (rw.get("headlines") or [])[:10]
        return "\n".join([h for h in headlines if str(h).strip()])

    if copy_type == "Email":
        parts = []
        if rw.get("subject"):
            parts.append(f"Subject: {rw.get('subject')}")
        if rw.get("preheader"):
            parts.append(f"Preheader: {rw.get('preheader')}")
        if rw.get("body"):
            parts.append(str(rw.get("body")))
        if rw.get("cta"):
            parts.append(f"CTA: {rw.get('cta')}")
        if rw.get("ps"):
            parts.append(f"P.S.: {rw.get('ps')}")
        return "\n\n".join([p for p in parts if str(p).strip()])

    if copy_type == "Sales Page":
        lines = []
        if rw.get("hero_headline"):
            lines.append(str(rw.get("hero_headline")))
        if rw.get("hero_subhead"):
            lines.append(str(rw.get("hero_subhead")))
        if rw.get("bullets"):
            lines.append("\n".join([f"- {b}" for b in (rw.get("bullets") or [])]))
        if rw.get("proof_block"):
            lines.append(str(rw.get("proof_block")))
        if rw.get("offer_stack"):
            lines.append("\n".join([f"- {b}" for b in (rw.get("offer_stack") or [])]))
        if rw.get("cta_block"):
            lines.append(str(rw.get("cta_block")))
        if rw.get("cta_button"):
            lines.append(f"CTA button: {rw.get('cta_button')}")
        return "\n\n".join([ln for ln in lines if str(ln).strip()])

    # Fallback: stringify the JSON.
    return json.dumps(rw, ensure_ascii=False, indent=2)
 

st.markdown("<div class='page-title'>Library</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='page-subtitle'>Everything generated in this project: signals, themes, drafts, tests, and rewrites. Select an item to view, reuse, or send it into another tool.</div>",
    unsafe_allow_html=True,
)

artifacts = list_artifacts(pid, limit=200)

if not artifacts:
    st.info("No artifacts yet. Start from Home.")
    st.stop()

all_types = sorted({a.type for a in artifacts})

# Filters (kept on main page; sidebar is hidden)
with st.expander("Filters", expanded=False):
    type_filter = st.selectbox("Type", options=["All"] + all_types)
    query = st.text_input("Search title", value="", placeholder="e.g., draft, spikes, focus group…")

filtered = artifacts
if type_filter != "All":
    filtered = [a for a in filtered if a.type == type_filter]
if query.strip():
    q = query.strip().lower()
    filtered = [a for a in filtered if q in (a.title or "").lower()]

if not filtered:
    st.warning("No items match the current filters.")
    st.stop()

left, right = st.columns([2, 3], gap="large")

with left:
    st.subheader("Items")

    options = [a.id for a in filtered]

    def fmt(aid: str) -> str:
        a = next(x for x in filtered if x.id == aid)
        return f"{human_time(a.created_at)} — {a.type} — {a.title}"

    selected_id = st.radio("", options=options, format_func=fmt)

with right:
    a = get_artifact(selected_id)

    st.subheader("Details")
    st.markdown(f"**{a.title}**")
    st.caption(f"Type: `{a.type}` | Created: {human_time(a.created_at)}")

    # --- Actions ---
    st.markdown("### Actions")

    # 1) Signals step2 report: choose one brief
    if a.type == "signals_daily_step2" and a.content_text:
        summary_text, briefs = parse_step2_report(a.content_text)
        if briefs:
            labels = [f"{i+1}. {b.get('title','Brief')}" for i, b in enumerate(briefs)]
            idx = st.selectbox("Brief", options=list(range(len(briefs))), format_func=lambda i: labels[i])
            chosen = briefs[idx]

            hook = (chosen.get("title") or "").strip()
            details = (chosen.get("body") or "").strip()

            colA, colB = st.columns(2)
            with colA:
                if st.button("Send selected brief to Copywriter", type="primary"):
                    set_copywriter_seed(mode="generate", hook=hook, details=details, source="library:signals_daily_step2")
                    st.switch_page("pages/06_Write_campaign_assets.py")
            with colB:
                if st.button("Use Summary of Findings as Copywriter brief"):
                    set_copywriter_seed(
                        mode="generate",
                        hook=a.title,
                        details=(summary_text or a.content_text),
                        source="library:signals_daily_step2_summary",
                    )
                    st.switch_page("pages/06_Write_campaign_assets.py")
        else:
            if st.button("Send report text to Copywriter", type="primary"):
                set_copywriter_seed(
                    mode="generate",
                    hook=a.title,
                    details=a.content_text,
                    source="library:signals_daily_step2",
                )
                st.switch_page("pages/06_Write_campaign_assets.py")

    # 2) Headline tests: pick a headline to use as hook
    elif a.type == "headline_test" and isinstance(a.content_json, dict):
        cj = a.content_json or {}
        headlines = cj.get("headlines") or []
        ranked = cj.get("ranked") or []
        context = (cj.get("context") or "").strip()

        if headlines:
            default_index = 0
            if ranked:
                try:
                    default_index = max(0, int(ranked[0][0]) - 1)
                except Exception:
                    default_index = 0

            idx = st.selectbox(
                "Headline",
                options=list(range(len(headlines))),
                index=default_index if default_index < len(headlines) else 0,
                format_func=lambda i: f"{i+1}. {headlines[i]}",
            )

            colA, colB = st.columns(2)
            with colA:
                if st.button("Send headline to Copywriter", type="primary"):
                    set_copywriter_seed(
                        mode="generate",
                        hook=str(headlines[idx]).strip(),
                        details=context,
                        source="library:headline_test",
                    )
                    st.switch_page("pages/06_Write_campaign_assets.py")
            with colB:
                if context and st.button("Use context as Copywriter brief"):
                    set_copywriter_seed(mode="generate", hook=a.title, details=context, source="library:headline_test_context")
                    st.switch_page("pages/06_Write_campaign_assets.py")
        else:
            st.caption("This headline_test record did not store headlines.")

    # 3) Focus group outputs: send original or rewrite as a draft
    elif a.type in {"focus_group", "campaign_pack_focus_group"} and isinstance(a.content_json, dict):
        cj = a.content_json or {}
        copy_type = (cj.get("copy_type") or "Email").strip()
        creative_full = (cj.get("creative_full") or cj.get("creative") or "").strip()
        moderator_json = cj.get("moderator_json") or {}
        rewrite = (moderator_json.get("rewrite") or {}) if isinstance(moderator_json, dict) else {}
        rewrite_text = _fmt_rewrite(copy_type, rewrite) if rewrite else ""

        colA, colB, colC = st.columns(3)
        with colA:
            if rewrite_text and st.button("Send rewrite to Copywriter", type="primary"):
                set_copywriter_seed(mode="revise", creative=rewrite_text, source=f"library:{a.type}:rewrite")
                st.switch_page("pages/06_Write_campaign_assets.py")
        with colB:
            if creative_full and st.button("Send original creative to Copywriter"):
                set_copywriter_seed(mode="revise", creative=creative_full, source=f"library:{a.type}:original")
                st.switch_page("pages/06_Write_campaign_assets.py")
        with colC:
            if creative_full and st.button("Pressure-test this creative"):
                st.session_state["draft_for_validation"] = creative_full
                st.switch_page("pages/05_Pressure_test_creative.py")

    # 4) Draft-like items: treat content_text as an editable draft
    elif a.content_text and a.content_text.strip():
        colA, colB = st.columns(2)
        with colA:
            if st.button("Open in Copywriter (Revise)", type="primary"):
                set_copywriter_seed(mode="revise", creative=a.content_text, source=f"library:{a.type}")
                st.switch_page("pages/06_Write_campaign_assets.py")
        with colB:
            if st.button("Pressure-test this text"):
                st.session_state["draft_for_validation"] = a.content_text
                st.switch_page("pages/05_Pressure_test_creative.py")

    # 5) JSON-only items: send as a brief
    elif a.content_json is not None:
        if st.button("Use JSON as Copywriter brief", type="primary"):
            set_copywriter_seed(
                mode="generate",
                hook=a.title,
                details=json.dumps(a.content_json, ensure_ascii=False, indent=2),
                source=f"library:{a.type}:json",
            )
            st.switch_page("pages/06_Write_campaign_assets.py")

    else:
        if st.button("Use title as Copywriter hook", type="primary"):
            set_copywriter_seed(mode="generate", hook=a.title, details="", source=f"library:{a.type}:title")
            st.switch_page("pages/06_Write_campaign_assets.py")

    st.divider()

    if a.metadata:
        with st.expander("Metadata", expanded=False):
            st.code(json.dumps(a.metadata, ensure_ascii=False, indent=2), language="json")

    if a.content_json is not None:
        with st.expander("JSON", expanded=False):
            st.code(json.dumps(a.content_json, ensure_ascii=False, indent=2), language="json")

    if a.content_text:
        st.markdown("---")
        st.markdown(a.content_text)
    elif a.content_json is not None:
        st.caption("No text content stored for this item.")
