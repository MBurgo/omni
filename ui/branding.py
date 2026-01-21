import streamlit as st

# Motley Fool AU palette (kept for reuse across the app)
FOOL_COLORS = {
    "gold": "#FFB81C",
    "bronze": "#CF7F00",
    "red": "#F9423A",
    "magenta": "#E31C79",
    "purple": "#981E97",
    "blue": "#485CC7",
    "cyan": "#0095C8",
    "green": "#43B02A",
    "midgray": "#53565A",
    "black": "#000000",
    "soft_green": "#C6EEB2",
    "soft_blue": "#DAF3F8",
    "soft_purple": "#D6CAED",
    "soft_red": "#FEE2E7",
    "soft_gold": "#FDEBD4",
    "soft_yellow": "#FDF5DA",
}


def apply_branding(footer_text: str = "Burgo’s AI Hub") -> None:
    """Apply Burgo's AI Hub styling.

    This is intentionally lightweight CSS that:
    - Uses a dark canvas (to match provided screenshots)
    - Sets consistent typography
    - Styles primary buttons as gold pills
    - Keeps Streamlit chrome out of the way
    """

    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;800&family=Inter:wght@300;400;600;700&display=swap');

/* --- Hide Streamlit chrome --- */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}

/* Keep the header so the sidebar expand/collapse control remains accessible.
   We still hide Streamlit's main menu and footer above. */
header[data-testid="stHeader"] {{ background: transparent; }}

/* Ensure the sidebar toggle is visible on a dark background */
[data-testid="collapsedControl"] {{
  color: rgba(255,255,255,0.92);
}}
[data-testid="collapsedControl"] svg {{
  fill: rgba(255,255,255,0.92);
  stroke: rgba(255,255,255,0.92);
}}

/* --- App background + base typography --- */
html, body {{
  background: {FOOL_COLORS['black']};
}}

[data-testid="stAppViewContainer"] {{
  background: radial-gradient(circle at 50% 0%, #111 0%, {FOOL_COLORS['black']} 65%);
  color: rgba(255,255,255,0.92);
}}

.stApp {{
  color: rgba(255,255,255,0.92);
}}

*, html, body, [class*="css"] {{
  font-family: 'Inter', sans-serif;
}}

/* --- Layout --- */
.block-container {{
  padding-top: 3.25rem;
  padding-bottom: 3.25rem;
  max-width: 1200px;
}}

/* --- Headings --- */
h1, h2, h3, .stTitle, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {{
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  color: rgba(255,255,255,0.96);
  letter-spacing: -0.02em;
}}

/* --- Helpers used by pages --- */
.hero-title {{
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 64px;
  line-height: 1.05;
  text-align: center;
  margin: 2.5rem 0 2.25rem 0;
  color: rgba(255,255,255,0.96);
}}

.page-title {{
  font-family: 'Poppins', sans-serif;
  font-weight: 800;
  font-size: 56px;
  line-height: 1.06;
  margin: 0 0 0.75rem 0;
  color: rgba(255,255,255,0.96);
}}

.page-subtitle {{
  font-size: 20px;
  line-height: 1.55;
  max-width: 1100px;
  color: rgba(255,255,255,0.82);
  margin: 0 0 1.5rem 0;
}}

.brand-footer {{
  position: fixed;
  right: 48px;
  bottom: 32px;
  font-family: 'Poppins', sans-serif;
  font-weight: 700;
  font-size: 22px;
  color: rgba(255,255,255,0.92);
  z-index: 1000;
  pointer-events: none;
}}

/* --- Buttons --- */
div.stButton > button[kind="primary"],
div.stDownloadButton > button {{
  background-color: {FOOL_COLORS['gold']};
  color: #000000;
  border: 0;
  border-radius: 9999px;
  padding: 0.50rem 1.25rem;
  font-family: 'Poppins', sans-serif;
  font-weight: 700;
}}

div.stButton > button[kind="primary"]:hover,
div.stDownloadButton > button:hover {{
  filter: brightness(0.96);
}}

/* Secondary buttons (neutral, dark) */
div.stButton > button[kind="secondary"] {{
  background: rgba(255,255,255,0.02);
  color: rgba(255,255,255,0.92);
  border: 2px solid rgba(255,255,255,0.65);
  border-radius: 16px;
  padding: 0.55rem 1.0rem;
  font-family: 'Poppins', sans-serif;
  font-weight: 600;
}}

div.stButton > button[kind="secondary"]:hover {{
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.92);
}}

/* --- Inputs (keep readable on dark background) --- */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{
  background: rgba(255,255,255,0.06);
  color: rgba(255,255,255,0.92);
  border: 1px solid rgba(255,255,255,0.20);
  border-radius: 12px;
}}

/* Select / multiselect (BaseWeb) */
[data-baseweb="select"] > div {{
  background: rgba(255,255,255,0.06);
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.20);
}}

/* Labels */
label, .stCaption {{
  color: rgba(255,255,255,0.78) !important;
}}

/* Dividers */
hr {{
  border-color: rgba(255,255,255,0.12);
}}

/* Links */
a {{
  color: rgba(255,255,255,0.92);
  text-decoration: underline;
}}

a:hover {{
  color: rgba(255,255,255,1.0);
}}
</style>
""",
        unsafe_allow_html=True,
    )

    # Always render the fixed footer label so every page is consistent,
    # even if the page exits early via st.stop().
    render_footer(footer_text)


def render_footer(text: str = "Burgo’s AI Hub") -> None:
    """Render the fixed bottom-right footer label used in the provided screenshots."""
    st.markdown(f"<div class=\"brand-footer\">{text}</div>", unsafe_allow_html=True)
