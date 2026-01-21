from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from engines.audience import ask_persona
from engines.llm import query_openai
from engines.personas import Persona, load_personas
from storage.store import save_artifact
from ui.branding import FOOL_COLORS, apply_branding, render_footer
from ui.layout import project_banner, require_project


def _ensure_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _initials(name: str) -> str:
    parts = [p.strip() for p in (name or "").split() if p.strip()]
    if not parts:
        return "?"
    if len(parts) == 1:
        return (parts[0][:2] or "?").upper()
    return (parts[0][0] + parts[1][0]).upper()


def _persona_image_url(p: Persona) -> Optional[str]:
    candidates = [
        "photo_url",
        "image_url",
        "avatar_url",
        "portrait_url",
        "image",
        "photo",
        "portrait",
        "avatar",
    ]

    for k in candidates:
        v = p.core.get(k) or p.extended.get(k)
        if isinstance(v, str) and v.strip().startswith(("http://", "https://", "data:")):
            return v.strip()
    return None


def _segment_option_key(seg: Dict[str, Any]) -> str:
    return str(seg.get("id") or seg.get("label") or "Unknown")


def _segment_option_label(seg: Dict[str, Any]) -> str:
    return str(seg.get("label") or seg.get("id") or "Unknown")


def _render_segment_cheat_sheet(segments: List[Dict[str, Any]]) -> None:
    with st.expander("Segment Cheat Sheet", expanded=False):
        for seg in segments:
            label = _segment_option_label(seg)
            summary = str(seg.get("summary") or "").strip()
            if summary:
                st.markdown(f"**{label}** — {summary}")
            else:
                st.markdown(f"**{label}**")


def _render_persona_grid(personas: List[Persona], selected_uid: Optional[str]) -> Optional[str]:
    """Render a 3-column grid of persona cards.

    Returns a new selected uid if a selection was made; otherwise returns None.
    """

    if not personas:
        st.info("No personas available for this segment.")
        return None

    cols = st.columns(3, gap="large")
    new_selected: Optional[str] = None

    for i, p in enumerate(personas):
        col = cols[i % 3]
        with col:
            is_selected = (p.uid == selected_uid)
            border = FOOL_COLORS["gold"] if is_selected else "rgba(255,255,255,0.14)"

            img = _persona_image_url(p)
            if img:
                photo_html = (
                    f"<div class='persona-photo' style=\"background-image:url('{img}');\"></div>"
                )
            else:
                photo_html = (
                    f"<div class='persona-photo persona-photo--placeholder'>{_initials(p.name)}</div>"
                )

            st.markdown(
                f"""
<div class='persona-card' style='border-color:{border};'>
  {photo_html}
  <div class='persona-card-name'>{p.name}</div>
  <div class='persona-card-seg'>{p.segment_label}</div>
</div>
""",
                unsafe_allow_html=True,
            )

            st.markdown("<div class='persona-card-btn'>", unsafe_allow_html=True)
            if st.button("Select", key=f"select_persona__{p.uid}", type="secondary", use_container_width=True):
                new_selected = p.uid
            st.markdown("</div>", unsafe_allow_html=True)

    return new_selected


def _render_persona_details(p: Persona) -> None:
    core = p.core or {}
    bt = core.get("behavioural_traits") or {}

    values = ", ".join([str(x) for x in _ensure_list(core.get("values")) if str(x).strip()][:6])
    goals = "; ".join([str(x) for x in _ensure_list(core.get("goals")) if str(x).strip()][:5])
    concerns = "; ".join([str(x) for x in _ensure_list(core.get("concerns")) if str(x).strip()][:5])

    def _v(x: Any) -> str:
        return str(x).strip() if x is not None else ""

    html = f"""
<div class='persona-details'>
  <div class='persona-details-title'>{_v(core.get('name'))} <span class='persona-details-seg'>({p.segment_label})</span></div>
  <div class='persona-details-grid'>
    <div><b>Age:</b> {_v(core.get('age'))}</div>
    <div><b>Income:</b> {_v(core.get('income'))}</div>
    <div><b>Location:</b> {_v(core.get('location'))}</div>
    <div><b>Risk:</b> {_v(bt.get('risk_tolerance'))}</div>
    <div><b>Occupation:</b> {_v(core.get('occupation'))}</div>
    <div><b>Confidence:</b> {_v(core.get('confidence'))}</div>
  </div>
  <div class='persona-details-rule'></div>
  <div class='persona-details-body'>
    <div><b>Values:</b> {values or '—'}</div>
    <div style='margin-top:0.35rem;'><b>Goals:</b> {goals or '—'}</div>
    <div style='margin-top:0.35rem;'><b>Concerns:</b> {concerns or '—'}</div>
    <div style='margin-top:0.35rem;'><b>Narrative:</b> {_v(core.get('narrative')) or '—'}</div>
  </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Ask a persona",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

# Page-local styles (persona cards + details panel)
st.markdown(
    f"""
