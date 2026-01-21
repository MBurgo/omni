import time

import streamlit as st

from engines.sheets_briefs import convert_single_asterisk_to_bold, parse_step2_report
from storage.store import save_artifact
from ui.branding import apply_branding
from ui.layout import hub_nav
from ui.seed import set_copywriter_seed

st.set_page_config(
    page_title="Market signals",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_branding()

pid = hub_nav()

# Fixed defaults (no user input on this page)
DEFAULT_QUERY = "ASX 200"
DEFAULT_TRENDS_TOPIC_ID = "/m/0bl5c2"

# Backwards compatibility: if older sessions have values set, force them back to defaults.
st.session_state["signals_query"] = DEFAULT_QUERY
st.session_state["signals_trends_q"] = DEFAULT_TRENDS_TOPIC_ID

query = DEFAULT_QUERY
trends_q = DEFAULT_TRENDS_TOPIC_ID

# --- Hero (matches screenshot copy) ---
st.markdown(
    "<div class='page-title'>Find out what’s making news in the financial markets</div>",
    unsafe_allow_html=True,
)

# Fixed config (kept visible without relying on the sidebar)
with st.expander("Run configuration", expanded=False):
    st.caption("This page runs a fixed scrape + summary pipeline.")
    st.write("**Query:** ASX 200")
    st.write("**Trends topic:** /m/0bl5c2")
    st.caption("Click **Start Run** to scrape and generate a fresh briefing.")
st.markdown(
    "<div class='page-subtitle'>This tool pulls live data from Google News and Google Trends to see what is making news in the financial markets right now.</div>",
    unsafe_allow_html=True,
)

# CTA button (gold)
run = st.button("Start Run", type="primary")

# Session cache (markdown-friendly report)
st.session_state.setdefault("step2_brief_md", None)

if run:
    with st.status("Running pipeline…", expanded=True) as status:
        try:
            # -----------------------------------------------------------------
            # Step 1: scrape + write raw data into the Google Sheet
            # -----------------------------------------------------------------
            st.write("Step 1/2 — Scraping and writing raw data to Google Sheets…")
            import data_retrieval_storage_news_engine as step1

            step1.main()

            # Give Google Sheets a moment to settle (helps avoid edge-case staleness)
            time.sleep(1.5)

            # -----------------------------------------------------------------
            # Step 2: read from the sheet + generate the briefing + append to Summaries
            # -----------------------------------------------------------------
            st.write("Step 2/2 — Generating briefing (5 detailed briefs)…")
            import step2_summarisation_with_easier_reading as step2

            raw = step2.generate_summary()
            if not raw or not str(raw).strip():
                raise RuntimeError("Step2 returned an empty summary.")

            md = convert_single_asterisk_to_bold(str(raw))

            # Save into Library
            title = f"Daily spikes: {query.strip()}"
            save_artifact(
                pid,
                type="signals_daily_step2",
                title=title,
                content_json=None,
                content_text=md,
                metadata={
                    "query": query.strip(),
                    "trends_query_or_topic_id": trends_q.strip(),
                    "source": "google_sheets_pipeline",
                    "step1": "data_retrieval_storage_news_engine.main",
                    "step2": "step2_summarisation_with_easier_reading.generate_summary",
                },
            )

            st.session_state.step2_brief_md = md
            status.update(label="Briefing ready", state="complete", expanded=False)

        except Exception as e:
            status.update(label="Failed", state="error", expanded=True)
            st.error(str(e))

md = st.session_state.get("step2_brief_md")
if md:
    st.divider()

    # Parse structured blocks (best-effort).
    summary_text, briefs = parse_step2_report(md)

    if briefs:
        left, right = st.columns([2, 3], gap="large")
        with left:
            st.subheader("Summary of Findings")
            st.markdown(summary_text or md)

        with right:
            st.subheader("5 Detailed Briefs")
            for i, b in enumerate(briefs, 1):
                title = (b.get("title") or f"Brief {i}").strip()
                body = b.get("body") or ""
                with st.expander(f"{i}. {title}"):
                    st.markdown(body)
                    if st.button("Send to Copywriter", key=f"send_copy_{i}"):
                        set_copywriter_seed(
                            mode="generate",
                            hook=title,
                            details=body,
                            source="signals_daily_step2",
                        )
                        st.switch_page("pages/06_Write_campaign_assets.py")
    else:
        # Fallback: display the whole report.
        st.markdown(md)

