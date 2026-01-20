import json

import streamlit as st

import streamlit.components.v1 as components

from engines.chatkit import build_chatkit_embed_html, create_chatkit_session
from engines.signals import collect_signals, summarise_horizon_scan
from storage.store import latest_artifact, save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project
from utils import get_secret

st.set_page_config(page_title="Futurist - Emerging themes", page_icon="🔮", layout="wide")
apply_branding()

st.title("🔮 Emerging themes")
st.caption("A horizon scan: turns current signals into plausible 3-12 month investor themes + campaign ideas.")

project_banner()
pid = require_project()

# --- Mode ---
# Prefer the embedded app (if configured) because it's the most reliable way
# to reuse an existing deployed workflow UI inside Streamlit.
_embed_cfg = bool(get_secret("futurist.embed_url") or get_secret("FUTURIST_EMBED_URL"))
_wf_cfg = bool(get_secret("futurist.workflow_id") or get_secret("FUTURIST_WORKFLOW_ID"))
_default_mode_index = 1 if _embed_cfg else (2 if _wf_cfg else 0)

mode = st.radio(
    "How do you want to run this?",
    options=[
        "Structured output",
        "Agent workflow (Embedded app)",
        "Agent workflow (ChatKit)",
    ],
    index=_default_mode_index,
    horizontal=True,
    help=(
        "Structured output uses the portal's own prompt-based horizon scan. "
        "Embedded app iframes your published AgentKit/ChatKit app (fastest + most reliable, but limited portal handoff). "
        "ChatKit embeds an OpenAI-hosted Agent Builder workflow directly in Streamlit (requires a workflow id)."
    ),
)

# --- Inputs ---
colA, colB, colC = st.columns([2,2,1])
with colA:
    query = st.text_input("Query", value=st.session_state.get("futurist_query", "ASX 200"))
with colB:
    trends_q = st.text_input("Trends query or topic id (optional)", value=st.session_state.get("futurist_trends_q", ""), placeholder="e.g. /m/0bl5c2")
with colC:
    # Only used in Structured output mode
    model = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0, disabled=(mode != "Structured output"))

cooldown_h = st.slider("Cooldown (hours)", min_value=0, max_value=48, value=12, disabled=(mode != "Structured output"))

last = latest_artifact(pid, "signals_horizon")
if last and cooldown_h > 0:
    import time
    age_h = (time.time() - last.created_at) / 3600
    cached = last.content_json if age_h <= cooldown_h else None
else:
    cached = None

if "horizon_json" not in st.session_state:
    st.session_state.horizon_json = cached

