"""
Invoice Generator Configuration Module
Loads environment variables and provides app-wide settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings loaded from environment."""

    # App
    APP_NAME: str = os.getenv("APP_NAME", "Invoice Generator")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")

    # Database
    SQLITE_DB_PATH: str = str(BASE_DIR / os.getenv("SQLITE_DB_PATH", "database/buildvoice.db"))

    # AI / NLP
    STT_ENGINE: str = os.getenv("STT_ENGINE", "vosk")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    VOSK_MODEL_PATH: str = str(BASE_DIR / os.getenv("VOSK_MODEL_PATH", "ai_engine/models/vosk-model-small-en-us-0.15"))

    # Server
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Invoice
    INVOICE_OUTPUT_DIR: str = str(BASE_DIR / os.getenv("INVOICE_OUTPUT_DIR", "invoices/output"))

    # Sync
    SYNC_ENABLED: bool = os.getenv("SYNC_ENABLED", "false").lower() == "true"

    # Dataset
    DATASET_PATH: str = str(BASE_DIR / "dataset" / "master_dataset.csv")

    # Logging
    LOG_DIR: str = str(BASE_DIR / "logs")


settings = Settings()
