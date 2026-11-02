"""Load and validate the versioned AI capability dictionary (family defaults + per-capability overrides)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from observatory.config import get_settings
from observatory.normalization.text import normalize_text
from observatory.provenance import sha256_file, sha256_json

PRIOR_KEYS = (
    "technical_capability",
    "maturity",
    "data_infrastructure",
    "supervision_need",
    "augmentation_affinity",
    "automation_affinity",
)


class Priors(BaseModel):
    technical_capability: float = Field(ge=0, le=1)
    maturity: float = Field(ge=0, le=1)
    data_infrastructure: float = Field(ge=0, le=1)
    supervision_need: float = Field(ge=0, le=1)
    augmentation_affinity: float = Field(ge=0, le=1)
    automation_affinity: float = Field(ge=0, le=1)


class Capability(BaseModel):
    capability_id: str
    family: str
    family_name: str
    name: str
    definition: str
    examples: list[str]
    negative_examples: list[str]
    technologies: list[str]
    modality: list[str]
    input_requirements: str
    output_type: str
    autonomy_levels: list[str]
    supervision_need: float
    limitations: list[str]
    risks: list[str]
    references: list[str]
    benchmarks: list[str] = []
    priors: Priors
    version: str
    valid_until: str
    review_status: str
    note: str | None = None

    @field_validator("examples")
    @classmethod
    def _needs_examples(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("capability needs at least one positive example")
        return v

    def positive_text(self) -> str:
        return f"{self.name}. {self.definition} " + " ".join(self.examples)


class CapabilityDictionary(BaseModel):
    version: str
    released_at: str
    valid_until: str
    status: str
    review_status: str
    content_hash: str
    capabilities: list[Capability]

    def by_id(self) -> dict[str, Capability]:
        return {c.capability_id: c for c in self.capabilities}

    def families(self) -> dict[str, str]:
        return {c.family: c.family_name for c in self.capabilities}


def default_path(version: str = "0.1.0") -> Path:
    return get_settings().capabilities_dir / f"ai_capabilities_v{version}.yaml"


def load_dictionary(path: Path | None = None) -> CapabilityDictionary:
    path = path or default_path()
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    caps: list[Capability] = []
    for fam_code, fam in raw["families"].items():
        defaults = fam.get("defaults", {})
        for entry in fam["capabilities"]:
            priors = {**defaults.get("priors", {}), **entry.get("priors", {})}
            merged = {**{k: v for k, v in defaults.items() if k != "priors"}, **entry}
            caps.append(
                Capability(
                    capability_id=entry["id"],
                    family=fam_code,
                    family_name=fam["name"],
                    name=entry["name"],
                    definition=entry["definition"],
                    examples=merged.get("examples", []),
                    negative_examples=merged.get("negative_examples", []),
                    technologies=merged.get("technologies", []),
                    modality=merged.get("modality", []),
                    input_requirements=merged.get("input_requirements", ""),
                    output_type=merged.get("output_type", ""),
                    autonomy_levels=merged.get("autonomy_levels", []),
                    supervision_need=priors["supervision_need"],
                    limitations=merged.get("limitations", []),
                    risks=merged.get("risks", []),
                    references=merged.get("references", []),
                    benchmarks=merged.get("benchmarks", []),
                    priors=Priors(**priors),
                    version=raw["version"],
                    valid_until=raw["valid_until"],
                    review_status=entry.get("review_status", raw["review_status"]),
                    note=merged.get("note"),
                )
            )
    ids = [c.capability_id for c in caps]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate capability ids")
    return CapabilityDictionary(
        version=raw["version"],
        released_at=raw["released_at"],
        valid_until=raw["valid_until"],
        status=raw["status"],
        review_status=raw["review_status"],
        content_hash=sha256_file(path),
        capabilities=caps,
    )


def capability_hash(cap: Capability) -> str:
    return sha256_json(cap.model_dump())


def find_leakage(dictionary: CapabilityDictionary, task_statements: list[str]) -> list[tuple[str, str]]:
    """Capability examples identical to an evaluated task statement inflate E1 (data leakage)."""
    tasks = {normalize_text(t) for t in task_statements}
    leaks = []
    for cap in dictionary.capabilities:
        for ex in cap.examples + cap.negative_examples:
            if normalize_text(ex) in tasks:
                leaks.append((cap.capability_id, ex))
    return leaks
