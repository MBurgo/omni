import streamlit as st

from storage.store import get_project
from ui.branding import apply_branding
from ui.layout import SINGLE_PROJECT_MODE, hub_nav

st.set_page_config(
    page_title="Projects",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

st.markdown("<div class='page-title'>Projects</div>", unsafe_allow_html=True)

# Top navigation.
pid = hub_nav()

if SINGLE_PROJECT_MODE:
    st.markdown(
        "<div class='page-subtitle'>Single-project mode is enabled. This hub always uses the <b>Default</b> project and hides project switching.</div>",
        unsafe_allow_html=True,
    )
    p = get_project(pid)
    st.markdown(f"**Current project:** {p.name}")
    if p.description:
        st.write(p.description)
    st.page_link("pages/09_Library.py", label="Open Library")
    st.stop()

# If multi-project mode is ever re-enabled, this page can be restored.
st.info("Multi-project management is currently disabled in this build.")
