"""Human annotation of the task ↔ AI-capability benchmark (methodology §10.1, semantic validation).

- Blinded: annotators never see the AI draft label, and pairs are shown in a seeded random order.
- Each item asks about the capabilities labelled in the draft (related and unrelated) plus the model's top-k, so
  missing relations in the draft (false negatives) can be found.
- Agreement: quadratic-weighted Cohen's kappa per annotator pair and Krippendorff's alpha (interval metric) for
  the whole group; each annotator is also compared with the AI draft.
- A gold set is exported only for pairs labelled by at least ``min_annotators`` humans (median label).
"""

from __future__ import annotations

import itertools
import json
import random
import statistics
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import cohen_kappa_score
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from observatory.db import models as M

SAMPLE_SET = "benchmark_v0.1.0"
AI_DRAFT = "ai_draft"
GRADES = (2, 1, 0)


class AnnotationError(ValueError):
    pass


# ------------------------------------------------------------------ task preparation
def prepare_tasks(index, items: list[dict], penalty: float, top_k: int = 3, seed: int = 20261103) -> dict:
    tasks = []
    for it in (i for i in items if i["item_type"] == "task_capability"):
        sc = index.scores([it["text"]], it["language"], penalty)["s"][0]
        top = [index.cap_ids[j] for j in np.argsort(-sc)[:top_k]]
        draft = {c: g for c, g in it["relevance"].items()} | {c: 0 for c in it.get("unrelated", [])}
        pairs = sorted(set(draft) | set(top))
        random.Random(f"{seed}:{it['id']}").shuffle(pairs)
        tasks.append(
            {
                "item_id": it["id"],
                "text": it["text"],
                "language": it["language"],
                "source_ref": it.get("source_ref"),
                "tags": it.get("tags", []),
                "pairs": pairs,
                "model_top": top,
                "draft": draft,
            }
        )
    return {
        "sample_set": SAMPLE_SET,
        "created_at": datetime.now(UTC).isoformat(),
        "model": index.embedder.provider.model_key,
        "seed": seed,
        "tasks": tasks,
    }