if mode == "Structured output" and st.button("Generate horizon scan", type="primary"):
    st.session_state["futurist_query"] = query
    st.session_state["futurist_trends_q"] = trends_q
    with st.status("Collecting signals and generating horizon scan...", expanded=True) as status:
        try:
            st.write("1) Fetching signals...")
            d = collect_signals(query=query.strip(), trends_query_or_topic_id=(trends_q.strip() or None))
            st.write("2) Synthesising emerging themes...")
            out = summarise_horizon_scan(d, model=model)
            save_artifact(
                pid,
                type="signals_horizon",
                title=f"Horizon scan: {query.strip()}",
                content_json=out if isinstance(out, dict) else None,
                content_text="",
                metadata={"query": query.strip(), "model": model},
            )
            st.session_state.horizon_json = out
            status.update(label="Horizon scan ready", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Failed", state="error", expanded=True)
            st.error(str(e))


def _render_structured(out: dict) -> None:
    st.subheader("Themes")
    for idx, th in enumerate(out.get("emerging_themes") or [], 1):
        with st.expander(f"{idx}. {th.get('theme','Theme')}"):
            st.write(th.get("why_now", ""))
            st.caption(f"Time horizon: {th.get('time_horizon','')}")

            cols = st.columns(2)
            with cols[0]:
                if th.get("what_to_watch"):
                    st.markdown("**What to watch**")
                    st.markdown("- " + "\n- ".join(th.get("what_to_watch")))
            with cols[1]:
                if th.get("investor_questions"):
                    st.markdown("**Investor questions**")
                    st.markdown("- " + "\n- ".join(th.get("investor_questions")))

            st.markdown("**Campaign ideas**")
            ideas = th.get("campaign_ideas") or []
            for j, idea in enumerate(ideas, 1):
                hook = idea.get("hook", "")
                angle = idea.get("angle", "")
                ch = ", ".join(idea.get("channels") or [])
                st.markdown(f"{j}. **{hook}**\n\n- Angle: {angle}\n- Channels: {ch}")

                if st.button("Send idea to Copywriter", key=f"send_idea_{idx}_{j}"):
                    st.session_state["seed_hook"] = hook or th.get("theme", "")
                    st.session_state["seed_details"] = json.dumps({"theme": th, "idea": idea}, ensure_ascii=False, indent=2)
                    st.session_state["seed_source"] = "signals_horizon"
                    st.switch_page("pages/06_Write_campaign_assets.py")

            if th.get("risks"):
                st.warning("Risks: " + "; ".join(th.get("risks")))


def _default_agent_prompt(q: str) -> str:
    return (
        "You are my futurist for Australian investors. "
        "Scan current news and trends for the query below and produce: "
        "(1) 5 emerging themes likely to matter in 3-12 months, "
        "(2) why each theme is gaining momentum now, "
        "(3) what to watch to validate/kill the theme, "
        "(4) investor questions it triggers, "
        "(5) 3 campaign ideas per theme (hook + angle + channel).\n\n"
        f"Query: {q.strip()}"
    )


def _render_embedded_app(query: str) -> None:
    """Embed a separately hosted AgentKit/ChatKit app via iframe.

    This is the most reliable way to reuse an existing deployed app, but it
    won't automatically hand structured outputs back into the portal without
    additional cross-origin messaging.
    """

    st.subheader("Agent workflow")

    url = (
        get_secret("futurist.embed_url")
        or get_secret("FUTURIST_EMBED_URL")
        or "https://openai-chatkit-starter-app-opal-xi.vercel.app/"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        height = st.slider("Embed height", min_value=560, max_value=1200, value=860, step=20)
    with col2:
        st.markdown(f"Open in new tab: {url}")

    st.caption(
        "Note: embedding is fast, but the portal cannot automatically read the output back from the iframe. "
        "Use the optional paste box below if you want to save results to this project."
    )

    # Helpful prompt context so users can paste into the embedded app (if needed).
    with st.expander("Optional: suggested prompt to use in the embedded app", expanded=False):
        st.code(_default_agent_prompt(query), language="text")

    # Render the iframe.
    # If the embedded app has a restrictive CSP or X-Frame-Options, the browser
    # may block it (you'll see a 'refused to connect' message).
    components.iframe(url, height=int(height), scrolling=True)

    # Optional capture for persistence.
    with st.expander("Optional: paste results here to save to the project library", expanded=False):
        pasted = st.text_area(
            "Paste output (JSON or text)",
            value="",
            height=180,
            placeholder="Paste the workflow output here to save it into the portal library...",
        )
        if st.button("Save pasted output", type="primary"):
            content_json = None
            content_text = pasted.strip()
            if content_text:
                try:
                    parsed = json.loads(content_text)
                    if isinstance(parsed, dict):
                        content_json = parsed
                        content_text = ""
                except Exception:
                    pass
            save_artifact(
                pid,
                type="signals_horizon_agentkit",
                title=f"AgentKit horizon scan: {query.strip()}",
                content_json=content_json,
                content_text=content_text,
                metadata={"query": query.strip(), "embed_url": url},
            )
            st.success("Saved to Library.")
            st.rerun()


def _render_chatkit(query: str, trends_q: str) -> None:
    st.subheader("Agent workflow")

    # Read config (optionally) from Streamlit secrets.
    wf_id = get_secret("futurist.workflow_id") or get_secret("FUTURIST_WORKFLOW_ID")
    wf_ver = get_secret("futurist.workflow_version") or get_secret("FUTURIST_WORKFLOW_VERSION")

    with st.expander("Workflow configuration", expanded=False):
        st.write("Set these in Streamlit secrets to enable the ChatKit-based workflow mode:")
        st.code(
            "[futurist]\nworkflow_id = \"wf_...\"\n# optional\nworkflow_version = \"draft\"\n",
            language="toml",
        )
        st.caption(
            "Tip: the OpenAI API key must be from the same org/project as the published workflow."
        )
        st.write(
            {
                "workflow_id_configured": bool(wf_id),
                "workflow_version_configured": bool(wf_ver),
            }
        )

    if not wf_id:
        st.warning("No futurist.workflow_id configured, so ChatKit mode can't start.")
        st.stop()

    # Persist a pseudo user id across reruns so ChatKit can keep thread continuity.
    if "chatkit_user_id" not in st.session_state:
        import uuid

        st.session_state["chatkit_user_id"] = f"portal-{uuid.uuid4().hex[:16]}"

    # Prompt builder
    st.caption("Prompt")
    default_prompt = st.session_state.get("futurist_agent_prompt") or _default_agent_prompt(query)
    # Streamlit discourages empty labels (and may error in the future), so keep
    # a non-empty label but hide it.
    agent_prompt = st.text_area(
        "Agent prompt",
        value=default_prompt,
        height=160,
        label_visibility="collapsed",
    )

    colX, colY, colZ = st.columns([1, 1, 2])
    with colX:
        auto_send = st.checkbox("Auto-send prompt", value=True)
    with colY:
        embed_height = st.slider("Chat height", min_value=520, max_value=980, value=740, step=20)
    with colZ:
        st.write("")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Start / refresh chat session", type="primary"):
            st.session_state["futurist_agent_prompt"] = agent_prompt
            sess = create_chatkit_session(
                workflow_id=wf_id,
                user_id=st.session_state["chatkit_user_id"],
                workflow_version=wf_ver,
                chatkit_configuration={
                    "file_upload": {"enabled": True},
                },
            )
            st.session_state["chatkit_session"] = sess
            st.session_state["chatkit_auto_send"] = bool(auto_send)
            st.rerun()

    with col2:
        if st.button("Collect signals (portal) and add to prompt"):
            st.session_state["futurist_query"] = query
            st.session_state["futurist_trends_q"] = trends_q
            with st.status("Collecting signals...", expanded=False):
                d = collect_signals(query=query.strip(), trends_query_or_topic_id=(trends_q.strip() or None))
            # Keep it compact: pass the full JSON but let the workflow decide.
            # `collect_signals` returns a dataclass (SignalsData). Convert to a
            # JSON-serializable dict before embedding into the prompt.
            try:
                from dataclasses import asdict

                signals_obj = asdict(d)
            except Exception:
                # Best-effort fallback for other object types.
                signals_obj = getattr(d, "__dict__", d)

            prompt = _default_agent_prompt(query)
            prompt += "\n\nOptional input signals (JSON):\n" + json.dumps(
                signals_obj,
                ensure_ascii=False,
                default=str,
            )
            st.session_state["futurist_agent_prompt"] = prompt
            st.rerun()

    sess = st.session_state.get("chatkit_session")
    if not sess:
        st.info("Click **Start / refresh chat session** to load the workflow.")
        st.stop()

    if isinstance(sess, dict) and sess.get("error"):
        st.error(sess.get("error"))
        with st.expander("Details"):
            st.code(json.dumps(sess.get("details"), ensure_ascii=False, indent=2), language="json")
        st.stop()

    client_secret = sess.get("client_secret") if isinstance(sess, dict) else None
    if not client_secret:
        st.error("ChatKit session missing client_secret.")
        st.stop()

    auto_send_text = agent_prompt if st.session_state.get("chatkit_auto_send") else None
    html = build_chatkit_embed_html(
        client_secret=client_secret,
        height_px=int(embed_height),
        auto_send_text=auto_send_text,
        accent_color=None,
    )
    components.html(html, height=int(embed_height) + 30, scrolling=True)

out = st.session_state.get("horizon_json")

# Render based on mode
if mode == "Agent workflow (Embedded app)":
    _render_embedded_app(query=query)
    st.stop()

if mode == "Agent workflow (ChatKit)":
    _render_chatkit(query=query, trends_q=trends_q)
    st.stop()

# Structured output mode
if not out:
    st.stop()
if "error" in out:
    st.error(out.get("error"))
    with st.expander("Raw output"):
        st.code(out.get("raw", ""))
    st.stop()

_render_structured(out)
