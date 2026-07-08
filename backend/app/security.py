"""
Security utilities for multi-user support:
- Fernet encryption/decryption for OAuth tokens stored in DB
- Signed session cookies for user identity (itsdangerous)
"""
import os
import logging
from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger(__name__)


def _get_fernet_key() -> bytes:
    """Get or derive a Fernet-compatible 32-byte key from TOKEN_ENCRYPTION_KEY."""
    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        # Fallback: derive from SECRET_KEY (not ideal but better than nothing)
        key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    # Fernet requires 32 url-safe base64 bytes
    if len(key) < 32:
        key = key.ljust(32, "x")
    return urlsafe_b64encode(key[:32].encode("utf-8"))


def _get_fernet() -> Fernet:
    return Fernet(_get_fernet_key())


def encrypt_token(token_str: str) -> str:
    """Encrypt a token string for safe DB storage."""
    if not token_str:
        return ""
    return _get_fernet().encrypt(token_str.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_str: str) -> str:
    """Decrypt a token string from DB storage."""
    if not encrypted_str:
        return ""
    try:
        return _get_fernet().decrypt(encrypted_str.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error("Failed to decrypt token: %s", e)
        return ""


def _get_serializer() -> URLSafeTimedSerializer:
    """Create serializer for signing user session cookies."""
    secret = os.getenv("SESSION_SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"))
    return URLSafeTimedSerializer(secret, salt="user-session")


def sign_user_id(user_id: str) -> str:
    """Create a signed cookie value for a user_id."""
    serializer = _get_serializer()
    return serializer.dumps(user_id)


def verify_user_id(signed_value: str, max_age_days: int = 365) -> str | None:
    """Verify a signed cookie and extract user_id. Returns None if invalid/expired."""
    serializer = _get_serializer()
    try:
        # itsdangerous expects max_age as integer seconds
        max_age_seconds = max_age_days * 24 * 60 * 60
        user_id = serializer.loads(signed_value, max_age=max_age_seconds)
        return user_id
    except SignatureExpired:
        logger.warning("User session cookie expired")
        return None
    except BadSignature:
        logger.warning("User session cookie has invalid signature")
        return None
