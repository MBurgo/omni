import streamlit as st

from storage.store import create_project, get_current_project_id, list_projects, set_current_project
from ui.branding import apply_branding

st.set_page_config(page_title="Projects", page_icon="📁", layout="centered")
apply_branding()

st.title("📁 Projects")
st.caption("Projects are lightweight containers for briefs, drafts, tests, and outputs.")

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

# --- List projects ---
projects = list_projects()
if not projects:
    st.info("No projects yet. Create one above.")
    st.stop()

current = get_current_project_id()
id_to_name = {p.id: p.name for p in projects}

st.subheader("Select a project")
sel = st.selectbox(
    "Current project",
    options=list(id_to_name.keys()),
    format_func=lambda pid: id_to_name.get(pid, pid),
    index=(list(id_to_name.keys()).index(current) if current in id_to_name else 0),
)
if sel != current:
    set_current_project(sel)
    st.rerun()

# --- Details ---
selected = next((p for p in projects if p.id == sel), None)
if selected:
    st.divider()
    st.markdown(f"**{selected.name}**")
    if selected.description:
        st.write(selected.description)

    st.caption(f"Project ID: `{selected.id}`")
