"""Human crosswalk review: HTML page, form validation, audit trail and decisions honoured by later runs."""

from __future__ import annotations

from fixtures.synthetic import build
from observatory.config import get_settings
from observatory.db import models as M
from observatory.db.session import make_engine, session_factory


def _rerun():
    from observatory.pipeline.vertical_slice import SliceConfig, run

    return run(
        SliceConfig(
            onet_code=build.ONET_CODE,
            onet_version="99.0",
            esco_uri=build.ESCO_URI,
            cbo_code="999901",
            aei_release="release_synthetic",
            offline=True,
            provider="baseline",
        )
    )


def _esco_mappings(client):
    return [
        m
        for m in client.get("/api/crosswalks").json()
        if m["source"].startswith("ESCO") and m["target"].startswith("ONET")
    ]


def _post(client, mid, **form):
    data = {
        "reviewer": "Especialista Teste",
        "justification": "Equivalente pelas tarefas centrais.",
        "api_key": "test-key",
        "action": "accept",
    } | form
    return client.post(f"/crosswalks/{mid}/review", data=data, follow_redirects=False)


def test_review_page_lists_candidates_with_accessible_forms(client):
    html = client.get("/crosswalks").text
    assert "<h1>Revisão humana dos crosswalks</h1>" in html
    mid = _esco_mappings(client)[0]["id"]
    for field in ("r", "j", "k"):
        assert f'<label for="{field}{mid}">' in html and f'id="{field}{mid}"' in html
    assert 'type="password"' in html and 'value="accept"' in html and 'value="reject"' in html
    assert "Crosswalk review" in client.get("/crosswalks?lang=en").text


def test_review_requires_valid_key_and_justification(client):
    mid = _esco_mappings(client)[0]["id"]
    assert _post(client, mid, api_key="wrong").status_code == 401
    assert _post(client, mid, justification="curta").status_code == 400
    assert next(m for m in _esco_mappings(client) if m["id"] == mid)["status"] == "proposed"


def test_accept_is_recorded_and_honoured_by_the_next_run(client):
    target = _esco_mappings(client)[-1]  # deliberately not the automatic best
    r = _post(client, target["id"])
    assert r.status_code == 303 and r.headers["location"].startswith("/crosswalks?msg=")
    m = next(x for x in _esco_mappings(client) if x["id"] == target["id"])
    assert m["status"] == "accepted" and m["reviewer"] == "Especialista Teste"
    assert [h["action"] for h in m["history"]][-1] == "accept"
    s = session_factory(make_engine(get_settings().database_url))()
    assert s.query(M.ExpertReview).filter_by(target_id=str(target["id"]), decision="accept").count() == 1
    assert s.query(M.AuditLog).filter_by(action="crosswalk_accept", target=f"mapping:{target['id']}").count() == 1
    s.close()

    report = _rerun()
    code = target["other_code"]
    esco = report.occupations["ESCO"]["quality"]
    assert esco["prior_source"] == "crosswalk_transfer" and esco["prior_from_occupation"] == code
    assert report.crosswalk_candidates["ESCO"]["human_decisions"] == {code: "accepted"}


def test_rejected_candidate_leaves_the_ranking(client):
    best = _esco_mappings(client)[0]
    assert _post(client, best["id"], action="reject").status_code == 303
    report = _rerun()
    ranked = [c["target"] for c in report.crosswalk_candidates["ESCO"]["candidates"]]
    assert f"ONET:{best['other_code']}" not in ranked


def test_decision_is_carried_to_a_new_mapping_row(client):
    from observatory.crosswalk.review import carry_decision, human_decisions

    target = _esco_mappings(client)[0]
    _post(client, target["id"])
    s = session_factory(make_engine(get_settings().database_url))()
    src = s.get(M.OccupationSourceMapping, target["id"]).source_occupation
    decided = human_decisions(s, "ESCO", src.code)
    assert decided[target["other_code"]].status == "accepted"
    fresh = M.OccupationSourceMapping(
        source_occupation_id=src.id,
        target_occupation_id=s.get(M.OccupationSourceMapping, target["id"]).target_occupation_id,
        method="test",
        mapping_confidence=0.5,
        confidence_class="x",
        status="proposed",
        methodology_version="test",
    )
    s.add(fresh)
    s.flush()
    carry_decision(fresh, decided[target["other_code"]], "test-run")
    assert fresh.status == "accepted" and "herdada" in fresh.justification
    assert fresh.history[-1].action == "carry"
    s.rollback()
    s.close()
