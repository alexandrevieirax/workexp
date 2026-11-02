"""Provider-agnostic embedding layer with content-addressed caching.

Cache key = sha256(model_key | canonical params | language | sha256(text)); vectors are L2-normalized.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from observatory.normalization.text import strip_accents
from observatory.provenance import canonical_json, sha256_text

CANDIDATE_MODELS = {
    "intfloat/multilingual-e5-large": {"query_prefix": "query: ", "passage_prefix": "passage: ", "dimension": 1024},
    "BAAI/bge-m3": {"query_prefix": "", "passage_prefix": "", "dimension": 1024},
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": {
        "query_prefix": "",
        "passage_prefix": "",
        "dimension": 768,
    },
}


class EmbeddingProvider(abc.ABC):
    model_key: str
    dimension: int
    is_semantic: bool = True
    params: dict

    @abc.abstractmethod
    def _encode(self, texts: list[str], kind: str) -> np.ndarray: ...

    def cache_key(self, text: str, language: str | None, kind: str) -> str:
        return sha256_text(
            "|".join([self.model_key, canonical_json({**self.params, "kind": kind}), language or "", sha256_text(text)])
        )

    def describe(self) -> dict:
        return {
            "model_key": self.model_key,
            "dimension": self.dimension,
            "params": self.params,
            "is_semantic": self.is_semantic,
        }


class HashingBaselineProvider(EmbeddingProvider):
    """Offline, deterministic LEXICAL baseline (character n-grams + words, hashed). Not a semantic model.

    Exists so the MVP runs without downloads or paid APIs and as the floor every candidate model must beat.
    """

    is_semantic = False

    def __init__(self, dimension: int = 2048, ngram_range: tuple[int, int] = (3, 5)):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dimension = dimension
        self.params = {
            "analyzer": "char_wb+word",
            "ngram_range": list(ngram_range),
            "norm": "l2",
            "alternate_sign": False,
            "lowercase": True,
            "strip_accents": True,
        }
        self.model_key = f"baseline/char-ngram-hashing@v1-d{dimension}"
        kw = dict(n_features=dimension, alternate_sign=False, norm=None, lowercase=True)
        self._char = HashingVectorizer(analyzer="char_wb", ngram_range=ngram_range, **kw)
        self._word = HashingVectorizer(analyzer="word", ngram_range=(1, 1), **kw)

    def _encode(self, texts: list[str], kind: str) -> np.ndarray:
        folded = [strip_accents(t) for t in texts]
        m = self._char.transform(folded).toarray() + 2.0 * self._word.transform(folded).toarray()
        return m


class SentenceTransformerProvider(EmbeddingProvider):
    """Local Sentence Transformers model (optional dependency: pip install '.[ml]')."""

    def __init__(self, model_name: str, revision: str | None = None, device: str | None = None):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError("sentence-transformers not installed; pip install '.[ml]'") from exc
        self._model = SentenceTransformer(model_name, revision=revision, device=device or "cpu")
        meta = CANDIDATE_MODELS.get(model_name, {"query_prefix": "", "passage_prefix": ""})
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        self.params = {
            "query_prefix": meta["query_prefix"],
            "passage_prefix": meta["passage_prefix"],
            "normalize": True,
        }
        # Pin the exact Hugging Face snapshot so cached vectors are tied to the weights that produced them.
        self.model_key = f"sentence-transformers:{model_name}@{(revision or _resolved_revision(model_name))[:12]}"

    def _encode(self, texts: list[str], kind: str) -> np.ndarray:  # pragma: no cover - needs model download
        prefix = self.params["query_prefix"] if kind == "query" else self.params["passage_prefix"]
        return self._model.encode(
            [prefix + t for t in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=32,
            show_progress_bar=False,
        )


def _resolved_revision(model_name: str) -> str:
    try:
        from huggingface_hub import snapshot_download

        return Path(snapshot_download(model_name, local_files_only=True)).name[:12]
    except Exception:  # pragma: no cover - offline cache layout differences
        return "unresolved"


class ExternalAPIProvider(EmbeddingProvider):
    """Placeholder contract for commercial APIs; only active when credentials are configured."""

    def __init__(self, model_key: str, env_var: str, dimension: int):
        if not os.environ.get(env_var):
            raise RuntimeError(f"{env_var} not set; external embedding provider disabled (MVP needs no paid API)")
        self.model_key, self.dimension, self.params = model_key, dimension, {"env": env_var}

    def _encode(self, texts: list[str], kind: str) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError("implement the vendor call in a subclass")


@dataclass
class EmbeddingCache:
    """In-memory cache; ``observatory.embeddings.store`` persists to the ``embedding`` table."""

    entries: dict[str, np.ndarray] = field(default_factory=dict)
    texts: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    hits: int = 0
    misses: int = 0


class Embedder:
    def __init__(self, provider: EmbeddingProvider, cache: EmbeddingCache | None = None):
        self.provider = provider
        self.cache = cache or EmbeddingCache()

    def embed(self, texts: list[str], language: str | None = None, kind: str = "passage") -> np.ndarray:
        keys = [self.provider.cache_key(t, language, kind) for t in texts]
        todo = [(i, t) for i, (k, t) in enumerate(zip(keys, texts, strict=True)) if k not in self.cache.entries]
        self.cache.hits += len(texts) - len(todo)
        self.cache.misses += len(todo)
        if todo:
            vecs = self.provider._encode([t for _, t in todo], kind)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs = vecs / np.where(norms == 0, 1, norms)
            for (i, t), v in zip(todo, vecs, strict=True):
                self.cache.entries[keys[i]] = v.astype(np.float32)
                self.cache.texts[keys[i]] = (t, language)
        return np.vstack([self.cache.entries[k] for k in keys]) if keys else np.zeros((0, self.provider.dimension))


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a @ b.T


def get_provider(spec: str, revision: str | None = None) -> EmbeddingProvider:
    if spec == "baseline":
        return HashingBaselineProvider()
    if spec.startswith("sentence-transformers:"):
        return SentenceTransformerProvider(spec.split(":", 1)[1], revision=revision)
    raise ValueError(f"unknown embedding provider spec {spec!r}")
