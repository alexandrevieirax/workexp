"""Building blocks for E1-E13: semantic matching, capability-property aggregation, priors and lexical cues."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import numpy as np

from observatory.capabilities.dictionary import CapabilityDictionary
from observatory.embeddings.providers import Embedder
from observatory.normalization.scales import ScaleRegistry
from observatory.normalization.text import normalize_text

PRIOR_DIMENSIONS = {
    "E6": "human_judgment_requirement",
    "E7": "social_requirement",
    "E8": "physical_requirement",
    "E9": "accountability_requirement",
    "E10": "organizational_context",
    "standardization": "process_standardization",
}


# --------------------------------------------------------------------------- semantic matching (E1)
class CapabilityIndex:
    def __init__(self, dictionary: CapabilityDictionary, embedder: Embedder):
        self.dictionary = dictionary
        self.embedder = embedder
        self.cap_ids = [c.capability_id for c in dictionary.capabilities]
        pos_texts, pos_owner, neg_texts, neg_owner = [], [], [], []
        for i, c in enumerate(dictionary.capabilities):
            for t in [f"{c.name}. {c.definition}", *c.examples]:
                pos_texts.append(t)
                pos_owner.append(i)
            for t in c.negative_examples:
                neg_texts.append(t)
                neg_owner.append(i)
        self._pos = embedder.embed(pos_texts, kind="passage")
        self._pos_owner = np.array(pos_owner)
        self._neg = embedder.embed(neg_texts, kind="passage") if neg_texts else None
        self._neg_owner = np.array(neg_owner)

    def _group_max(self, sims: np.ndarray, owner: np.ndarray) -> np.ndarray:
        out = np.full((sims.shape[0], len(self.cap_ids)), np.nan)
        for j in range(len(self.cap_ids)):
            cols = owner == j
            if cols.any():
                out[:, j] = sims[:, cols].max(axis=1)
        return out

    def scores(self, texts: list[str], language: str | None, penalty: float) -> dict[str, np.ndarray]:
        q = self.embedder.embed(texts, language=language, kind="query")
        s_pos = self._group_max(q @ self._pos.T, self._pos_owner)
        s_neg = (
            self._group_max(q @ self._neg.T, self._neg_owner) if self._neg is not None else np.full_like(s_pos, np.nan)
        )
        gap = np.nan_to_num(s_neg - s_pos, nan=0.0)
        s = s_pos - penalty * np.maximum(0.0, gap)
        return {"s": s, "s_pos": s_pos, "s_neg": s_neg}


@dataclass
class Calibration:
    model_key: str
    floor: float
    ceiling: float
    benchmark_version: str
    n_related: int
    n_unrelated: int
    method: str = "floor=p75(unrelated), ceiling=median(related)"

    def apply(self, s: np.ndarray) -> np.ndarray:
        return np.clip((s - self.floor) / (self.ceiling - self.floor), 0.0, 1.0)

    def to_dict(self) -> dict:
        return asdict(self)


def calibrate(
    index: CapabilityIndex, items: list[dict], penalty: float, floor_pct: float, ceil_q: float, benchmark_version: str
) -> Calibration:
    related, unrelated = [], []
    col = {c: j for j, c in enumerate(index.cap_ids)}
    for lang in sorted({it["language"] for it in items}):
        sub = [it for it in items if it["language"] == lang]
        s = index.scores([it["text"] for it in sub], lang, penalty)["s"]
        for i, it in enumerate(sub):
            related += [s[i, col[c]] for c, g in it["relevance"].items() if g == 2 and c in col]
            unrelated += [s[i, col[c]] for c in it.get("unrelated", []) if c in col]
    floor = float(np.percentile(unrelated, floor_pct))
    ceiling = float(np.quantile(related, ceil_q))
    if ceiling <= floor:
        raise ValueError(
            f"embedding model cannot separate related/unrelated pairs (floor {floor} >= ceiling {ceiling})"
        )
    return Calibration(
        index.embedder.provider.model_key, floor, ceiling, benchmark_version, len(related), len(unrelated)
    )


# --------------------------------------------------------------------------- capability properties (E2, E11-E13)
def capability_weighted(dictionary: CapabilityDictionary, matches: list[tuple[str, float]], prop: str) -> float | None:
    caps = dictionary.by_id()
    total = sum(w for _, w in matches)
    if total <= 0:
        return None
    return sum(getattr(caps[c].priors, prop) * w for c, w in matches) / total


# --------------------------------------------------------------------------- occupational priors (E6-E10)
def occupational_priors(descriptors: list[dict], scales: ScaleRegistry, cfg: dict) -> dict[str, dict]:
    index = {(d["domain"], d["element_id"], d["scale_id"]): d for d in descriptors if d.get("category") in (None, "")}
    out: dict[str, dict] = {}
    for dim, elements in cfg["occupational_priors"].items():
        if not isinstance(elements, list):
            continue
        used, skipped = [], []
        for el in elements:
            d = index.get((el["domain"], el["element_id"], el["scale"]))
            if d is None or d["value"] is None:
                skipped.append({"element_id": el["element_id"], "reason": "missing"})
                continue
            if d.get("suppressed"):
                skipped.append({"element_id": el["element_id"], "reason": "recommend_suppress"})
                continue
            v = scales.normalize(el["scale"], d["value"])
            if el.get("invert"):
                v = 1 - v
            used.append(
                {
                    "element_id": el["element_id"],
                    "element_name": d["element_name"],
                    "scale": el["scale"],
                    "raw": d["value"],
                    "normalized": round(v, 4),
                    "inverted": bool(el.get("invert")),
                }
            )
        out[dim] = {
            "value": (sum(u["normalized"] for u in used) / len(used)) if used else None,
            "elements": used,
            "skipped": skipped,
        }
    return out


# --------------------------------------------------------------------------- lexical cues
def _cue_regex(cue: str) -> re.Pattern:
    words = [re.escape(w) for w in normalize_text(cue).split()]
    return re.compile(r"\b" + r"\w*\s+".join(words))


_CUE_CACHE: dict[str, re.Pattern] = {}


def cue_hits(text: str, cues: list[str]) -> list[str]:
    t = normalize_text(text)
    hits = []
    for cue in cues:
        rx = _CUE_CACHE.setdefault(cue, _cue_regex(cue))
        if rx.search(t):
            hits.append(cue)
    return sorted(set(hits))


def lexical_adjust(prior: float, text: str, lexicon: dict[str, list[str]], delta: float) -> tuple[float, dict]:
    pos = cue_hits(text, lexicon.get("pos", []))
    neg = cue_hits(text, lexicon.get("neg", []))
    value = prior + (delta if pos else 0.0) - (delta if neg else 0.0)
    return min(1.0, max(0.0, value)), {"prior": round(prior, 4), "pos_hits": pos, "neg_hits": neg, "delta": delta}
