"""Prerequisites:
- Python 3.10+
- ffmpeg installed and on PATH (https://www.gyan.dev/ffmpeg/builds/)
- agent_client_secrets.json (Desktop OAuth client, downloaded from Google Cloud Console)
- agent_config.json (copy agent_config.example.json and fill in your values)
 
Run with: python agent.py
"""
 
import os
import sys
import time
import json
import sqlite3
import logging
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
 
from onvif import ONVIFCamera
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("agent")
 
CONFIG_FILE = "agent_config.json"
TOKEN_FILE = "token.json"
CLIENT_SECRETS_FILE = "agent_client_secrets.json"
STATE_DB = "agent_state.db"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
 
 
def load_config():
    if not os.path.exists(CONFIG_FILE):
        logger.error(
            "%s not found. Copy agent_config.example.json to %s and fill in your values.",
            CONFIG_FILE, CONFIG_FILE,
        )
        sys.exit(1)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)
 
 
def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        logger.error(
            "ffmpeg not found on PATH. Install it from https://www.gyan.dev/ffmpeg/builds/ "
            "and add its 'bin' folder to your system PATH, then restart your terminal."
        )
        sys.exit(1)
 
 
def init_db():
    conn = sqlite3.connect(STATE_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS uploaded (
            recording_token TEXT PRIMARY KEY,
            file_name TEXT,
            uploaded_at TEXT
        )
        """
    )
    conn.commit()
    return conn
 
 
def already_uploaded(conn, recording_token):
    cur = conn.execute(
        "SELECT 1 FROM uploaded WHERE recording_token = ?", (recording_token,)
    )
    return cur.fetchone() is not None
 
 
def mark_uploaded(conn, recording_token, file_name):
    conn.execute(
        "INSERT OR REPLACE INTO uploaded (recording_token, file_name, uploaded_at) VALUES (?, ?, ?)",
        (recording_token, file_name, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
 
 
def get_drive_service():
    """Handles the agent's own Google sign-in (separate from the web app's)."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None
 
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Token refresh failed (%s), re-authenticating...", e)
                creds = None
 
        if not creds:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                logger.error(
                    "%s not found. Download it from Google Cloud Console "
                    "(OAuth client, Desktop app type) and place it here.",
                    CLIENT_SECRETS_FILE,
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            logger.info("Opening browser for Google sign-in...")
            creds = flow.run_local_server(port=0)
 
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
 
    return build("drive", "v3", credentials=creds)
 
 
def get_or_create_drive_folder(drive_service, folder_name):
    query = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{folder_name}' and trashed=false"
    )
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    folder = drive_service.files().create(body=file_metadata, fields="id").execute()
    logger.info("Created Drive folder '%s'", folder_name)
    return folder["id"]
 
 
def connect_camera(config):
    return ONVIFCamera(
        config["onvif_host"],
        config["onvif_port"],
        config["onvif_user"],
        config["onvif_password"],
    )
 
 
def find_recordings(cam, days_back):
    """Uses ONVIF Profile G search to find recordings on the camera's SD card."""
    search_service = cam.create_search_service()
 
    scope = search_service.create_type("SearchScope")
    scope.IncludedRecordings = []
    scope.IncludedSources = []
    scope.RecordingInformationFilter = None
 
    token = search_service.FindRecordings(
        {
            "Scope": scope,
            "MaxMatches": 50,
            "KeepAliveTime": "PT30S",
        }
    )
 
    results = []
    for _ in range(15):
        time.sleep(1)
        response = search_service.GetRecordingSearchResults(
            {
                "SearchToken": token,
                "MinResults": 0,
                "MaxResults": 50,
                "WaitTime": "PT1S",
            }
        )
        if getattr(response, "ResultList", None):
            results.extend(response.ResultList)
        if getattr(response, "State", None) == "COMPLETED":
            break
 
    try:
        search_service.EndSearch({"SearchToken": token})
    except Exception:
        pass
 
    return results
 
 
def get_replay_uri(cam, recording_token):
    replay_service = cam.create_replay_service()
    stream_setup = {
        "Stream": "RTP-Unicast",
        "Transport": {"Protocol": "RTSP"},
    }
    uri_response = replay_service.GetReplayUri(
        {
            "StreamSetup": stream_setup,
            "RecordingToken": recording_token,
        }
    )
    return uri_response.Uri
 
 