<style>
.persona-callout {{
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.12);
  border-left: 6px solid {FOOL_COLORS['blue']};
  border-radius: 16px;
  padding: 1.0rem 1.1rem;
  margin: 0.35rem 0 1.25rem 0;
}}
.persona-callout-title {{
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 18px;
  margin-bottom: 0.25rem;
}}
.persona-callout-body {{
  color: rgba(255,255,255,0.82);
  font-size: 14px;
  line-height: 1.55;
}}

.persona-card {{
  background: rgba(255,255,255,0.03);
  border: 2px solid rgba(255,255,255,0.14);
  border-radius: 18px;
  padding: 0.80rem;
  margin: 0 0 0.65rem 0;
}}
.persona-photo {{
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: 14px;
  background-size: cover;
  background-position: center;
  background-color: rgba(255,255,255,0.08);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.persona-photo--placeholder {{
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 42px;
  color: rgba(255,255,255,0.92);
}}
.persona-card-name {{
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 18px;
  margin-top: 0.70rem;
}}
.persona-card-seg {{
  color: rgba(255,255,255,0.72);
  font-size: 12px;
  margin-top: 0.10rem;
  min-height: 2.35rem;
}}
.persona-card-btn div.stButton > button[kind="secondary"] {{
  border-radius: 14px;
  padding: 0.60rem 0.9rem;
}}

.persona-details {{
  background: rgba(67,176,42,0.10);
  border: 1px solid rgba(67,176,42,0.35);
  border-radius: 16px;
  padding: 1.05rem 1.10rem;
  margin: 1.0rem 0 1.25rem 0;
}}
.persona-details-title {{
  font-family: 'Poppins', sans-serif;
  font-weight: 900;
  font-size: 20px;
  margin-bottom: 0.35rem;
}}
.persona-details-seg {{
  font-weight: 700;
  color: rgba(255,255,255,0.78);
}}
.persona-details-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.35rem 1.25rem;
  font-size: 13px;
  color: rgba(255,255,255,0.88);
}}
.persona-details-rule {{
  height: 1px;
  background: rgba(255,255,255,0.14);
  margin: 0.75rem 0 0.75rem 0;
}}
.persona-details-body {{
  font-size: 13px;
  line-height: 1.55;
  color: rgba(255,255,255,0.88);
}}

/* Suggested question buttons */
.suggested-questions div.stButton > button[kind="secondary"] {{
  min-height: 70px;
  text-align: left;
  padding: 0.75rem 0.85rem;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.25;
}}
</style>
""",
    unsafe_allow_html=True,
)

# Sidebar configuration (keeps the main canvas clean)
with st.sidebar:
    project_banner()

    st.divider()
    st.markdown("## Settings")
    model = st.selectbox("Model", options=["gpt-4o-mini", "gpt-4o"], index=0)
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.2, value=0.7, step=0.1)
    max_batch = st.slider("Max personas for batch / focus group", min_value=2, max_value=15, value=8)
    st.caption("Personas respond in-character. They do not provide financial advice.")

pid = require_project()

# Hero
st.markdown(
    "<div class='page-title'>Ask our AI Personas brand, marketing or product-related questions</div>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='page-subtitle'>Our AI personas are built using real Australian investor demographics and traits. Ask them any questions regarding their feelings, motivations or opinions.</div>",
    unsafe_allow_html=True,
)

# About panel (styled to resemble the reference screenshot)
st.markdown(
    """
<div class='persona-callout'>
  <div class='persona-callout-title'>About This Tool</div>
  <div class='persona-callout-body'>
    This tool interviews synthetic Australian investor personas for <b>strategic analysis</b>, <b>copy reactions</b>, trust triggers and objections.<br/>
    Tip: For long prompts, paste your creative as-is and ask for a reaction + suggested improvements.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# Load personas
path, segments, personas = load_personas()
if not personas:
    st.error("No personas found. Expected personas.json (with segments.personas) in the app root.")
    render_footer()
    st.stop()

