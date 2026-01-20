from __future__ import annotations

import time
from typing import Optional

import streamlit as st

from storage.store import get_current_project_id, get_project, list_projects, set_current_project


def project_banner() -> Optional[str]:
    """Render a compact project selector banner. Return selected project_id or None."""
    projects = list_projects()
    current = get_current_project_id()

    if not projects:
        st.info("No projects yet. Create one in the Projects page.")
        return None

    id_to_name = {p.id: p.name for p in projects}

    default_index = 0
    if current and current in id_to_name:
        default_index = list(id_to_name.keys()).index(current)

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


def require_project() -> str:
    pid = get_current_project_id()
    if pid:
        return pid

    projects = list_projects()
    if projects:
        set_current_project(projects[0].id)
        return projects[0].id

    st.warning("Create a project first (Projects page).")
    st.stop()


def human_time(ts: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return str(ts)
