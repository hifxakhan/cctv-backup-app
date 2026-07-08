import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple
from ftplib import FTP, error_perm, error_temp, Error


class FTPClientError(Exception):
    """Raised when the FTP client cannot complete an operation."""


class FTPClient:
    def __init__(self, host: str, port: int = 21, username: str = "", password: str = "", timeout: int = 10, retries: int = 3):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout
        self.retries = retries
        self._ftp: Optional[FTP] = None

    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)

    def connect(self) -> FTP:
        if self._ftp is not None:
            return self._ftp

        if not self.is_configured():
            raise FTPClientError("FTP configuration is incomplete.")

        ftp = FTP()
        ftp.connect(self.host, self.port, self.timeout)
        ftp.login(self.username, self.password)
        ftp.set_pasv(True)
        ftp.encoding = "utf-8"
        self._ftp = ftp
        return ftp

    def disconnect(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.quit()
            except Exception:
                pass
            self._ftp = None

    def list_files(self, remote_path: str = "/", extensions: Optional[Tuple[str, ...]] = None) -> List[dict[str, Any]]:
        ftp = self.connect()
        files: List[dict[str, Any]] = []
        try:
            if remote_path and remote_path != "/":
                ftp.cwd(remote_path)
            else:
                ftp.cwd("/")

            names = ftp.nlst()
            for name in names:
                if name in {".", ".."}:
                    continue
                try:
                    size = ftp.size(name)
                except Exception:
                    size = 0
                if extensions and not any(name.lower().endswith(ext.lower()) for ext in extensions):
                    continue
                files.append({
                    "name": name,
                    "path": f"{remote_path.rstrip('/')}/{name}".replace("//", "/") if remote_path not in {"", "/"} else name,
                    "size": size,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            return sorted(files, key=lambda item: item["name"])
        except (error_perm, error_temp, Error) as exc:
            raise FTPClientError(f"Unable to list FTP files: {exc}") from exc

    def download_file(self, remote_path: str, local_path: str, expected_size: Optional[int] = None, callback: Optional[Callable[[int], None]] = None) -> dict[str, Any]:
        ftp = self.connect()
        last_error: Optional[Exception] = None

        for attempt in range(max(1, self.retries)):
            try:
                Path(local_path).parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as handle:
                    def write_chunk(chunk: bytes) -> None:
                        if not chunk:
                            return
                        handle.write(chunk)
                        if callback is not None:
                            callback(len(chunk))

                    ftp.retrbinary(f"RETR {remote_path}", write_chunk)

                file_size = os.path.getsize(local_path)
                md5_hash = self._calculate_md5(local_path)
                if expected_size is not None and file_size != expected_size:
                    raise FTPClientError(f"Downloaded file size mismatch for {remote_path}")
                return {"path": local_path, "size": file_size, "md5_hash": md5_hash}
            except (error_perm, error_temp, Error, OSError) as exc:
                last_error = exc
                if attempt < self.retries - 1:
                    self.disconnect()
                    continue
                raise FTPClientError(f"Failed to download {remote_path} after {self.retries} attempts: {exc}") from exc

        if last_error is not None:
            raise FTPClientError(f"Failed to download {remote_path}: {last_error}") from last_error
        raise FTPClientError(f"Failed to download {remote_path}")

    def download_to_temp(self, remote_path: str, suffix: str = ".tmp", callback: Optional[Callable[[int], None]] = None) -> dict[str, Any]:
        temp_dir = Path(tempfile.gettempdir()) / "cctv_backup"
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / f"{Path(remote_path).name or 'download'}{suffix}"
        return self.download_file(remote_path, str(local_path), callback=callback)

    @staticmethod
    def _calculate_md5(file_path: str) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
