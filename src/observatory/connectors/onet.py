"""O*NET text-database connector (zip or extracted directory). Supports the 31.0 layout and earlier ones."""

from __future__ import annotations

import io
import re
import zipfile
from functools import cached_property
from pathlib import Path

import httpx
import pandas as pd

from observatory.connectors.base import (
    ParsedOccupation,
    ParsedTask,
    SourceDescriptor,
    SourceUnavailableError,
    is_marked_synthetic,
    require_columns,
)
from observatory.normalization.scales import ScaleRegistry
from observatory.provenance import sha256_file

DOWNLOAD_URL = "https://www.onetcenter.org/dl_files/database/db_{v}_text.zip"
# Harmonization rule jobzone_to_isco_skill_level_v0: Job Zone -> ISCO-08 skill level (1..4) rescaled to 0-1.
JOB_ZONE_TO_LEVEL = {1: 0.0, 2: 1 / 3, 3: 2 / 3, 4: 1.0, 5: 1.0}

REQUIRED = {
    "Occupation Data.txt": ["O*NET-SOC Code", "Title", "Description"],
    "Task Statements.txt": ["O*NET-SOC Code", "Task ID", "Task", "Task Type"],
    "Task Ratings.txt": [
        "O*NET-SOC Code",
        "Task ID",
        "Scale ID",
        "Category",
        "Data Value",
        "N",
        "Standard Error",
        "Lower CI Bound",
        "Upper CI Bound",
        "Recommend Suppress",
    ],
    "Scales Reference.txt": ["Scale ID", "Scale Name", "Minimum", "Maximum"],
    "Job Zones.txt": ["O*NET-SOC Code", "Job Zone"],
}
DESCRIPTOR_FILES = {
    "work_context": ["Work Context.txt"],
    "work_activity": ["Work Activities.txt"],
    "knowledge": ["Knowledge.txt"],
    "ability": ["Abilities.txt"],
    "skill": ["Essential Skills.txt", "Transferable Skills.txt", "Skills.txt"],
}


