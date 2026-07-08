from flask_socketio import emit

from .. import socketio
from ..utils.logger import get_logger

logger = get_logger(__name__)


def register_socketio_handlers(socketio_instance) -> None:
    @socketio_instance.on("connect")
    def handle_connect():
        logger.info("Client connected to websocket")
        emit("status", {"message": "Connected"})

    @socketio_instance.on("disconnect")
    def handle_disconnect():
        logger.info("Client disconnected from websocket")


def emit_sync_update(payload: dict) -> None:
    socketio.emit("sync_update", payload)
