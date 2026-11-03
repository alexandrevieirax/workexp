"""Benchmark annotation: blinding, storage, agreement statistics, gold export and pages."""

from __future__ import annotations

import json

import pytest

from observatory.benchmark.metrics import load_benchmark
from observatory.capabilities.dictionary import load_dictionary
from observatory.config import get_settings
from observatory.db import models as M
from observatory.db.session import create_schema, make_engine, session_factory
from observatory.embeddings.providers import Embedder, HashingBaselineProvider
from observatory.exposure.dimensions import CapabilityIndex
from observatory.validation import annotation as A


@pytest.fixture(scope="module")
def tasks():
    _, items = load_benchmark(get_settings().validation_dir / "benchmark_v0.1.0.jsonl")
    index = CapabilityIndex(load_dictionary(), Embedder(HashingBaselineProvider()))
    return A.prepare_tasks(index, items, 1.0, top_k=3)


@pytest.fixture
def session():
    engine = make_engine("sqlite://")
    create_schema(engine)
    s = session_factory(engine)()
    yield s
    s.close()


def test_krippendorff_alpha_known_values():
    assert A.krippendorff_alpha_interval([[2, 2], [0, 0], [1, 1]]) == pytest.approx(1.0)
    assert A.krippendorff_alpha_interval([[2, 0], [0, 2]]) < 0
    assert A.krippendorff_alpha_interval([[2]]) is None  # nothing pairable
    assert A.interpret(0.85) == "reliable" and A.interpret(0.7) == "tentative" and A.interpret(0.3) == "unreliable"


def test_tasks_are_blinded_complete_and_deterministic(tasks):
    t = tasks["tasks"][0]
    assert set(t["draft"]) <= set(t["pairs"]) and set(t["model_top"]) <= set(t["pairs"])
    assert len(tasks["tasks"]) == 36
    _, items = load_benchmark(get_settings().validation_dir / "benchmark_v0.1.0.jsonl")
    again = A.prepare_tasks(CapabilityIndex(load_dictionary(), Embedder(HashingBaselineProvider())), items, 1.0)
    assert [x["pairs"] for x in again["tasks"]] == [x["pairs"] for x in tasks["tasks"]]


def test_save_validates_and_replaces(session, tasks):
    t = tasks["tasks"][0]
    caps = t["pairs"]
    with pytest.raises(A.AnnotationError):
        A.save_annotation(session, "x", t, {caps[0]: 2})  # name too short
    with pytest.raises(A.AnnotationError):
        A.save_annotation(session, "ai_draft", t, {caps[0]: 2})  # reserved
    with pytest.raises(A.AnnotationError):
        A.save_annotation(session, "Ana", t, {"Z.99": 2})  # not in item
    with pytest.raises(A.AnnotationError):
        A.save_annotation(session, "Ana", t, {c: None for c in caps})  # only "não sei"
    assert A.save_annotation(session, "Ana", t, {caps[0]: 2, caps[1]: None}) == 1  # "não sei" not stored
    A.save_annotation(session, "Ana", t, {caps[0]: 0, caps[1]: 1})  # replaces previous answers
    rows = session.query(M.ValidationSample).filter_by(annotator="Ana").all()
    assert sorted((r.right_ref, r.label) for r in rows) == sorted([(caps[0], 0), (caps[1], 1)])
    assert all(r.item_id == t["item_id"] and not r.is_gold for r in rows)


def test_agreement_and_gold(session, tasks, tmp_path):
    t1, t2 = tasks["tasks"][:2]
    for who, shift in (("Ana", 0), ("Bruno", 0), ("Carla", 1)):
        for t in (t1, t2):
            labels = {c: min(2, t["draft"].get(c, 0) + (shift if i == 0 else 0)) for i, c in enumerate(t["pairs"])}
            A.save_annotation(session, who, t, labels)
    stats = A.agreement(session, tasks)
    assert stats["annotators"] == ["Ana", "Bruno", "Carla"]
    ab = next(p for p in stats["pairwise"] if p["a"] == "Ana" and p["b"] == "Bruno")
    assert ab["kappa"] == pytest.approx(1.0)
    assert stats["krippendorff_alpha"] > 0.8 and stats["items_annotated"] == 2
    ana = next(v for v in stats["vs_ai_draft"] if v["annotator"] == "Ana")
    assert ana["kappa"] == pytest.approx(1.0)
    out = A.build_gold(session, tasks, tmp_path / "gold.jsonl")
    lines = [json.loads(x) for x in (tmp_path / "gold.jsonl").read_text(encoding="utf-8").splitlines()]
    assert out["items"] == 2 and lines[0]["_meta"] and all(x["is_gold"] for x in lines[1:])
    first = lines[1]
    assert set(first["relevance"]) | set(first["unrelated"]) == set(t1["pairs"])  # median of 3 annotators


