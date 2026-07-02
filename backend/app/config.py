import os
import sqlite3
from pathlib import Path

def load_env(env_path=None):
    if env_path is None:
        # Search upwards for .env starting from this file's directory
        start_dir = Path(__file__).resolve().parent
        for _ in range(4):  # Check current directory and up to 3 parent directories
            test_path = start_dir / ".env"
            if test_path.exists():
                env_path = test_path
                break
            start_dir = start_dir.parent

    if env_path and os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
        except Exception as e:
            print(f"Warning: Failed to load .env file from {env_path}: {e}")

def load_token_from_db(db_path=None):
    if db_path is None:
        start_dir = Path(__file__).resolve().parent
        for _ in range(4):
            test_path = start_dir / "token.db"
            if test_path.exists():
                db_path = test_path
                break
            start_dir = start_dir.parent

    if db_path and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT key, value FROM secrets")
            for key, value in cursor.fetchall():
                if key not in os.environ:
                    os.environ[key] = value
            conn.close()
        except Exception as e:
            print(f"Warning: Failed to load token.db from {db_path}: {e}")

# Load environment variables on import
load_env()
load_token_from_db()

# App Configuration Settings
CWA_API_TOKEN = os.environ.get("CWA_API_TOKEN", "")
WINDY_API_KEY = os.environ.get("WINDY_API_KEY", os.environ.get("NEXT_PUBLIC_WINDY_API_KEY", ""))
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "600"))  # Default 10 minutes
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
DEBUG = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes")

# Base CWA Opendata URL
CWA_DATA_URL = os.environ.get("CWA_DATA_URL", "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0001-001?downloadType=WEB&format=JSON")
