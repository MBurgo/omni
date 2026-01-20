import json

import streamlit as st
import streamlit.components.v1 as components

from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import project_banner, require_project
from utils import get_secret

st.set_page_config(page_title="Futurist - Emerging themes", page_icon="🔮", layout="wide")
apply_branding()

st.title("🔮 Emerging themes")
st.caption(
    "Runs the Futurist agent workflow via an embedded app. "
    "Use the embedded experience to generate themes, then optionally save outputs into the portal Library."
)

project_banner()
pid = require_project()

# --- Embedded app (only mode) ---
url = (
    get_secret("futurist.embed_url")
    or get_secret("FUTURIST_EMBED_URL")
    or "https://openai-chatkit-starter-app-opal-xi.vercel.app/"
)

if not url:
    st.error(
        "Futurist embedded app URL not configured. Add this to Streamlit secrets:\n\n"
        "[futurist]\nembed_url = \"https://...\""
    )
    st.stop()

col1, col2 = st.columns([1, 3])
with col1:
    height = st.slider("Embed height", min_value=560, max_value=1400, value=860, step=20)
with col2:
    st.markdown(f"[Open embedded app in a new tab]({url})")

components.iframe(url, height=int(height), scrolling=True)

# --- Optional capture (persistence) ---
with st.expander("Save results to Library", expanded=False):
    st.caption(
        "The portal can’t automatically read the output back from the embedded app. "
        "If you want the result stored with this project, paste it below."
    )

    query = st.text_input(
        "Optional topic focus (stored with the record)",
        value=st.session_state.get("futurist_query", "ASX 200"),
        help="This does not control the embedded app; it’s just saved as metadata.",
    )
    st.session_state["futurist_query"] = query

    pasted = st.text_area(
        "Paste workflow output (JSON or text)",
        value="",
        height=220,
        placeholder="Paste the workflow output here to save it into the portal Library...",
    )

    colA, colB = st.columns([1, 3])
    with colA:
        if st.button("Save to Library", type="primary"):
            content_json = None
            content_text = pasted.strip()

            if not content_text:
                st.warning("Paste some output first.")
                st.stop()

            # If the user pasted JSON, store it as structured content.
            try:
                parsed = json.loads(content_text)
                if isinstance(parsed, dict):
                    content_json = parsed
                    content_text = ""
            except Exception:
                pass

            title = "Agent workflow output"
            if query.strip():
                title = f"Agent workflow output: {query.strip()}"

            save_artifact(
                pid,
                type="signals_horizon_agentkit",
                title=title,
                content_json=content_json,
                content_text=content_text,
                metadata={
                    "query": query.strip(),
                    "embed_url": url,
                },
            )

            st.success("Saved. Open Library to view or reuse it in other flows.")

    with colB:
        st.page_link("pages/09_Library.py", label="Open Library", icon="🗂️")
