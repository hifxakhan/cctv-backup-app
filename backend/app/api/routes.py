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
    try:
        stats = db.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({
            "total_files": 0,
            "total_size_gb": 0.0,
            "last_upload": None
        }), 200


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
    from ..deps import get_or_create_current_user
    user = get_or_create_current_user()
    saved = db.get_camera_config(user["id"])
    if saved:
        return jsonify(saved)
    # sensible defaults for a brand-new user
    return jsonify({
        "protocol_type": "onvif", "storage_destination": "both",
        "onvif_host": "", "onvif_port": 80, "onvif_user": "",
        "onvif_password": "", "onvif_days_back": 3,
        "drive_folder": "CCTV_Backup", "sync_interval": 60,
    })


@api_bp.route("/config", methods=["POST"])
def save_config():
    from ..deps import get_or_create_current_user
    user = get_or_create_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        db.save_camera_config(user["id"], payload)
        return jsonify({"status": "saved", "message": "Configuration saved"})
    except Exception as exc:
        logger.exception("Unable to save configuration")
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_bp.route("/folder/browse", methods=["GET"])
def browse_folder():
    """Browse directories on the server (Render's file system)."""
    try:
        # Get the current path from query param, default to /tmp
        current_path = request.args.get('path', '/tmp')
        
        # Security: prevent browsing outside allowed directories
        allowed_prefixes = ['/tmp', '/app', '/opt/render', '/home']
        if not any(current_path.startswith(p) for p in allowed_prefixes):
            current_path = '/tmp'
        
        # List directories
        items = []
        try:
            for item in os.listdir(current_path):
                full_path = os.path.join(current_path, item)
                if os.path.isdir(full_path) and not item.startswith('.'):
                    items.append({
                        'name': item,
                        'path': full_path,
                        'type': 'directory'
                    })
        except PermissionError:
            pass
        
        # Sort directories
        items.sort(key=lambda x: x['name'].lower())
        
        return jsonify({
            'status': 'success',
            'current_path': current_path,
            'directories': items
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_bp.route("/agent/config", methods=["GET"])
def get_agent_config():
    """Agent calls this with its Bearer token to fetch this user's camera settings."""
    from ..deps import get_or_create_current_user
    user = get_or_create_current_user()
    config = db.get_camera_config(user["id"])
    if not config:
        return jsonify({"status": "error", "message": "No camera configured yet"}), 404
    return jsonify({"status": "success", "config": config})


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