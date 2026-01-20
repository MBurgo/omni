# Goal-First AI Marketing Portal (Streamlit)

This is a consolidated, goal-driven portal that wraps your existing tools into a single UX:

- **Signals**: "What's spiking today" (News + Trends -> opportunities)
- **Futurist**: "Emerging themes" (horizon scan)
- **Audience**: ask personas, test headlines, pressure-test creative (Believer vs Skeptic + moderator rewrite)
- **Creative**: generate, revise, and localise campaign copy
- **Wizard**: end-to-end campaign pack

## Run locally

```bash
pip install -r requirements.txt
# Copy secrets template and fill keys
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run Home.py
```

## Required secrets

- `serpapi.api_key` (required for signals + trends)
- `openai.api_key` (required for persona + copy + summaries)
- `google.api_key` (optional; enables Gemini for moderator analysis; OpenAI fallback is built in)

## Persistence

Outputs are stored in a local SQLite DB at `data/portal.db`.
Set `PORTAL_DB_PATH` to override.