def download(version: str, dest_dir: Path, client: httpx.Client | None = None) -> Path:
    v = version.replace(".", "_")
    url = DOWNLOAD_URL.format(v=v)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"db_{v}_text.zip"
    if target.exists():
        return target
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    with client.stream("GET", url) as resp:
        resp.raise_for_status()
        with open(target, "wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return target


class OnetArchive:
    def __init__(self, path: Path, is_synthetic: bool = False):
        if not path.exists():
            raise SourceUnavailableError(
                "O*NET archive not found",
                procedure="python -m observatory.cli download-onet --version 31.0",
                expected_location=str(path),
            )
        self.path = path
        self.is_synthetic = is_synthetic or is_marked_synthetic(path)
        self._cache: dict[str, pd.DataFrame] = {}

    # ------------------------------------------------------------------ raw access
    @cached_property
    def _members(self) -> dict[str, str]:
        if self.path.is_dir():
            return {p.name: str(p) for p in self.path.rglob("*.txt")}
        with zipfile.ZipFile(self.path) as z:
            return {Path(n).name: n for n in z.namelist() if n.endswith(".txt")}

    def has(self, name: str) -> bool:
        return name in self._members

    def _read_bytes(self, name: str) -> bytes:
        if name not in self._members:
            raise SourceUnavailableError(f"{name} missing from O*NET archive", "re-download", str(self.path))
        if self.path.is_dir():
            return Path(self._members[name]).read_bytes()
        with zipfile.ZipFile(self.path) as z:
            return z.read(self._members[name])

    def table(self, name: str) -> pd.DataFrame:
        if name not in self._cache:
            df = pd.read_csv(io.BytesIO(self._read_bytes(name)), sep="\t", dtype=str, keep_default_na=False)
            if name in REQUIRED:
                require_columns("ONET", name, list(df.columns), REQUIRED[name])
            self._cache[name] = df
        return self._cache[name]

    def validate(self) -> list[str]:
        for name in REQUIRED:
            self.table(name)
        return list(REQUIRED)

    # ------------------------------------------------------------------ metadata
    @cached_property
    def version(self) -> str:
        if self.has("Read Me.txt"):
            m = re.search(r"O\*NET\s+([\d.]+)\s+Database", self._read_bytes("Read Me.txt").decode("utf-8", "replace"))
            if m:
                return m.group(1)
        raise ValueError("cannot determine O*NET version from Read Me.txt")

    def descriptor(self) -> SourceDescriptor:
        return SourceDescriptor(
            dataset_code="ONET",
            dataset_name="O*NET Database",
            publisher="U.S. Department of Labor / National Center for O*NET Development",
            homepage="https://www.onetcenter.org/database.html",
            version=self.version,
            source_url=DOWNLOAD_URL.format(v=self.version.replace(".", "_")),
            retrieval_method="download" if not self.is_synthetic else "synthetic_fixture",
            file_sha256=sha256_file(self.path) if self.path.is_file() else None,
            license_name="CC BY 4.0",
            license_url="https://www.onetcenter.org/license_db.html",
            is_synthetic=self.is_synthetic,
        )

    @cached_property
    def scales(self) -> ScaleRegistry:
        return ScaleRegistry.from_rows(self.table("Scales Reference.txt").to_dict("records"))

    # ------------------------------------------------------------------ occupation
    def occupation(self, code: str) -> ParsedOccupation:
        occ = self.table("Occupation Data.txt")
        row = occ[occ["O*NET-SOC Code"] == code]
        if row.empty:
            raise KeyError(f"O*NET-SOC {code} not in database {self.version}")
        r = row.iloc[0]
        jz = self.table("Job Zones.txt")
        jzr = jz[jz["O*NET-SOC Code"] == code]
        job_zone = int(jzr.iloc[0]["Job Zone"]) if not jzr.empty else None
        aliases = [(r["Title"], "en", "preferred")]
        if self.has("Job Titles.txt"):
            jt = self.table("Job Titles.txt")
            aliases += [(t, "en", "alternative") for t in jt.loc[jt["O*NET-SOC Code"] == code, "Job Title"]]
        if self.has("Sample of Reported Titles.txt"):
            st = self.table("Sample of Reported Titles.txt")
            aliases += [(t, "en", "reported") for t in st.loc[st["O*NET-SOC Code"] == code, "Reported Job Title"]]
        return ParsedOccupation(
            taxonomy="ONET",
            code=code,
            title=r["Title"],
            description=r["Description"],
            language="en",
            group_code=code[:7],  # SOC detailed occupation
            qualification_level=JOB_ZONE_TO_LEVEL.get(job_zone) if job_zone else None,
            aliases=list(dict.fromkeys(aliases)),
            attributes={"job_zone": job_zone, "soc_major_group": code[:2]},
            is_synthetic=self.is_synthetic,
        )

    def tasks(self, code: str, include_emerging: bool = False) -> list[ParsedTask]:
        ts = self.table("Task Statements.txt")
        ts = ts[ts["O*NET-SOC Code"] == code]
        ratings = self._task_ratings(code)
        out = [
            ParsedTask(
                original_id=r["Task ID"],
                statement=r["Task"],
                language="en",
                unit_type="onet_task",
                task_type=r["Task Type"] or None,
                ratings=ratings.get(r["Task ID"], {}),
                attributes={
                    "incumbents_responding": r.get("Incumbents Responding"),
                    "date": r.get("Date"),
                    "domain_source": r.get("Domain Source"),
                },
            )
            for _, r in ts.iterrows()
        ]
        if include_emerging and self.has("Emerging Tasks.txt"):
            et = self.table("Emerging Tasks.txt")
            for i, r in et[et["O*NET-SOC Code"] == code].reset_index().iterrows():
                out.append(
                    ParsedTask(
                        original_id=f"emerging-{i}",
                        statement=r["Task"],
                        language="en",
                        unit_type="onet_emerging_task",
                        task_type=r["Category"],
                    )
                )
        return out

    def _task_ratings(self, code: str) -> dict[str, dict]:
        tr = self.table("Task Ratings.txt")
        tr = tr[tr["O*NET-SOC Code"] == code]
        out: dict[str, dict] = {}
        for _, r in tr.iterrows():
            entry = out.setdefault(r["Task ID"], {})
            rec = {
                "value": _f(r["Data Value"]),
                "n": _i(r["N"]),
                "se": _f(r["Standard Error"]),
                "ci_low": _f(r["Lower CI Bound"]),
                "ci_high": _f(r["Upper CI Bound"]),
                "suppressed": r["Recommend Suppress"] == "Y",
            }
            if r["Scale ID"] == "FT":
                entry.setdefault("FT", {})[r["Category"]] = rec
            else:
                entry[r["Scale ID"]] = rec
        return out

    def descriptors(self, code: str, domain: str) -> list[dict]:
        rows: list[dict] = []
        for name in DESCRIPTOR_FILES[domain]:
            if not self.has(name):
                continue
            df = self.table(name)
            df = df[df["O*NET-SOC Code"] == code]
            for _, r in df.iterrows():
                rows.append(
                    {
                        "domain": domain,
                        "element_id": r["Element ID"],
                        "element_name": r["Element Name"],
                        "scale_id": r["Scale ID"],
                        "category": _none(r.get("Category")),
                        "value": _f(r["Data Value"]),
                        "n": _i(r.get("N")),
                        "standard_error": _f(r.get("Standard Error")),
                        "ci_low": _f(r.get("Lower CI Bound")),
                        "ci_high": _f(r.get("Upper CI Bound")),
                        "suppressed": r.get("Recommend Suppress") == "Y",
                        "not_relevant": r.get("Not Relevant") == "Y",
                        "data_date": _none(r.get("Date")),
                        "domain_source": _none(r.get("Domain Source")),
                        "file": name,
                    }
                )
        return rows

    def dwas_for_tasks(self, code: str) -> dict[str, list[tuple[str, str]]]:
        if not self.has("Tasks to DWAs.txt"):
            return {}
        t2d = self.table("Tasks to DWAs.txt")
        t2d = t2d[t2d["O*NET-SOC Code"] == code]
        names = {}
        if self.has("GWAs to IWAs to DWAs.txt"):
            ref = self.table("GWAs to IWAs to DWAs.txt")
            names = dict(zip(ref["DWA Element ID"], ref["DWA Element Name"], strict=False))
        out: dict[str, list[tuple[str, str]]] = {}
        for _, r in t2d.iterrows():
            out.setdefault(r["Task ID"], []).append((r["DWA Element ID"], names.get(r["DWA Element ID"], "")))
        return out


def _none(v):
    return None if v in (None, "", "n/a") else v


def _f(v) -> float | None:
    v = _none(v)
    return float(v) if v is not None else None


def _i(v) -> int | None:
    v = _none(v)
    return int(float(v)) if v is not None else None
