"""FastAPI application: JSON API (stable contract for the phase-7 Next.js frontend) + accessible HTML pages."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from observatory.about.render import render_about
from observatory.api import html as H
from observatory.capabilities.dictionary import load_dictionary
from observatory.config import get_settings
from observatory.crosswalk.review import ReviewError, apply_review
from observatory.db import models as M
from observatory.db.session import make_engine, session_factory
from observatory.methodology import load_methodology, load_registry

app = FastAPI(title="AI Occupational and Curriculum Exposure Observatory", version="0.1.0")
_factory = None


def get_session():
    global _factory
    if _factory is None:
        _factory = session_factory(make_engine(get_settings().database_url))
    s = _factory()
    try:
        yield s
    finally:
        s.close()


def configure(database_url: str) -> None:
    """Point the app at another database (tests)."""
    global _factory
    _factory = session_factory(make_engine(database_url))


def require_admin(x_api_key: str | None = Header(default=None)) -> str:
    key = get_settings().admin_api_key
    if key == "change-me":
        raise HTTPException(status_code=503, detail="admin endpoints disabled: set OBS_ADMIN_API_KEY")
    if x_api_key != key:
        raise HTTPException(status_code=401, detail="admin API key required")
    return "admin"


# --------------------------------------------------------------------------- serializers
def _latest_assessment(s: Session, occ_id: int) -> M.ExposureAssessment | None:
    aid = s.scalar(select(func.max(M.ExposureAssessment.id)).where(M.ExposureAssessment.occupation_id == occ_id))
    return s.get(M.ExposureAssessment, aid) if aid else None


def _assessment_dict(a: M.ExposureAssessment, full: bool = True) -> dict:
    d = {
        "id": a.id,
        "run_id": a.run_id,
        "created_at": a.created_at.isoformat(),
        "scores": a.scores,
        "intervals": a.intervals,
        "quality": a.quality,
        "sensitivity": a.sensitivity,
        "limitations": a.limitations,
        "methodology_version": a.methodology_version,
        "methodology_fingerprint": a.methodology_fingerprint,
        "capability_version": a.capability_version,
        "embedding_model": a.embedding_model,
        "embedding_calibration": a.embedding_calibration,
        "pipeline_version": a.pipeline_version,
    }
    if full:
        d["components"] = [
            {
                "occupation_task_id": c.occupation_task_id,
                "task_id": c.occupation_task.task_id,
                "source_task_id": c.occupation_task.task.original_id,
                "statement": c.occupation_task.task.statement,
                "unit_type": c.occupation_task.task.unit_type,
                "task_weight": c.task_weight,
                "dimensions": c.dimensions,
                "dimension_sources": c.dimension_sources,
                "technical_exposure": c.technical_exposure,
                "automation_potential": c.automation_potential,
                "augmentation_potential": c.augmentation_potential,
                "transformation_potential": c.transformation_potential,
                "task_class": c.task_class,
                "confidence": c.confidence,
                "justification": c.justification,
                "matched_capabilities": c.matched_capabilities,
                "evidence": c.evidence,
                "barriers": c.barriers,
                "missing_flags": c.missing_flags,
                "raw_ratings": {
                    "importance": c.occupation_task.importance,
                    "importance_n": c.occupation_task.importance_n,
                    "importance_suppressed": c.occupation_task.importance_suppressed,
                    "relevance": c.occupation_task.relevance,
                    "frequency_distribution": c.occupation_task.frequency_distribution,
                },
            }
            for c in a.components
        ]
    return d


def _mapping_dict(mp: M.OccupationSourceMapping, perspective: int | None = None) -> dict:
    other = mp.target_occupation if perspective in (None, mp.source_occupation_id) else mp.source_occupation
    return {
        "id": mp.id,
        "source": f"{mp.source_occupation.taxonomy}:{mp.source_occupation.code}",
        "target": f"{mp.target_occupation.taxonomy}:{mp.target_occupation.code}",
        "other_taxonomy": other.taxonomy,
        "other_code": other.code,
        "other_title": other.title,
        "title_similarity": mp.title_similarity,
        "task_similarity": mp.task_similarity,
        "skill_similarity": mp.skill_similarity,
        "hierarchy_consistency": mp.hierarchy_consistency,
        "qualification_consistency": mp.qualification_consistency,
        "mapping_confidence": mp.mapping_confidence,
        "confidence_class": mp.confidence_class,
        "status": mp.status,
        "method": mp.method,
        "rules": (mp.rules_applied or {}).get("rules", []),
        "embedding_model": mp.embedding_model,
        "methodology_version": mp.methodology_version,
        "justification": mp.justification,
        "reviewer": mp.reviewer,
        "history": [
            {"action": h.action, "actor": h.actor, "justification": h.justification, "at": h.at.isoformat()}
            for h in mp.history
        ],
    }


def _occupation_dict(s: Session, o: M.Occupation, full: bool = True) -> dict:
    a = _latest_assessment(s, o.id)
    sv = o.source_version
    d = {
        "id": o.id,
        "taxonomy": o.taxonomy,
        "code": o.code,
        "title": o.title,
        "description": o.description,
        "group_code": o.group_code,
        "qualification_level": o.qualification_level,
        "attributes": o.attributes,
        "is_synthetic": o.is_synthetic,
        "source": {
            "dataset": sv.dataset.code,
            "version": sv.version,
            "source_url": sv.source_url,
            "retrieval_date": sv.retrieval_date.isoformat(),
            "retrieval_method": sv.retrieval_method,
            "file_sha256": sv.file_sha256,
            "license": sv.license.name if sv.license else None,
        },
        "scores": a.scores if a else None,
        "intervals": a.intervals if a else None,
        "quality": a.quality if a else None,
    }
    if full:
        d["aliases"] = [{"label": x.label, "language": x.language, "type": x.alias_type} for x in o.aliases]
        maps = s.scalars(
            select(M.OccupationSourceMapping).where(
                or_(
                    M.OccupationSourceMapping.source_occupation_id == o.id,
                    M.OccupationSourceMapping.target_occupation_id == o.id,
                )
            )
        ).all()
        d["crosswalks"] = [_mapping_dict(mp, o.id) for mp in maps]
        d["assessment"] = _assessment_dict(a) if a else None
        d["history"] = [
            _assessment_dict(h, full=False)
            for h in s.scalars(
                select(M.ExposureAssessment)
                .where(M.ExposureAssessment.occupation_id == o.id)
                .order_by(M.ExposureAssessment.id.desc())
            ).all()
        ]
    return d


def _search(s: Session, q: str | None, taxonomy: str | None) -> list[M.Occupation]:
    stmt = select(M.Occupation)
    if taxonomy:
        stmt = stmt.where(M.Occupation.taxonomy == taxonomy.upper())
    if q:
        like = f"%{q.lower()}%"
        alias_ids = select(M.OccupationAlias.occupation_id).where(func.lower(M.OccupationAlias.label).like(like))
        task_ids = select(M.OccupationTask.occupation_id).join(M.Task).where(func.lower(M.Task.statement).like(like))
        stmt = stmt.where(
            or_(
                func.lower(M.Occupation.title).like(like),
                func.lower(M.Occupation.code).like(like),
                M.Occupation.id.in_(alias_ids),
                M.Occupation.id.in_(task_ids),
            )
        )
    return list(s.scalars(stmt.order_by(M.Occupation.taxonomy, M.Occupation.code)).all())


def _warnings() -> list[str]:
    p = get_settings().reports_dir / "vertical_slice_latest.json"
    return json.loads(p.read_text(encoding="utf-8")).get("warnings", []) if p.exists() else []


# --------------------------------------------------------------------------- JSON API
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "methodology_version": load_methodology().version}


@app.get("/api/occupations")
def api_occupations(q: str | None = None, taxonomy: str | None = None, s: Session = Depends(get_session)) -> list:
    return [_occupation_dict(s, o, full=False) for o in _search(s, q, taxonomy)]


@app.get("/api/occupations/{occ_id}")
def api_occupation(occ_id: int, s: Session = Depends(get_session)) -> dict:
    o = s.get(M.Occupation, occ_id)
    if o is None:
        raise HTTPException(404, "occupation not found")
    return _occupation_dict(s, o)


@app.get("/api/occupations/{occ_id}/assessment")
def api_assessment(occ_id: int, s: Session = Depends(get_session)) -> dict:
    a = _latest_assessment(s, occ_id)
    if a is None:
        raise HTTPException(404, "no assessment")
    return _assessment_dict(a)


@app.get("/api/crosswalks")
def api_crosswalks(s: Session = Depends(get_session)) -> list:
    return [_mapping_dict(mp) for mp in s.scalars(select(M.OccupationSourceMapping)).all()]


class Review(BaseModel):
    action: Literal["accept", "reject", "edit", "split", "merge"]
    reviewer: str = Field(min_length=2)
    justification: str = Field(min_length=10)
    edits: dict | None = None


@app.post("/api/crosswalks/{mapping_id}/review")
def api_review(
    mapping_id: int, body: Review, s: Session = Depends(get_session), actor: str = Depends(require_admin)
) -> dict:
    mp = s.get(M.OccupationSourceMapping, mapping_id)
    if mp is None:
        raise HTTPException(404, "mapping not found")
    apply_review(s, mp, body.action, body.reviewer, body.justification, actor, body.edits, _mapping_dict(mp))
    s.commit()
    return _mapping_dict(mp)


@app.get("/api/capabilities")
def api_capabilities() -> dict:
    m = load_methodology()
    return load_dictionary(get_settings().capabilities_dir / m.capability_dictionary_file).model_dump()


@app.get("/api/methodology")
def api_methodology() -> dict:
    m = load_methodology()
    return {"version": m.version, "fingerprint": m.fingerprint, "config": m.config, "registry": load_registry()}


@app.get("/api/sources")
def api_sources(s: Session = Depends(get_session)) -> list:
    return [
        {
            "dataset": sv.dataset.code,
            "version": sv.version,
            "url": sv.source_url,
            "retrieval_date": sv.retrieval_date.isoformat(),
            "method": sv.retrieval_method,
            "sha256": sv.file_sha256,
            "license": sv.license.name if sv.license else None,
            "notes": sv.notes,
            "is_synthetic": sv.is_synthetic,
        }
        for sv in s.scalars(select(M.SourceVersion)).all()
    ]


@app.get("/api/about")
def api_about(lang: str = Query("pt-BR")) -> dict:
    return render_about(lang)


@app.get("/figures/{version}/{name}")
def figure(version: str, name: str):
    base = (get_settings().figures_dir / version).resolve()
    path = (base / name).resolve()
    if base not in path.parents or not path.exists() or path.suffix not in (".svg", ".mmd", ".json"):
        raise HTTPException(404)
    return FileResponse(path, media_type="image/svg+xml" if path.suffix == ".svg" else "text/plain")


# --------------------------------------------------------------------------- HTML
@app.get("/", response_class=HTMLResponse)
def page_home(q: str | None = None, lang: str = "pt-BR", s: Session = Depends(get_session)) -> str:
    occs = [_occupation_dict(s, o, full=False) for o in _search(s, q, None)]
    return H.layout(H.t(lang)["app_name"], H.home(occs, _warnings(), lang, q or ""), lang)


@app.get("/occupations/{occ_id}", response_class=HTMLResponse)
def page_occupation(occ_id: int, lang: str = "pt-BR", s: Session = Depends(get_session)) -> str:
    o = s.get(M.Occupation, occ_id)
    if o is None:
        raise HTTPException(404, "occupation not found")
    return H.layout(o.title, H.occupation_page(_occupation_dict(s, o), lang), lang)


def _review_groups(s: Session) -> list[dict]:
    m = load_methodology()
    margin_cfg = m.config["crosswalk"]["candidates"]["ambiguity_margin"]
    maps = s.scalars(
        select(M.OccupationSourceMapping).where(M.OccupationSourceMapping.methodology_version == m.version)
    ).all()
    groups: dict[tuple[str, str], dict] = {}
    for mp in maps:
        src = mp.source_occupation
        g = groups.setdefault(
            (src.taxonomy, src.code),
            {"source": {"id": src.id, "taxonomy": src.taxonomy, "code": src.code, "title": src.title}, "mappings": []},
        )
        d = _mapping_dict(mp, src.id)
        d["target_id"] = mp.target_occupation_id
        d["target_assessed"] = _latest_assessment(s, mp.target_occupation_id) is not None
        d["official"] = (mp.rules_applied or {}).get("official", {})
        g["mappings"].append(d)
    order = {"ESCO": 0, "CBO": 1}
    out = []
    for key in sorted(groups, key=lambda k: (order.get(k[0], 9), k[1])):
        g = groups[key]
        g["mappings"].sort(key=lambda x: -x["mapping_confidence"])
        live = [x for x in g["mappings"] if x["status"] != "rejected" and x["other_taxonomy"] == "ONET"]
        g["margin"] = round(live[0]["mapping_confidence"] - live[1]["mapping_confidence"], 4) if len(live) > 1 else None
        g["ambiguous"] = g["margin"] is not None and g["margin"] < margin_cfg
        out.append(g)
    return out


@app.get("/crosswalks", response_class=HTMLResponse)
def page_crosswalks(lang: str = "pt-BR", msg: str | None = None, s: Session = Depends(get_session)) -> str:
    return H.layout(H.t(lang)["review_title"], H.review_page(_review_groups(s), lang, msg), lang)


@app.post("/crosswalks/{mapping_id}/review", response_class=HTMLResponse)
async def page_review(mapping_id: int, request: Request, lang: str = "pt-BR", s: Session = Depends(get_session)):
    form = await request.form()
    key = get_settings().admin_api_key
    status_code, message = 200, None
    mp = s.get(M.OccupationSourceMapping, mapping_id)
    if mp is None:
        status_code, message = 404, "mapping not found"
    elif key == "change-me":
        status_code, message = 503, "admin endpoints disabled: set OBS_ADMIN_API_KEY"
    elif form.get("api_key") != key:
        status_code, message = 401, "chave administrativa inválida / invalid admin key"
    else:
        try:
            apply_review(
                s,
                mp,
                str(form.get("action", "")),
                str(form.get("reviewer", "")),
                str(form.get("justification", "")),
                "admin:review-page",
                None,
                _mapping_dict(mp),
            )
            s.commit()
            q = "&lang=en" if lang == "en" else ""
            return RedirectResponse(f"/crosswalks?msg=mapping+{mapping_id}+{mp.status}{q}#m{mapping_id}", 303)
        except ReviewError as exc:
            s.rollback()
            status_code, message = 400, str(exc)
    body = H.review_page(_review_groups(s), lang, message, error=True)
    return HTMLResponse(H.layout(H.t(lang)["review_title"], body, lang), status_code=status_code)


@app.get("/about", response_class=HTMLResponse)
def page_about(lang: str = "pt-BR") -> str:
    return H.layout(H.t(lang)["about"], H.about_page(render_about(lang), lang), lang, mermaid=True)
