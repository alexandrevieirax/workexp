"""Vertical slice: one CBO, one ESCO and one O*NET occupation end to end (sources → assessment → report)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from observatory.benchmark.metrics import evaluate, load_benchmark
from observatory.capabilities.dictionary import find_leakage, load_dictionary
from observatory.config import Settings, get_settings
from observatory.connectors.aei import AeiRelease
from observatory.connectors.base import SourceUnavailableError
from observatory.connectors.cbo import CboFiles
from observatory.connectors.esco import EscoClient, parse_occupation, parse_skills, skills_as_tasks
from observatory.connectors.onet import OnetArchive
from observatory.crosswalk.candidates import CandidateSearch, OnetIndex
from observatory.crosswalk.candidates import search as candidate_search
from observatory.crosswalk.engine import CrosswalkSide, OfficialCodeCrosswalk, calibrate_pairs, propose
from observatory.crosswalk.review import carry_decision, human_decisions
from observatory.db import models as M
from observatory.db.session import make_engine, session_factory, session_scope
from observatory.embeddings import store as emb_store
from observatory.embeddings.providers import Embedder, get_provider
from observatory.exposure.dimensions import CapabilityIndex, calibrate, occupational_priors
from observatory.exposure.engine import AssessmentResult, ExposureEngine, PriorContext, TaskInput
from observatory.exposure.weights import TaskWeightInput
from observatory.methodology import load_methodology, load_registry
from observatory.pipeline import ingest
from observatory.provenance import pipeline_version

CLASS_RANK = {"very_strong": 3, "strong": 2, "moderate": 1, "not_accepted_automatically": 0}


@dataclass
class SliceConfig:
    onet_code: str = "15-1252.00"
    onet_version: str = "31.0"
    esco_uri: str = "http://data.europa.eu/esco/occupation/f2b15a0e-e65a-438a-affb-29b9d50b77d1"
    cbo_code: str = "212405"
    aei_release: str = "release_2025_03_27"
    provider: str | None = None  # None → methodology default (config: embedding.provider)
    offline: bool = False
    database_url: str | None = None


@dataclass
class SliceReport:
    run_id: str
    started_at: str
    sources: dict[str, Any] = field(default_factory=dict)
    occupations: dict[str, Any] = field(default_factory=dict)
    crosswalks: list[dict] = field(default_factory=list)
    crosswalk_candidates: dict[str, Any] = field(default_factory=dict)
    benchmark: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    methodology: dict[str, Any] = field(default_factory=dict)
    pipeline: dict[str, Any] = field(default_factory=dict)


def check_methodology_registered(m) -> None:
    reg = load_registry()
    entry = next(v for v in reg["versions"] if v["version"] == m.version)
    if entry["fingerprint"] != m.fingerprint:
        raise RuntimeError(
            f"Methodology {m.version} fingerprint {m.fingerprint[:12]} differs from registry "
            f"({entry['fingerprint'][:12]}). A methodological change requires a new version, changelog entry and "
            "'Sobre' update (python -m observatory.cli methodology-status)."
        )


def task_inputs(occ: M.Occupation) -> list[TaskInput]:
    out = []
    for ot in occ.tasks:
        wi = None
        if occ.taxonomy == "ONET":
            wi = TaskWeightInput(
                key=ot.id,
                importance=ot.importance,
                importance_suppressed=bool(ot.importance_suppressed),
                importance_n=ot.importance_n,
                relevance=ot.relevance,
                relevance_suppressed=bool(ot.relevance_suppressed),
                frequency_distribution=ot.frequency_distribution,
                frequency_suppressed=bool(ot.frequency_suppressed),
            )
        out.append(
            TaskInput(
                key=ot.id,
                statement=ot.task.statement,
                language=ot.task.language or "en",
                unit_type=ot.task.unit_type,
                weight_input=wi,
                source_ref=ot.task.original_id,
            )
        )
    return out


def persist_assessment(
    session: Session, run_id: str, occ: M.Occupation, res: AssessmentResult, m, d, cal, cap_pk: dict[str, int], pv: dict
) -> M.ExposureAssessment:
    a = M.ExposureAssessment(
        run_id=run_id,
        occupation_id=occ.id,
        methodology_version=m.version,
        methodology_fingerprint=m.fingerprint,
        capability_version=d.version,
        embedding_model=cal.model_key,
        embedding_calibration=cal.to_dict(),
        pipeline_version=pv,
        scores=res.scores,
        intervals=res.intervals,
        quality=res.quality,
        sensitivity=res.sensitivity,
        limitations=res.limitations,
    )
    session.add(a)
    session.flush()
    ot_by_id = {ot.id: ot for ot in occ.tasks}
    for t in res.tasks:
        session.add(
            M.ExposureComponent(
                assessment_id=a.id,
                occupation_task_id=t.key,
                task_weight=t.weight,
                dimensions={k: (round(v, 4) if isinstance(v, float) else v) for k, v in t.dimensions.items()},
                dimension_sources={**t.dimension_sources, "weight": t.weight_detail},
                technical_exposure=t.outputs.technical_exposure,
                automation_potential=t.outputs.automation_potential,
                augmentation_potential=t.outputs.augmentation_potential,
                transformation_potential=t.outputs.transformation_potential,
                task_class=t.task_class,
                confidence=t.confidence,
                justification=t.justification,
                matched_capabilities=t.matched,
                evidence=t.evidence,
                barriers=t.barriers,
                missing_flags=t.missing,
            )
        )
        ot = ot_by_id[t.key]
        ot.weight, ot.weight_raw, ot.weight_method = t.weight, t.weight_detail["weight_raw"], t.weight_detail["method"]
        ot.missing_flags = {"flags": t.missing}
        for rank, mt in enumerate(t.matched, 1):
            session.add(
                M.SemanticMapping(
                    task_id=ot.task_id,
                    capability_pk=cap_pk[mt["capability_id"]],
                    model_key=cal.model_key,
                    raw_similarity=mt["raw_similarity"],
                    negative_similarity=mt["negative_similarity"],
                    calibrated_similarity=mt["calibrated_similarity"],
                    rank=rank,
                    methodology_version=m.version,
                    assessment_id=a.id,
                )
            )
        for ev in t.evidence:
            session.add(
                M.AIEvidence(
                    evidence_type=ev["type"],
                    task_id=ot.task_id,
                    reference_id=ev.get("reference"),
                    metric="pct_of_conversations",
                    value=ev.get("pct_of_conversations"),
                    payload=ev,
                    peer_reviewed=ev.get("peer_reviewed"),
                    match_method=ev.get("match_method"),
                )
            )
    session.flush()
    return a


def side(occ: M.Occupation, language: str, skills: list[str]) -> CrosswalkSide:
    titles = [
        a.label
        for a in occ.aliases
        if a.language == language and a.alias_type in ("preferred", "alternative", "synonym")
    ] or [occ.title]
    tasks = [ot.task.statement for ot in occ.tasks]
    if occ.taxonomy == "ESCO" and language == "pt":
        tasks = [ot.task.attributes.get("title_pt") or ot.task.statement for ot in occ.tasks]
    return CrosswalkSide(
        occupation_ref=f"{occ.taxonomy}:{occ.code}",
        taxonomy=occ.taxonomy,
        titles=titles[:30],
        language=language,
        tasks=tasks,
        skills=skills,
        group_code=occ.group_code,
        qualification_level=occ.qualification_level,
        official_code=(occ.attributes or {}).get("esco_code") if occ.taxonomy == "ESCO" else occ.code,
    )


def persist_mapping(
    s: Session, source: M.Occupation, target: M.Occupation, prop, model_key: str, version: str, run_id: str
) -> M.OccupationSourceMapping:
    mp = s.scalar(
        select(M.OccupationSourceMapping).where(
            M.OccupationSourceMapping.source_occupation_id == source.id,
            M.OccupationSourceMapping.target_occupation_id == target.id,
            M.OccupationSourceMapping.methodology_version == version,
        )
    )
    if mp is not None:
        return mp
    mp = M.OccupationSourceMapping(
        source_occupation_id=source.id,
        target_occupation_id=target.id,
        method="composite_candidates_v1",
        title_similarity=prop.title_similarity,
        task_similarity=prop.task_similarity,
        skill_similarity=prop.skill_similarity,
        hierarchy_consistency=prop.hierarchy_consistency,
        qualification_consistency=prop.qualification_consistency,
        mapping_confidence=prop.mapping_confidence,
        confidence_class=prop.confidence_class,
        status="proposed",
        rules_applied={"rules": prop.rules_applied, **prop.details},
        embedding_model=model_key,
        methodology_version=version,
    )
    s.add(mp)
    s.flush()
    s.add(
        M.CrosswalkChange(
            mapping_id=mp.id,
            action="create",
            after=prop.to_dict(),
            actor=f"pipeline:{run_id}",
            justification="automatic proposal (not accepted)",
        )
    )
    return mp


def onet_usage_reference(onet: OnetArchive, aei: AeiRelease | None, codes: list[str], cfg: dict) -> list[dict] | None:
    """O*NET tasks of the mapped occupation(s) with their observed-usage value, treated exactly as in O*NET
    assessments (percentile when matched in the AEI sample, the configured value when absent from it)."""
    if aei is None:
        return None
    out = []
    for code in codes:
        for t in onet.tasks(code):
            ou = aei.lookup(t.statement)
            out.append(
                {
                    "statement": t.statement,
                    "onet_code": code,
                    "e3": ou.percentile if ou else cfg["observed_usage"]["absent_from_sample_value"],
                    "status": ou.match_method if ou else "absent_from_sample",
                }
            )
    return out


def onet_priors_for(onet: OnetArchive, codes: list[str], cfg: dict) -> dict:
    """Occupational priors of one O*NET occupation, or the mean of several (pooled for tied candidates)."""
    per = []
    for code in codes:
        rows = onet.descriptors(code, "work_context") + onet.descriptors(code, "work_activity")
        per.append(occupational_priors(rows, onet.scales, cfg))
    if len(per) == 1:
        return per[0]
    out = {}
    for dim in per[0]:
        vals = [p[dim]["value"] for p in per if p[dim]["value"] is not None]
        out[dim] = {
            "value": sum(vals) / len(vals) if vals else None,
            "pooled_from": codes,
            "elements": [e for p in per for e in p[dim]["elements"]],
            "skipped": [],
        }
    return out


def without_rejected(found: CandidateSearch, decided: dict) -> CandidateSearch:
    ranked = [
        p
        for p in found.ranked
        if decided.get(p.target.split(":", 1)[1], None) is None
        or decided[p.target.split(":", 1)[1]].status != "rejected"
    ]
    margin = round(ranked[0].mapping_confidence - ranked[1].mapping_confidence, 4) if len(ranked) > 1 else None
    ambiguous = margin is not None and margin < found.ambiguity_margin
    return CandidateSearch(found.source, ranked, ambiguous, margin, found.candidate_origin, found.ambiguity_margin)


def run(cfg: SliceConfig | None = None, settings: Settings | None = None) -> SliceReport:
    cfg = cfg or SliceConfig()
    settings = settings or get_settings()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    report = SliceReport(run_id=run_id, started_at=datetime.now(UTC).isoformat())
    m = load_methodology()
    check_methodology_registered(m)
    d = load_dictionary(settings.capabilities_dir / m.capability_dictionary_file)
    pv = pipeline_version()
    report.methodology = {
        "version": m.version,
        "fingerprint": m.fingerprint,
        "status": m.config["status"],
        "capability_dictionary": d.version,
        "capability_review_status": d.review_status,
    }
    report.pipeline = pv

    engine = make_engine(cfg.database_url or settings.database_url)
    if engine.dialect.name == "sqlite":
        from observatory.db.session import create_schema

        create_schema(engine)  # dev convenience; PostgreSQL deployments run `alembic upgrade head`
    factory = session_factory(engine)

    with session_scope(factory) as s:
        ingest.methodology(s, m)
        cap_pk = ingest.capabilities(s, d)
        emb_cfg = m.config.get("embedding", {})
        default_provider = emb_cfg.get("provider", "baseline")
        provider_spec = cfg.provider or default_provider
        if provider_spec != default_provider:
            report.warnings.append(
                f"Embedding provider overridden ({provider_spec}); methodology {m.version} specifies "
                f"{default_provider}. Results are not the official methodology output."
            )
        embedder = Embedder(
            get_provider(provider_spec, emb_cfg.get("revision") if provider_spec == default_provider else None)
        )
        emb_store.load_into(embedder, s)
        index = CapabilityIndex(d, embedder)
        meta, bench = load_benchmark(settings.validation_dir / "benchmark_v0.1.0.jsonl")
        sm = m.config["semantic_match"]
        tc_items = [i for i in bench if i["item_type"] == "task_capability"]
        cal = calibrate(
            index,
            tc_items,
            sm["negative_penalty"],
            sm["calibration"]["floor_percentile_unrelated"],
            sm["calibration"]["ceiling_quantile_related"],
            meta["version"],
        )
        tcal = m.config["crosswalk"]["title_calibration"]
        pair_items = [i for i in bench if i["item_type"] == "occupation_pair"]
        for fname in tcal["extra_pair_files"]:
            pair_items += load_benchmark(settings.validation_dir / fname)[1]
        try:
            title_cal = calibrate_pairs(
                embedder,
                pair_items,
                meta["version"] + "+" + "+".join(tcal["extra_pair_files"]),
                tcal["floor_percentile_nonequivalent"],
                tcal["ceiling_quantile_equivalent"],
            )
        except ValueError as exc:
            title_cal = None
            report.warnings.append(
                f"Title calibration impossible for {embedder.provider.model_key}: {exc}. "
                "title_similarity is treated as unknown in every crosswalk."
            )
        if title_cal is not None and title_cal.ceiling - title_cal.floor < 0.05:
            report.warnings.append(
                f"Title calibration is narrow (floor {title_cal.floor:.3f}, ceiling {title_cal.ceiling:.3f}, "
                f"{title_cal.n_related}+{title_cal.n_unrelated} pairs): for this model, non-equivalent titles score "
                "almost like equivalent ones, so title_similarity behaves close to a 0/1 step. Treat it as weak "
                "evidence (weight 0.20)."
            )
        bench_result = evaluate(index, cal, bench, sm["negative_penalty"])
        exp_dir = settings.experiments_dir / f"benchmark-{run_id}"
        exp_dir.mkdir(parents=True, exist_ok=True)
        (exp_dir / "params.json").write_text(
            json.dumps(
                {"model": embedder.provider.describe(), "benchmark_version": meta["version"], "methodology": m.version},
                indent=2,
            ),
            encoding="utf-8",
        )
        (exp_dir / "metrics.json").write_text(json.dumps(bench_result, indent=2, ensure_ascii=False), encoding="utf-8")
        report.benchmark = {
            k: bench_result[k]
            for k in (
                "model",
                "calibration",
                "overall",
                "spearman_grade_vs_score",
                "false_positive_rate",
                "false_negative_rate",
                "by_language",
                "caveat",
            )
        } | {"artifact": str(exp_dir), "title_pair_calibration": title_cal.to_dict() if title_cal else None}
        if not embedder.provider.is_semantic:
            report.warnings.append(
                "Embedding provider is the lexical baseline; install '.[ml]' and evaluate "
                "multilingual-e5-large / BGE-M3 before drawing substantive conclusions."
            )

        # ---------------------------------------------------------------- sources
        onet = OnetArchive(
            settings.raw_data_dir / "onet" / cfg.onet_version / f"db_{cfg.onet_version.replace('.', '_')}_text.zip"
        )
        onet.validate()
        sv_onet = ingest.source_version(s, onet.descriptor())
        aei = None
        try:
            aei = AeiRelease(settings.raw_data_dir / "aei" / cfg.aei_release, cfg.aei_release)
            ingest.source_version(s, aei.descriptor())
            report.sources["AEI"] = {"status": "loaded", "release": cfg.aei_release, "tasks": aei.n_tasks}
        except SourceUnavailableError as exc:
            report.warnings.append(str(exc))
            report.sources["AEI"] = {"status": "unavailable"}

        p_onet = onet.occupation(cfg.onet_code)
        occ_onet = ingest.occupation(s, sv_onet, p_onet)
        t_onet = onet.tasks(cfg.onet_code)
        ingest.tasks(s, sv_onet, occ_onet, t_onet)
        desc_rows = []
        for dom in ("work_context", "work_activity", "knowledge", "ability", "skill"):
            desc_rows += onet.descriptors(cfg.onet_code, dom)
        ingest.descriptors(s, occ_onet, desc_rows)
        dwas = sorted({name for lst in onet.dwas_for_tasks(cfg.onet_code).values() for _, name in lst if name})
        report.sources["ONET"] = {
            "status": "loaded",
            "version": onet.version,
            "occupation": cfg.onet_code,
            "tasks": len(t_onet),
            "descriptors": len(desc_rows),
            "sha256": sv_onet.file_sha256,
        }
        leaks = find_leakage(d, [t.statement for t in t_onet])
        if leaks:
            report.warnings.append(f"Capability examples identical to evaluated tasks (leakage): {leaks}")

        occs: dict[str, M.Occupation] = {"ONET": occ_onet}
        skills_by: dict[str, dict[str, list[str]]] = {"ONET": {"en": dwas}}
        try:
            esco = EscoClient(settings.raw_data_dir / "esco", offline=cfg.offline)
            raw_en = esco.occupation_raw(cfg.esco_uri, "en")
            raw_pt = esco.occupation_raw(cfg.esco_uri, "pt")
            p_esco = parse_occupation(raw_en, raw_pt, esco.is_synthetic)
            skills = parse_skills(raw_en, raw_pt)
            sv_esco = ingest.source_version(s, esco.descriptor())
            occ_esco = ingest.occupation(s, sv_esco, p_esco)
            esco_units = skills_as_tasks(skills)
            ingest.tasks(s, sv_esco, occ_esco, esco_units)
            ingest.esco_skills(s, sv_esco, occ_esco, skills)
            occs["ESCO"] = occ_esco
            skills_by["ESCO"] = {
                "en": [x["title_en"] for x in skills],
                "pt": [x["title_pt"] for x in skills if x["title_pt"]],
            }
            report.sources["ESCO"] = {
                "status": "loaded",
                "version": sv_esco.version,
                "uri": cfg.esco_uri,
                "isco": p_esco.group_code,
                "essential_skills_as_tasks": len(esco_units),
                "skills_total": len(skills),
                "api_responses": len(esco.retrievals),
            }
        except Exception as exc:  # network/API failure must not fabricate data
            report.warnings.append(f"ESCO unavailable: {exc}")
            report.sources["ESCO"] = {"status": "unavailable", "error": str(exc)}

        try:
            cbo = CboFiles(settings.raw_data_dir / "cbo")
            sv_cbo = ingest.source_version(s, cbo.descriptor())
            occ_cbo = ingest.occupation(s, sv_cbo, cbo.occupation(cfg.cbo_code))
            acts = cbo.activities(cfg.cbo_code)
            ingest.tasks(s, sv_cbo, occ_cbo, acts)
            comps = cbo.personal_competencies(cfg.cbo_code)
            ingest.cbo_personal_competencies(s, sv_cbo, occ_cbo, comps)
            occs["CBO"] = occ_cbo
            # Personal competencies are not comparable to O*NET DWAs / ESCO skills → skill component unknown.
            skills_by["CBO"] = {"pt": []}
            report.sources["CBO"] = {
                "status": "loaded",
                "version": sv_cbo.version,
                "code": cfg.cbo_code,
                "activities": len(acts),
                "personal_competencies": len(comps),
                "activity_scope": acts[0].attributes["scope"] if acts else None,
                "sha256": sv_cbo.file_sha256,
            }
        except SourceUnavailableError as exc:
            report.warnings.append(
                "CBO not loaded: official files require manual download (reCAPTCHA). " + exc.procedure
            )
            report.sources["CBO"] = {
                "status": "pending_manual_download",
                "expected_location": exc.expected_location,
                "procedure": exc.procedure,
            }
        s.flush()
        for o in occs.values():
            s.refresh(o)

        # ---------------------------------------------------------------- crosswalks
        official = OfficialCodeCrosswalk.from_dir(settings.raw_data_dir / "crosswalks")
        cw_cfg = m.config["crosswalk"]
        onet_index = OnetIndex(onet, embedder)
        searches: dict[str, CandidateSearch] = {}
        decisions: dict[str, dict] = {}
        for tax, lang in (("ESCO", "en"), ("CBO", "pt")):
            if tax not in occs:
                continue
            src = side(occs[tax], lang, skills_by[tax].get(lang, []))
            found = candidate_search(src, onet_index, title_cal, m.config, official)
            # Human decisions from earlier runs: rejected candidates leave the ranking, accepted ones are kept.
            decided = human_decisions(s, tax, occs[tax].code)
            all_ranked = list(found.ranked)
            found = without_rejected(found, decided)
            searches[tax] = found
            decisions[tax] = decided
            report.crosswalk_candidates[tax] = found.to_dict() | {
                "human_decisions": {c: d.status for c, d in decided.items()}
            }
            keep = found.ranked[: cw_cfg["candidates"]["persist_top"]]
            keep += [p for p in all_ranked if p not in keep and p.target.split(":", 1)[1] in decided]
            for prop in keep:
                code = prop.target.split(":", 1)[1]
                target = occ_onet if code == cfg.onet_code else ingest.occupation(s, sv_onet, onet.occupation(code))
                mp = persist_mapping(s, occs[tax], target, prop, cal.model_key, m.version, run_id)
                if code in decided and mp.status == "proposed":
                    carry_decision(mp, decided[code], run_id)
                report.crosswalks.append(prop.to_dict() | {"mapping_id": mp.id, "status": mp.status})
            if found.ambiguous and not any(d.status == "accepted" for d in decided.values()):
                report.warnings.append(
                    f"{tax}: best O*NET candidates are ambiguous (margin {found.margin:.3f} < "
                    f"{cw_cfg['candidates']['ambiguity_margin']}); human review should choose the mapping."
                )
        if "CBO" in occs and "ESCO" in occs:
            # No CBO↔ISCO-08 official table and no ESCO null sample: tasks/skills stay unknown by design.
            prop = propose(
                side(occs["CBO"], "pt", []),
                side(occs["ESCO"], "pt", skills_by["ESCO"].get("pt", [])),
                embedder,
                title_cal,
                m.config,
                official,
            )
            mp = persist_mapping(s, occs["CBO"], occs["ESCO"], prop, cal.model_key, m.version, run_id)
            report.crosswalks.append(prop.to_dict() | {"mapping_id": mp.id, "status": mp.status})

        # ---------------------------------------------------------------- assessments
        eng = ExposureEngine(m, d, index, cal, onet.scales, aei)
        onet_priors = occupational_priors(desc_rows, onet.scales, m.config)
        min_rank = CLASS_RANK[cw_cfg["prior_transfer_min_class"]]
        for tax, occ in occs.items():
            cw_quality = None
            if tax == "ONET":
                ctx = PriorContext(onet_priors, "onet_direct")
            else:
                found = searches.get(tax)
                best = found.best if found else None
                cw_quality = best.mapping_confidence if best else None
                accepted_codes = [c for c, d in decisions.get(tax, {}).items() if d.status == "accepted"]
                strong = best is not None and CLASS_RANK[best.confidence_class] >= min_rank
                unambiguous = found is not None and not (
                    found.ambiguous and cw_cfg["candidates"]["require_unambiguous"]
                )
                tied = found.tied() if found is not None and found.ambiguous else []
                pool = (
                    cw_cfg["candidates"]["ambiguous_policy"] == "pool_within_margin"
                    and tied
                    and all(CLASS_RANK[p.confidence_class] >= min_rank for p in tied)
                )
                if accepted_codes:  # a human reviewer chose the equivalent: it overrides automatic ranking
                    latest = max(accepted_codes, key=lambda c: decisions[tax][c].at)
                    mp_dec = s.get(M.OccupationSourceMapping, decisions[tax][latest].mapping_id)
                    ctx = PriorContext(
                        onet_priors_for(onet, [latest], m.config),
                        "crosswalk_transfer",
                        mp_dec.mapping_confidence if mp_dec else None,
                        latest,
                        onet_usage_reference(onet, aei, [latest], m.config),
                    )
                    report.warnings.append(
                        f"{tax}: using the mapping to {latest} accepted by {decisions[tax][latest].reviewer}."
                    )
                elif best is not None and strong and unambiguous:
                    code = best.target.split(":", 1)[1]
                    ctx = PriorContext(
                        onet_priors_for(onet, [code], m.config),
                        "crosswalk_transfer",
                        best.mapping_confidence,
                        code,
                        onet_usage_reference(onet, aei, [code], m.config),
                    )
                elif pool:
                    codes = [p.target.split(":", 1)[1] for p in tied]
                    ctx = PriorContext(
                        onet_priors_for(onet, codes, m.config),
                        "crosswalk_pooled",
                        min(p.mapping_confidence for p in tied),
                        ", ".join(codes),
                        onet_usage_reference(onet, aei, codes, m.config),
                    )
                    report.warnings.append(
                        f"{tax}: {len(codes)} O*NET candidates tied within the ambiguity margin; priors pooled "
                        f"from {', '.join(codes)} (extra uncertainty). Human review should pick the equivalent."
                    )
                else:
                    ctx = PriorContext({}, "default")
                    if best is not None:
                        why = "ambiguous candidates" if strong and not unambiguous else f"'{best.confidence_class}'"
                        report.warnings.append(
                            f"{tax}: best O*NET candidate {best.target} is {why} ({best.mapping_confidence:.2f}); "
                            "O*NET priors NOT transferred, default prior used."
                        )
            res = eng.assess(task_inputs(occ), ctx, cw_quality)
            a = persist_assessment(s, run_id, occ, res, m, d, cal, cap_pk, pv)
            report.occupations[tax] = {
                "occupation_id": occ.id,
                "code": occ.code,
                "title": occ.title,
                "assessment_id": a.id,
                "scores": res.scores,
                "intervals": {k: v for k, v in res.intervals.items() if k in res.scores},
                "quality": res.quality,
                "max_abs_delta_OAE": res.sensitivity["max_abs_delta_OAE"],
                "limitations": res.limitations,
            }
        if "ONET" in report.occupations and "ESCO" in report.occupations:
            report.occupations["divergence_ESCO_vs_ONET_OAE"] = round(
                abs(report.occupations["ESCO"]["scores"]["OAE"] - report.occupations["ONET"]["scores"]["OAE"]), 4
            )
        emb_store.persist(embedder, s)
        s.add(
            M.SystemRelease(
                version=f"slice-{run_id}",
                methodology_version=m.version,
                capability_version=d.version,
                pipeline_version=pv,
                notes="vertical slice run",
            )
        )
        ingest.audit(
            s,
            f"pipeline:{run_id}",
            "vertical_slice_run",
            "system",
            {"sources": report.sources, "warnings": report.warnings},
        )

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    out = settings.reports_dir / f"vertical_slice_{run_id}.json"
    out.write_text(json.dumps(report.__dict__, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (settings.reports_dir / "vertical_slice_latest.json").write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
    return report


def latest_report(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).reports_dir / "vertical_slice_latest.json"
