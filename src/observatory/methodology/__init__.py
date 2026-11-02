"""Methodology registry: loads the YAML configuration and computes the binding fingerprint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from observatory.config import PROJECT_ROOT, get_settings
from observatory.provenance import sha256_json, sha256_text

FORMULA_MODULES = [
    PROJECT_ROOT / "src" / "observatory" / "exposure" / "formulas.py",
    PROJECT_ROOT / "src" / "observatory" / "exposure" / "weights.py",
    PROJECT_ROOT / "src" / "observatory" / "crosswalk" / "engine.py",
    PROJECT_ROOT / "src" / "observatory" / "exposure" / "engine.py",  # Monte Carlo, sensitivity, uncertainty flags
    PROJECT_ROOT / "src" / "observatory" / "exposure" / "dimensions.py",  # E1 matching, priors, lexical cues
]


@dataclass
class Methodology:
    version: str
    config: dict[str, Any]
    lexicon: dict[str, dict[str, list[str]]]
    config_path: Path
    capability_dictionary_file: str

    @property
    def fingerprint(self) -> str:
        return compute_fingerprint(self.config_path, self.capability_dictionary_file)


def registry_path() -> Path:
    return get_settings().methodology_dir / "registry.json"


def load_registry() -> dict[str, Any]:
    return json.loads(registry_path().read_text(encoding="utf-8"))


def _read_normalized(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def compute_fingerprint(config_path: Path, capability_file: str) -> str:
    parts = {
        "config": sha256_text(_read_normalized(config_path)),
        "lexicon": sha256_text(
            _read_normalized(
                config_path.parent / yaml.safe_load(_read_normalized(config_path))["lexical_adjustment"]["lexicon_file"]
            )
        ),
        "capabilities": sha256_text(_read_normalized(get_settings().capabilities_dir / capability_file)),
        "formulas": {p.name: sha256_text(_read_normalized(p)) for p in FORMULA_MODULES},
    }
    return sha256_json(parts)


def load_methodology(version: str | None = None) -> Methodology:
    reg = load_registry()
    version = version or reg["current"]
    entry = next(v for v in reg["versions"] if v["version"] == version)
    path = get_settings().methodology_dir / entry["config_file"]
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config["version"] != version:
        raise ValueError(f"config file declares {config['version']} but registry says {version}")
    lexicon = yaml.safe_load((path.parent / config["lexical_adjustment"]["lexicon_file"]).read_text(encoding="utf-8"))
    return Methodology(
        version=version,
        config=config,
        lexicon=lexicon,
        config_path=path,
        capability_dictionary_file=entry["capability_dictionary"],
    )
