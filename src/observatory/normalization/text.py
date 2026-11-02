"""Text normalization. Rules are named so that each record can list exactly what was applied."""

from __future__ import annotations

import re
import unicodedata

NORMALIZATION_RULES = ["unicode_nfkc", "strip_accents", "lowercase", "collapse_whitespace", "strip_trailing_period"]

_WS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = strip_accents(t).lower()
    t = _WS.sub(" ", t).strip()
    return t.rstrip(".").strip()


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(text))


def split_gendered_title(title: str) -> list[str]:
    """ESCO pt titles come as 'Programador de software/Programadora de software'."""
    return [p.strip() for p in title.split("/") if p.strip()]
