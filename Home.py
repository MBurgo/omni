import streamlit as st

from ui.branding import apply_branding
from ui.layout import project_banner, require_project

st.set_page_config(
    page_title="Burgo’s AI Hub",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

# Ensure the portal always has a project selected (Option A: auto-create Default).
require_project()

with st.sidebar:
    project_banner(compact=True)

# --- Page-specific CSS to turn secondary buttons into the home tiles ---
st.markdown(
    """
<style>
/* Make the six objective tiles look like the provided screenshot */
.home-tiles div.stButton > button[kind="secondary"] {
  width: 100%;
  min-height: 96px;
  border-radius: 28px;
  border-width: 3px;
  background: rgba(0,0,0,0.00);
  padding: 1.10rem 1.15rem;
  font-size: 20px;
  line-height: 1.25;
  text-align: center;
  white-space: normal;
}

/* Slight hover fill */
.home-tiles div.stButton > button[kind="secondary"]:hover {
  background: rgba(255,255,255,0.06);
}

/* Center the grid container */
.home-wrap {
  max-width: 1150px;
  margin: 0 auto;
}
</style>
""",
    unsafe_allow_html=True,
)

# --- Hero + tile grid ---
st.markdown("<div class='home-wrap'>", unsafe_allow_html=True)
st.markdown("<div class='hero-title'>Hi, Fool. What’s your objective today?</div>", unsafe_allow_html=True)

st.markdown("<div class='home-tiles'>", unsafe_allow_html=True)

# Mapping: tile label -> page
TILES = [
    (
        "Find out what’s making news in the financial markets",
        "pages/01_Find_spikes_today.py",
        None,
    ),
    (
        "Ask our futurist for emerging trends investors should know about",
        "pages/02_Find_emerging_themes.py",
        None,
    ),
    (
        "Ask our AI Personas brand, marketing or product-related questions",
        "pages/03_Ask_a_persona.py",
        None,
    ),
    (
        "Stress test creative using our AI Focus Panel",
        "pages/05_Pressure_test_creative.py",
        None,
    ),
    (
        "Brief our AI copywriter to deliver campaign assets",
        "pages/06_Write_campaign_assets.py",
        {"copywriter_mode": "generate"},
    ),
    (
        "Brief our AI copywriter to adapt existing campaign assets",
        "pages/06_Write_campaign_assets.py",
        {"copywriter_mode": "adapt"},
    ),
]

rows = [TILES[i : i + 3] for i in range(0, len(TILES), 3)]
for r_i, row in enumerate(rows):
    cols = st.columns(3, gap="large")
    for c_i, (label, page, state) in enumerate(row):
        with cols[c_i]:
            if st.button(label, type="secondary", use_container_width=True, key=f"tile_{r_i}_{c_i}"):
                if state:
                    for k, v in state.items():
                        st.session_state[k] = v
                st.switch_page(page)

st.markdown("</div>", unsafe_allow_html=True)  # home-tiles
st.markdown("</div>", unsafe_allow_html=True)  # home-wrap
