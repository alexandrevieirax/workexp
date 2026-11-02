"""Human review of crosswalk proposals: one code path for the JSON API, the HTML review page and the pipeline.

Decisions are stored on the mapping row (status, reviewer, justification), in ``crosswalk_change`` (history),
``expert_review`` and ``audit_log``. Each pipeline run creates new proposal rows, so decisions are looked up by
(source taxonomy, source code, target code) — not by row id — and carried into new runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from observatory.db import models as M

ACTIONS = {"accept": "accepted", "reject": "rejected", "edit": "edited", "split": "split", "merge": "merged"}
DECISIONS = ("accepted", "rejected")


class ReviewError(ValueError):
    pass


@dataclass
class Decision:
    status: str
    mapping_id: int
    reviewer: str | None
    justification: str | None
    at: datetime


def apply_review(
    s: Session,
    mp: M.OccupationSourceMapping,
    action: str,
    reviewer: str,
    justification: str,
    actor: str,
    edits: dict | None = None,
    before: dict | None = None,
) -> M.OccupationSourceMapping:
    if action not in ACTIONS:
        raise ReviewError(f"unknown action {action!r}")
    if len(reviewer.strip()) < 2:
        raise ReviewError("reviewer name is required")
    if len(justification.strip()) < 10:
        raise ReviewError("justification must have at least 10 characters")
    mp.status = ACTIONS[action]
    mp.reviewer, mp.justification = reviewer.strip(), justification.strip()
    if action == "edit" and edits:
        for k in ("mapping_confidence", "confidence_class", "target_occupation_id"):
            if k in edits:
                setattr(mp, k, edits[k])
    payload = {"action": action, "reviewer": mp.reviewer, "justification": mp.justification, "edits": edits}
    mp.history.append(
        M.CrosswalkChange(
            action=action, before=before, after=payload, actor=mp.reviewer, justification=mp.justification
        )
    )
    s.add(
        M.ExpertReview(
            target_type="crosswalk",
            target_id=str(mp.id),
            reviewer=mp.reviewer,
            decision=action,
            justification=mp.justification,
        )
    )
    s.add(M.AuditLog(actor=actor, action=f"crosswalk_{action}", target=f"mapping:{mp.id}", payload=payload))
    return mp


def human_decisions(s: Session, source_taxonomy: str, source_code: str) -> dict[str, Decision]:
    """Latest human accept/reject per target occupation code for a source occupation, across all runs."""
    src, tgt = aliased(M.Occupation), aliased(M.Occupation)
    rows = s.execute(
        select(M.OccupationSourceMapping, tgt.code)
        .join(src, src.id == M.OccupationSourceMapping.source_occupation_id)
        .join(tgt, tgt.id == M.OccupationSourceMapping.target_occupation_id)
        .where(
            src.taxonomy == source_taxonomy,
            src.code == source_code,
            M.OccupationSourceMapping.status.in_(DECISIONS),
            M.OccupationSourceMapping.reviewer.is_not(None),
        )
        .order_by(M.OccupationSourceMapping.updated_at)
    ).all()
    out: dict[str, Decision] = {}
    for mp, code in rows:  # later decisions overwrite earlier ones
        out[code] = Decision(mp.status, mp.id, mp.reviewer, mp.justification, mp.updated_at)
    return out


def carry_decision(mp: M.OccupationSourceMapping, decision: Decision, run_id: str) -> None:
    """Copy a prior human decision onto a freshly proposed mapping row of a new run (with history)."""
    mp.status = decision.status
    mp.reviewer = decision.reviewer
    mp.justification = f"{decision.justification} [decisão herdada do mapeamento #{decision.mapping_id}]"
    mp.history.append(
        M.CrosswalkChange(
            action="carry",
            before=None,
            after={"status": decision.status, "from_mapping": decision.mapping_id},
            actor=f"pipeline:{run_id}",
            justification=f"carried human decision #{decision.mapping_id}",
        )
    )
