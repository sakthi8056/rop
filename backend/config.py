"""
Application configuration.
All settings can be overridden via environment variables.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


# Base directories
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    # Application
    APP_NAME: str = "ROP AI Screener"
    APP_VERSION: str = "1.0.0-prototype"
    APP_DESCRIPTION: str = "AI-Assisted Retinopathy of Prematurity Screening — Research Prototype"
    DEBUG: bool = False

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Database
    DATABASE_PATH: str = str(BASE_DIR / "rop_screening.db")
    TURSO_DATABASE_URL: str = ""
    TURSO_AUTH_TOKEN: str = ""

    # File storage
    UPLOADS_DIR: str = str(BASE_DIR / "uploads")
    REPORTS_DIR: str = str(BASE_DIR / "reports")

    # AI Model
    MODEL_WEIGHTS_DIR: str = str(BASE_DIR / "ml" / "weights")
    MODEL_WEIGHTS_FILE: str = "rop_model.pth"
    MODEL_NAME: str = "EfficientNet-B0 (ROP)"
    MODEL_VERSION: str = "demo-v1.0"
    MODEL_INPUT_SIZE: int = 224
    MODEL_NUM_CLASSES: int = 3
    MODEL_CLASS_LABELS: list[str] = ["Normal", "Pre-Plus/Mild", "Plus Disease/Severe"]

    # Fonts
    FONTS_DIR: str = str(BASE_DIR / "static" / "fonts")

    # Auth
    JWT_SECRET_KEY: str = "rop-screening-local-dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 480  # 8 hours

    # Upload constraints
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_EXTENSIONS: list[str] = [".jpg", ".jpeg", ".png"]

    # Image quality thresholds
    MIN_IMAGE_RESOLUTION: int = 200  # pixels
    BLUR_THRESHOLD: float = 100.0  # Laplacian variance
    MIN_BRIGHTNESS: float = 40.0
    MAX_BRIGHTNESS: float = 220.0
    MIN_CONTRAST: float = 20.0

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def model_weights_path(self) -> Path:
        return Path(self.MODEL_WEIGHTS_DIR) / self.MODEL_WEIGHTS_FILE

    @property
    def is_model_available(self) -> bool:
        return self.model_weights_path.exists()

    @property
    def demo_mode(self) -> bool:
        return not self.is_model_available

    @property
    def is_turso_enabled(self) -> bool:
        return bool(self.TURSO_DATABASE_URL and self.TURSO_AUTH_TOKEN)

    class Config:
        env_file = (str(BASE_DIR / ".env"), ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def ensure_directories():
    """Create required directories if they don't exist."""
    settings = get_settings()
    for dir_path in [
        settings.UPLOADS_DIR,
        settings.REPORTS_DIR,
        settings.MODEL_WEIGHTS_DIR,
        settings.FONTS_DIR,
    ]:
        os.makedirs(dir_path, exist_ok=True)

    # Create .gitkeep files
    for dir_path in [settings.UPLOADS_DIR, settings.REPORTS_DIR]:
        gitkeep = Path(dir_path) / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
