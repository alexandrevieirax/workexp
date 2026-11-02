"""Human crosswalk review: admin key setup, HTML page, form validation, audit trail and later runs."""

from __future__ import annotations

from fixtures.synthetic import build
from observatory.config import Settings, env_file_encoding, get_settings, write_admin_key
from observatory.db import models as M
from observatory.db.session import make_engine, session_factory

KEY = "test-key-long-enough-123"


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
        "mapping_id": str(mid),
        "action": "accept",
        "reviewer": "Especialista Teste",
        "justification": "Equivalente pelas tarefas centrais.",
        "api_key": KEY,
    } | form
    return client.post("/crosswalks/review", data=data, follow_redirects=False)


# ------------------------------------------------------------------ admin key
def test_env_written_by_powershell_utf16_is_read(tmp_path):
    env = tmp_path / ".env"
    env.write_text(f"OBS_ADMIN_API_KEY={KEY}\n", encoding="utf-16")  # what `echo ... >> .env` does in PowerShell
    assert env_file_encoding(env) == "utf-16"
    s = Settings(_env_file=env, _env_file_encoding=env_file_encoding(env))
    assert s.admin_api_key == KEY and s.admin_key_configured


def test_placeholder_or_short_keys_are_not_accepted():
    for k in ("change-me", "troque-por-uma-chave-longa", "curta"):
        assert not Settings(_env_file=None, admin_api_key=k).admin_key_configured


def test_admin_key_writer_keeps_other_lines_and_uses_utf8(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OBS_DATABASE_URL=sqlite://\nOBS_ADMIN_API_KEY=troque-por-uma-chave-longa\n", encoding="utf-16")
    write_admin_key(KEY, env)
    text = env.read_bytes().decode("utf-8")
    assert text == f"OBS_DATABASE_URL=sqlite://\nOBS_ADMIN_API_KEY={KEY}\n"


# ------------------------------------------------------------------ page
def test_page_asks_a_clear_question_with_one_form_per_occupation(client):
    html = client.get("/crosswalks").text
    assert "Qual ocupação do O*NET é a equivalente de" in html
    assert "Sugestão automática" in html and "Por quê:" in html
    assert html.count('action="/crosswalks/review"') == 2  # ESCO and CBO, one form each
    assert "<legend>1. Escolha a ocupação O*NET</legend>" in html and 'type="password"' in html
    assert "Chave administrativa configurada" in html


def test_page_explains_how_to_create_the_key_when_missing(client, monkeypatch):
    monkeypatch.setenv("OBS_ADMIN_API_KEY", "troque-por-uma-chave-longa")
    get_settings.cache_clear()
    html = client.get("/crosswalks").text
    assert "python -m observatory.cli admin-key" in html and "desativada" in html
    mid = _esco_mappings(client)[0]["id"]
    r = _post(client, mid, api_key="troque-por-uma-chave-longa")
    assert r.status_code == 503 and "admin-key" in r.text


def test_validation_messages_are_specific_and_keep_typed_values(client):
    mid = _esco_mappings(client)[0]["id"]
    r = _post(client, mid, api_key="wrong")
    assert r.status_code == 401 and "Chave administrativa incorreta" in r.text
    r = _post(client, mid, justification="curta")
    assert r.status_code == 400 and "pelo menos 10 caracteres" in r.text
    assert 'value="Especialista Teste"' in r.text  # the reviewer does not have to type it again
    r = client.post("/crosswalks/review", data={"api_key": KEY, "reviewer": "x" * 3, "justification": "y" * 12})
    assert r.status_code == 400 and "Escolha uma ocupação candidata" in r.text
    assert all(m["status"] == "proposed" for m in _esco_mappings(client))


# ------------------------------------------------------------------ decisions
def test_accept_is_recorded_and_honoured_by_the_next_run(client):
    target = _esco_mappings(client)[-1]  # deliberately not the automatic best
    r = _post(client, target["id"])
    assert r.status_code == 303 and r.headers["location"].startswith("/crosswalks?msg=")
    m = next(x for x in _esco_mappings(client) if x["id"] == target["id"])
    assert m["status"] == "accepted" and m["reviewer"] == "Especialista Teste"
    assert [h["action"] for h in m["history"]][-1] == "accept"
    assert "Decisão registrada" in client.get(r.headers["location"]).text
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


def test_recommendation_prefers_officially_confirmed_candidates():
    from observatory.api.app import recommend

    cands = [
        {
            "id": 1,
            "mapping_confidence": 0.880,
            "official": {"votes": {"a": 1.0, "b": 0.0}},
            "qualification_consistency": 0.67,
        },
        {
            "id": 2,
            "mapping_confidence": 0.878,
            "official": {"votes": {"a": 1.0, "b": 1.0}},
            "qualification_consistency": 1.0,
        },
        {
            "id": 3,
            "mapping_confidence": 0.700,
            "official": {"votes": {"a": 1.0, "b": 1.0}},
            "qualification_consistency": 1.0,
        },
    ]
    assert recommend(cands, 0.06)["id"] == 2  # within the window, confirmed by both sources
    assert recommend(cands, 0.0)["id"] == 1  # no tie window → the best one


def test_decision_is_carried_to_a_new_mapping_row(client):
    from observatory.crosswalk.review import carry_decision, human_decisions

    target = _esco_mappings(client)[0]
    _post(client, target["id"])
    s = session_factory(make_engine(get_settings().database_url))()
    orig = s.get(M.OccupationSourceMapping, target["id"])
    decided = human_decisions(s, "ESCO", orig.source_occupation.code)
    assert decided[target["other_code"]].status == "accepted"
    fresh = M.OccupationSourceMapping(
        source_occupation_id=orig.source_occupation_id,
        target_occupation_id=orig.target_occupation_id,
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
