"""Idempotent persistence of parsed source records with provenance."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatory.capabilities.dictionary import CapabilityDictionary, capability_hash
from observatory.connectors.base import ParsedOccupation, ParsedTask, SourceDescriptor
from observatory.db import models as M
from observatory.methodology import Methodology
from observatory.normalization.text import NORMALIZATION_RULES, normalize_text
from observatory.provenance import sha256_text


def _prov(text: str, language: str, original_id: str | None, synthetic: bool, rules: list[str] | None = None) -> dict:
    return {
        "original_id": original_id,
        "original_text": text,
        "normalized_text": normalize_text(text),
        "language": language,
        "translation_method": "none",
        "content_hash": sha256_text(text),
        "transformation_rules": {"rules": NORMALIZATION_RULES + (rules or [])},
        "confidence": 1.0,
        "is_synthetic": synthetic,
    }


def source_version(session: Session, desc: SourceDescriptor) -> M.SourceVersion:
    ds = session.scalar(select(M.SourceDataset).where(M.SourceDataset.code == desc.dataset_code))
    if ds is None:
        ds = M.SourceDataset(
            code=desc.dataset_code, name=desc.dataset_name, publisher=desc.publisher, homepage=desc.homepage
        )
        session.add(ds)
        session.flush()
    lic = session.scalar(select(M.License).where(M.License.name == desc.license_name))
    if lic is None:
        lic = M.License(name=desc.license_name, url=desc.license_url)
        session.add(lic)
        session.flush()
    sv = session.scalar(
        select(M.SourceVersion).where(
            M.SourceVersion.dataset_id == ds.id,
            M.SourceVersion.version == desc.version,
            M.SourceVersion.file_sha256 == desc.file_sha256,
        )
    )
    if sv is None:
        sv = M.SourceVersion(
            dataset_id=ds.id,
            version=desc.version,
            source_url=desc.source_url,
            retrieval_date=desc.retrieval_date,
            retrieval_method=desc.retrieval_method,
            file_sha256=desc.file_sha256,
            license_id=lic.id,
            notes=desc.notes,
            is_synthetic=desc.is_synthetic,
        )
        session.add(sv)
        session.flush()
    return sv


def occupation(session: Session, sv: M.SourceVersion, p: ParsedOccupation) -> M.Occupation:
    occ = session.scalar(
        select(M.Occupation).where(
            M.Occupation.taxonomy == p.taxonomy, M.Occupation.code == p.code, M.Occupation.source_version_id == sv.id
        )
    )
    if occ is not None:
        return occ
    occ = M.Occupation(
        source_version_id=sv.id,
        taxonomy=p.taxonomy,
        code=p.code,
        title=p.title,
        description=p.description,
        group_code=p.group_code,
        qualification_level=p.qualification_level,
        attributes=p.attributes,
        **_prov(p.title, p.language, p.code, p.is_synthetic),
    )
    session.add(occ)
    session.flush()
    for label, lang, kind in p.aliases:
        session.add(M.OccupationAlias(occupation_id=occ.id, label=label, language=lang, alias_type=kind))
    session.flush()
    return occ


def tasks(session: Session, sv: M.SourceVersion, occ: M.Occupation, parsed: list[ParsedTask]) -> list[M.OccupationTask]:
    existing = {ot.task.original_id: ot for ot in occ.tasks}
    out = []
    for t in parsed:
        if t.original_id in existing:
            out.append(existing[t.original_id])
            continue
        task = M.Task(
            source_version_id=sv.id,
            unit_type=t.unit_type,
            statement=t.statement,
            task_type=t.task_type,
            attributes=t.attributes,
            **_prov(t.statement, t.language, t.original_id, occ.is_synthetic),
        )
        session.add(task)
        session.flush()
        r = t.ratings
        ft = r.get("FT", {})
        ot = M.OccupationTask(
            occupation_id=occ.id,
            task_id=task.id,
            importance=r.get("IM", {}).get("value"),
            importance_n=r.get("IM", {}).get("n"),
            importance_se=r.get("IM", {}).get("se"),
            importance_ci_low=r.get("IM", {}).get("ci_low"),
            importance_ci_high=r.get("IM", {}).get("ci_high"),
            importance_suppressed=r.get("IM", {}).get("suppressed"),
            relevance=r.get("RT", {}).get("value"),
            relevance_n=r.get("RT", {}).get("n"),
            relevance_suppressed=r.get("RT", {}).get("suppressed"),
            frequency_distribution={c: v["value"] for c, v in ft.items()} or None,
            frequency_suppressed=any(v["suppressed"] for v in ft.values()) if ft else None,
        )
        session.add(ot)
        session.flush()
        ot.task = task
        out.append(ot)
    return out


def descriptors(session: Session, occ: M.Occupation, rows: list[dict]) -> int:
    if session.scalar(
        select(M.OccupationDescriptorValue.id).where(M.OccupationDescriptorValue.occupation_id == occ.id).limit(1)
    ):
        return 0
    for r in rows:
        session.add(M.OccupationDescriptorValue(occupation_id=occ.id, **{k: v for k, v in r.items() if k != "file"}))
    session.flush()
    return len(rows)


def esco_skills(session: Session, sv: M.SourceVersion, occ: M.Occupation, skills: list[dict]) -> int:
    if session.scalar(select(M.OccupationSkill.id).where(M.OccupationSkill.occupation_id == occ.id).limit(1)):
        return 0
    for s in skills:
        stype = (s["skill_type"] or "").rsplit("/", 1)[-1]
        if stype == "knowledge":
            session.add(
                M.Knowledge(
                    source_version_id=sv.id,
                    taxonomy="ESCO",
                    label=s["title_en"],
                    **_prov(s["title_en"], "en", s["uri"], occ.is_synthetic),
                )
            )
            continue
        sk = M.Skill(
            source_version_id=sv.id,
            taxonomy="ESCO",
            label=s["title_en"],
            skill_type=stype,
            **_prov(s["title_en"], "en", s["uri"], occ.is_synthetic),
        )
        session.add(sk)
        session.flush()
        session.add(M.OccupationSkill(occupation_id=occ.id, skill_id=sk.id, relation=s["relation"]))
    session.flush()
    return len(skills)


def capabilities(session: Session, d: CapabilityDictionary) -> dict[str, int]:
    v = session.scalar(select(M.AICapabilityVersion).where(M.AICapabilityVersion.version == d.version))
    if v is None:
        v = M.AICapabilityVersion(
            version=d.version,
            released_at=d.released_at,
            content_hash=d.content_hash,
            status=d.status,
            notes=f"review_status={d.review_status}",
        )
        session.add(v)
        session.flush()
        for c in d.capabilities:
            session.add(
                M.AICapability(
                    version_id=v.id,
                    capability_id=c.capability_id,
                    family=c.family,
                    name=c.name,
                    definition=c.definition,
                    payload=c.model_dump(),
                    content_hash=capability_hash(c),
                )
            )
        session.flush()
    elif v.content_hash != d.content_hash:
        raise ValueError(f"capability dictionary {d.version} changed without a version bump")
    rows = session.scalars(select(M.AICapability).where(M.AICapability.version_id == v.id)).all()
    return {r.capability_id: r.id for r in rows}


def methodology(session: Session, m: Methodology) -> M.MethodologyVersion:
    mv = session.scalar(select(M.MethodologyVersion).where(M.MethodologyVersion.version == m.version))
    if mv is None:
        mv = M.MethodologyVersion(
            version=m.version,
            fingerprint=m.fingerprint,
            released_at=m.config["released_at"],
            config=m.config,
            status=m.config["status"],
        )
        session.add(mv)
        session.flush()
    elif mv.fingerprint != m.fingerprint:
        raise ValueError(f"methodology {m.version} fingerprint changed; bump methodology_version")
    return mv


def audit(session: Session, actor: str, action: str, target: str, payload: dict | None = None) -> None:
    session.add(M.AuditLog(actor=actor, action=action, target=target, payload=payload))
