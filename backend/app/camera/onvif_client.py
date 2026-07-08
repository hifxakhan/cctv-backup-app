import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPDigestAuth

from ..utils.logger import get_logger

logger = get_logger(__name__)

try:
    from onvif import ONVIFCamera as OnvifDeviceCamera
except Exception as exc:  # pragma: no cover - runtime dependency check
    OnvifDeviceCamera = None
    _ONVIF_IMPORT_ERROR = exc
else:
    _ONVIF_IMPORT_ERROR = None


class ONVIFClientError(RuntimeError):
    """Raised when ONVIF operations fail."""


class ONVIFCamera:
    """Minimal ONVIF client tailored for SD-card recording access."""

    def __init__(
        self,
        host: str,
        port: int = 80,
        username: str = "",
        password: str = "",
        timeout: float = 10.0,
        days_back: int = 3,
        max_retries: int = 3,
    ) -> None:
        self.host = host.strip()
        self.port = port or 80
        self.username = username
        self.password = password
        self.timeout = timeout
        self.days_back = days_back
        self.max_retries = max_retries
        self._device: Optional[Any] = None
        self._media_service: Optional[Any] = None
        self._replay_service: Optional[Any] = None
        self._profiles: List[Dict[str, Any]] = []

    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)

    def connect(self) -> bool:
        """Connect to the camera using HTTP Digest authentication."""
        if not self.is_configured():
            logger.warning("ONVIF client is not configured")
            return False

        if self._device is not None:
            return True

        ports = [self.port, 80, 8080]
        for candidate_port in ports:
            try:
                self._connect_once(candidate_port)
                logger.info("Connected to ONVIF camera at %s:%s", self.host, candidate_port)
                return True
            except ONVIFClientError as exc:
                logger.warning("ONVIF connection attempt failed for %s:%s: %s", self.host, candidate_port, exc)
                break
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Unexpected ONVIF connection failure for %s:%s: %s", self.host, candidate_port, exc)
                break

        return False

    def get_profiles(self) -> List[Dict[str, Any]]:
        """Return available media profiles for the camera."""
        if not self.connect():
            return []

        if self._media_service is None:
            return []

        try:
            profiles_response = self._media_service.GetProfiles()
            profiles = self._extract_items(profiles_response, "Profiles", ["Profile", "profiles"])
        except Exception as exc:
            logger.warning("Unable to retrieve ONVIF profiles: %s", exc)
            return []

        normalized: List[Dict[str, Any]] = []
        for profile in profiles:
            normalized.append(
                {
                    "token": self._read_value(profile, "token") or self._read_value(profile, "Token"),
                    "name": self._read_value(profile, "name") or self._read_value(profile, "Name") or "Profile",
                }
            )
        self._profiles = normalized
        return normalized

    def get_recordings(self, days_back: int = 3) -> List[Dict[str, Any]]:
        """List recordings from the SD card that are recent enough."""
        if not self.connect():
            raise ONVIFClientError("Unable to connect to ONVIF camera")

        if self._replay_service is None:
            raise ONVIFClientError("Replay service is not available")

        try:
            response = self._replay_service.GetRecordings()
            raw_items = self._extract_items(response, "Recording", ["Recordings", "recordings"])
        except Exception as exc:
            logger.warning("Unable to query ONVIF recordings: %s", exc)
            return []

        recordings: List[Dict[str, Any]] = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        for item in raw_items:
            normalized = self._normalize_recording(item)
            start_time = self._parse_datetime(normalized.get("start_time"))
            if start_time is None:
                recordings.append(normalized)
                continue
            if start_time >= cutoff:
                recordings.append(normalized)

        return sorted(recordings, key=lambda item: item.get("start_time") or "", reverse=True)

    def download_recording(self, recording_token: str, download_path: str) -> Optional[str]:
        """Download a recording via the ONVIF replay URI."""
        if not self.connect():
            raise ONVIFClientError("Unable to connect to ONVIF camera")

        if not recording_token:
            raise ONVIFClientError("Recording token is required")

        destination = Path(download_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        replay_uri = None
        if self._replay_service is not None:
            try:
                replay_response = self._replay_service.GetReplayUri(RecordingToken=recording_token)
                replay_uri = self._read_value(replay_response, "Uri") or self._read_value(replay_response, "uri")
            except Exception as exc:
                logger.warning("Unable to obtain replay URI for %s: %s", recording_token, exc)

        if not replay_uri:
            raise ONVIFClientError("Replay URI is not available for recording")

        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    replay_uri,
                    auth=HTTPDigestAuth(self.username, self.password),
                    timeout=self.timeout,
                    stream=True,
                )
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            handle.write(chunk)
                logger.info("Downloaded ONVIF recording '%s' to %s", recording_token, destination)
                return str(destination)
            except Exception as exc:
                logger.warning("Download attempt %s failed for %s: %s", attempt + 1, recording_token, exc)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        raise ONVIFClientError("Failed to download recording from ONVIF replay URI")

    def delete_recording(self, recording_token: str) -> bool:
        """Delete a recording from the SD card if the camera supports it."""
        if not self.connect():
            raise ONVIFClientError("Unable to connect to ONVIF camera")

        if not recording_token:
            raise ONVIFClientError("Recording token is required")

        if self._replay_service is None:
            raise ONVIFClientError("Replay service is not available")

        for method_name in ("DeleteRecording", "DeleteRecordings", "Delete"):
            method = getattr(self._replay_service, method_name, None)
            if callable(method):
                try:
                    method(RecordingToken=recording_token)
                    logger.info("Deleted ONVIF recording %s", recording_token)
                    return True
                except TypeError:
                    try:
                        method(recording_token)
                        logger.info("Deleted ONVIF recording %s", recording_token)
                        return True
                    except Exception as exc:
                        logger.warning("Delete method %s failed: %s", method_name, exc)
                except Exception as exc:
                    logger.warning("Delete method %s failed: %s", method_name, exc)

        raise ONVIFClientError("Camera does not support recording deletion")

    def get_sd_card_info(self) -> Dict[str, Any]:
        """Return a best-effort summary of SD-card information."""
        if not self.connect():
            return {"status": "disconnected", "host": self.host, "port": self.port}

        payload: Dict[str, Any] = {
            "status": "connected",
            "host": self.host,
            "port": self.port,
            "profiles": self.get_profiles(),
        }

        if self._device is not None:
            try:
                storage_config = self._device.devicemgmt.GetStorageConfiguration()
                payload["storage_config"] = str(storage_config)
            except Exception as exc:
                logger.warning("Unable to retrieve storage configuration: %s", exc)
                payload["storage_config"] = None

        return payload

    def _connect_once(self, port: int) -> None:
        if OnvifDeviceCamera is None:
            raise ONVIFClientError(f"ONVIF dependency is not installed: {_ONVIF_IMPORT_ERROR}")

        device = OnvifDeviceCamera(self.host, port, self.username, self.password)
        try:
            device.devicemgmt.GetSystemDateAndTime()
        except Exception as exc:  # pragma: no cover - some devices do not support this call
            logger.debug("System date call failed during ONVIF connect: %s", exc)

        self._device = device
        try:
            self._media_service = device.create_media_service()
        except Exception as exc:
            logger.debug("Unable to create ONVIF media service: %s", exc)
            self._media_service = None

        try:
            self._replay_service = device.create_replay_service()
        except Exception as exc:
            logger.debug("Unable to create ONVIF replay service: %s", exc)
            self._replay_service = None

    def _normalize_recording(self, item: Any) -> Dict[str, Any]:
        token = self._read_value(item, "token") or self._read_value(item, "Token") or self._read_value(item, "RecordingToken")
        name = self._read_value(item, "name") or self._read_value(item, "Name") or token or "Recording"
        return {
            "token": token or "",
            "name": name,
            "start_time": self._read_value(item, "startTime") or self._read_value(item, "StartTime") or self._read_value(item, "start_time"),
            "end_time": self._read_value(item, "endTime") or self._read_value(item, "EndTime") or self._read_value(item, "end_time"),
            "source": self._read_value(item, "source") or self._read_value(item, "Source") or "",
        }

    def _extract_items(self, response: Any, fallback_key: str, candidate_keys: List[str]) -> List[Any]:
        if isinstance(response, list):
            return response
        if isinstance(response, tuple):
            return list(response)
        if hasattr(response, fallback_key):
            value = getattr(response, fallback_key)
            if isinstance(value, list):
                return value
            if isinstance(value, tuple):
                return list(value)
            return [value]
        for key in candidate_keys:
            if hasattr(response, key):
                value = getattr(response, key)
                if isinstance(value, list):
                    return value
                if isinstance(value, tuple):
                    return list(value)
                return [value]
        if isinstance(response, dict):
            for key in candidate_keys + [fallback_key]:
                value = response.get(key)
                if isinstance(value, list):
                    return value
                if isinstance(value, tuple):
                    return list(value)
                if value is not None:
                    return [value]
        return []

    def _read_value(self, item: Any, key: str) -> Optional[str]:
        if item is None:
            return None
        if isinstance(item, dict):
            return item.get(key) or item.get(key.lower()) or item.get(key.capitalize())
        for attribute_name in (key, key.lower(), key.capitalize()):
            if hasattr(item, attribute_name):
                value = getattr(item, attribute_name)
                if value is not None:
                    return str(value)
        return None

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            try:
                return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
