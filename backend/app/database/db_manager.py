import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..security import encrypt_token, decrypt_token


class DatabaseManager:
    def __init__(self, db_path: str = "cctv_backup.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS uploaded_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    md5_hash TEXT,
                    upload_date TEXT,
                    drive_file_id TEXT,
                    drive_link TEXT,
                    UNIQUE(file_path, file_name)
                )
                """
            )
            # Users table - one row per browser/app user
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )
            # Google OAuth credentials - one per user
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS google_credentials (
                    user_id TEXT PRIMARY KEY,
                    google_email TEXT,
                    encrypted_access_token TEXT NOT NULL,
                    encrypted_refresh_token TEXT,
                    token_expiry TEXT,
                    scopes TEXT,
                    drive_folder_id TEXT,
                    connected_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def record_upload(self, file_name: str, file_path: str, file_size: int, md5_hash: str, drive_file_id: str, drive_link: str) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO uploaded_files (file_name, file_path, file_size, md5_hash, upload_date, drive_file_id, drive_link)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_name, file_path, file_size, md5_hash, datetime.now(timezone.utc).isoformat(), drive_file_id, drive_link),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "file_name": file_name, "file_path": file_path}
        finally:
            conn.close()

    def file_exists(self, file_path: str, file_name: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT 1 FROM uploaded_files WHERE file_path = ? AND file_name = ?",
                (file_path, file_name),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_upload_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT id, file_name, file_path, file_size, md5_hash, upload_date, drive_file_id, drive_link
                FROM uploaded_files
                ORDER BY upload_date DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "file_name": row[1],
                    "file_path": row[2],
                    "file_size": row[3],
                    "md5_hash": row[4],
                    "upload_date": row[5],
                    "drive_file_id": row[6],
                    "drive_link": row[7],
                }
                for row in rows
            ]
        finally:
            conn.close()

    def get_pending_files(self) -> List[Dict[str, Any]]:
        return []

    def cleanup_old_records(self, days: int = 30) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM uploaded_files WHERE upload_date < ?", (cutoff,))
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_files,
                    SUM(file_size) as total_size,
                    MAX(upload_date) as last_upload
                FROM uploaded_files
                """
            )
            row = cursor.fetchone()
            return {
                "total_files": row[0] or 0,
                "total_size_gb": (row[1] or 0) / (1024**3),
                "last_upload": row[2],
            }
        finally:
            conn.close()

    def get_stats_range(self, days: int = 7) -> Dict[str, Any]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_files,
                    SUM(file_size) as total_size_bytes,
                    MAX(upload_date) as last_upload
                FROM uploaded_files
                WHERE upload_date >= ?
                """,
                (cutoff,),
            )
            row = cursor.fetchone()
            return {
                "total_files": row[0] or 0,
                "total_size_bytes": row[1] or 0,
                "last_upload": row[2],
            }
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # Multi-User methods
    # -----------------------------------------------------------------------

    def get_or_create_user(self, user_id: str) -> Dict[str, Any]:
        """Get existing user or create a new one. Returns user dict."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("SELECT id, created_at FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "created_at": row[1]}
            # Create new user
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO users (id, created_at) VALUES (?, ?)", (user_id, now))
            conn.commit()
            return {"id": user_id, "created_at": now}
        finally:
            conn.close()

    def save_google_credentials(
        self,
        user_id: str,
        google_email: str,
        access_token: str,
        refresh_token: Optional[str],
        token_expiry: Optional[str],
        scopes: str,
    ) -> None:
        """Encrypt and store Google OAuth credentials for a user."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO google_credentials
                    (user_id, google_email, encrypted_access_token, encrypted_refresh_token,
                     token_expiry, scopes, connected_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    google_email,
                    encrypt_token(access_token),
                    encrypt_token(refresh_token) if refresh_token else "",
                    token_expiry or "",
                    scopes,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_google_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get decrypted Google OAuth credentials for a user. Returns None if not connected."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                SELECT user_id, google_email, encrypted_access_token, encrypted_refresh_token,
                       token_expiry, scopes, drive_folder_id, connected_at, updated_at
                FROM google_credentials WHERE user_id = ?
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "google_email": row[1],
                "access_token": decrypt_token(row[2]),
                "refresh_token": decrypt_token(row[3]) if row[3] else None,
                "token_expiry": row[4],
                "scopes": row[5],
                "drive_folder_id": row[6],
                "connected_at": row[7],
                "updated_at": row[8],
            }
        finally:
            conn.close()

    def update_drive_folder_id(self, user_id: str, folder_id: str) -> None:
        """Cache the user's CCTV_Backup folder ID."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE google_credentials SET drive_folder_id = ?, updated_at = ? WHERE user_id = ?",
                (folder_id, now, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_google_credentials(self, user_id: str) -> bool:
        """Remove a user's Google Drive connection."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM google_credentials WHERE user_id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_google_credentials_by_email(self, google_email: str) -> Optional[Dict[str, Any]]:
        """Look up credentials by Google email (for admin purposes)."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT user_id FROM google_credentials WHERE google_email = ?",
                (google_email,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_google_credentials(row[0])
        finally:
            conn.close()
