from __future__ import annotations

import time
from typing import Optional

import streamlit as st

from storage.store import create_project, get_current_project_id, list_projects, set_current_project


DEFAULT_PROJECT_NAME = "Default"
DEFAULT_PROJECT_DESCRIPTION = "Auto-created project"


def _ensure_default_project() -> str:
    """Ensure the portal always has a usable project selected.

    Option A: If no project exists yet, automatically create a
    lightweight default project and select it.

    Returns the current project_id.
    """

    # Fast path: a valid current project is already selected.
    current = get_current_project_id()
    projects = list_projects()

    if not projects:
        p = create_project(name=DEFAULT_PROJECT_NAME, description=DEFAULT_PROJECT_DESCRIPTION)
        set_current_project(p.id)
        return p.id

    if current and any(p.id == current for p in projects):
        return current

    # Fall back to the most recently updated project (list_projects is ordered by updated_at DESC).
    set_current_project(projects[0].id)
    return projects[0].id


def project_banner(compact: bool = False) -> Optional[str]:
    """Render a project selector.

    - compact=False (default): 3-column banner used in the main canvas.
    - compact=True: sidebar-friendly vertical layout.

    Returns the selected project_id.
    """

    # Ensure there's always at least one project so the portal can run.
    current = _ensure_default_project()

    projects = list_projects()
    id_to_name = {p.id: p.name for p in projects}

    default_index = 0
    if current and current in id_to_name:
        default_index = list(id_to_name.keys()).index(current)

    if compact:
        st.markdown("## Project")
        sel = st.selectbox(
            "Current project",
            options=list(id_to_name.keys()),
            index=default_index,
            format_func=lambda pid: id_to_name.get(pid, pid),
            key="__project_selector",
        )
        if sel != current:
            set_current_project(sel)
            current = sel

        st.divider()
        st.page_link("pages/00_Projects.py", label="Projects", icon="📁")
        st.page_link("pages/09_Library.py", label="Library", icon="🗂️")
    else:
        cols = st.columns([3, 1, 1])
        with cols[0]:
            sel = st.selectbox(
                "Current project",
                options=list(id_to_name.keys()),
                index=default_index,
                format_func=lambda pid: id_to_name.get(pid, pid),
                key="__project_selector",
            )
            if sel != current:
                set_current_project(sel)
                current = sel

        with cols[1]:
            st.page_link("pages/00_Projects.py", label="Projects", icon="📁")
        with cols[2]:
            st.page_link("pages/09_Library.py", label="Library", icon="🗂️")

    return current


def hub_nav(
    *,
    show_home_link: bool = True,
    show_project_selector: bool = True,
    show_projects_link: bool = False,
    show_library_link: bool = False,
) -> str:
    """Render a lightweight top navigation bar for all pages.

    The portal intentionally hides Streamlit's sidebar navigation. This helper provides:
    - A "Back to hub" link
    - A project selector (so users can switch context without a sidebar)

    Returns the current project_id.
    """

    current = _ensure_default_project()
    projects = list_projects()
    id_to_name = {p.id: p.name for p in projects}

    default_index = 0
    if current and current in id_to_name:
        default_index = list(id_to_name.keys()).index(current)

    # Layout: Back link | Project selector
    cols = st.columns([1.6, 4.4], gap="small")

    with cols[0]:
        if show_home_link:
            # Streamlit renders this as an inline link-style control.
            # Keep this compact: no icons/emojis and a short label.
            st.page_link("Home.py", label="Back to hub")
        else:
            st.write("")

    with cols[1]:
        if show_project_selector:
            sel = st.selectbox(
                "Project",
                options=list(id_to_name.keys()),
                index=default_index,
                format_func=lambda pid: id_to_name.get(pid, pid),
                key="__project_selector_topnav",
                label_visibility="collapsed",
            )
            if sel != current:
                set_current_project(sel)
                current = sel
        else:
            st.write("")

    # Keep the separator subtle and tight to reduce vertical footprint.
    st.markdown(
        "<hr style='margin: 0.35rem 0 0.9rem 0; border: none; border-top: 1px solid rgba(255,255,255,0.12);' />",
        unsafe_allow_html=True,
    )
    return current


def require_project() -> str:
    """Return the selected project_id.

    With Option A enabled, this will auto-create a default project if needed.
    """

    return _ensure_default_project()


def human_time(ts: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return str(ts)
