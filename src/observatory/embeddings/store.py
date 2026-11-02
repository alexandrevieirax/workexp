"""Persist / reload the embedding cache to the ``embedding`` table (pgvector on PostgreSQL)."""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from observatory.db.models import Embedding
from observatory.embeddings.providers import Embedder
from observatory.provenance import sha256_text


def load_into(embedder: Embedder, session: Session) -> int:
    rows = session.scalars(select(Embedding).where(Embedding.model_key == embedder.provider.model_key)).all()
    for r in rows:
        embedder.cache.entries[r.cache_key] = np.asarray(r.vector, dtype=np.float32)
        embedder.cache.texts[r.cache_key] = (r.text, r.language)
    return len(rows)


def persist(embedder: Embedder, session: Session) -> int:
    existing = set(
        session.scalars(select(Embedding.cache_key).where(Embedding.model_key == embedder.provider.model_key)).all()
    )
    added = 0
    for key, vec in embedder.cache.entries.items():
        if key in existing:
            continue
        text, language = embedder.cache.texts[key]
        session.add(
            Embedding(
                cache_key=key,
                model_key=embedder.provider.model_key,
                dimension=embedder.provider.dimension,
                params=embedder.provider.params,
                language=language,
                text_hash=sha256_text(text),
                text=text,
                vector=vec.tolist(),
            )
        )
        added += 1
    session.flush()
    return added
