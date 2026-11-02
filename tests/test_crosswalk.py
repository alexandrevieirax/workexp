from __future__ import annotations

from observatory.crosswalk.engine import CrosswalkSide, OfficialCodeCrosswalk, classify, propose
from observatory.embeddings.providers import Embedder, HashingBaselineProvider
from observatory.exposure.dimensions import Calibration
from observatory.methodology import load_methodology

CFG = load_methodology().config
EMB = Embedder(HashingBaselineProvider())
CAL = Calibration("baseline", 0.1, 0.5, "test", 1, 1)


def side(ref, titles, tasks, tax="ONET", group=None, q=0.75, lang="en"):
    return CrosswalkSide(ref, tax, titles, lang, tasks, [], group, q)


TASKS = ["Write computer programs from specifications", "Test software and fix defects", "Prepare reports"]


def test_identical_occupations_score_high_but_are_never_auto_accepted():
    p = propose(
        side("a", ["software developer"], TASKS, "ESCO"), side("b", ["software developer"], TASKS), EMB, CAL, CAL, CFG
    )
    assert p.task_similarity == 1.0 and p.status == "proposed" and p.details["auto_accept"] is False


def test_title_match_alone_cannot_reach_moderate():
    """False friend: same title, unrelated tasks → must stay below the acceptance threshold."""
    p = propose(
        side("a", ["engineer"], ["Drive locomotives on rail lines", "Inspect train brakes"], "ESCO"),
        side("b", ["engineer"], ["Write computer programs", "Design database schemas"]),
        EMB,
        CAL,
        CAL,
        CFG,
        null_tasks=[[f"Unrelated synthetic duty number {i}"] for i in range(10)],
    )
    assert p.title_similarity == 1.0
    assert p.confidence_class == "not_accepted_automatically"


def test_unknown_components_are_neutral_and_reported():
    p = propose(side("a", ["x"], TASKS, "ESCO", q=None), side("b", ["x"], TASKS), EMB, CAL, CAL, CFG)
    assert p.qualification_consistency is None and p.hierarchy_consistency is None
    assert set(p.details["unknown_components"]) >= {
        "qualification_consistency",
        "hierarchy_consistency",
        "skill_similarity",
    }
    assert any("unknown" in r for r in p.rules_applied)


def test_official_table_drives_hierarchy():
    off = OfficialCodeCrosswalk({("ISCO08", "2512", "SOC2018", "15-1252")}, ["synthetic.csv"])
    ok = propose(
        side("a", ["x"], TASKS, "ESCO", group="2512"), side("b", ["x"], TASKS, group="15-1252"), EMB, CAL, CAL, CFG, off
    )
    bad = propose(
        side("a", ["x"], TASKS, "ESCO", group="2512"), side("b", ["x"], TASKS, group="47-2111"), EMB, CAL, CAL, CFG, off
    )
    assert ok.hierarchy_consistency == 1.0 and bad.hierarchy_consistency == 0.0


def test_confidence_classes():
    classes = CFG["crosswalk"]["classes"]
    assert classify(0.95, classes) == "very_strong"
    assert classify(0.80, classes) == "strong"
    assert classify(0.65, classes) == "moderate"
    assert classify(0.59, classes) == "not_accepted_automatically"


def test_review_requires_key_and_records_history(client):
    maps = client.get("/api/crosswalks").json()
    assert maps and all(m["status"] == "proposed" for m in maps)
    mid = maps[0]["id"]
    body = {"action": "accept", "reviewer": "Especialista Teste", "justification": "Revisão sintética de teste."}
    assert client.post(f"/api/crosswalks/{mid}/review", json=body).status_code == 401
    r = client.post(f"/api/crosswalks/{mid}/review", json=body, headers={"x-api-key": "test-key"})
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    actions = [h["action"] for h in r.json()["history"]]
    assert actions == ["create", "accept"]
    short = {"action": "reject", "reviewer": "x", "justification": "curta"}
    assert (
        client.post(f"/api/crosswalks/{mid}/review", json=short, headers={"x-api-key": "test-key"}).status_code == 422
    )