def test_annotation_pages(client):
    intro = client.get("/annotations").text
    assert "Anotação do benchmark" in intro and 'name="annotator"' in intro
    assert client.get("/annotations?annotator=x").status_code == 400
    page = client.get("/annotations?annotator=Ana Teste").text
    assert "0/36" in page and 'value="na"' in page and "Não sei" in page
    tasks = A.load_tasks(get_settings().validation_dir / "annotation_tasks_v0.1.0.json")
    t = tasks["tasks"][0]
    assert t["text"] in page
    for cap, grade in t["draft"].items():  # the AI draft grade is never shown next to the pair
        assert f'name="label_{cap}" value="{grade}" checked' not in page
    form = {"annotator": "Ana Teste", "item_id": t["item_id"]} | {f"label_{c}": "2" for c in t["pairs"]}
    r = client.post("/annotations", data=form, follow_redirects=False)
    assert r.status_code == 303
    assert "1/36" in client.get(r.headers["location"]).text
    bad = {"annotator": "Ana Teste", "item_id": t["item_id"]} | {f"label_{c}": "na" for c in t["pairs"]}
    assert client.post("/annotations", data=bad).status_code == 400
    agree = client.get("/annotations/agreement").text
    assert "Ana Teste" in agree and "Krippendorff" in agree
    skipped = client.get(f"/annotations?annotator=Ana Teste&skip={tasks['tasks'][1]['item_id']}").text
    assert tasks["tasks"][2]["text"] in skipped


def test_claude_page_is_blind_and_self_contained(tasks):
    caps = {
        c.capability_id: {"name": c.name, "definition": c.definition, "examples": c.examples}
        for c in load_dictionary().capabilities
    }
    html = A.render_page(tasks, caps)
    assert "/*__DATA__*/" not in html and "<title>" in html
    data = json.loads(html.split('<script id="data" type="application/json">')[1].split("</script>")[0])
    assert len(data["tasks"]) == 36
    assert all(set(t) == {"item_id", "text", "language", "pairs"} for t in data["tasks"])  # no draft, no model_top
    assert {r["path"] for r in A.PAGE_DB_RULES} == {"annotations", "annotations/{self}"}
    assert next(r for r in A.PAGE_DB_RULES if r["path"] == "annotations")["write"] == "self"


def test_import_remote_annotations(session, tasks):
    t1, t2 = tasks["tasks"][:2]
    docs = {
        "u_bbb": {"items": {t1["item_id"]: {"labels": {c: 2 for c in t1["pairs"]}, "comment": "ok"}}},
        "u_aaa": {
            "items": {
                t1["item_id"]: {"labels": {c: -1 for c in t1["pairs"]}},  # only "não sei": skipped
                t2["item_id"]: {"labels": {t2["pairs"][0]: 0, t2["pairs"][1]: -1}},
                "tc-unknown": {"labels": {"A.01": 2}},
            }
        },
    }
    assert A.import_remote(session, tasks, docs) == {"claude.ai anotador 1": 1, "claude.ai anotador 2": 1}
    rows = session.query(M.ValidationSample).filter_by(annotator="claude.ai anotador 1").all()
    assert [(r.item_id, r.right_ref, r.label) for r in rows] == [(t2["item_id"], t2["pairs"][0], 0)]
    assert A.import_remote(session, tasks, docs)  # idempotent re-import replaces, never duplicates
    assert session.query(M.ValidationSample).filter_by(annotator="claude.ai anotador 2").count() == len(t1["pairs"])
