import os
from pathlib import Path


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").lower()
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    WTF_CSRF_TIME_LIMIT = 3600
    MAIL_SERVER = os.getenv("MAIL_SERVER", "")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "")
    MAIL_SENDER_NAME = os.getenv("MAIL_SENDER_NAME", "Estoque de Camarões")
    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "SMTP").upper()
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:5000")).rstrip("/")
    PASSWORD_RESET_TOKEN_MAX_AGE = int(os.getenv("PASSWORD_RESET_TOKEN_MAX_AGE", "3600"))
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        if APP_ENV == "production":
            raise RuntimeError("Configure DATABASE_URL no ambiente de produção.")
        instance_dir = Path(__file__).resolve().parent.parent / "instance"
        instance_dir.mkdir(parents=True, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{(instance_dir / 'estoque.db').as_posix()}"

    if not SECRET_KEY:
        if APP_ENV == "production":
            raise RuntimeError("Configure SECRET_KEY no ambiente de produção.")
        SECRET_KEY = "dev-only-change-before-deploy-8f2c4b7a"

