"""
Multi-User Google OAuth 2.0 routes.
Each user gets a signed cookie identifying them, and their Drive credentials
are stored encrypted in the database keyed to that user ID.
"""
import os
import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, redirect, session, g

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from ..config import Config
from ..database.db_manager import DatabaseManager
from ..deps import get_or_create_current_user, set_user_cookie, get_user_id

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

# OAuth Configuration
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REDIRECT_URI = "http://localhost:5000/api/drive/auth/callback"
FRONTEND_ORIGIN = "http://localhost:3000"


def _find_client_secrets():
    """Locate client_secrets.json in the backend directory."""
    search_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", CLIENT_SECRETS_FILE),
        os.path.join(os.getcwd(), CLIENT_SECRETS_FILE),
        CLIENT_SECRETS_FILE,
    ]
    for path in search_paths:
        resolved = os.path.abspath(path)
        if os.path.exists(resolved):
            return resolved
    return None


def _get_flow_from_secrets(state=None):
    """Create a Flow from the client_secrets.json file."""
    secrets_path = _find_client_secrets()
    if not secrets_path:
        logger.error("client_secrets.json not found")
        return None

    try:
        if state:
            flow = Flow.from_client_secrets_file(
                secrets_path, scopes=SCOPES, state=state, redirect_uri=REDIRECT_URI
            )
        else:
            flow = Flow.from_client_secrets_file(
                secrets_path, scopes=SCOPES, redirect_uri=REDIRECT_URI
            )
        return flow
    except Exception as e:
        logger.error("Failed to create OAuth flow: %s", e)
        return None


@auth_bp.route("/drive/auth")
def drive_auth():
    """Start OAuth flow — user clicks this to connect Google Drive.
    This sets a signed cookie to identify the user BEFORE redirecting to Google."""
    try:
        # Ensure user has an identity cookie before OAuth flow
        user = get_or_create_current_user()
        user_id = user["id"]

        secrets_path = _find_client_secrets()
        if not secrets_path:
            return jsonify({"error": "client_secrets.json not found. Please place it in the backend/ folder."}), 500

        flow = _get_flow_from_secrets()
        if not flow:
            return jsonify({"error": "Failed to create OAuth flow. Check client_secrets.json format."}), 500

        # Generate authorization URL
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account",
        )

        # Store state in Flask session (maps back to user when callback arrives)
        session["oauth_state"] = state
        session["oauth_user_id"] = user_id
        session.permanent = True

        logger.info("User %s redirecting to Google OAuth", user_id)

        # Redirect to Google — but also set the user cookie on the redirect response
        response = redirect(auth_url)
        set_user_cookie(response, user_id)
        return response

    except Exception as e:
        logger.error("OAuth auth error: %s", e)
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/drive/auth/callback")
def oauth2callback():
    """Google sends the user back here after login.
    The user_id is recovered from the Flask session (stored when /drive/auth was called)."""
    try:
        state = session.get("oauth_state")
        user_id = session.get("oauth_user_id")

        if not state:
            return _error_page("No OAuth state found. Please try connecting again.")
        if not user_id:
            return _error_page("No user session found. Please try connecting again.")

        flow = _get_flow_from_secrets(state=state)
        if not flow:
            return _error_page("Failed to create OAuth flow.")

        # Exchange authorization code for credentials
        flow.fetch_token(authorization_response=request.url)

        credentials = flow.credentials
        access_token = credentials.token
        refresh_token = credentials.refresh_token
        token_expiry = credentials.expiry.isoformat() if credentials.expiry else None
        scopes_str = " ".join(credentials.scopes) if credentials.scopes else " ".join(SCOPES)

        # Get user info from Google
        drive_service = build("drive", "v3", credentials=credentials)
        about = drive_service.about().get(fields="user").execute()
        user_info = about.get("user", {})
        google_email = user_info.get("emailAddress", "unknown@unknown.com")

        # Save credentials to database (encrypted)
        db = DatabaseManager()
        db.save_google_credentials(
            user_id=user_id,
            google_email=google_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            scopes=scopes_str,
        )

        logger.info("User %s (%s) authenticated with Google Drive", user_id, google_email)

        # Return success page that closes the popup
        return _success_page(google_email)

    except Exception as e:
        logger.error("OAuth callback error: %s", e)
        return _error_page(str(e))


