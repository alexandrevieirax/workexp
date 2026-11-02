"""Runtime settings. Each storage concern has its own location (ADR 0001, decision 4)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
# Example values from the docs must never work as a real key.
PLACEHOLDER_KEYS = {"", "change-me", "troque-por-uma-chave-longa"}
MIN_KEY_LENGTH = 16


def env_file_encoding(path: Path) -> str:
    """Windows PowerShell's `echo ... >> .env` writes UTF-16; read it instead of crashing."""
    try:
        head = path.read_bytes()[:3]
    except OSError:
        return "utf-8"
    if head[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if head == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return "utf-8"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OBS_", env_file=ENV_FILE, extra="ignore")

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

    @property
    def admin_key_configured(self) -> bool:
        k = self.admin_api_key.strip()
        return k not in PLACEHOLDER_KEYS and len(k) >= MIN_KEY_LENGTH


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file_encoding=env_file_encoding(ENV_FILE))


def write_admin_key(key: str, path: Path = ENV_FILE) -> Path:
    """Set OBS_ADMIN_API_KEY in .env (UTF-8), keeping any other lines, whatever the file's current encoding."""
    lines: list[str] = []
    if path.exists():
        text = path.read_bytes().decode(env_file_encoding(path))
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("OBS_ADMIN_API_KEY")]
    lines.append(f"OBS_ADMIN_API_KEY={key}")
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))  # UTF-8, LF, no BOM on every OS
    return path