# State
st.session_state.setdefault("persona_chat", {})  # uid -> [(q,a),...]
st.session_state.setdefault("persona_selected_uid", personas[0].uid)
st.session_state.setdefault("persona_question", "")
st.session_state.setdefault("persona_ask_all", False)
st.session_state.setdefault("persona_last_batch", None)
st.session_state.setdefault("persona_focus_question", "")
st.session_state.setdefault("persona_last_focus", None)

# Segment selection helpers
segment_opts = ["All"] + [_segment_option_key(s) for s in segments]
segment_label = {_segment_option_key(s): _segment_option_label(s) for s in segments}


def _filter_personas(seg_key: str) -> List[Persona]:
    if seg_key == "All":
        return personas
    # Match either segment_id or the label.
    wanted_label = segment_label.get(seg_key, seg_key)
    return [p for p in personas if p.segment_id == seg_key or p.segment_label == wanted_label]


# Tabs
interview_tab, focus_tab = st.tabs(["🗣️ Individual Interview", "👥 Focus Group Debate"])

# -----------------------------------------------------------------------------
# Individual Interview
# -----------------------------------------------------------------------------
with interview_tab:
    seg = st.selectbox(
        "Filter by Segment",
        options=segment_opts,
        format_func=lambda x: "All" if x == "All" else segment_label.get(x, x),
        key="persona_segment_filter",
    )
    _render_segment_cheat_sheet(segments)

    visible = _filter_personas(seg)

    # Ensure selection is valid in the current filter
    if st.session_state.persona_selected_uid not in {p.uid for p in visible}:
        if visible:
            st.session_state.persona_selected_uid = visible[0].uid

    st.markdown("### 👤 Select a Persona")
    new_sel = _render_persona_grid(visible, st.session_state.persona_selected_uid)
    if new_sel:
        st.session_state.persona_selected_uid = new_sel
        st.rerun()

    selected = next((p for p in personas if p.uid == st.session_state.persona_selected_uid), None)
    if selected:
        _render_persona_details(selected)

    # Suggested questions
    st.markdown("### 💡 Suggested Questions")
    suggestions = [
        "What would make this offer feel credible to you?",
        "What objections do you have to this headline (and why)?",
        "What proof would you need to see before you’d trust this claim?",
    ]

    st.markdown("<div class='suggested-questions'>", unsafe_allow_html=True)
    s_cols = st.columns(3, gap="large")
    for i, s in enumerate(suggestions):
        with s_cols[i % 3]:
            if st.button(f"Ask: {s}", type="secondary", use_container_width=True, key=f"persona_suggestion_{i}"):
                st.session_state.persona_question = s
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Interaction
    st.markdown("### 💬 Interaction")
    question = st.text_area(
        "Enter your question:",
        key="persona_question",
        placeholder="Paste your headline, email, landing page copy, or simply ask a strategic question…",
        height=150,
    )

    ask_all = st.checkbox("Ask ALL visible personas (Batch Test)", key="persona_ask_all")

    if st.button("Ask Persona(s)", type="primary", use_container_width=True, key="persona_ask_button"):
        q = (question or "").strip()
        if not q:
            st.warning("Enter a question.")
        else:
            if ask_all:
                batch = visible[:max_batch]
                results: List[Dict[str, Any]] = []

                with st.status(f"Interviewing {len(batch)} personas…", expanded=True) as status:
                    for p in batch:
                        ans = ask_persona(p, q, history=None, model=model, temperature=temperature)
                        results.append({"persona": p.name, "uid": p.uid, "segment": p.segment_label, "answer": ans})
                        st.write(f"- {p.name}: done")
                    status.update(label="Batch complete", state="complete", expanded=False)

                st.session_state.persona_last_batch = {"question": q, "segment": seg, "results": results}

                save_artifact(
                    pid,
                    type="persona_batch",
                    title=f"Batch: {q[:60]}",
                    content_json={"question": q, "results": results},
                    content_text="\n\n".join([f"**{r['persona']} ({r['segment']}):** {r['answer']}" for r in results]),
                    metadata={"segment": seg, "model": model, "n": len(results)},
                )

                st.rerun()

            else:
                if not selected:
                    st.warning("Select a persona first.")
                else:
                    history: List[Tuple[str, str]] = st.session_state.persona_chat.get(selected.uid, [])
                    ans = ask_persona(selected, q, history=history, model=model, temperature=temperature)

                    st.session_state.persona_chat.setdefault(selected.uid, []).append((q, ans))

                    save_artifact(
                        pid,
                        type="persona_interview",
                        title=f"{selected.name}: {q[:60]}",
                        content_json={
                            "persona_uid": selected.uid,
                            "persona": selected.name,
                            "question": q,
                            "answer": ans,
                        },
                        content_text=f"**Q:** {q}\n\n**A ({selected.name}):** {ans}",
                        metadata={"persona_uid": selected.uid, "segment": selected.segment_label, "model": model},
                    )

                    st.session_state.persona_question = ""
                    st.rerun()

    # Display results
    if ask_all and st.session_state.get("persona_last_batch"):
        payload = st.session_state.persona_last_batch
        st.divider()
        st.subheader("Batch Results")
        for r in payload.get("results", []):
            st.markdown(f"**{r['persona']} ({r['segment']}):** {r['answer']}")
            st.divider()

    elif selected:
        hist = st.session_state.persona_chat.get(selected.uid, [])
        if hist:
            st.divider()
            st.subheader("Conversation")
            for q, a in reversed(hist[-10:]):
                st.markdown(f"**You:** {q}")
                st.markdown(f"**{selected.name}:** {a}")
                st.divider()


