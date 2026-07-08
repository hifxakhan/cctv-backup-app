"""
FastAPI-style dependency for multi-user session identity.
Works with Flask by providing a before_request handler that
reads/sets a signed cookie to identify the user.

This is NOT an actual FastAPI dependency — it's a Flask-compatible
utility that hooks into the request lifecycle.
"""
import uuid
import logging
from typing import Optional

from flask import request, g, make_response

from .security import sign_user_id, verify_user_id
from .database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# Cookie name for user session
USER_COOKIE_NAME = "cctv_user_id"
# Max age of the cookie in seconds (1 year)
USER_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def get_or_create_current_user() -> dict:
    """
    Dependency that gets or creates a user from the signed cookie.
    Attaches user info to Flask's g object.
    Returns the user dict.
    """
    # Check if already resolved in this request
    if hasattr(g, "current_user"):
        return g.current_user

    db = DatabaseManager()
    signed_user_id = request.cookies.get(USER_COOKIE_NAME)

    if signed_user_id:
        user_id = verify_user_id(signed_user_id)
        if user_id:
            user = db.get_or_create_user(user_id)
            logger.debug("Existing user from cookie: %s", user["id"])
            g.current_user = user
            return user
        else:
            logger.warning("Invalid user cookie, creating new user")

    # No valid cookie: create new user
    user_id = str(uuid.uuid4())
    user = db.get_or_create_user(user_id)
    logger.info("Created new user: %s", user_id)
    g.current_user = user
    return user


def set_user_cookie(response, user_id: str) -> None:
    """Set the signed user cookie on a response."""
    signed = sign_user_id(user_id)
    response.set_cookie(
        USER_COOKIE_NAME,
        signed,
        max_age=USER_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=False,  # Set to True in production with HTTPS
    )


def get_user_id() -> Optional[str]:
    """Get the current user's ID from Flask's g object."""
    if hasattr(g, "current_user"):
        return g.current_user.get("id")
    return None