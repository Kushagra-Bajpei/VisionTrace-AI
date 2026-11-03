"""
VisionTrace AI – Application Settings
Uses pydantic-settings to load and validate environment variables.
"""
from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str = "change-me"
    debug: bool = True
    app_name: str = "VisionTrace AI"
    app_version: str = "0.1.0"

    # ── API Server ────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_url: str = "http://localhost:5173"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+psycopg://visiontrace:visiontrace@localhost:5432/visiontrace_db"
    )

    # ── Redis & Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Processing & Frame Extraction ─────────────────────────────────────────
    frame_extraction_fps: float = 1.0  # Sample 1 frame per second
    frames_storage_dir: str = "storage/frames"

    # ── Storage Configuration ─────────────────────────────────────────────────
    storage_path: str = "storage"
    video_storage_dir: str = "storage/videos"
    video_thumbnail_dir: str = "storage/thumbnails"
    video_temp_dir: str = "storage/temp"
    reports_storage_dir: str = "storage/reports"
    max_upload_size_mb: int = 500

    # ── AI & Computer Vision Models ───────────────────────────────────────────
    yolo_model_name: str = "yolov8n.pt"
    yolo_confidence_threshold: float = 0.25
    yolo_tracker_config: str = "bytetrack.yaml"
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"
    crops_storage_dir: str = "storage/crops"
    mock_embeddings: bool = False
    models_dir: str = "storage/models"
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str) -> str:
        return v

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def storage_base(self) -> Path:
        p = Path(self.storage_path)
        if p.name == "storage":
            return (PROJECT_ROOT / "storage").resolve()
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def videos_dir(self) -> Path:
        p = Path(self.video_storage_dir)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def thumbnails_dir(self) -> Path:
        p = Path(self.video_thumbnail_dir)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def frames_dir(self) -> Path:
        p = Path(self.frames_storage_dir)
        if p.name == "frames":
            return (self.storage_base / "frames").resolve()
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def crops_dir(self) -> Path:
        p = Path(self.crops_storage_dir)
        if p.name == "crops":
            return (self.storage_base / "crops").resolve()
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def temp_dir(self) -> Path:
        p = Path(self.video_temp_dir)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def reports_dir(self) -> Path:
        p = Path(self.reports_storage_dir)
        if p.name == "reports":
            return (self.storage_base / "reports").resolve()
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def models_path(self) -> Path:
        p = Path(self.models_dir)
        if p.name == "models":
            return (self.storage_base / "models").resolve()
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
