from __future__ import annotations

import numpy as np

from observatory.db.session import create_schema, make_engine, session_factory
from observatory.embeddings import store
from observatory.embeddings.providers import Embedder, HashingBaselineProvider


def test_embeddings_are_deterministic_and_normalized():
    a = Embedder(HashingBaselineProvider()).embed(["Desenvolver programas de computador"], "pt")
    b = Embedder(HashingBaselineProvider()).embed(["Desenvolver programas de computador"], "pt")
    assert np.array_equal(a, b)
    assert np.allclose(np.linalg.norm(a, axis=1), 1.0)


def test_cache_hits_and_key_versioning():
    p = HashingBaselineProvider()
    e = Embedder(p)
    e.embed(["x y z", "a b c"])
    e.embed(["x y z"])
    assert e.cache.hits == 1 and e.cache.misses == 2
    k = p.cache_key("x", "en", "query")
    assert k != p.cache_key("x", "pt", "query")
    assert k != p.cache_key("x", "en", "passage")
    assert k != HashingBaselineProvider(dimension=1024).cache_key("x", "en", "query")


def test_lexical_baseline_is_flagged_as_not_semantic():
    p = HashingBaselineProvider()
    assert p.is_semantic is False and "baseline" in p.model_key


def test_embedding_cache_persists_with_model_and_hash():
    engine = make_engine("sqlite://")
    create_schema(engine)
    s = session_factory(engine)()
    e = Embedder(HashingBaselineProvider())
    v = e.embed(["texto de teste"], "pt")
    assert store.persist(e, s) == 1
    assert store.persist(e, s) == 0  # idempotent
    fresh = Embedder(HashingBaselineProvider())
    assert store.load_into(fresh, s) == 1
    assert np.allclose(fresh.embed(["texto de teste"], "pt"), v) and fresh.cache.hits == 1
