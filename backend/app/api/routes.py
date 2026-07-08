import json
import os
from flask import Blueprint, jsonify, request

from ..camera.onvif_client import ONVIFCamera, ONVIFClientError
from ..database.db_manager import DatabaseManager
from ..scheduler.job import SyncJob
from ..utils.logger import get_logger, read_logs

api_bp = Blueprint("api", __name__)
logger = get_logger(__name__)
db = DatabaseManager()


def _update_env_file(key: str, value: str) -> None:
    """Update or add a key=value line in the .env file."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
        found = False
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f'{key}='):
                new_lines.append(f'{key}={value}\n')
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f'{key}={value}\n')
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
    except OSError as exc:
        logger.warning("Unable to update .env file: %s", exc)


@api_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "message": "Backend is running!"})


@api_bp.route("/stats", methods=["GET"])
def get_stats():
    stats = db.get_stats()
    return jsonify(stats)


@api_bp.route("/sync/start", methods=["POST"])
def start_sync():
    try:
        job = SyncJob(db_manager=db)
        job.start_in_background()
        return jsonify({"status": "started", "message": "Sync job started in background"})
    except Exception as exc:
        logger.exception("Failed to start sync")
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/protocol", methods=["GET"])
def get_protocol():
    from ..config import Config
    return jsonify({"protocol_type": Config.PROTOCOL_TYPE})


@api_bp.route("/protocol", methods=["POST"])
def save_protocol():
    payload = request.get_json(silent=True) or {}
    protocol_type = str(payload.get("protocol_type", "onvif")).strip().lower()
    if protocol_type not in {"onvif", "ftp"}:
        return jsonify({"status": "error", "message": "protocol_type must be either onvif or ftp"}), 400

    from ..config import Config
    Config.PROTOCOL_TYPE = protocol_type
    return jsonify({"status": "saved", "protocol_type": Config.PROTOCOL_TYPE})


@api_bp.route("/config", methods=["GET"])
def get_config():
    from ..config import Config
    return jsonify({
        "protocol_type": Config.PROTOCOL_TYPE,
        "storage_destination": Config.STORAGE_DESTINATION,
        "local_storage_path": Config.LOCAL_STORAGE_PATH,
        "ftp_host": Config.FTP_HOST,
        "ftp_port": Config.FTP_PORT,
        "ftp_path": Config.FTP_PATH,
        "drive_folder": Config.DRIVE_BACKUP_FOLDER,
        "sync_interval": Config.SYNC_INTERVAL_MINUTES,
        "onvif_enabled": str(Config.ONVIF_ENABLED).lower(),
        "onvif_host": Config.ONVIF_HOST,
        "onvif_port": Config.ONVIF_PORT,
        "onvif_user": Config.ONVIF_USER,
        "onvif_password": Config.ONVIF_PASSWORD,
        "onvif_days_back": Config.ONVIF_DAYS_BACK,
    })


@api_bp.route("/config", methods=["POST"])
def save_config():
    payload = request.get_json(silent=True) or {}
    protocol_type = str(payload.get("protocol_type", "onvif")).strip().lower()
    if protocol_type not in {"onvif", "ftp"}:
        return jsonify({"status": "error", "message": "protocol_type must be either onvif or ftp"}), 400

    from ..config import Config
    try:
        Config.PROTOCOL_TYPE = protocol_type
        Config.STORAGE_DESTINATION = str(payload.get("storage_destination", Config.STORAGE_DESTINATION)).strip().lower()
        if Config.STORAGE_DESTINATION not in {"local", "google_drive", "both"}:
            Config.STORAGE_DESTINATION = "both"
        Config.LOCAL_STORAGE_PATH = payload.get("local_storage_path", Config.LOCAL_STORAGE_PATH)
        Config.DRIVE_BACKUP_FOLDER = payload.get("drive_folder", Config.DRIVE_BACKUP_FOLDER)
        Config.SYNC_INTERVAL_MINUTES = int(payload.get("sync_interval", Config.SYNC_INTERVAL_MINUTES))

        # Save Google OAuth credentials if provided (from the UI setup dialog)
        google_client_id = payload.get("google_oauth_client_id")
        google_client_secret = payload.get("google_oauth_client_secret")
        if google_client_id and google_client_secret:
            Config.GOOGLE_OAUTH_CLIENT_ID = google_client_id
            Config.GOOGLE_OAUTH_CLIENT_SECRET = google_client_secret
            # Persist to .env file so it survives restarts
            _update_env_file("GOOGLE_OAUTH_CLIENT_ID", google_client_id)
            _update_env_file("GOOGLE_OAUTH_CLIENT_SECRET", google_client_secret)

        if protocol_type == "ftp":
            missing = [field for field in ["ftp_host", "ftp_user", "ftp_password", "ftp_path"] if not str(payload.get(field, "")).strip()]
            if missing:
                return jsonify({"status": "error", "message": f"Missing fields: {missing}"}), 400
            Config.FTP_HOST = payload["ftp_host"]
            Config.FTP_PORT = int(payload.get("ftp_port", Config.FTP_PORT))
            Config.FTP_USER = payload["ftp_user"]
            Config.FTP_PASSWORD = payload["ftp_password"]
            Config.FTP_PATH = payload["ftp_path"]
        else:
            missing = [field for field in ["onvif_host", "onvif_user", "onvif_password"] if not str(payload.get(field, "")).strip()]
            if missing:
                return jsonify({"status": "error", "message": f"Missing fields: {missing}"}), 400
            Config.ONVIF_ENABLED = str(payload.get("onvif_enabled", str(Config.ONVIF_ENABLED).lower())).lower() == "true"
            Config.ONVIF_HOST = payload.get("onvif_host", Config.ONVIF_HOST)
            Config.ONVIF_PORT = int(payload.get("onvif_port", Config.ONVIF_PORT))
            Config.ONVIF_USER = payload.get("onvif_user", Config.ONVIF_USER)
            Config.ONVIF_PASSWORD = payload.get("onvif_password", Config.ONVIF_PASSWORD)
            Config.ONVIF_DAYS_BACK = int(payload.get("onvif_days_back", Config.ONVIF_DAYS_BACK))

        return jsonify({"status": "saved", "message": "Configuration saved", "protocol_type": Config.PROTOCOL_TYPE})
    except Exception as exc:
        logger.exception("Unable to save configuration")
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/uploads", methods=["GET"])
def get_uploads():
    limit = int(request.args.get("limit", 20))
    offset = int(request.args.get("offset", 0))
    return jsonify(db.get_upload_history(limit=limit, offset=offset))


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    limit = int(request.args.get("limit", 200))
    return jsonify({"logs": read_logs(limit=limit)})


@api_bp.route("/cameras", methods=["GET"])
def get_cameras():
    return jsonify({"cameras": [{"id": 1, "name": "Front Door", "status": "online"}]})


@api_bp.route("/onvif/recordings", methods=["GET"])
def get_onvif_recordings():
    try:
        from ..config import Config

        client = ONVIFCamera(
            host=Config.ONVIF_HOST,
            port=Config.ONVIF_PORT,
            username=Config.ONVIF_USER,
            password=Config.ONVIF_PASSWORD,
            days_back=int(request.args.get("days_back", Config.ONVIF_DAYS_BACK)),
        )
        recordings = client.get_recordings(days_back=client.days_back)
        return jsonify({"status": "success", "recordings": recordings})
    except ONVIFClientError as exc:
        logger.warning("Unable to list ONVIF recordings: %s", exc)
        return jsonify({"status": "error", "message": str(exc), "recordings": []})
    except Exception as exc:
        logger.exception("Unexpected error while listing ONVIF recordings")
        return jsonify({"status": "error", "message": str(exc), "recordings": []})


@api_bp.route("/onvif/sd-info", methods=["GET"])
def get_onvif_sd_info():
    try:
        from ..config import Config

        client = ONVIFCamera(
            host=Config.ONVIF_HOST,
            port=Config.ONVIF_PORT,
            username=Config.ONVIF_USER,
            password=Config.ONVIF_PASSWORD,
        )
        return jsonify({"status": "success", "sd_info": client.get_sd_card_info()})
    except ONVIFClientError as exc:
        logger.warning("Unable to fetch ONVIF SD info: %s", exc)
        return jsonify({"status": "error", "message": str(exc), "sd_info": {"status": "unavailable"}})
    except Exception as exc:
        logger.exception("Unexpected error while fetching ONVIF SD info")
        return jsonify({"status": "error", "message": str(exc), "sd_info": {"status": "unavailable"}})


@api_bp.route("/onvif/sync", methods=["POST"])
def start_onvif_sync():
    try:
        job = SyncJob(db_manager=db)
        result = job.sync_onvif(progress_callback=lambda payload: logger.info("ONVIF sync progress: %s", payload))
        return jsonify({"status": "success", "result": result})
    except ONVIFClientError as exc:
        logger.warning("Unable to start ONVIF sync: %s", exc)
        return jsonify({"status": "error", "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error while starting ONVIF sync")
        return jsonify({"status": "error", "message": str(exc)})


@api_bp.route("/onvif/delete", methods=["POST"])
def delete_onvif_recording():
    payload = request.get_json(silent=True) or {}
    recording_token = payload.get("recording_token")
    if not recording_token:
        return jsonify({"status": "error", "message": "recording_token is required"}), 400

    try:
        from ..config import Config

        client = ONVIFCamera(
            host=Config.ONVIF_HOST,
            port=Config.ONVIF_PORT,
            username=Config.ONVIF_USER,
            password=Config.ONVIF_PASSWORD,
        )
        deleted = client.delete_recording(recording_token)
        return jsonify({"status": "success", "deleted": deleted})
    except ONVIFClientError as exc:
        logger.warning("Unable to delete ONVIF recording: %s", exc)
        return jsonify({"status": "error", "message": str(exc)})
    except Exception as exc:
        logger.exception("Unexpected error while deleting ONVIF recording")
        return jsonify({"status": "error", "message": str(exc)})


@api_bp.route("/folder/browse", methods=["GET"])
def browse_folder():
    """Open a native folder dialog on the server (local machine) to select a directory."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.update()

        folder_path = filedialog.askdirectory(
            title="Select Upload Folder",
            initialdir="D:\\" if os.name == 'nt' else "/"
        )

        root.destroy()

        if folder_path:
            return jsonify({"status": "success", "path": folder_path})
        else:
            return jsonify({"status": "cancelled", "message": "No folder selected"})
    except Exception as exc:
        logger.exception("Unable to open folder dialog")
        return jsonify({"status": "error", "message": str(exc)}), 500


