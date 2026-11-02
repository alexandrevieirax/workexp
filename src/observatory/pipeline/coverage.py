"""Run the vertical slice for several occupation sets (CBO + ESCO + O*NET) and compare them side by side.

The sets were chosen to test whether the index separates different kinds of work: cognitive IT work, cognitive
non-IT work, manual work and regulated health work. They are configuration, not methodology.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from observatory.config import get_settings
from observatory.pipeline.vertical_slice import SliceConfig, run

ESCO = "http://data.europa.eu/esco/occupation/"


@dataclass
class OccupationSet:
    label: str
    profile: str
    onet_code: str
    esco_uri: str
    cbo_code: str


DEFAULT_SETS = [
    OccupationSet(
        "desenvolvimento-de-sistemas",
        "cognitiva (TI)",
        "15-1252.00",
        ESCO + "f2b15a0e-e65a-438a-affb-29b9d50b77d1",
        "212405",
    ),
    OccupationSet(
        "contabilidade", "cognitiva (não TI)", "13-2011.00", ESCO + "eda0d957-3c3c-4139-b89a-a18bc9e18897", "252210"
    ),
    OccupationSet("eletricista", "manual", "47-2111.00", ESCO + "5dbb9cf0-b226-402c-a295-2f42ef05ff8b", "715610"),
    OccupationSet(
        "tecnico-de-enfermagem",
        "saúde, regulamentada",
        "29-2061.00",
        ESCO + "87d0795a-d41f-47ee-979f-0ab7d73836e7",
        "322205",
    ),
]


def summarize(label: str, profile: str, rep) -> dict:
    occs = {}
    for tax in ("ONET", "ESCO", "CBO"):
        o = rep.occupations.get(tax)
        if not isinstance(o, dict):
            continue
        q = o["quality"]
        occs[tax] = {
            "code": o["code"],
            "title": o["title"],
            "scores": o["scores"],
            "intervals": o["intervals"],
            "mean_uncertainty": q["mean_uncertainty"],
            "prior_source": q["prior_source"],
            "prior_from_occupation": q.get("prior_from_occupation"),
            "class_distribution": q["class_distribution"],
            "observed_usage_coverage": q["observed_usage_coverage"],
            "task_count": q["task_count"],
        }
    crosswalks = {}
    for tax, c in rep.crosswalk_candidates.items():
        best = c["candidates"][0] if c["candidates"] else None
        crosswalks[tax] = {
            "best": best and {k: best[k] for k in ("target", "mapping_confidence", "confidence_class", "hierarchy")},
            "ambiguous": c["ambiguous"],
            "margin": c["margin"],
            "human_decisions": c.get("human_decisions", {}),
        }
    cbo_esco = next((x for x in rep.crosswalks if x["source"].startswith("CBO") and "ESCO" in x["target"]), None)
    if cbo_esco:
        crosswalks["CBO->ESCO"] = {
            k: cbo_esco[k]
            for k in ("mapping_confidence", "confidence_class", "hierarchy_consistency", "qualification_consistency")
        }
    return {
        "label": label,
        "profile": profile,
        "run_id": rep.run_id,
        "occupations": occs,
        "crosswalks": crosswalks,
        "warnings": rep.warnings,
        "sources": rep.sources,
    }


def render_markdown(result: dict) -> str:
    lines = [
        f"# Comparação entre ocupações — metodologia {result['methodology_version']}",
        "",
        f"Gerado em {result['created_at']}. Intervalos de 90% por Monte Carlo. Exposição não é risco de desemprego.",
        "",
        "| Conjunto | Perfil | Base | Ocupação | OAE | OAP | OAuP | OTP | E14 | Priors | Classe predominante |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in result["sets"]:
        for tax, o in r["occupations"].items():
            s, i = o["scores"], o["intervals"]
            top = max(o["class_distribution"].items(), key=lambda kv: kv[1]) if o["class_distribution"] else ("-", 0)
            prior = o["prior_source"] + (f" ({o['prior_from_occupation']})" if o["prior_from_occupation"] else "")
            lines.append(
                f"| {r['label']} | {r['profile']} | {tax} | {o['title']} | {s['OAE']:.2f} [{i['OAE'][0]:.2f}–"
                f"{i['OAE'][1]:.2f}] | {s['OAP']:.2f} | {s['OAuP']:.2f} | {s['OTP']:.2f} | {o['mean_uncertainty']:.2f} "
                f"| {prior} | {top[0]} ({top[1]:.0%}) |"
            )
    lines += [
        "",
        "## Crosswalks",
        "",
        "| Conjunto | Origem | Melhor candidato | Confiança | Ambíguo | Decisão humana |",
        "|---|---|---|---|---|---|",
    ]
    for r in result["sets"]:
        for tax, c in r["crosswalks"].items():
            if tax == "CBO->ESCO":
                lines.append(
                    f"| {r['label']} | CBO→ESCO | — | {c['mapping_confidence']:.2f} ({c['confidence_class']}; "
                    f"hierarquia {c['hierarchy_consistency']}) | — | — |"
                )
                continue
            b = c["best"] or {}
            dec = ", ".join(f"{k}: {v}" for k, v in c["human_decisions"].items()) or "—"
            lines.append(
                f"| {r['label']} | {tax}→O*NET | {b.get('target', '—')} | {b.get('mapping_confidence', 0):.2f} "
                f"({b.get('confidence_class', '')}) | {'sim' if c['ambiguous'] else 'não'} | {dec} |"
            )
    return "\n".join(lines) + "\n"


def run_coverage(
    sets: list[OccupationSet] | None = None, provider: str | None = None, offline: bool = False, **slice_options
) -> dict:
    """``slice_options`` are passed to every SliceConfig (e.g. onet_version, aei_release)."""
    sets = sets or DEFAULT_SETS
    out = []
    version = None
    for occ in sets:
        rep = run(
            SliceConfig(
                onet_code=occ.onet_code,
                esco_uri=occ.esco_uri,
                cbo_code=occ.cbo_code,
                provider=provider,
                offline=offline,
                **slice_options,
            )
        )
        version = rep.methodology["version"]
        out.append(summarize(occ.label, occ.profile, rep))
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "methodology_version": version,
        "set_definitions": [asdict(s) for s in sets],
        "sets": out,
    }
    reports = get_settings().reports_dir
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "coverage_latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (reports / "coverage_latest.md").write_text(render_markdown(result), encoding="utf-8")
    return result
