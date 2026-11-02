"""Runtime settings. Each storage concern has its own location (ADR 0001, decision 4)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OBS_", env_file=".env", extra="ignore")

    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'artifacts' / 'observatory.sqlite').as_posix()}"
    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    validation_dir: Path = PROJECT_ROOT / "data" / "validation"
    capabilities_dir: Path = PROJECT_ROOT / "data" / "capabilities"
    methodology_dir: Path = PROJECT_ROOT / "config" / "methodology"
    artifacts_dir: Path = PROJECT_ROOT / "artifacts"
    models_dir: Path = PROJECT_ROOT / "artifacts" / "models"
    experiments_dir: Path = PROJECT_ROOT / "artifacts" / "experiments"
    figures_dir: Path = PROJECT_ROOT / "artifacts" / "figures"
    reports_dir: Path = PROJECT_ROOT / "artifacts" / "reports"
    logs_dir: Path = PROJECT_ROOT / "logs"
    docs_dir: Path = PROJECT_ROOT / "docs"
    admin_api_key: str = "change-me"
    http_timeout_s: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
