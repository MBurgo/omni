import streamlit as st

from storage.store import create_project, get_current_project_id, list_projects, set_current_project
from ui.branding import apply_branding
from ui.layout import human_time, project_banner, require_project

st.set_page_config(
    page_title="Projects",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

# Ensure a project always exists (Option A: auto-create Default).
require_project()

with st.sidebar:
    project_banner(compact=True)

st.markdown("<div class='page-title'>Projects</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='page-subtitle'>Projects are lightweight containers for briefs, drafts, tests, and outputs. Create one for each campaign, sprint, or experiment.</div>",
    unsafe_allow_html=True,
)

# --- Create project ---
with st.expander("Create a new project", expanded=False):
    with st.form("create_project_form"):
        name = st.text_input("Project name", placeholder="e.g., Share Advisor - Feb 2026 acquisition push")
        description = st.text_area("Description (optional)", placeholder="What are we trying to achieve?", height=90)
        submitted = st.form_submit_button("Create project", type="primary")
        if submitted:
            if not name.strip():
                st.warning("Please enter a project name.")
            else:
                p = create_project(name=name.strip(), description=description.strip())
                set_current_project(p.id)
                st.success("Project created.")
                st.rerun()

projects = list_projects()
if not projects:
    st.info("No projects yet. Create one above.")
    st.stop()

current = get_current_project_id() or projects[0].id
if not any(p.id == current for p in projects):
    current = projects[0].id
    set_current_project(current)

left, right = st.columns([2, 3], gap="large")

with left:
    st.subheader("All projects")

    options = [p.id for p in projects]

    def fmt(pid: str) -> str:
        p = next(x for x in projects if x.id == pid)
        return f"{human_time(p.updated_at)} — {p.name}"

    sel = st.radio("", options=options, format_func=fmt, index=options.index(current) if current in options else 0)
    if sel != current:
        set_current_project(sel)
        current = sel
        st.rerun()

with right:
    st.subheader("Details")
    p = next((x for x in projects if x.id == current), None)
    if p:
        st.markdown(f"**{p.name}**")
        if p.description:
            st.write(p.description)
        st.caption(f"Project ID: `{p.id}`")
        st.caption(f"Created: {human_time(p.created_at)} | Updated: {human_time(p.updated_at)}")

        st.divider()
        st.page_link("pages/09_Library.py", label="Open Library", icon="🗂️")
