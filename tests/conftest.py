from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from fixtures.synthetic import build  # noqa: E402
from observatory.config import get_settings  # noqa: E402


@pytest.fixture
def synthetic_env(tmp_path, monkeypatch):
    """Isolated settings whose raw-data dir contains only SYNTHETIC sources."""
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "SYNTHETIC_DATA_DO_NOT_USE").write_text("synthetic test fixtures only", encoding="utf-8")
    build.build_onet_zip(raw / "onet" / "99.0" / "db_99_0_text.zip")
    build.build_cbo_dir(raw / "cbo")
    build.build_aei_dir(raw / "aei" / "release_synthetic")
    from observatory.connectors.esco import EscoClient

    esco = EscoClient(raw / "esco", client=build.esco_mock_client())
    esco.occupation_raw(build.ESCO_URI, "en")
    esco.occupation_raw(build.ESCO_URI, "pt")
    for key, val in {
        "OBS_DATABASE_URL": f"sqlite:///{(tmp_path / 'obs.sqlite').as_posix()}",
        "OBS_RAW_DATA_DIR": str(raw),
        "OBS_REPORTS_DIR": str(tmp_path / "reports"),
        "OBS_EXPERIMENTS_DIR": str(tmp_path / "experiments"),
        "OBS_FIGURES_DIR": str(tmp_path / "figures"),
        "OBS_ADMIN_API_KEY": "test-key-long-enough-123",
    }.items():
        monkeypatch.setenv(key, val)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def slice_run(synthetic_env):
    from observatory.pipeline.vertical_slice import SliceConfig, run

    report = run(
        SliceConfig(
            onet_code=build.ONET_CODE,
            onet_version="99.0",
            esco_uri=build.ESCO_URI,
            cbo_code="999901",
            aei_release="release_synthetic",
            offline=True,
            provider="baseline",  # tests must not download models (CI installs no ML extras)
        )
    )
    return synthetic_env, report


@pytest.fixture
def client(slice_run):
    from fastapi.testclient import TestClient

    from observatory.api import app as app_module

    app_module.configure(get_settings().database_url)
    with TestClient(app_module.app) as c:
        yield c
    app_module._factory = None
