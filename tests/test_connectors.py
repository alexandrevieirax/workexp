"""Import of O*NET, ESCO, CBO and AEI from SYNTHETIC fixtures (no network, no real data)."""

from __future__ import annotations

import pytest

from fixtures.synthetic import build
from observatory.connectors.aei import AeiRelease
from observatory.connectors.base import SchemaValidationError, SourceUnavailableError
from observatory.connectors.cbo import CboFiles
from observatory.connectors.esco import EscoClient, parse_occupation, parse_skills, skills_as_tasks
from observatory.connectors.onet import OnetArchive


@pytest.fixture
def onet(tmp_path):
    return OnetArchive(build.build_onet_zip(tmp_path / "onet.zip"), is_synthetic=True)


def test_onet_import_preserves_scales_and_metadata(onet):
    assert onet.version == "99.0"
    assert onet.validate()
    occ = onet.occupation(build.ONET_CODE)
    assert occ.title.startswith(build.TAG) and occ.is_synthetic
    assert occ.attributes["job_zone"] == 4 and occ.qualification_level == 1.0
    tasks = onet.tasks(build.ONET_CODE)
    assert len(tasks) == 4
    t1 = next(t for t in tasks if t.original_id.endswith("1"))
    assert set(t1.ratings) == {"IM", "RT", "FT"}  # scales kept separately, never summed
    assert t1.ratings["IM"]["n"] == 30 and t1.ratings["IM"]["se"] == 0.1
    assert len(t1.ratings["FT"]) == 7


def test_onet_suppressed_flag_is_preserved(onet):
    t3 = next(t for t in onet.tasks(build.ONET_CODE) if t.original_id.endswith("3"))
    assert t3.ratings["FT"]["1"]["suppressed"] is True
    assert t3.ratings["FT"]["2"]["suppressed"] is False


def test_onet_missing_frequency_is_missing_not_zero(onet):
    t4 = next(t for t in onet.tasks(build.ONET_CODE) if t.original_id.endswith("4"))
    assert "FT" not in t4.ratings


def test_onet_missing_archive_explains_procedure(tmp_path):
    with pytest.raises(SourceUnavailableError) as exc:
        OnetArchive(tmp_path / "nope.zip")
    assert "download-onet" in exc.value.procedure


def test_onet_descriptors_keep_ci_and_suppression(onet):
    rows = onet.descriptors(build.ONET_CODE, "work_context")
    assert rows and all({"ci_low", "ci_high", "suppressed", "n"} <= r.keys() for r in rows)


def test_esco_import_via_api_cache(tmp_path):
    client = EscoClient(tmp_path, client=build.esco_mock_client())
    raw_en = client.occupation_raw(build.ESCO_URI, "en")
    raw_pt = client.occupation_raw(build.ESCO_URI, "pt")
    occ = parse_occupation(raw_en, raw_pt)
    assert occ.group_code == "2512" and occ.qualification_level == 1.0
    assert any(lang == "pt" for _, lang, _ in occ.aliases)
    skills = parse_skills(raw_en, raw_pt)
    units = skills_as_tasks(skills)
    assert [u.statement for u in units] == ["write computer programs", "prepare project reports"]  # knowledge excluded
    assert units[0].attributes["title_pt"] == "escrever programas"
    # offline mode reads the cache and records the retrieval provenance
    offline = EscoClient(tmp_path, offline=True)
    assert offline.occupation_raw(build.ESCO_URI, "en")["uri"] == build.ESCO_URI
    assert offline.retrievals[0]["sha256"]


def test_esco_offline_without_cache_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        EscoClient(tmp_path, offline=True).occupation_raw("http://x", "en")


def test_cbo_import(tmp_path):
    cbo = CboFiles(build.build_cbo_dir(tmp_path / "cbo"), is_synthetic=True)
    occ = cbo.occupation("9999-01")
    assert occ.title.startswith(build.TAG) and occ.group_code == "9999"
    assert "descricao_sumaria" in occ.attributes["fields_not_available_in_source_file"]
    assert [a for a, _, kind in occ.aliases if kind == "synonym"] == [f"{build.TAG} Sinônimo"]
    acts = cbo.activities("999901")
    assert len(acts) == 3 and acts[0].language == "pt" and acts[0].attributes["scope"] == "occupation"
    assert cbo.descriptor().retrieval_method == "synthetic_fixture"


def test_cbo_personal_competencies_are_not_tasks(tmp_path):
    cbo = CboFiles(build.build_cbo_dir(tmp_path / "cbo"))
    assert all(a.attributes["area_code"] != "Z" for a in cbo.activities("999901"))
    assert [c["label"] for c in cbo.personal_competencies("999901")] == ["Demonstrar capacidade de síntese"]


def test_cbo_stray_semicolons_are_repaired_and_counted(tmp_path):
    cbo = CboFiles(build.build_cbo_dir(tmp_path / "cbo"))
    assert "Instalar cabos de rede; testar conexões" in [a.statement for a in cbo.activities("999901")]
    assert cbo.repaired_rows["perfil"] == 1
    assert "repaired rows" in cbo.descriptor().notes


def test_cbo_schema_validation(tmp_path):
    with pytest.raises(SchemaValidationError) as exc:
        CboFiles(build.build_cbo_dir(tmp_path / "cbo", drop_column="TITULO"))
    assert "TITULO" in exc.value.missing


def test_cbo_absent_never_fabricates(tmp_path):
    with pytest.raises(SourceUnavailableError) as exc:
        CboFiles(tmp_path / "empty")
    assert "reCAPTCHA" in exc.value.procedure


def test_aei_exact_fuzzy_and_absent(tmp_path):
    aei = AeiRelease(build.build_aei_dir(tmp_path / "aei"), "release_synthetic")
    exact = aei.lookup("Write and maintain computer programs from written specifications.")
    assert exact.match_method == "exact_normalized_text" and exact.automation_share == pytest.approx(0.5 / 0.9)
    fuzzy = aei.lookup("Prepare status reports for project managers.")
    assert fuzzy.match_method == "fuzzy_text" and 0.85 <= fuzzy.match_score < 1
    assert aei.lookup("Install network cables inside office walls.") is None
