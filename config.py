import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY") or "your_default_secret_key"
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or "your_default_jwt_secret_key"
    DB_HOST = os.getenv("DB_HOST") or "localhost"
    DB_USER = os.getenv("DB_USER") or "root"
    DB_PASS = os.getenv("DB_PASS") or ""
    DB_NAME = os.getenv("DB_NAME") or "komodo_hub"
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")