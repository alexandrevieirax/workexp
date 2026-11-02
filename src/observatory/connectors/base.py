"""Shared connector types. Connectors parse sources; they never invent values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SYNTHETIC_MARKER = "SYNTHETIC_DATA_DO_NOT_USE"


def is_marked_synthetic(path: Path) -> bool:
    """Synthetic fixtures carry an explicit marker file next to (or above, up to 3 levels) the source files."""
    p = path if path.is_dir() else path.parent
    return any((d / SYNTHETIC_MARKER).exists() for d in [p, *list(p.parents)[:3]])


class SourceUnavailableError(RuntimeError):
    """Raised when an official file/API is missing. Carries the manual procedure."""

    def __init__(self, message: str, procedure: str, expected_location: str):
        super().__init__(f"{message}\nExpected location: {expected_location}\nProcedure: {procedure}")
        self.procedure = procedure
        self.expected_location = expected_location


class SchemaValidationError(ValueError):
    def __init__(self, source: str, file: str, missing: list[str], found: list[str]):
        super().__init__(f"[{source}] {file}: missing columns {missing}; found {found}")
        self.missing = missing


def require_columns(source: str, file: str, columns: list[str], required: list[str]) -> None:
    missing = [c for c in required if c not in columns]
    if missing:
        raise SchemaValidationError(source, file, missing, list(columns))


@dataclass
class SourceDescriptor:
    dataset_code: str
    dataset_name: str
    publisher: str
    homepage: str
    version: str
    source_url: str
    retrieval_method: str
    file_sha256: str | None
    license_name: str
    license_url: str | None
    retrieval_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None
    is_synthetic: bool = False


@dataclass
class ParsedOccupation:
    taxonomy: str
    code: str
    title: str
    description: str | None
    language: str
    group_code: str | None = None
    qualification_level: float | None = None
    aliases: list[tuple[str, str, str]] = field(default_factory=list)  # (label, language, alias_type)
    attributes: dict[str, Any] = field(default_factory=dict)
    is_synthetic: bool = False


@dataclass
class ParsedTask:
    original_id: str
    statement: str
    language: str
    unit_type: str
    task_type: str | None = None
    ratings: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
