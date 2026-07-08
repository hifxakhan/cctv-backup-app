import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from ..camera.ftp_client import FTPClient, FTPClientError
from ..camera.onvif_client import ONVIFCamera, ONVIFClientError
from ..database.db_manager import DatabaseManager
from ..uploader.drive_uploader import GoogleDriveUploader, DriveUploadError
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SyncJob:
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        ftp_client: Optional[FTPClient] = None,
        drive_uploader: Optional[GoogleDriveUploader] = None,
        user_id: Optional[str] = None,
    ):
        self.db = db_manager or DatabaseManager()
        self.ftp_client = ftp_client or FTPClient(
            host=os.getenv("FTP_HOST", ""),
            port=int(os.getenv("FTP_PORT", 21)),
            username=os.getenv("FTP_USER", ""),
            password=os.getenv("FTP_PASSWORD", ""),
        )
        # Accept optional user_id for per-user Drive uploads
        self.user_id = user_id
        if drive_uploader:
            self.drive_uploader = drive_uploader
        elif user_id:
            # Create uploader scoped to this user (reads credentials from DB via session)
            self.drive_uploader = GoogleDriveUploader(
                folder_name=os.getenv("DRIVE_BACKUP_FOLDER", "CCTV_Backup"),
            )
        else:
            # Legacy fallback for server-wide sync (no user context)
            self.drive_uploader = GoogleDriveUploader(
                folder_name=os.getenv("DRIVE_BACKUP_FOLDER", "CCTV_Backup"),
            )
        self.onvif_client = ONVIFCamera(
            host=os.getenv("ONVIF_HOST", ""),
            port=int(os.getenv("ONVIF_PORT", 80)),
            username=os.getenv("ONVIF_USER", ""),
            password=os.getenv("ONVIF_PASSWORD", ""),
            days_back=int(os.getenv("ONVIF_DAYS_BACK", 3)),
        )
        self.storage_destination = (os.getenv("STORAGE_DESTINATION", "both") or "both").strip().lower()
        self.local_storage_path = os.getenv("LOCAL_STORAGE_PATH", r"D:\CCTV_Recordings")

    def _copy_to_local(self, source_path: str, file_name: str) -> Optional[str]:
        """Copy a downloaded file to the local storage directory. Returns the destination path."""
        if self.storage_destination not in ("local", "both"):
            return None
        dest_dir = Path(self.local_storage_path)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file_name
        try:
            shutil.copy2(source_path, str(dest_path))
            logger.info("Copied %s to local storage: %s", file_name, dest_path)
            return str(dest_path)
        except OSError as exc:
            logger.warning("Failed to copy %s to local storage: %s", file_name, exc)
            return None

    def sync_once(self, progress_callback: Optional[Callable[[dict[str, Any]], None]] = None) -> dict[str, Any]:
        logger.info("Starting sync job")
        self._emit(progress_callback, {"status": "running", "message": "Connecting to FTP server"})

        try:
            if not self.ftp_client.is_configured():
                raise FTPClientError("FTP configuration is incomplete")

            try:
                remote_files = self.ftp_client.list_files(remote_path=os.getenv("FTP_PATH", "/"), extensions=(".mp4", ".jpg", ".jpeg", ".png", ".avi", ".mkv"))
            except Exception as exc:
                logger.warning("FTP sync skipped because the camera is unavailable: %s", exc)
                self._emit(progress_callback, {"status": "completed", "message": "FTP camera unavailable", "files": 0})
                return {"status": "completed", "files": 0}
            pending_files = []
            for remote_file in remote_files:
                if self.db.file_exists(remote_file["path"], remote_file["name"]):
                    continue
                pending_files.append(remote_file)

            if not pending_files:
                logger.info("No new files found to upload")
                self._emit(progress_callback, {"status": "completed", "message": "No new files found", "files": 0})
                return {"status": "completed", "files": 0}

            logger.info("Found %s files to upload", len(pending_files))
            uploaded_count = 0

            for remote_file in pending_files:
                self._emit(progress_callback, {"status": "processing", "message": f"Downloading {remote_file['name']}", "file": remote_file["name"]})
                temp_dir = Path(tempfile.gettempdir()) / "cctv_backup"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_path = temp_dir / remote_file["name"]

                try:
                    download_result = self.ftp_client.download_file(remote_file["path"], str(temp_path), expected_size=remote_file.get("size"), callback=lambda chunk: self._emit(progress_callback, {"status": "downloading", "message": "Downloading", "file": remote_file["name"]}))

                    drive_file_id = None
                    drive_link = None

                    # Upload to Google Drive if destination includes it
                    if self.storage_destination in ("google_drive", "both"):
                        try:
                            folder_id = self.drive_uploader.ensure_folder(self.drive_uploader.folder_name)
                            self._emit(progress_callback, {"status": "uploading", "message": f"Uploading {remote_file['name']} to Google Drive", "file": remote_file["name"]})
                            upload_result = self.drive_uploader.upload_file(download_result["path"], file_name=remote_file["name"], parent_folder_id=folder_id, progress_callback=lambda value: self._emit(progress_callback, {"status": "uploading", "message": f"Uploading {remote_file['name']} to Google Drive", "file": remote_file["name"], "progress": value}))
                            drive_file_id = upload_result.get("id")
                            drive_link = upload_result.get("link")
                        except DriveUploadError as exc:
                            logger.warning("Google Drive upload failed for %s: %s", remote_file["name"], exc)
                            self._emit(progress_callback, {"status": "error", "message": f"Drive upload failed: {exc}", "file": remote_file["name"]})

                    # Copy to local storage if destination includes it
                    if self.storage_destination in ("local", "both"):
                        self._copy_to_local(download_result["path"], remote_file["name"])

                    self.db.record_upload(
                        file_name=remote_file["name"],
                        file_path=remote_file["path"],
                        file_size=download_result["size"],
                        md5_hash=download_result["md5_hash"],
                        drive_file_id=drive_file_id,
                        drive_link=drive_link,
                    )
                    uploaded_count += 1
                    logger.info("Processed file %s", remote_file["name"])
                except FTPClientError as exc:
                    logger.warning("Skipping file %s due to error: %s", remote_file["name"], exc)
                    self._emit(progress_callback, {"status": "error", "message": str(exc), "file": remote_file["name"]})
                finally:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass

            self._emit(progress_callback, {"status": "completed", "message": "Sync completed", "files": uploaded_count})
            return {"status": "completed", "files": uploaded_count}
        except Exception as exc:
            logger.exception("Sync job failed")
            self._emit(progress_callback, {"status": "failed", "message": str(exc)})
            return {"status": "failed", "message": str(exc)}

    def sync_onvif(self, progress_callback: Optional[Callable[[dict[str, Any]], None]] = None) -> dict[str, Any]:
        logger.info("Starting ONVIF sync job")
        self._emit(progress_callback, {"status": "running", "message": "Connecting to ONVIF camera"})

        try:
            enabled = os.getenv("ONVIF_ENABLED", "true").lower() == "true"
            if not enabled:
                raise ONVIFClientError("ONVIF is disabled in configuration")
            if not self.onvif_client.is_configured():
                raise ONVIFClientError("ONVIF configuration is incomplete")

            try:
                recordings = self.onvif_client.get_recordings(days_back=self.onvif_client.days_back)
            except ONVIFClientError as exc:
                logger.warning("ONVIF sync skipped because the camera is unavailable: %s", exc)
                self._emit(progress_callback, {"status": "completed", "message": "ONVIF camera unavailable", "files": 0})
                return {"status": "completed", "files": 0}
            if not recordings:
                self._emit(progress_callback, {"status": "completed", "message": "No ONVIF recordings found", "files": 0})
                return {"status": "completed", "files": 0}

            uploaded_count = 0

            for recording in recordings:
                token = recording.get("token")
                name = recording.get("name") or f"onvif_recording_{token or uploaded_count}.mp4"
                self._emit(progress_callback, {"status": "processing", "message": f"Downloading {name}", "file": name})
                temp_dir = Path(tempfile.gettempdir()) / "cctv_backup_onvif"
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_path = temp_dir / name

                try:
                    downloaded_path = self.onvif_client.download_recording(token, str(temp_path))

                    drive_file_id = None
                    drive_link = None

                    # Upload to Google Drive if destination includes it
                    if self.storage_destination in ("google_drive", "both"):
                        try:
                            folder_id = self.drive_uploader.ensure_folder(self.drive_uploader.folder_name)
                            self._emit(progress_callback, {"status": "uploading", "message": f"Uploading {name} to Google Drive", "file": name})
                            upload_result = self.drive_uploader.upload_file(downloaded_path, file_name=name, parent_folder_id=folder_id, progress_callback=lambda value: self._emit(progress_callback, {"status": "uploading", "message": f"Uploading {name} to Google Drive", "file": name, "progress": value}))
                            drive_file_id = upload_result.get("id")
                            drive_link = upload_result.get("link")
                        except DriveUploadError as exc:
                            logger.warning("Google Drive upload failed for %s: %s", name, exc)
                            self._emit(progress_callback, {"status": "error", "message": f"Drive upload failed: {exc}", "file": name})

                    # Copy to local storage if destination includes it
                    if self.storage_destination in ("local", "both"):
                        self._copy_to_local(downloaded_path, name)

                    self.db.record_upload(file_name=name, file_path=token, file_size=Path(downloaded_path).stat().st_size if Path(downloaded_path).exists() else 0, md5_hash="", drive_file_id=drive_file_id, drive_link=drive_link)
                    if os.getenv("DELETE_AFTER_UPLOAD", "false").lower() == "true":
                        self.onvif_client.delete_recording(token)
                    uploaded_count += 1
                except (ONVIFClientError, DriveUploadError) as exc:
                    logger.warning("Skipping ONVIF recording %s due to error: %s", name, exc)
                    self._emit(progress_callback, {"status": "error", "message": str(exc), "file": name})
                finally:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass

            self._emit(progress_callback, {"status": "completed", "message": "ONVIF sync completed", "files": uploaded_count})
            return {"status": "completed", "files": uploaded_count}
        except Exception as exc:
            logger.exception("ONVIF sync job failed")
            self._emit(progress_callback, {"status": "failed", "message": str(exc)})
            return {"status": "failed", "message": str(exc)}

    def start_in_background(self, progress_callback: Optional[Callable[[dict[str, Any]], None]] = None) -> threading.Thread:
        thread = threading.Thread(target=self._run_background, args=(progress_callback,), daemon=True)
        thread.start()
        return thread

    def _run_background(self, progress_callback: Optional[Callable[[dict[str, Any]], None]] = None) -> None:
        self.sync_once(progress_callback=progress_callback)

    @staticmethod
    def _emit(progress_callback: Optional[Callable[[dict[str, Any]], None]], payload: dict[str, Any]) -> None:
        if progress_callback is not None:
            progress_callback(payload)


def run_sync_once(progress_callback: Optional[Callable[[dict[str, Any]], None]] = None) -> dict[str, Any]:
    return SyncJob().sync_once(progress_callback=progress_callback)