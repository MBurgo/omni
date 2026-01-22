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


def _toggle_objective(objective_key: str) -> None:
    """Toggle which objective is expanded on the homepage."""
    current = st.session_state.get("__home_objective")
    st.session_state["__home_objective"] = None if current == objective_key else objective_key


# --- Page-specific CSS to match the objective-tile homepage design ---
st.markdown(
    """
<style>
/* Center the content container */
.home-wrap {
  max-width: 1180px;
  margin: 0 auto;
}

/* Objective tiles */
.objective-tiles div.stButton > button[kind="secondary"] {
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

.objective-tiles div.stButton > button[kind="secondary"]:hover {
  background: rgba(255,255,255,0.06);
}

/* Drop-down tool buttons (nested under the objective tile) */
.objective-dropdown {
  margin-top: -0.25rem;
  padding-top: 0.25rem;
}

.objective-dropdown div.stButton > button[kind="secondary"] {
  width: 100%;
  min-height: 56px;
  border-radius: 18px;
  border-width: 2px;
  background: rgba(255,255,255,0.02);
  padding: 0.70rem 0.95rem;
  font-size: 16px;
  line-height: 1.25;
  text-align: left;
  white-space: normal;
}

.objective-dropdown div.stButton > button[kind="secondary"]:hover {
  background: rgba(255,255,255,0.06);
}

.objective-dropdown .dropdown-label {
  font-family: 'Poppins', sans-serif;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  margin: 0.65rem 0 0.45rem 0;
  color: rgba(255,255,255,0.70);
}
</style>
""",
    unsafe_allow_html=True,
)

# --- Hero + objective tiles ---
st.markdown("<div class='home-wrap'>", unsafe_allow_html=True)
st.markdown("<div class='hero-title'>Hi, Fool. What’s your objective today?</div>", unsafe_allow_html=True)

OBJECTIVES = [
    {
        "key": "ideas",
        "label": "I need help generating\nideas for campaigns",
        "tools": [
            {
                "label": "Find out what’s making news in financial markets",
                "page": "pages/01_Find_spikes_today.py",
                "state": None,
            },
            {
                "label": "Explore emerging investing themes",
                "page": "pages/02_Find_emerging_themes.py",
                "state": None,
            },
        ],
    },
    {
        "key": "research",
        "label": "I want to do customer\nresearch using AI personas",
        "tools": [
            {
                "label": "Stress test creative using the AI Focus Panel",
                "page": "pages/05_Pressure_test_creative.py",
                "state": None,
            },
            {
                "label": "Ask questions to AI Personas",
                "page": "pages/03_Ask_a_persona.py",
                "state": None,
            },
        ],
    },
    {
        "key": "copy",
        "label": "I need help generating\ncopy for a campaign",
        "tools": [
            {
                "label": "Deliver campaign assets from a brief",
                "page": "pages/06_Write_campaign_assets.py",
                "state": {"copywriter_mode": "generate"},
            },
            {
                "label": "Adapt existing assets for a new market",
                "page": "pages/06_Write_campaign_assets.py",
                "state": {"copywriter_mode": "adapt"},
            },
            {
                "label": "Guided campaign flow from scratch",
                "page": "pages/08_Campaign_pack_wizard.py",
                # Reset wizard state so it opens "from scratch" even if used previously.
                "state": {
                    "wiz_brief": None,
                    "wiz_selected_opp": None,
                    "wiz_hook": "",
                    "wiz_details": "",
                    "wiz_draft": "",
                    "wiz_focus": None,
                    "wiz_pack": "",
                },
            },
        ],
    },
]

cols = st.columns(3, gap="large")
for i, obj in enumerate(OBJECTIVES):
    with cols[i]:
        st.markdown("<div class='objective-tiles'>", unsafe_allow_html=True)
        if st.button(obj["label"], type="secondary", use_container_width=True, key=f"objective_{obj['key']}"):
            _toggle_objective(obj["key"])
        st.markdown("</div>", unsafe_allow_html=True)

        # Drop-down: show tools for the selected objective under the corresponding tile.
        if st.session_state.get("__home_objective") == obj["key"]:
            st.markdown("<div class='objective-dropdown'>", unsafe_allow_html=True)
            st.markdown("<div class='dropdown-label'>Tools</div>", unsafe_allow_html=True)

            for t_i, tool in enumerate(obj["tools"]):
                if st.button(tool["label"], type="secondary", use_container_width=True, key=f"tool_{obj['key']}_{t_i}"):
                    if tool.get("state"):
                        for k, v in tool["state"].items():
                            st.session_state[k] = v
                    st.switch_page(tool["page"])

            st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