@auth_bp.route("/drive/status")
def drive_status():
    """Check if current user is authenticated with Google Drive.
    Uses the signed cookie to identify the user (not Flask session)."""
    try:
        user = get_or_create_current_user()
        user_id = user["id"]

        db = DatabaseManager()
        creds = db.get_google_credentials(user_id)

        if creds and creds.get("access_token"):
            return jsonify({
                "authenticated": True,
                "user": {
                    "email": creds["google_email"],
                },
                "auth_mode": "oauth",
            })

        return jsonify({
            "authenticated": False,
            "user": None,
            "auth_mode": None,
        })
    except Exception as e:
        logger.error("Drive status error: %s", e)
        return jsonify({
            "authenticated": False,
            "user": None,
            "auth_mode": None,
        })


@auth_bp.route("/drive/disconnect", methods=["POST"])
def drive_disconnect():
    """Disconnect the current user's Google Drive."""
    try:
        user = get_or_create_current_user()
        user_id = user["id"]

        db = DatabaseManager()
        db.delete_google_credentials(user_id)

        logger.info("User %s disconnected from Google Drive", user_id)
        return jsonify({"status": "disconnected"})
    except Exception as e:
        logger.error("Drive disconnect error: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


def get_user_drive_service(user_id=None):
    """Get an authenticated Drive service for a user from DB-stored credentials."""
    from ..deps import get_user_id
    uid = user_id or get_user_id()
    if not uid:
        return None

    db = DatabaseManager()
    creds = db.get_google_credentials(uid)
    if not creds or not creds.get("access_token"):
        return None

    credentials = Credentials(
        token=creds["access_token"],
        refresh_token=creds.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
        client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
        scopes=creds.get("scopes", SCOPES),
    )
    return build("drive", "v3", credentials=credentials)


def _success_page(user_email):
    """HTML page shown after successful OAuth — sends postMessage to parent."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Google Drive Connected!</title>
    <style>
        body {{ display: flex; justify-content: center; align-items: center; height: 100vh;
               font-family: Arial, sans-serif; background: #f0f4f8; margin: 0; }}
        .container {{ text-align: center; padding: 40px; background: white; border-radius: 12px;
                     box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .success {{ color: #4CAF50; font-size: 48px; }}
    </style></head>
    <body>
        <div class="container">
            <div class="success">✅</div>
            <h2>Google Drive Connected!</h2>
            <p>You are connected with:<br><strong>{user_email}</strong></p>
            <p>This window will close automatically.</p>
            <button class="close-btn" onclick="closeWindow()"
                    style="background:#4CAF50;color:white;border:none;padding:10px 30px;
                           border-radius:5px;cursor:pointer;font-size:16px;margin-top:20px;">
                Close Window
            </button>
        </div>
        <script>
            function closeWindow() {{
                if (window.opener) {{
                    window.opener.postMessage('drive_connected', '{FRONTEND_ORIGIN}');
                }}
                window.close();
            }}
            setTimeout(closeWindow, 3000);
        </script>
    </body>
    </html>
    """


def _error_page(message):
    """HTML page shown after failed OAuth."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Connection Failed</title>
    <style>
        body {{ display: flex; justify-content: center; align-items: center; height: 100vh;
               font-family: Arial, sans-serif; background: #fff0f0; margin: 0; }}
        .container {{ text-align: center; padding: 40px; background: white; border-radius: 12px; }}
        .error {{ color: #f44336; font-size: 48px; }}
    </style></head>
    <body>
        <div class="container">
            <div class="error">❌</div>
            <h2>Connection Failed</h2>
            <p>{message}</p>
            <p>Please close this window and try again.</p>
            <button onclick="window.close()"
                    style="background:#f44336;color:white;border:none;padding:10px 30px;
                           border-radius:5px;cursor:pointer;font-size:16px;margin-top:20px;">
                Close Window
            </button>
        </div>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{type: 'oauth-error', message: '{message}'}}, '{FRONTEND_ORIGIN}');
            }}
        </script>
    </body>
    </html>
    """