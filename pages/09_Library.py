import json

import streamlit as st

from storage.store import get_artifact, list_artifacts
from ui.branding import apply_branding
from ui.layout import project_banner, human_time, require_project

st.set_page_config(page_title="Library", page_icon="🗂️", layout="wide")
apply_branding()

st.title("🗂️ Library")
st.caption("Everything generated in this project: signals, themes, drafts, tests, and rewrites.")

project_banner()
pid = require_project()

artifacts = list_artifacts(pid, limit=200)

if not artifacts:
    st.info("No artifacts yet. Start from Home.")
    st.stop()

# Filters
all_types = sorted({a.type for a in artifacts})
type_filter = st.selectbox("Filter by type", options=["All"] + all_types)
filtered = artifacts if type_filter == "All" else [a for a in artifacts if a.type == type_filter]

left, right = st.columns([2, 3])

with left:
    st.subheader("Items")
    options = [a.id for a in filtered]
    def fmt(aid: str) -> str:
        a = next(x for x in filtered if x.id == aid)
        return f"{human_time(a.created_at)} - {a.type} - {a.title}"

    selected_id = st.radio("", options=options, format_func=fmt)

with right:
    st.subheader("Details")
    a = get_artifact(selected_id)
    st.markdown(f"**{a.title}**")
    st.caption(f"Type: `{a.type}` | Created: {human_time(a.created_at)}")

    if a.metadata:
        with st.expander("Metadata", expanded=False):
            st.code(json.dumps(a.metadata, ensure_ascii=False, indent=2), language="json")

    if a.content_json is not None:
        with st.expander("JSON", expanded=False):
            st.code(json.dumps(a.content_json, ensure_ascii=False, indent=2), language="json")

    if a.content_text:
        st.markdown("---")
        st.markdown(a.content_text)
