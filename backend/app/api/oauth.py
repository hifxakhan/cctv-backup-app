"""
Legacy OAuth module - kept for backward compatibility.
All OAuth logic has moved to auth.py for multi-user support.
"""
import logging

logger = logging.getLogger(__name__)

# OAuth scopes
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_oauth_flow(redirect_uri: str):
    """
    Legacy function. Use auth.py's _get_flow_from_secrets instead.
    """
    from google_auth_oauthlib.flow import Flow
    import os

    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return None

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow