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
NULLS = [
    ["Feed livestock and clean stalls"],
    ["Repair roof shingles"],
    ["Cook meals for guests"],
    ["Drive buses on city routes"],
    ["Cut and style hair"],
    ["Harvest crops by hand"],
    ["Paint walls of buildings"],
    ["Weld steel beams"],
    ["Sing in a choir"],
    ["Guard museum entrances"],
]


def test_identical_occupations_score_high_but_are_never_auto_accepted():
    p = propose(
        side("a", ["software developer"], TASKS, "ESCO"),
        side("b", ["software developer"], TASKS),
        EMB,
        CAL,
        CFG,
        null_tasks=NULLS,
    )
    assert p.task_similarity == 1.0 and p.status == "proposed" and p.details["auto_accept"] is False


def test_set_similarity_without_null_sample_is_unknown_not_saturated():
    """Regression: CBO→ESCO had no null sample and the old fallback reported task_similarity = 1.0."""
    p = propose(side("a", ["x"], TASKS, "CBO"), side("b", ["x"], TASKS, "ESCO"), EMB, CAL, CFG)
    assert p.task_similarity is None and "task_similarity" in p.details["unknown_components"]
    assert p.details["null"]["tasks"]["n_null"] == 0


def test_title_match_alone_cannot_reach_moderate():
    """False friend: same title, unrelated tasks → must stay below the acceptance threshold."""
    p = propose(
        side("a", ["engineer"], ["Drive locomotives on rail lines", "Inspect train brakes"], "ESCO"),
        side("b", ["engineer"], ["Write computer programs", "Design database schemas"]),
        EMB,
        CAL,
        CFG,
        null_tasks=NULLS,
    )
    assert p.title_similarity == 1.0
    assert p.confidence_class == "not_accepted_automatically"


def test_unknown_components_are_neutral_and_reported():
    p = propose(side("a", ["x"], TASKS, "ESCO", q=None), side("b", ["x"], TASKS), EMB, CAL, CFG)
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
        side("a", ["x"], TASKS, "ESCO", group="2512"), side("b", ["x"], TASKS, group="15-1252"), EMB, CAL, CFG, off
    )
    bad = propose(
        side("a", ["x"], TASKS, "ESCO", group="2512"), side("b", ["x"], TASKS, group="47-2111"), EMB, CAL, CFG, off
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


def test_official_esco_lookup_requires_code_and_title():
    off = OfficialCodeCrosswalk(
        esco_onet={
            ("2512.4", "software developer"): {"15-1252.00", "15-1251.00"},
            ("2512.3", "software architect"): {"15-1299.08"},
        }
    )
    # same code, different title (ESCO renumbering): must NOT take the architect row
    targets, how = off.esco_targets("2512.3", "software developer")
    assert targets == {"15-1252.00", "15-1251.00"} and how.startswith("esco_title_within_isco_group")
    assert off.esco_targets("2512.4", "software developer")[1] == "esco_code_and_title"
    assert off.esco_targets("9999.1", "software developer") == (None, "no_official_entry")


def test_official_membership_sets_hierarchy():
    off = OfficialCodeCrosswalk(esco_onet={("2512.4", "software developer"): {"15-1252.00"}})
    a = CrosswalkSide("ESCO:x", "ESCO", ["software developer"], "en", TASKS, [], "2512", 1.0, "2512.3")
    inside = CrosswalkSide(
        "ONET:15-1252.00", "ONET", ["Software Developers"], "en", TASKS, [], "15-1252", 1.0, "15-1252.00"
    )
    outside = CrosswalkSide(
        "ONET:47-2111.00", "ONET", ["Electricians"], "en", TASKS, [], "47-2111", 1 / 3, "47-2111.00"
    )
    assert propose(a, inside, EMB, CAL, CFG, off).hierarchy_consistency == 1.0
    assert propose(a, outside, EMB, CAL, CFG, off).hierarchy_consistency == 0.0


def test_set_similarity_is_normal_cdf_of_z():
    p = propose(side("a", ["x"], TASKS, "ESCO"), side("b", ["x"], TASKS), EMB, CAL, CFG, null_tasks=NULLS)
    z = p.details["null"]["tasks"]["z"]
    assert z > 2 and p.task_similarity > 0.97
    unrelated = propose(
        side("a", ["x"], ["Unrelated synthetic duty number 3"], "ESCO"),
        side("b", ["x"], TASKS),
        EMB,
        CAL,
        CFG,
        null_tasks=NULLS,
    )
    assert unrelated.task_similarity < p.task_similarity


def test_relative_factor_separates_neighbours_from_the_best():
    """Phi(z) alone saturates for every related candidate; the factor relative to the best restores ranking."""
    nulls = NULLS
    src = side("a", ["x"], TASKS, "ESCO")
    best = side("b", ["x"], TASKS)
    near = side("c", ["x"], ["Write computer programs", "Prepare budgets", "Clean offices"])
    p_best = propose(src, best, EMB, CAL, CFG, null_tasks=nulls)
    p_near = propose(src, near, EMB, CAL, CFG, null_tasks=nulls)
    ref = {"tasks": max(p_best.details["null"]["tasks"]["raw"], p_near.details["null"]["tasks"]["raw"])}
    r_best = propose(src, best, EMB, CAL, CFG, null_tasks=nulls, reference_raw=ref)
    r_near = propose(src, near, EMB, CAL, CFG, null_tasks=nulls, reference_raw=ref)
    assert r_best.details["null"]["tasks"]["relative_to_best"] == 1.0
    assert r_near.task_similarity < r_best.task_similarity
    assert r_near.details["null"]["tasks"]["relative_to_best"] < 1.0


def test_candidate_search_ranks_and_flags_ambiguity(tmp_path):
    from fixtures.synthetic import build
    from observatory.connectors.onet import OnetArchive
    from observatory.crosswalk.candidates import OnetIndex, search

    onet = OnetArchive(build.build_onet_zip(tmp_path / "onet.zip"))
    index = OnetIndex(onet, EMB)
    src = side("ESCO:s", ["Occupation 99-0001.00"], [t for _, t in build.TASKS], "ESCO")
    found = search(src, index, CAL, CFG, None)
    confs = [p.mapping_confidence for p in found.ranked]
    assert confs == sorted(confs, reverse=True) and len(found.ranked) >= 2
    # the synthetic occupations share near-identical tasks, so the best match cannot be told apart
    assert found.ambiguous is (found.margin < CFG["crosswalk"]["candidates"]["ambiguity_margin"])
    assert set(found.candidate_origin.values()) == {"embedding_prefilter"}