# -----------------------------------------------------------------------------
# Focus Group Debate
# -----------------------------------------------------------------------------
with focus_tab:
    seg2 = st.selectbox(
        "Filter by Segment",
        options=segment_opts,
        format_func=lambda x: "All" if x == "All" else segment_label.get(x, x),
        key="persona_segment_filter_focus",
    )
    _render_segment_cheat_sheet(segments)

    visible2 = _filter_personas(seg2)

    st.markdown("### 👥 Focus Group")
    st.caption("Runs the same prompt across multiple personas and (optionally) generates a moderator summary.")

    prompt = st.text_area(
        "Prompt",
        key="persona_focus_question",
        placeholder="e.g., Here’s a landing page headline and subhead. React as a focus group: what do you trust, what feels hypey, and what would you need to see?",
        height=170,
    )
    make_summary = st.checkbox("Generate moderator summary", value=True, key="persona_focus_make_summary")

    if st.button("Run Focus Group", type="primary", use_container_width=True, key="persona_focus_run"):
        q = (prompt or "").strip()
        if not q:
            st.warning("Enter a prompt.")
        else:
            batch = visible2[:max_batch]
            responses: List[Dict[str, Any]] = []

            with st.status(f"Collecting responses from {len(batch)} personas…", expanded=True) as status:
                for p in batch:
                    ans = ask_persona(
                        p,
                        "In a focus group setting, give your candid reaction. " + q,
                        history=None,
                        model=model,
                        temperature=temperature,
                    )
                    responses.append({"persona": p.name, "uid": p.uid, "segment": p.segment_label, "answer": ans})
                    st.write(f"- {p.name}: done")
                status.update(label="Responses collected", state="complete", expanded=False)

            moderator_summary = ""
            if make_summary and responses:
                joined = "\n\n".join([f"{r['persona']} ({r['segment']}): {r['answer']}" for r in responses])
                moderator_summary = query_openai(
                    [
                        {
                            "role": "system",
                            "content": (
                                "You are a focus group moderator for an Australian investing brand. "
                                "Summarise agreement, disagreement, key objections, trust triggers, and concrete copy suggestions. "
                                "Be specific and actionable."
                            ),
                        },
                        {"role": "user", "content": f"PROMPT:\n{q}\n\nRESPONSES:\n{joined}"},
                    ],
                    model=model,
                    temperature=0.3,
                )

            payload = {"prompt": q, "segment": seg2, "n": len(responses), "responses": responses, "moderator_summary": moderator_summary}
            st.session_state.persona_last_focus = payload

            save_artifact(
                pid,
                type="persona_focus_group",
                title=f"Focus group: {q[:60]}",
                content_json=payload,
                content_text=(
                    (f"## Moderator summary\n\n{moderator_summary}\n\n" if moderator_summary else "")
                    + "\n\n".join([f"**{r['persona']} ({r['segment']}):** {r['answer']}" for r in responses])
                ),
                metadata={"segment": seg2, "model": model, "n": len(responses)},
            )

            st.rerun()

    if st.session_state.get("persona_last_focus"):
        data = st.session_state.persona_last_focus
        st.divider()
        left, right = st.columns([2, 3], gap="large")
        with left:
            st.subheader("Moderator Summary")
            if data.get("moderator_summary"):
                st.markdown(data.get("moderator_summary"))
            else:
                st.caption("No summary generated.")

        with right:
            st.subheader("Responses")
            for r in data.get("responses", []):
                with st.expander(f"{r['persona']} ({r['segment']})"):
                    st.markdown(r.get("answer") or "")


render_footer()
