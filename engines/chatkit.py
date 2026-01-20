"""Hosted ChatKit helpers.

This module supports using OpenAI-hosted Agent Builder workflows (workflow IDs
starting with "wf_") inside Streamlit by:

1) Creating a ChatKit session server-side (using your OpenAI API key)
2) Returning a client_secret that can be used by the embedded `openai-chatkit`
   web component.

The resulting experience is a "portal" UI that can still leverage your
Agent Builder workflow via ChatKit.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from utils import get_secret


CHATKIT_SESSIONS_URL = "https://api.openai.com/v1/chatkit/sessions"


@dataclass
class ChatKitSession:
    client_secret: str
    expires_at: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None


def _openai_api_key() -> Optional[str]:
    # Prefer Streamlit secrets, then env.
    return get_secret("openai.api_key") or get_secret("OPENAI_API_KEY")


def create_chatkit_session(
    *,
    workflow_id: str,
    user_id: Optional[str] = None,
    workflow_version: Optional[str] = None,
    chatkit_configuration: Optional[Dict[str, Any]] = None,
    timeout_s: float = 60.0,
) -> Dict[str, Any]:
    """Create a ChatKit session for an Agent Builder workflow.

    Returns a dict with either:
      {"client_secret": "...", "expires_at": 123, "raw": {...}}
    or:
      {"error": "...", "details": {...}}
    """

    api_key = _openai_api_key()
    if not api_key:
        return {
            "error": "OpenAI API key not configured. Add openai.api_key to Streamlit secrets or set OPENAI_API_KEY.",
        }

    if not (workflow_id or "").strip().startswith("wf_"):
        return {
            "error": "ChatKit workflow_id is missing or invalid (expected to start with 'wf_').",
            "details": {"workflow_id": workflow_id},
        }

    if not user_id:
        user_id = f"streamlit-{uuid.uuid4().hex[:16]}"

    payload: Dict[str, Any] = {
        "workflow": {"id": workflow_id.strip()},
        "user": user_id,
    }

    if workflow_version:
        payload["workflow"]["version"] = str(workflow_version)

    if chatkit_configuration:
        payload["chatkit_configuration"] = chatkit_configuration

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # ChatKit is in beta and requires this header.
        "OpenAI-Beta": "chatkit_beta=v1",
    }

    try:
        with httpx.Client(timeout=timeout_s) as client:
            r = client.post(CHATKIT_SESSIONS_URL, headers=headers, json=payload)
    except Exception as e:
        return {"error": f"Failed to reach OpenAI ChatKit sessions endpoint: {e}"}

    if r.status_code >= 400:
        # Try to include JSON error details if present.
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        return {
            "error": f"ChatKit session creation failed (HTTP {r.status_code}).",
            "details": body,
        }

    try:
        data = r.json()
    except Exception:
        return {"error": "ChatKit session response was not valid JSON.", "details": {"raw": r.text}}

    client_secret = (data or {}).get("client_secret")
    if not client_secret:
        return {"error": "ChatKit session response missing client_secret.", "details": data}

    return {
        "client_secret": client_secret,
        "expires_at": (data or {}).get("expires_at"),
        "raw": data,
    }


def build_chatkit_embed_html(
    *,
    client_secret: str,
    height_px: int = 720,
    element_id: str = "chatkit-container",
    auto_send_text: Optional[str] = None,
    accent_color: Optional[str] = None,
) -> str:
    """Return HTML that embeds the ChatKit web component.

    Important: This returns HTML only. Use `st.components.v1.html(...)` to
    render it.
    """

    # Escape/encode safely for JS.
    client_secret_js = json.dumps(client_secret)
    auto_text_js = json.dumps(auto_send_text) if auto_send_text else "null"

    # If an accent color is provided, we add a tiny CSS variable override.
    # ChatKit supports theming in richer ways, but this keeps it simple.
    accent_css = ""
    if accent_color and str(accent_color).strip():
        accent_css = f"""
<style>
  /* Best-effort override; ChatKit may ignore this depending on its theme config */
  :root {{ --chatkit-accent: {str(accent_color).strip()}; }}
</style>
""".strip()

    # Use the official ChatKit CDN script.
    # We use the web component API documented in chatkit-js.
    return f"""
{accent_css}
<script src="https://cdn.platform.openai.com/deployments/chatkit/chatkit.js" async></script>

<openai-chatkit id="{element_id}" style="height:{height_px}px; width: 100%;"></openai-chatkit>

<script type="module">
  const clientSecret = {client_secret_js};
  const autoSendText = {auto_text_js};

  async function init() {{
    // Wait for the custom element definition.
    try {{
      await customElements.whenDefined('openai-chatkit');
    }} catch (e) {{
      console.error('ChatKit custom element not available', e);
      return;
    }}

    const chatkit = document.getElementById({json.dumps(element_id)});
    if (!chatkit) return;

    // Provide the client secret directly.
    chatkit.setOptions({{
      api: {{
        async getClientSecret(current) {{
          // If ChatKit requests a refresh and we still have a secret, reuse it.
          // If it fails due to expiry, refresh the Streamlit page to generate a new session.
          return current || clientSecret;
        }}
      }}
    }});

    // Optionally auto-send a first message once the frame is ready.
    if (autoSendText) {{
      const sendOnce = async () => {{
        try {{
          await chatkit.sendUserMessage({{ text: autoSendText, newThread: true }});
        }} catch (e) {{
          console.error('Auto-send failed', e);
        }}
      }};

      // If already ready, send immediately; otherwise wait.
      let sent = false;
      const handler = async () => {{
        if (sent) return;
        sent = true;
        chatkit.removeEventListener('chatkit.ready', handler);
        await sendOnce();
      }};
      chatkit.addEventListener('chatkit.ready', handler);
      // Also attempt shortly after init in case the ready event fired before we attached.
      setTimeout(() => handler(), 600);
    }}
  }}

  init();
</script>
""".strip()
