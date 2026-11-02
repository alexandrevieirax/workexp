"""Coverage runner: several occupation sets in one database, compared side by side (SYNTHETIC data)."""

from __future__ import annotations

import json

from fixtures.synthetic import build
from observatory.config import get_settings
from observatory.pipeline.coverage import DEFAULT_SETS, OccupationSet, render_markdown, run_coverage


def test_default_sets_cover_different_kinds_of_work():
    profiles = {s.profile for s in DEFAULT_SETS}
    assert {"manual", "saúde, regulamentada"} <= profiles and len(DEFAULT_SETS) >= 4
    assert len({s.onet_code for s in DEFAULT_SETS}) == len(DEFAULT_SETS)


def test_run_coverage_writes_comparison(synthetic_env):
    sets = [OccupationSet("sintetico", "teste", build.ONET_CODE, build.ESCO_URI, "999901")]
    result = run_coverage(sets, provider="baseline", offline=True, onet_version="99.0", aei_release="release_synthetic")
    assert result["sets"][0]["label"] == "sintetico"
    assert set(result["sets"][0]["occupations"]) == {"ONET", "ESCO", "CBO"}
    saved = json.loads((get_settings().reports_dir / "coverage_latest.json").read_text(encoding="utf-8"))
    assert saved["sets"][0]["run_id"] == result["sets"][0]["run_id"]
    md = render_markdown(result)
    assert "| sintetico | teste | ONET |" in md and "## Crosswalks" in md
