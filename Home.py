import streamlit as st

from storage.store import get_current_project_id, list_artifacts, list_projects, set_current_project
from ui.branding import apply_branding

st.set_page_config(page_title="AI Marketing Portal", page_icon="🧭", layout="wide")
apply_branding()

st.title("🧭 AI Marketing Portal")
st.caption("Pick an end goal, then the portal funnels you to the right workflow.")

# --- Project selection (inline, lightweight) ---
projects = list_projects()
if not projects:
    st.info("No projects yet. Create one first.")
    st.page_link("pages/00_Projects.py", label="Create a project", icon="📁")
    st.stop()

cur = get_current_project_id()
if not cur:
    set_current_project(projects[0].id)
    cur = projects[0].id

id_to_name = {p.id: p.name for p in projects}
sel = st.selectbox(
    "Current project",
    options=list(id_to_name.keys()),
    format_func=lambda pid: id_to_name.get(pid, pid),
    index=(list(id_to_name.keys()).index(cur) if cur in id_to_name else 0),
)
if sel != cur:
    set_current_project(sel)
    cur = sel

st.page_link("pages/00_Projects.py", label="Manage projects", icon="📁")
st.page_link("pages/09_Library.py", label="Open library", icon="🗂️")

st.divider()

st.markdown("## What are you looking to accomplish today?")

# --- Goal tiles ---
GOALS = [
    {
        "title": "Find what's spiking today",
        "desc": "Google News + Trends -> 6 campaign opportunities.",
        "page": "pages/01_Find_spikes_today.py",
        "icon": "📰",
    },
    {
        "title": "Predict emerging investor themes",
        "desc": "Horizon scan -> 5 themes + campaign ideas.",
        "page": "pages/02_Find_emerging_themes.py",
        "icon": "🔮",
    },
    {
        "title": "Ask a persona",
        "desc": "Interview investor segments for objections and trust triggers.",
        "page": "pages/03_Ask_a_persona.py",
        "icon": "🧠",
    },
    {
        "title": "Test headlines",
        "desc": "Get click/trust reactions and pick a winner.",
        "page": "pages/04_Test_headlines.py",
        "icon": "🧪",
    },
    {
        "title": "Pressure-test creative",
        "desc": "Believer vs Skeptic debate + moderator rewrite.",
        "page": "pages/05_Pressure_test_creative.py",
        "icon": "🔬",
    },
    {
        "title": "Write campaign assets",
        "desc": "Generate or revise email/ad/sales-page copy.",
        "page": "pages/06_Write_campaign_assets.py",
        "icon": "✍️",
    },
    {
        "title": "Build a campaign pack",
        "desc": "Wizard: insight -> draft -> validate -> export.",
        "page": "pages/08_Campaign_pack_wizard.py",
        "icon": "🧩",
    },
]

rows = [GOALS[i : i + 3] for i in range(0, len(GOALS), 3)]
for row in rows:
    cols = st.columns(3)
    for i, goal in enumerate(row):
        with cols[i]:
            with st.container(border=True):
                st.markdown(f"### {goal['icon']} {goal['title']}")
                st.caption(goal["desc"])
                if st.button("Open", key=f"goal_{goal['page']}"):
                    st.switch_page(goal["page"])

st.divider()

# --- Recent items ---
st.markdown("## Recent items in this project")
arts = list_artifacts(cur, limit=12)
if not arts:
    st.caption("No artifacts yet.")
else:
    for a in arts:
        st.markdown(f"- **{a.type}** — {a.title}")


