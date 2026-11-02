"""Anthropic Economic Index (observed usage) connector — task-level shares mapped to O*NET task text."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import httpx
import pandas as pd

from observatory.connectors.base import SourceDescriptor, SourceUnavailableError, is_marked_synthetic, require_columns
from observatory.normalization.text import normalize_text
from observatory.provenance import sha256_file

HF_BASE = "https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main"
FILES = ["task_pct_v2.csv", "automation_vs_augmentation_by_task.csv"]
AUTOMATION_COLS = ["directive", "feedback_loop"]
AUGMENTATION_COLS = ["validation", "task_iteration", "learning"]
# AEI release_2025_03_27 maps to the SOC-2010-based O*NET taxonomy; many statements were reworded in later
# O*NET versions, so exact matching under-counts. Fuzzy matches at or above this ratio are accepted and flagged.
FUZZY_ACCEPT = 0.85


def download(release: str, dest_dir: Path, client: httpx.Client | None = None) -> Path:
    target = dest_dir / release
    target.mkdir(parents=True, exist_ok=True)
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    for f in FILES:
        p = target / f
        if not p.exists():
            r = client.get(f"{HF_BASE}/{release}/{f}")
            r.raise_for_status()
            p.write_bytes(r.content)
    return target


@dataclass
class ObservedUsage:
    pct: float
    percentile: float
    automation_share: float | None
    augmentation_share: float | None
    filtered_share: float | None
    match_method: str = "exact_normalized_text"
    match_score: float = 1.0
    matched_text: str | None = None


class AeiRelease:
    def __init__(self, directory: Path, release: str):
        self.directory = directory
        self.release = release
        p = directory / "task_pct_v2.csv"
        if not p.exists():
            raise SourceUnavailableError(
                "AEI release files not found",
                f"python -m observatory.cli download-aei --release {release}",
                str(directory),
            )
        pct = pd.read_csv(p)
        require_columns("AEI", p.name, list(pct.columns), ["task_name", "pct"])
        pct["key"] = pct["task_name"].map(normalize_text)
        pct = pct.groupby("key", as_index=False)["pct"].sum()
        pct["percentile"] = pct["pct"].rank(pct=True, method="average")
        self._pct = pct.set_index("key")
        self._mix = None
        mp = directory / "automation_vs_augmentation_by_task.csv"
        if mp.exists():
            mix = pd.read_csv(mp)
            require_columns(
                "AEI", mp.name, list(mix.columns), ["task_name", *AUTOMATION_COLS, *AUGMENTATION_COLS, "filtered"]
            )
            mix["key"] = mix["task_name"].map(normalize_text)
            self._mix = mix.drop_duplicates("key").set_index("key")
        self.files = [p] + ([mp] if mp.exists() else [])

    def descriptor(self) -> SourceDescriptor:
        return SourceDescriptor(
            dataset_code="AEI",
            dataset_name="Anthropic Economic Index",
            publisher="Anthropic",
            homepage="https://huggingface.co/datasets/Anthropic/EconomicIndex",
            version=self.release,
            source_url=f"{HF_BASE}/{self.release}/",
            retrieval_method="download",
            file_sha256=sha256_file(self.files[0]),
            license_name="See dataset card (verify)",
            license_url="https://huggingface.co/datasets/Anthropic/EconomicIndex",
            notes="Observed usage of Claude.ai conversations mapped to O*NET tasks (preprint: handa2025which)",
            is_synthetic=is_marked_synthetic(self.directory),
        )

    @property
    def n_tasks(self) -> int:
        return len(self._pct)

    def _fuzzy(self, key: str) -> tuple[str, float] | None:
        words = set(key.split())
        best, best_score = None, 0.0
        for cand in self._pct.index:
            cw = set(cand.split())
            if len(words & cw) / max(1, len(words | cw)) < 0.4:  # cheap prefilter (Jaccard)
                continue
            score = SequenceMatcher(None, key, cand).ratio()
            if score > best_score:
                best, best_score = cand, score
        return (best, best_score) if best is not None else None

    def lookup(self, task_statement: str) -> ObservedUsage | None:
        key = normalize_text(task_statement)
        method, score = "exact_normalized_text", 1.0
        if key not in self._pct.index:
            fuzzy = self._fuzzy(key)
            if fuzzy is None or fuzzy[1] < FUZZY_ACCEPT:
                return None
            key, score = fuzzy
            method = "fuzzy_text"
        row = self._pct.loc[key]
        auto = aug = filt = None
        if self._mix is not None and key in self._mix.index:
            m = self._mix.loc[key]
            filt = float(m["filtered"])
            denom = 1 - filt
            if denom > 0:
                auto = float(sum(m[c] for c in AUTOMATION_COLS)) / denom
                aug = float(sum(m[c] for c in AUGMENTATION_COLS)) / denom
        return ObservedUsage(
            pct=float(row["pct"]),
            percentile=float(row["percentile"]),
            automation_share=auto,
            augmentation_share=aug,
            filtered_share=filt,
            match_method=method,
            match_score=round(score, 4),
            matched_text=key,
        )
