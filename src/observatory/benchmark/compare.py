"""Compare embedding providers on the domain benchmark with a selection rule fixed BEFORE seeing results.

Selection rule (pre-registered in docs/adr/0002-embedding-model-selection.md):
    selection_score = mean(MAP overall, MAP pt, occupation-pair AUC)
A candidate is eligible only if its false-positive rate is not worse than the lexical baseline's.
Portuguese MAP is weighted explicitly because the CBO side of the system is in Portuguese.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from observatory.benchmark.metrics import evaluate, load_benchmark
from observatory.capabilities.dictionary import CapabilityDictionary
from observatory.embeddings.providers import Embedder, get_provider
from observatory.exposure.dimensions import CapabilityIndex, calibrate


def pair_auc(embedder: Embedder, items: list[dict]) -> dict:
    """Probability that an equivalent occupation pair scores above a non-equivalent one (incl. false friends)."""
    scored = []
    for it in items:
        left = embedder.embed([it["left"]], it["left_lang"], "query")[0]
        right = embedder.embed([it["right"]], it["right_lang"], "query")[0]
        scored.append((it["label"], float(left @ right), it))
    pos = [s for lab, s, _ in scored if lab == 2]
    neg = [s for lab, s, _ in scored if lab == 0]
    auc = float(np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])) if pos and neg else float("nan")
    cross = [(lab, s) for lab, s, it in scored if "cross_lingual" in it.get("tags", [])]
    return {
        "auc": round(auc, 4),
        "n_pos": len(pos),
        "n_neg": len(neg),
        "pairs": [{"id": it["id"], "label": lab, "cosine": round(s, 4)} for lab, s, it in scored],
        "cross_lingual_equivalent_mean": round(float(np.mean([s for lab, s in cross if lab == 2])), 4)
        if any(lab == 2 for lab, _ in cross)
        else None,
    }


def compare(
    providers: list[str], dictionary: CapabilityDictionary, benchmark_path: Path, cfg: dict, out_dir: Path
) -> dict:
    meta, items = load_benchmark(benchmark_path)
    sm = cfg["semantic_match"]
    tc = [i for i in items if i["item_type"] == "task_capability"]
    op = [i for i in items if i["item_type"] == "occupation_pair"]
    results = []
    for spec in providers:
        t0 = time.time()
        emb = Embedder(get_provider(spec))
        index = CapabilityIndex(dictionary, emb)
        cal = calibrate(
            index,
            tc,
            sm["negative_penalty"],
            sm["calibration"]["floor_percentile_unrelated"],
            sm["calibration"]["ceiling_quantile_related"],
            meta["version"],
        )
        ev = evaluate(index, cal, items, sm["negative_penalty"])
        pairs = pair_auc(emb, op)
        # reproducibility: re-encoding a sample must give identical vectors
        sample = [i["text"] for i in tc[:5]]
        fresh = Embedder(emb.provider).embed(sample, "en", "query")
        again = Embedder(emb.provider).embed(sample, "en", "query")
        results.append(
            {
                "spec": spec,
                "model": emb.provider.describe(),
                "seconds": round(time.time() - t0, 1),
                "calibration": cal.to_dict(),
                "overall": ev["overall"],
                "by_language": {k: v for k, v in ev["by_language"].items()},
                "by_tag": ev["by_tag"],
                "spearman": ev["spearman_grade_vs_score"],
                "fpr": ev["false_positive_rate"],
                "fnr": ev["false_negative_rate"],
                "occupation_pairs": pairs,
                "reproducible": bool(np.allclose(fresh, again, atol=1e-6)),
                "calibration_spread": round(cal.ceiling - cal.floor, 4),
            }
        )
    baseline_fpr = next((r["fpr"] for r in results if r["spec"] == "baseline"), None)
    for r in results:
        maps = [r["overall"]["MAP"], r["by_language"].get("pt", {}).get("MAP"), r["occupation_pairs"]["auc"]]
        r["selection_score"] = round(float(np.mean([m for m in maps if m is not None])), 4)
        r["eligible"] = baseline_fpr is None or r["fpr"] is None or r["fpr"] <= baseline_fpr + 1e-9
    eligible = [r for r in results if r["eligible"]]
    chosen = max(eligible, key=lambda r: r["selection_score"]) if eligible else None
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "benchmark_version": meta["version"],
        "selection_rule": "mean(MAP overall, MAP pt, occupation-pair AUC); eligible if FPR <= baseline FPR",
        "caveats": [
            "Benchmark labels are AI-drafted (not gold) and small (36 task queries, 10 occupation pairs).",
            "Calibration and error rates are in-sample.",
            "Temporal stability cannot be measured with a single snapshot; model snapshots are pinned instead.",
        ],
        "results": results,
        "chosen": chosen["spec"] if chosen else None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "comparison.md").write_text(render_markdown(report), encoding="utf-8")
    return report


def render_markdown(report: dict) -> str:
    head = (
        "| Modelo | MAP | MAP en | MAP pt | nDCG@5 | P@3 | Spearman | FPR | FNR | AUC pares | Score | Tempo (s) |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = []
    for r in report["results"]:
        o, bl = r["overall"], r["by_language"]
        mark = " **(escolhido)**" if r["spec"] == report["chosen"] else ("" if r["eligible"] else " (inelegível)")
        rows.append(
            f"| `{r['model']['model_key']}`{mark} | {o['MAP']} | {bl.get('en', {}).get('MAP')} | "
            f"{bl.get('pt', {}).get('MAP')} | {o['ndcg@5']} | {o['p@3']} | {r['spearman']} | {r['fpr']} | {r['fnr']} | "
            f"{r['occupation_pairs']['auc']} | {r['selection_score']} | {r['seconds']} |"
        )
    return (
        f"# Comparação de modelos de embeddings (benchmark v{report['benchmark_version']})\n\n"
        f"Regra de seleção (definida antes dos resultados): {report['selection_rule']}.\n\n"
        + head
        + "\n".join(rows)
        + "\n\n"
        + "\n".join(f"- {c}" for c in report["caveats"])
        + "\n"
    )