def capture_rtsp_to_file(rtsp_url, output_path, duration_seconds, onvif_user, onvif_password):
    """Uses ffmpeg to pull the recorded stream from the camera into a local file."""
    if "@" not in rtsp_url and onvif_user:
        scheme, rest = rtsp_url.split("://", 1)
        rtsp_url = f"{scheme}://{onvif_user}:{onvif_password}@{rest}"
 
    cmd = [
        "ffmpeg", "-y",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-t", str(max(duration_seconds, 5)),
        "-c", "copy",
        output_path,
    ]
    logger.info("Capturing recording via ffmpeg (%ds)...", duration_seconds)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=duration_seconds + 60
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")
 
 
def upload_to_drive(drive_service, folder_id, file_path, file_name):
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    request = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("  Upload progress: %d%%", int(status.progress() * 100))
    return response.get("id")
 
 
def report_to_backend(config, uploaded_files):
    """Optional: tells your Render backend what was just uploaded, for the dashboard."""
    url = config.get("backend_report_url")
    agent_token = config.get("agent_token")
    if not url or not agent_token:
        return
    try:
        import requests
        requests.post(
            url,
            json={"files": uploaded_files},
            headers={"Authorization": f"Bearer {agent_token}"},
            timeout=10,
        )
    except Exception as e:
        logger.warning("Could not report to backend (non-fatal): %s", e)
 
 
def run_sync(config, drive_service, folder_id, db_conn):
    logger.info("=== Starting sync cycle ===")
 
    try:
        cam = connect_camera(config)
    except Exception as e:
        logger.error("Could not connect to camera: %s", e)
        return
 
    try:
        recordings = find_recordings(cam, config.get("days_back", 3))
    except Exception as e:
        logger.error(
            "Recording search failed (camera may not support ONVIF Profile G "
            "recording search): %s", e,
        )
        return
 
    logger.info("Found %d recording(s) reported by camera", len(recordings))
    uploaded_files = []
 
    for rec in recordings:
        recording_token = getattr(rec, "RecordingToken", None)
        if not recording_token or already_uploaded(db_conn, recording_token):
            continue
 
        try:
            rtsp_uri = get_replay_uri(cam, recording_token)
 
            tracks = getattr(rec, "Track", None) or []
            if tracks and getattr(tracks[0], "DataFrom", None) and getattr(tracks[0], "DataTo", None):
                start = tracks[0].DataFrom
                end = tracks[0].DataTo
                duration = max(int((end - start).total_seconds()), 5)
            else:
                start = datetime.now(timezone.utc)
                duration = 60  # fallback duration if camera doesn't report track times
 
            file_name = f"recording_{recording_token}_{start.strftime('%Y%m%d_%H%M%S')}.mp4"
 
            with tempfile.TemporaryDirectory() as tmp:
                local_path = os.path.join(tmp, file_name)
                capture_rtsp_to_file(
                    rtsp_uri, local_path, duration,
                    config["onvif_user"], config["onvif_password"],
                )
                upload_to_drive(drive_service, folder_id, local_path, file_name)
 
            mark_uploaded(db_conn, recording_token, file_name)
            uploaded_files.append(file_name)
            logger.info("Uploaded: %s", file_name)
 
        except Exception as e:
            logger.error("Failed to process recording %s: %s", recording_token, e)
 
    if uploaded_files:
        report_to_backend(config, uploaded_files)
 
    logger.info("=== Sync cycle complete: %d file(s) uploaded ===", len(uploaded_files))
 
 
def main():
    check_ffmpeg()
    config = load_config()
    db_conn = init_db()
 
    logger.info("Signing in to Google Drive...")
    drive_service = get_drive_service()
    folder_id = get_or_create_drive_folder(drive_service, config.get("drive_folder", "CCTV_Backup"))
    logger.info("Ready. Uploading to Drive folder '%s'", config.get("drive_folder", "CCTV_Backup"))
 
    interval_seconds = config.get("sync_interval_minutes", 60) * 60
 
    while True:
        try:
            run_sync(config, drive_service, folder_id, db_conn)
        except Exception as e:
            logger.error("Unexpected error during sync cycle: %s", e)
 
        logger.info("Sleeping for %d minute(s)...", interval_seconds // 60)
        time.sleep(interval_seconds)
 
 
if __name__ == "__main__":
    main()
 