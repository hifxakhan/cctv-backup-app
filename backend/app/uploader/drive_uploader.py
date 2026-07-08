import os
from flask import session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class DriveUploadError(Exception):
    """Raised when a Google Drive upload cannot be completed."""


class GoogleDriveUploader:
    """Google Drive uploader that uses the CURRENT USER's OAuth credentials
    from the Flask session. Each user uploads to THEIR OWN Drive."""

    def __init__(self, folder_name=None):
        self.folder_name = folder_name or os.getenv("DRIVE_BACKUP_FOLDER", "CCTV_Backup")
        self._service = None
        self._user_email = None

    def _get_service(self):
        """Get the Drive service using credentials from the current session."""
        if self._service is not None:
            return self._service

        # Get credentials from session (set by auth.py during OAuth)
        creds_data = session.get("drive_credentials")

        if not creds_data:
            raise DriveUploadError(
                "No authenticated user found. Please connect your Google Drive first."
            )

        try:
            credentials = Credentials(
                token=creds_data["token"],
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data["token_uri"],
                client_id=creds_data["client_id"],
                client_secret=creds_data["client_secret"],
                scopes=creds_data["scopes"],
            )

            self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

            # Store user email for logging
            about = self._service.about().get(fields="user").execute()
            user_info = about.get("user", {})
            self._user_email = user_info.get("emailAddress", "Unknown user")

            return self._service

        except Exception as e:
            raise DriveUploadError(f"Failed to authenticate user's Drive: {e}")

    def get_user_email(self):
        """Get the email of the currently authenticated user."""
        if self._user_email is None:
            try:
                self._get_service()
            except Exception:
                return None
        return self._user_email

    def file_exists(self, file_name, parent_folder_id=None):
        try:
            service = self._get_service()
            query = f"name = '{file_name}' and trashed = false"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"
            results = service.files().list(q=query, fields="files(id)", pageSize=10).execute()
            return bool(results.get("files", []))
        except DriveUploadError:
            raise
        except Exception as exc:
            raise DriveUploadError(f"Unable to verify drive file existence: {exc}") from exc

    def ensure_folder(self, folder_name=None):
        """Create or get the user's CCTV_Backup folder in THEIR Drive."""
        service = self._get_service()
        folder_name = folder_name or self.folder_name

        # Check if folder exists in user's Drive
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        response = service.files().list(q=query, fields="files(id, name)", pageSize=10).execute()
        folders = response.get("files", [])

        if folders:
            folder_id = folders[0]["id"]
            return folder_id

        # Create the folder in user's Drive
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        folder = service.files().create(body=file_metadata, fields="id").execute()
        folder_id = folder.get("id")

        return folder_id

    def upload_file(self, file_path, file_name=None, parent_folder_id=None, progress_callback=None):
        """Upload a file to the CURRENT USER's Google Drive."""
        from pathlib import Path
        import mimetypes

        path = Path(file_path)
        if not path.exists():
            raise DriveUploadError(f"Local file does not exist: {file_path}")

        service = self._get_service()
        file_name = file_name or path.name

        # Get or create the user's CCTV_Backup folder
        if parent_folder_id is None:
            parent_folder_id = self.ensure_folder(self.folder_name)

        # Check if file already exists in user's Drive
        if self.file_exists(file_name, parent_folder_id):
            raise DriveUploadError(f"File already exists in user's Drive: {file_name}")

        # Prepare file metadata
        mime_type, _ = mimetypes.guess_type(str(path))
        mime_type = mime_type or "application/octet-stream"
        file_metadata = {
            "name": file_name,
            "parents": [parent_folder_id]
        }

        # Upload file (resumable for large files)
        if path.stat().st_size > 10 * 1024 * 1024:
            media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
            request = service.files().create(body=file_metadata, media_body=media, fields="id,webViewLink")
            response = None
            while response is None:
                status, response = request.next_chunk()
                if progress_callback is not None and status:
                    progress_callback(int(status.progress() * 100))
            return {
                "id": response.get("id"),
                "link": response.get("webViewLink"),
                "mode": "resumable"
            }

        # Standard upload for small files
        media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
        response = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id,webViewLink"
        ).execute()

        return {
            "id": response.get("id"),
            "link": response.get("webViewLink"),
            "mode": "standard"
        }