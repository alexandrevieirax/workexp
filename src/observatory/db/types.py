"""Dialect-portable column types."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.types import JSON, Text, TypeDecorator


class VectorType(TypeDecorator):
    """pgvector ``vector`` on PostgreSQL, JSON-encoded list elsewhere (SQLite tests).

    Dimension is intentionally not fixed: one table stores vectors from several
    embedding models; per-model HNSW indexes are created on PostgreSQL with a
    partial index over ``model_key`` (see migrations).
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        values = [float(x) for x in value]
        if dialect.name == "postgresql":
            return values
        return json.dumps(values)

    def process_result_value(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return [float(x) for x in value]


JSONType = JSON
