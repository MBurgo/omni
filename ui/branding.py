import streamlit as st

# Motley Fool AU palette (subset used in UI)
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


def apply_branding() -> None:
    """Apply lightweight, consistent styling."""
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css?family=Oswald:400,700');
@import url('https://fonts.googleapis.com/css?family=Roboto:300,400,500,700,900');

html, body, [class*="css"] {{
  font-family: 'Roboto', sans-serif;
  color: {FOOL_COLORS['midgray']};
}}

h1, .stTitle {{
  font-family: 'Oswald', sans-serif;
  color: {FOOL_COLORS['red']};
}}

h2, h3 {{
  font-family: 'Oswald', sans-serif;
  color: {FOOL_COLORS['bronze']};
}}

/* Buttons */
div.stButton > button {{
  background-color: {FOOL_COLORS['green']};
  color: white;
  border: none;
  border-radius: 8px;
  padding: 0.55rem 1.0rem;
}}
div.stButton > button:hover {{
  background-color: {FOOL_COLORS['blue']};
  color: white;
}}

/* Secondary buttons */
button[kind="secondary"] {{
  border-radius: 8px;
}}

/* Containers */
[data-testid="stMetric"] {{
  background: {FOOL_COLORS['soft_blue']};
  border-radius: 10px;
  padding: 10px 12px;
}}

/* Code blocks */
code {{ white-space: pre-wrap; }}

/* Reduce top padding */
.block-container {{ padding-top: 2rem; }}

</style>
""",
        unsafe_allow_html=True,
    )
