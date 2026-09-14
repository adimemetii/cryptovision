import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Keep secrets in .env or hosting environment variables, never in GitHub.
    SECRET_KEY = os.getenv("SECRET_KEY") or "local-" + os.urandom(24).hex()
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "cryptovision")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_SSL_CA = os.getenv("DB_SSL_CA", "").strip()
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    if DB_SSL_CA:
        SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {"ssl": {"ca": DB_SSL_CA}}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / "uploads")
