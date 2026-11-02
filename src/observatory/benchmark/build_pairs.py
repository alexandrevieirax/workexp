"""Build occupation-pair benchmark items whose labels come from official sources, not from human/AI judgement.

Equivalent pairs (label 2):
  - O*NET occupation title  vs one of its official alternate job titles          (en-en)
  - ESCO preferred label en vs the same concept's official pt label               (en-pt, cross-lingual)
  - CBO occupation title    vs one of its official synonyms                       (pt-pt)
Non-equivalent pairs (label 0), "hard negatives":
  - two different occupations of the same source whose titles share a word        (false friends)
  - ESCO en label of one concept vs pt label of a different concept sharing a word (cross-lingual)

The occupations evaluated in the vertical slice are excluded so calibration is not tuned on them.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from observatory.connectors.cbo import CboFiles
from observatory.connectors.esco import EscoClient
from observatory.connectors.onet import OnetArchive
from observatory.normalization.text import split_gendered_title, tokens

ESCO_TERMS = [
    "nurse",
    "electrician",
    "accountant",
    "primary school teacher",
    "lawyer",
    "truck driver",
    "cook",
    "data scientist",
    "translator",
    "civil engineer",
    "pharmacist",
    "carpenter",
    "receptionist",
    "architect",
    "journalist",
    "car mechanic",
    "police officer",
    "farmer",
    "graphic designer",
    "welder",
    "cashier",
    "general practitioner",
    "social worker",
    "plumber",
    "bank teller",
    "hairdresser",
    "librarian",
    "chemical engineer",
    "dental hygienist",
    "network administrator",
]
STOP = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "e",
    "em",
    "and",
    "of",
    "the",
    "or",
    "a",
    "o",
    "para",
    "in",
    "except",
    "all",
    "other",
    "outros",
    "workers",
    "trabalhadores",
}


def _content_words(text: str) -> set[str]:
    return {t for t in tokens(text) if len(t) > 3 and t not in STOP}


def _hard_negatives(items: list[tuple[str, str]], n: int, rng: random.Random) -> list[tuple[str, str]]:
    """Pairs of different ids whose labels share at least one content word."""
    by_word: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for oid, label in items:
        for w in _content_words(label):
            by_word[w].append((oid, label))
    cands = set()
    for group in by_word.values():
        if len(group) < 2:
            continue
        for _ in range(3):
            a, b = rng.sample(group, 2)
            if a[0] != b[0]:
                cands.add((a, b) if a < b else (b, a))
    picked = rng.sample(sorted(cands), min(n, len(cands)))
    return [(a[1], b[1]) for a, b in picked]


def build(
    onet: OnetArchive,
    cbo: CboFiles | None,
    esco: EscoClient | None,
    exclude: dict[str, str],
    per_type: int = 20,
    seed: int = 20261102,
) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []

    def add(kind, left, ll, right, rl, label, tags, source):
        out.append(
            {
                "id": f"op2-{len(out) + 1:03d}",
                "item_type": "occupation_pair",
                "left": left,
                "left_lang": ll,
                "right": right,
                "right_lang": rl,
                "label": label,
                "tags": tags,
                "annotator": f"constructed:{source}",
                "is_gold": False,
                "label_basis": kind,
            }
        )

    # O*NET
    occ = onet.table("Occupation Data.txt")
    jt = onet.table("Job Titles.txt") if onet.has("Job Titles.txt") else None
    codes = [c for c in occ["O*NET-SOC Code"] if c[:7] != exclude.get("onet", "")[:7]]
    titles = dict(zip(occ["O*NET-SOC Code"], occ["Title"], strict=True))
    if jt is not None:
        for c in rng.sample(codes, per_type * 3):
            alts = [t for t in jt.loc[jt["O*NET-SOC Code"] == c, "Job Title"] if t.lower() != titles[c].lower()]
            if alts and sum(1 for o in out if o["label_basis"] == "onet_alternate_title") < per_type:
                add("onet_alternate_title", titles[c], "en", rng.choice(alts), "en", 2, ["equivalent"], "onet")
    for a, b in _hard_negatives([(c, titles[c]) for c in codes], per_type, rng):
        add("onet_different_occupation_shared_word", a, "en", b, "en", 0, ["false_friend"], "onet")

    # CBO
    if cbo is not None:
        o = cbo.tables["ocupacao"]
        syn = cbo.tables.get("sinonimo")
        ex = exclude.get("cbo", "")
        cbo_items = [(c, t) for c, t in zip(o["CODIGO"], o["TITULO"], strict=True) if c[:4] != ex[:4]]
        if syn is not None:
            syn_by = syn.groupby("OCUPACAO")["SINONIMO"].apply(list).to_dict()
            for c, t in rng.sample(cbo_items, per_type * 3):
                alts = [s for s in syn_by.get(c, []) if s.lower() != t.lower()]
                if alts and sum(1 for x in out if x["label_basis"] == "cbo_synonym") < per_type:
                    add("cbo_synonym", t, "pt", rng.choice(alts), "pt", 2, ["equivalent"], "cbo")
        for a, b in _hard_negatives(cbo_items, per_type, rng):
            add("cbo_different_occupation_shared_word", a, "pt", b, "pt", 0, ["false_friend"], "cbo")

    # ESCO (official multilingual labels of the same concept)
    if esco is not None:
        concepts = []
        for term in ESCO_TERMS:
            try:
                hits = esco.search_occupations(term, "en", limit=1)
                if not hits or hits[0]["uri"] == exclude.get("esco"):
                    continue
                raw = esco.occupation_raw(hits[0]["uri"], "pt")
            except Exception:  # API errors skip the term; nothing is invented to replace it
                continue
            en, pt = raw["preferredLabel"].get("en"), raw["preferredLabel"].get("pt")
            if en and pt:
                concepts.append((hits[0]["uri"], en, split_gendered_title(pt)[0]))
        for _, en, pt in concepts:
            add("esco_official_translation", en, "en", pt, "pt", 2, ["equivalent", "cross_lingual"], "esco")
        # cross-lingual negatives: en label of one concept vs pt label of another
        for i, (uri, en, _) in enumerate(concepts):
            others = [c for c in concepts if c[0] != uri]
            if others:
                other = others[(i * 7) % len(others)]
                add("esco_different_concept", en, "en", other[2], "pt", 0, ["cross_lingual"], "esco")
    return out


def write(items: list[dict], path: Path, version: str) -> None:
    meta = {
        "_meta": True,
        "version": version,
        "item_type": "occupation_pair",
        "description": "Occupation pairs with labels derived from official sources (alternate titles, synonyms, "
        "official translations, distinct occupations). See observatory.benchmark.build_pairs.",
        "grades": {"2": "equivalent", "0": "not equivalent"},
    }
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [meta, *items]) + "\n", encoding="utf-8")


def summarize(items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for x in items:
        out[x["label_basis"]] += 1
    return dict(out)
