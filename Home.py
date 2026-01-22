import streamlit as st

from ui.branding import apply_branding
from ui.layout import hub_nav

st.set_page_config(
    page_title="Burgo’s AI Hub",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

# Top navigation. On the hub homepage itself we hide the back-link.
hub_nav(show_home_link=False)

# --- Page-specific CSS to turn secondary buttons into the home tiles ---
st.markdown(
    """
<style>
/* Make the objective tiles look like the provided screenshot */
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

.home-section {
  margin-top: 1.1rem;
  margin-bottom: 0.75rem;
}

.home-section h3 {
  margin: 0.0rem 0 0.25rem 0;
}

.home-section p {
  margin: 0 0 0.35rem 0;
  opacity: 0.92;
}
</style>
""",
    unsafe_allow_html=True,
)

# --- Hero + tile grid ---
st.markdown("<div class='home-wrap'>", unsafe_allow_html=True)
st.markdown("<div class='hero-title'>Hi, Fool. What’s your objective today?</div>", unsafe_allow_html=True)

# Mapping: tile label -> page
GROUPS = [
    {
        "title": "Idea generation",
        "subtitle": "Spot what’s trending, then turn it into angles worth testing.",
        "tiles": [
            (
                "Find out what’s making news in the financial markets",
                "pages/01_Find_spikes_today.py",
                None,
            ),
            (
                "Emerging investing trends investors should know about",
                "pages/02_Find_emerging_themes.py",
                None,
            ),
        ],
    },
    {
        "title": "Customer research",
        "subtitle": "Pressure test messaging against realistic investor segments.",
        "tiles": [
            (
                "Stress test creative using our AI Focus Panel",
                "pages/05_Pressure_test_creative.py",
                None,
            ),
            (
                "AI Personas: ask brand, marketing or product questions",
                "pages/03_Ask_a_persona.py",
                None,
            ),
        ],
    },
    {
        "title": "Copywriting",
        "subtitle": "Generate or localise campaign assets with consistent structure and compliance.",
        "tiles": [
            (
                "Deliver campaign assets from a brief",
                "pages/06_Write_campaign_assets.py",
                {"copywriter_mode": "generate"},
            ),
            (
                "Adapt existing campaign assets for a new market",
                "pages/06_Write_campaign_assets.py",
                {"copywriter_mode": "adapt"},
            ),
        ],
    },
]

st.markdown("<div class='home-tiles'>", unsafe_allow_html=True)

for g_i, group in enumerate(GROUPS):
    st.markdown(
        f"""<div class='home-section'><h3>{group['title']}</h3><p>{group['subtitle']}</p></div>""",
        unsafe_allow_html=True,
    )

    tiles = group["tiles"]
    cols = st.columns(2, gap="large")
    for t_i, (label, page, state) in enumerate(tiles):
        with cols[t_i]:
            if st.button(label, type="secondary", use_container_width=True, key=f"tile_{g_i}_{t_i}"):
                if state:
                    for k, v in state.items():
                        st.session_state[k] = v
                st.switch_page(page)

st.markdown("</div>", unsafe_allow_html=True)  # home-tiles
st.markdown("</div>", unsafe_allow_html=True)  # home-wrap
