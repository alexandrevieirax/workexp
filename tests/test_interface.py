"""i18n, accessibility, traceability and export checks on the API/HTML built from a SYNTHETIC slice."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from observatory.about.render import load_content, section_ids
from observatory.api.i18n import STRINGS


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def _parse(html: str) -> list[tuple[str, dict]]:
    c = _Collector()
    c.feed(html)
    return c.tags


# ------------------------------------------------------------------ i18n
def test_ui_strings_have_same_keys_in_all_languages():
    keys = [set(v) for v in STRINGS.values()]
    assert all(k == keys[0] for k in keys)


def test_about_sections_aligned_across_languages():
    assert section_ids(load_content("pt-BR")[1]) == section_ids(load_content("en")[1])


def test_language_switch(client):
    assert '<html lang="en">' in client.get("/?lang=en").text
    assert "Assessed occupations" in client.get("/?lang=en").text
    assert '<html lang="pt-BR">' in client.get("/").text


# ------------------------------------------------------------------ accessibility
def test_pages_are_accessible(client):
    occ_id = client.get("/api/occupations").json()[0]["id"]
    for url in ["/", f"/occupations/{occ_id}", "/about"]:
        html = client.get(url).text
        tags = _parse(html)
        assert sum(1 for t, _ in tags if t == "h1") == 1, url
        assert any(t == "a" and a.get("class") == "skip" for t, a in tags), url
        assert all(a.get("alt") for t, a in tags if t == "img"), url
        assert all(a.get("scope") for t, a in tags if t == "th"), url
        assert 'role="note"' in html  # disclaimer always present


# ------------------------------------------------------------------ traceability
def test_every_result_is_traceable(client, slice_run):
    _, report = slice_run
    for occ in client.get("/api/occupations").json():
        full = client.get(f"/api/occupations/{occ['id']}").json()
        assert full["is_synthetic"] is True
        src = full["source"]
        assert src["version"] and src["retrieval_date"] and src["retrieval_method"] and src["license"]
        a = full["assessment"]
        assert a["methodology_version"] == report.methodology["version"]
        assert len(a["methodology_fingerprint"]) == 64
        assert a["pipeline_version"]["source_tree_sha256"]
        assert a["embedding_model"] and a["embedding_calibration"]["floor"] is not None
        for c in a["components"]:
            assert c["justification"] and c["dimension_sources"]["E1"]["model"] == a["embedding_model"]
            assert set(c["dimensions"]) >= {f"E{i}" for i in range(1, 15)}
            assert c["dimension_sources"]["weight"]["method"]


def test_report_records_sources_and_warnings(slice_run):
    _, report = slice_run
    assert {"ONET", "ESCO", "CBO", "AEI"} <= set(report.sources)
    assert all(v["status"] == "loaded" for v in report.sources.values())
    assert any("lexical baseline" in w for w in report.warnings)


def test_esco_without_strong_crosswalk_does_not_inherit_priors(slice_run):
    _, report = slice_run
    esco = report.occupations["ESCO"]["quality"]
    cw = next(c for c in report.crosswalks if c["source"].startswith("ESCO") and c["target"].startswith("ONET"))
    if cw["confidence_class"] in ("strong", "very_strong"):
        assert esco["prior_source"] == "crosswalk_transfer"
    else:
        assert esco["prior_source"] == "default"


# ------------------------------------------------------------------ export
def test_json_export_contains_components_and_provenance(client):
    occ_id = client.get("/api/occupations?taxonomy=ONET").json()[0]["id"]
    exp = client.get(f"/api/occupations/{occ_id}/assessment").json()
    assert exp["components"] and exp["intervals"]["OAE"] and exp["sensitivity"]["one_at_a_time"]
    assert all("raw_ratings" in c for c in exp["components"])


def test_search_by_code_synonym_and_task(client):
    assert client.get("/api/occupations?q=99-0001").json()
    assert client.get("/api/occupations?q=sinônimo").json()  # CBO synonym
    assert client.get("/api/occupations?q=network cables").json()  # task text


def test_figures_are_generated_versioned_and_described(client, synthetic_env):
    from observatory.about.figures import build_figures

    manifest = build_figures()
    assert manifest["methodology_version"] == "0.1.0"
    for name in (
        "flow",
        "relation",
        "er",
        "calculation",
        "automation_augmentation",
        "sensitivity",
        "uncertainty",
        "crosswalk",
    ):
        f = manifest["figures"][name]
        assert f["alt"] and f["caption"] and len(f["sha256"]) == 64
    html = client.get("/about").text
    assert re.search(r'<img src="/figures/0\.1\.0/calculation\.svg" alt="[^"]+"', html)
    assert client.get("/figures/0.1.0/calculation.svg").status_code == 200
    assert client.get("/figures/0.1.0/..%2F..%2Fobs.sqlite").status_code == 404