def load_tasks(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ storage
def validate_annotator(name: str) -> str:
    name = (name or "").strip()
    if not 2 <= len(name) <= 64:
        raise AnnotationError("name must have 2 to 64 characters")
    if name.lower() == AI_DRAFT:
        raise AnnotationError("reserved name")
    return name


def save_annotation(s: Session, annotator: str, task: dict, labels: dict[str, int | None], comment: str = "") -> int:
    """Replace this annotator's labels for one item. ``None`` means "não sei" and is not stored."""
    annotator = validate_annotator(annotator)
    unknown = set(labels) - set(task["pairs"])
    if unknown:
        raise AnnotationError(f"capabilities not in this item: {sorted(unknown)}")
    bad = [c for c, g in labels.items() if g is not None and g not in GRADES]
    if bad:
        raise AnnotationError(f"invalid grade for {bad}")
    if not any(g is not None for g in labels.values()):
        raise AnnotationError("label at least one pair")
    s.execute(
        delete(M.ValidationSample).where(
            M.ValidationSample.sample_set == SAMPLE_SET,
            M.ValidationSample.item_id == task["item_id"],
            M.ValidationSample.annotator == annotator,
        )
    )
    n = 0
    for cap, grade in labels.items():
        if grade is None:
            continue
        s.add(
            M.ValidationSample(
                sample_set=SAMPLE_SET,
                item_id=task["item_id"],
                item_type="task_capability",
                left_text=task["text"],
                right_ref=cap,
                label=grade,
                tags=task["tags"],
                language=task["language"],
                annotator=annotator,
                is_gold=False,
                is_synthetic=False,
                comment=comment.strip() or None,
            )
        )
        n += 1
    s.add(
        M.AuditLog(
            actor=annotator,
            action="benchmark_annotation",
            target=f"{SAMPLE_SET}:{task['item_id']}",
            payload={"labels": labels},
        )
    )
    return n


def human_labels(s: Session) -> dict[tuple[str, str], dict[str, int]]:
    """{(item_id, capability): {annotator: grade}} for human annotators only."""
    rows = s.scalars(
        select(M.ValidationSample).where(
            M.ValidationSample.sample_set == SAMPLE_SET, M.ValidationSample.annotator != AI_DRAFT
        )
    ).all()
    out: dict[tuple[str, str], dict[str, int]] = {}
    for r in rows:
        out.setdefault((r.item_id, r.right_ref), {})[r.annotator] = r.label
    return out


def progress(s: Session, annotator: str, tasks: dict) -> tuple[set[str], dict | None]:
    done = set(
        s.scalars(
            select(M.ValidationSample.item_id).where(
                M.ValidationSample.sample_set == SAMPLE_SET, M.ValidationSample.annotator == annotator
            )
        ).all()
    )
    nxt = next((t for t in tasks["tasks"] if t["item_id"] not in done), None)
    return done, nxt


# ------------------------------------------------------------------ agreement
def krippendorff_alpha_interval(units: list[list[float]]) -> float | None:
    """Krippendorff's alpha, interval metric; units with fewer than two values are not pairable."""
    units = [u for u in units if len(u) >= 2]
    values = [v for u in units for v in u]
    n = len(values)
    if n < 2:
        return None
    d_o = sum(sum((a - b) ** 2 for a, b in itertools.permutations(u, 2)) / (len(u) - 1) for u in units) / n
    d_e = sum((a - b) ** 2 for a, b in itertools.permutations(values, 2)) / (n * (n - 1))
    if d_e == 0:
        return None
    return 1 - d_o / d_e


def _kappa(a: list[int], b: list[int]) -> float | None:
    if len(a) < 2 or len(set(a) | set(b)) < 2:
        return None
    return float(cohen_kappa_score(a, b, weights="quadratic", labels=list(GRADES)))


def agreement(s: Session, tasks: dict) -> dict:
    labels = human_labels(s)
    draft = {(t["item_id"], c): g for t in tasks["tasks"] for c, g in t["draft"].items()}
    annotators = sorted({a for v in labels.values() for a in v})
    pairs = []
    for x, y in itertools.combinations(annotators, 2):
        common = [(v[x], v[y]) for v in labels.values() if x in v and y in v]
        pairs.append(
            {"a": x, "b": y, "n": len(common), "kappa": _kappa([c[0] for c in common], [c[1] for c in common])}
        )
    vs_draft = []
    for a in annotators:
        common = [(v[a], draft[k]) for k, v in labels.items() if a in v and k in draft]
        found = sum(1 for k, v in labels.items() if a in v and v[a] >= 1 and k not in draft)
        vs_draft.append(
            {
                "annotator": a,
                "n": len(common),
                "kappa": _kappa([c[0] for c in common], [c[1] for c in common]),
                "related_pairs_missing_from_draft": found,
            }
        )
    alpha = krippendorff_alpha_interval([list(v.values()) for v in labels.values()])
    items = {k[0] for k in labels}
    return {
        "annotators": annotators,
        "items_annotated": len(items),
        "total_items": len(tasks["tasks"]),
        "pairs_labelled": len(labels),
        "pairs_with_2plus": sum(1 for v in labels.values() if len(v) >= 2),
        "pairwise": pairs,
        "vs_ai_draft": vs_draft,
        "krippendorff_alpha": alpha,
        "interpretation": interpret(alpha),
    }


def interpret(alpha: float | None) -> str:
    """Krippendorff's conventional thresholds: ≥ 0.800 reliable, 0.667–0.800 tentative conclusions only."""
    if alpha is None:
        return "insufficient"
    if alpha >= 0.8:
        return "reliable"
    if alpha >= 0.667:
        return "tentative"
    return "unreliable"


# ------------------------------------------------------------------ gold set
def build_gold(s: Session, tasks: dict, path: Path, min_annotators: int = 2) -> dict:
    labels = human_labels(s)
    stats = agreement(s, tasks)
    by_item: dict[str, dict[str, int]] = {}
    for (item, cap), v in labels.items():
        if len(v) >= min_annotators:
            by_item.setdefault(item, {})[cap] = int(round(statistics.median(v.values())))
    meta = {
        "_meta": True,
        "version": f"{SAMPLE_SET}-gold-{datetime.now(UTC).strftime('%Y%m%d')}",
        "description": f"Human consensus labels (median of >= {min_annotators} annotators) for task-capability pairs.",
        "annotators": stats["annotators"],
        "krippendorff_alpha": stats["krippendorff_alpha"],
        "interpretation": stats["interpretation"],
        "grades": {"2": "related", "1": "partial", "0": "unrelated"},
    }
    out = [meta]
    for t in tasks["tasks"]:
        if t["item_id"] not in by_item:
            continue
        g = by_item[t["item_id"]]
        out.append(
            {
                "id": t["item_id"],
                "item_type": "task_capability",
                "source_ref": t["source_ref"],
                "text": t["text"],
                "language": t["language"],
                "relevance": {c: x for c, x in g.items() if x >= 1},
                "unrelated": sorted(c for c, x in g.items() if x == 0),
                "tags": t["tags"],
                "annotator": "human_consensus",
                "is_gold": True,
            }
        )
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n", encoding="utf-8")
    return {"items": len(out) - 1, "path": str(path), **{k: meta[k] for k in ("krippendorff_alpha", "interpretation")}}


# ------------------------------------------------------------------ claude.ai page (remote annotation)
PAGE_TEMPLATE = Path(__file__).with_name("annotation_page.html")
# Each expert writes only annotations/<own id>; only the artifact owner reads everyone's (blind, independent).
PAGE_DB_RULES = [
    {"path": "annotations", "read": "owner", "write": "self"},
    {"path": "annotations/{self}", "read": "interact", "write": "interact"},
]


def render_page(tasks: dict, caps: dict) -> str:
    """Self-contained annotation page for claude.ai. Carries NO draft labels (blinding)."""
    payload = {
        "sample_set": tasks["sample_set"],
        "tasks": [
            {"item_id": t["item_id"], "text": t["text"], "language": t["language"], "pairs": t["pairs"]}
            for t in tasks["tasks"]
        ],
        "caps": {
            c: {"name": v["name"], "definition": v["definition"], "examples": v["examples"][:2]}
            for c, v in caps.items()
            if any(c in t["pairs"] for t in tasks["tasks"])
        },
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", r"<\/")
    return PAGE_TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/", data)


def import_remote(s: Session, tasks: dict, docs: dict[str, dict]) -> dict:
    """Load annotations exported from the claude.ai page ({opaque user id: {"items": {...}}}).

    Annotators are labelled "claude.ai anotador N" by sorted id, the same order the page's owner panel uses.
    -1 ("não sei") is not stored. Re-importing replaces each annotator's answers per item.
    """
    by_id = {t["item_id"]: t for t in tasks["tasks"]}
    summary = {}
    for n, uid in enumerate(sorted(docs), 1):
        name = f"claude.ai anotador {n}"
        items = (docs[uid] or {}).get("items") or {}
        saved = 0
        for item_id, entry in items.items():
            task = by_id.get(item_id)
            labels = {c: (None if v == -1 else v) for c, v in (entry.get("labels") or {}).items()}
            if task is None or not any(v is not None for v in labels.values()):
                continue
            save_annotation(s, name, task, labels, entry.get("comment") or "")
            saved += 1
        summary[name] = saved
    return summary
