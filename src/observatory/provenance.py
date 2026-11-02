"""Hashing and pipeline-version helpers used to make every record traceable."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from observatory.config import PROJECT_ROOT


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def sha256_json(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def source_tree_hash(root: Path | None = None) -> str:
    root = root or PROJECT_ROOT / "src" / "observatory"
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def pipeline_version() -> dict[str, Any]:
    """Git commit when available; always the source-tree hash (works on uncommitted trees)."""
    info: dict[str, Any] = {"source_tree_sha256": source_tree_hash()}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        info["git_commit"] = commit.stdout.strip() if commit.returncode == 0 else None
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        info["git_dirty"] = bool(status.stdout.strip()) if status.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        info["git_commit"] = None
        info["git_dirty"] = None
    return info
