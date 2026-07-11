import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Protocol Selection
    PROTOCOL_TYPE = (os.getenv('PROTOCOL_TYPE', 'onvif') or 'onvif').strip().lower()
    LOCAL_STORAGE_PATH = os.getenv('LOCAL_STORAGE_PATH', r'D:\CCTV_Recordings')

    # Storage Destination: 'local', 'google_drive', or 'both'
    STORAGE_DESTINATION = (os.getenv('STORAGE_DESTINATION', 'both') or 'both').strip().lower()

    # FTP Settings
    FTP_HOST = os.getenv('FTP_HOST', '')
    FTP_PORT = int(os.getenv('FTP_PORT', 21))
    FTP_USER = os.getenv('FTP_USER', '')
    FTP_PASSWORD = os.getenv('FTP_PASSWORD', '')
    FTP_PATH = os.getenv('FTP_PATH', '/')

    # ONVIF Settings
    ONVIF_ENABLED = os.getenv('ONVIF_ENABLED', 'false').lower() == 'true'
    ONVIF_HOST = os.getenv('ONVIF_HOST', '')
    ONVIF_PORT = int(os.getenv('ONVIF_PORT', 80))
    ONVIF_USER = os.getenv('ONVIF_USER', '')
    ONVIF_PASSWORD = os.getenv('ONVIF_PASSWORD', '')
    ONVIF_DAYS_BACK = int(os.getenv('ONVIF_DAYS_BACK', 3))

    # Google Drive Settings
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'service-account-key.json')
    DRIVE_BACKUP_FOLDER = os.getenv('DRIVE_BACKUP_FOLDER', 'CCTV_Backup')
    # OAuth 2.0 settings (for user-based auth)
    GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
    GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:5000/api/drive/auth/callback')

    # App Settings
    SYNC_INTERVAL_MINUTES = int(os.getenv('SYNC_INTERVAL_MINUTES', 60))
    DELETE_AFTER_UPLOAD = os.getenv('DELETE_AFTER_UPLOAD', 'false').lower() == 'true'
    MAX_FILE_AGE_DAYS = int(os.getenv('MAX_FILE_AGE_DAYS', 30))

    # Database
    DB_PATH = os.getenv('DB_PATH', 'cctv_backup.db')

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    # Session cookie settings for cross-site support
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'None'
    SESSION_COOKIE_HTTPONLY = True