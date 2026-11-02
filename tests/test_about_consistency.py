"""Fails when a methodological change is not accompanied by version, changelog, "Sobre" and references updates."""

from __future__ import annotations

import shutil

import pytest

from observatory.about import consistency
from observatory.about.render import render_about
from observatory.config import get_settings
from observatory.methodology import load_methodology


def test_repository_is_consistent():
    assert consistency.check_consistency() == []


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Copy of the methodology/docs/capabilities so the governance check can be exercised on edits."""
    s = get_settings()
    for name, src in {"methodology": s.methodology_dir, "docs": s.docs_dir, "caps": s.capabilities_dir}.items():
        shutil.copytree(src, tmp_path / name)
    monkeypatch.setenv("OBS_METHODOLOGY_DIR", str(tmp_path / "methodology"))
    monkeypatch.setenv("OBS_DOCS_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("OBS_CAPABILITIES_DIR", str(tmp_path / "caps"))
    get_settings.cache_clear()
    from observatory.about import render

    render.references.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    render.references.cache_clear()


def test_weight_change_without_new_version_fails(sandbox):
    cfg = sandbox / "methodology" / "methodology_v0.1.0.yaml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace("alpha: 0.50", "alpha: 0.60"), encoding="utf-8")
    problems = consistency.check_consistency()
    assert any(p.startswith("fingerprint") for p in problems)


def test_capability_dictionary_change_changes_fingerprint(sandbox):
    before = load_methodology().fingerprint
    caps = sandbox / "caps" / "ai_capabilities_v0.1.0.yaml"
    caps.write_text(
        caps.read_text(encoding="utf-8").replace(
            "technical_capability: 0.75, maturity: 0.75", "technical_capability: 0.70, maturity: 0.75", 1
        ),
        encoding="utf-8",
    )
    assert load_methodology().fingerprint != before


def test_missing_changelog_section_fails(sandbox):
    cl = sandbox / "docs" / "CHANGELOG-methodology.md"
    cl.write_text(cl.read_text(encoding="utf-8").replace("## [0.1.0]", "## [0.0.9]"), encoding="utf-8")
    assert any(p.startswith("changelog") for p in consistency.check_consistency())


def test_unknown_reference_fails(sandbox):
    refs = sandbox / "docs" / "references" / "references.json"
    refs.write_text(
        refs.read_text(encoding="utf-8").replace('"id": "autor2003skill"', '"id": "renamed"'), encoding="utf-8"
    )
    assert any("autor2003skill" in p for p in consistency.check_consistency())


def test_about_numbers_come_from_config():
    cfg = load_methodology().config
    html = render_about("pt-BR")["html"]
    assert f"importance_norm^{cfg['task_weights']['alpha']}" in html
    assert load_methodology().fingerprint[:16] in html
    assert "bloco desconhecido" not in html and "<mark>" not in html


def test_about_has_all_required_sections():
    about = render_about("pt-BR")
    assert len(about["sections"]) == 20
    for sid in (
        "objetivo",
        "nao-mede",
        "formulas",
        "incertezas",
        "limitacoes",
        "etica",
        "versoes",
        "referencias",
        "licencas",
        "contestacao",
    ):
        assert sid in about["sections"]
