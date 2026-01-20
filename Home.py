import streamlit as st

from storage.store import get_current_project_id, list_projects, set_current_project
from ui.branding import apply_branding

st.set_page_config(page_title="Burgo's AI Hub", page_icon="🧭", layout="wide")
apply_branding()

# --- Header ---
st.title("Hi, Fool. What’s your objective today?")
st.write("")  # Spacer

# --- Logic: Project selection (Required for app to function) ---
# We check this first to ensure a project is active, but we display the selector 
# at the bottom or cleanly to avoid cluttering the visual hub.
projects = list_projects()
if not projects:
    st.info("No projects yet. Create one first.")
    st.page_link("pages/00_Projects.py", label="Create a project", icon="📁")
    st.stop()

cur = get_current_project_id()
if not cur:
    # Default to first project if none selected
    set_current_project(projects[0].id)
    cur = projects[0].id

# --- Goal Grid (3x2 Layout) ---

# ROW 1
col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("Find out what’s making news in the financial markets")
        st.write("") # Visual spacing
        if st.button("Open", key="goal_spikes", use_container_width=True):
            st.switch_page("pages/01_Find_spikes_today.py")

with col2:
    with st.container(border=True):
        st.subheader("Ask our futurist for emerging trends investors should know about")
        st.write("")
        if st.button("Open", key="goal_futurist", use_container_width=True):
            st.switch_page("pages/02_Find_emerging_themes.py")

with col3:
    with st.container(border=True):
        st.subheader("Ask our AI investing personas their thoughts about marketing/product")
        st.write("")
        if st.button("Open", key="goal_personas", use_container_width=True):
            st.switch_page("pages/03_Ask_a_persona.py")

st.write("") # Row spacing

# ROW 2
col4, col5, col6 = st.columns(3)

with col4:
    with st.container(border=True):
        st.subheader("Stress test creative using our AI Focus Panel")
        st.write("")
        if st.button("Open", key="goal_pressure", use_container_width=True):
            st.switch_page("pages/05_Pressure_test_creative.py")

with col5:
    with st.container(border=True):
        st.subheader("Brief our AI copywriter to deliver campaign assets")
        st.write("")
        if st.button("Open", key="goal_copywriter_new", use_container_width=True):
            # We can set state here if we want to default the page to 'Generate' mode
            st.switch_page("pages/06_Write_campaign_assets.py")

with col6:
    with st.container(border=True):
        st.subheader("Brief our AI copywriter to adapt existing campaign assets")
        st.write("")
        if st.button("Open", key="goal_copywriter_adapt", use_container_width=True):
            # This also goes to the copywriter page, where users can select 'Revise' or 'Localise'
            st.switch_page("pages/06_Write_campaign_assets.py")

st.divider()

# --- Footer & Context ---
f_col1, f_col2 = st.columns([3, 1])

with f_col1:
    # Project selector kept accessible but out of the main "Hero" area
    id_to_name = {p.id: p.name for p in projects}
    sel = st.selectbox(
        "Active Project",
        options=list(id_to_name.keys()),
        format_func=lambda pid: id_to_name.get(pid, pid),
        index=(list(id_to_name.keys()).index(cur) if cur in id_to_name else 0),
    )
    if sel != cur:
        set_current_project(sel)
        st.rerun()

with f_col2:
    st.write("") 
    st.write("") 
    st.markdown("<div style='text-align: right; font-weight: bold;'>Burgo’s AI Hub</div>", unsafe_allow_html=True)
