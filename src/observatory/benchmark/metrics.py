"""Domain benchmark for embedding models: ranking metrics, error rates and per-group breakdowns."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from observatory.exposure.dimensions import Calibration, CapabilityIndex


def load_benchmark(path: Path) -> tuple[dict, list[dict]]:
    meta, items = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("_meta"):
            meta = rec
        else:
            items.append(rec)
    return meta, items


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in ranked[:k] if c in relevant) / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1 for c in ranked[:k] if c in relevant) / len(relevant) if relevant else float("nan")


def average_precision(ranked: list[str], relevant: set[str]) -> float:
    hits, total = 0, 0.0
    for i, c in enumerate(ranked, 1):
        if c in relevant:
            hits += 1
            total += hits / i
    return total / len(relevant) if relevant else float("nan")


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float:
    dcg = sum((2 ** grades.get(c, 0) - 1) / math.log2(i + 2) for i, c in enumerate(ranked[:k]))
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else float("nan")


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if not math.isnan(x)]
    return round(float(np.mean(xs)), 4) if xs else None


def evaluate(
    index: CapabilityIndex,
    calibration: Calibration,
    items: list[dict],
    penalty: float,
    threshold: float = 0.5,
    ks: tuple[int, ...] = (1, 3, 5),
) -> dict:
    tc = [it for it in items if it["item_type"] == "task_capability"]
    per_item: list[dict] = []
    labeled_scores, labeled_grades = [], []
    fp, fp_n, fn, fn_n = 0, 0, 0, 0
    for lang in sorted({it["language"] for it in tc}):
        sub = [it for it in tc if it["language"] == lang]
        s = calibration.apply(index.scores([it["text"] for it in sub], lang, penalty)["s"])
        for i, it in enumerate(sub):
            order = [index.cap_ids[j] for j in np.argsort(-s[i])]
            grades = {c: g for c, g in it["relevance"].items() if c in index.cap_ids}
            relevant = {c for c, g in grades.items() if g >= 1}
            col = {c: j for j, c in enumerate(index.cap_ids)}
            rec = {"id": it["id"], "language": lang, "tags": it.get("tags", []), "top5": order[:5]}
            if relevant:
                for k in ks:
                    rec[f"p@{k}"] = precision_at_k(order, relevant, k)
                    rec[f"r@{k}"] = recall_at_k(order, relevant, k)
                rec["ap"] = average_precision(order, relevant)
                rec["ndcg@5"] = ndcg_at_k(order, grades, 5)
            for c, g in grades.items():
                labeled_scores.append(s[i, col[c]])
                labeled_grades.append(g)
                if g == 2:
                    fn_n += 1
                    fn += int(s[i, col[c]] < threshold)
            for c in it.get("unrelated", []):
                if c in col:
                    labeled_scores.append(s[i, col[c]])
                    labeled_grades.append(0)
                    fp_n += 1
                    fp += int(s[i, col[c]] >= threshold)
            per_item.append(rec)

    def summarize(recs: list[dict]) -> dict:
        keys = [f"p@{k}" for k in ks] + [f"r@{k}" for k in ks] + ["ap", "ndcg@5"]
        out = {("MAP" if k == "ap" else k): _mean([r[k] for r in recs if k in r]) for k in keys}
        out["n_queries"] = sum(1 for r in recs if "ap" in r)
        return out

    by_lang = {
        lang: summarize([r for r in per_item if r["language"] == lang]) for lang in {r["language"] for r in per_item}
    }
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for r in per_item:
        for t in r["tags"]:
            by_tag[t].append(r)
    rho = spearmanr(labeled_grades, labeled_scores).statistic if len(set(labeled_grades)) > 1 else float("nan")
    return {
        "model": calibration.model_key,
        "calibration": calibration.to_dict(),
        "overall": summarize(per_item),
        "spearman_grade_vs_score": round(float(rho), 4),
        "false_positive_rate": round(fp / fp_n, 4) if fp_n else None,
        "false_negative_rate": round(fn / fn_n, 4) if fn_n else None,
        "threshold": threshold,
        "error_rates_in_sample": True,
        "by_language": by_lang,
        "by_tag": {t: summarize(v) for t, v in sorted(by_tag.items())},
        "per_item": per_item,
        "caveat": "Labels are AI-drafted (not gold); calibration uses the same items, so error rates are in-sample.",
    }
