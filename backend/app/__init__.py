from flask import Flask, g, make_response, request
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_session import Session

from .config import Config

socketio = SocketIO(async_mode="threading")

from .api.routes import api_bp
from .api.auth import auth_bp
from .api.websocket import register_socketio_handlers


def create_app():
    app = Flask(__name__, static_folder='../../frontend/build', static_url_path='/')
    app.config.from_object(Config)

    # Session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SECRET_KEY'] = Config.SECRET_KEY

    Session(app)

    CORS(app, resources={r"/api/*": {"origins": "https://cctv-backup-app.vercel.app"}}, supports_credentials=True)

    # Before request: ensure every visitor gets identified with a user cookie
    from .deps import get_or_create_current_user, set_user_cookie

    @app.before_request
    def identify_user():
        """Ensure every request has a user identity, setting cookie if needed."""
        if not request.path.startswith("/api/"):
            return  # Only apply to API routes
        user = get_or_create_current_user()
        # Store user_id in g for other handlers
        g.current_user = user

    @app.after_request
    def set_identity_cookie(response):
        """Set the user cookie on every response if we have a user."""
        if hasattr(g, "current_user") and g.current_user:
            # Check if cookie needs to be set
            from .deps import USER_COOKIE_NAME
            if not request.cookies.get(USER_COOKIE_NAME):
                set_user_cookie(response, g.current_user["id"])
        return response

    socketio.init_app(app, cors_allowed_origins="*")
    register_socketio_handlers(socketio)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")

    @app.route("/")
    def index():
        return app.send_static_file('index.html')

    # Catch-all for React routing - serve index.html for unknown paths
    @app.route("/<path:path>")
    def serve_react(path):
        if path.startswith("api/"):
            return {"error": "Not found"}, 404
        try:
            return app.send_static_file(path)
        except Exception:
            return app.send_static_file('index.html')

    return app