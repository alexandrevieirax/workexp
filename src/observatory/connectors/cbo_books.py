"""Parser for the official CBO 2002 books (MTE, 3rd edition, 2010): "Códigos, títulos e descrições", volumes 1-2.

Each occupational family page carries fields that are absent from the "Estrutura CBO (CSV)" files:
descrição sumária, formação e experiência, condições gerais de exercício, recursos de trabalho and, crucially,
"CÓDIGO INTERNACIONAL CIUO 88" — the MTE's own family → ISCO-88 correspondence. PDFs are downloaded manually
(the portal is protected by reCAPTCHA). Nothing is inferred: a family without a CIUO 88 section gets no link.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from observatory.provenance import sha256_file

HEADERS = [
    "TÍTULO",
    "DESCRIÇÃO SUMÁRIA",
    "FORMAÇÃO E EXPERIÊNCIA",
    "CONDIÇÕES GERAIS DE EXERCÍCIO",
    "CÓDIGO INTERNACIONAL CIUO 88",
    "NOTAS",
    "RECURSOS DE TRABALHO",
    "PARTICIPANTES DA DESCRIÇÃO",
]
FIELD = {
    "DESCRIÇÃO SUMÁRIA": "descricao_sumaria",
    "FORMAÇÃO E EXPERIÊNCIA": "formacao_experiencia",
    "CONDIÇÕES GERAIS DE EXERCÍCIO": "condicoes_gerais_exercicio",
    "CÓDIGO INTERNACIONAL CIUO 88": "ciuo88_text",
    "RECURSOS DE TRABALHO": "recursos_trabalho",
    "NOTAS": "notas",
}
_FAMILY = re.compile(r"CÓDIGO\s+(\d{4})\s*\n")
_HEADER = re.compile(r"^\s*(" + "|".join(re.escape(h) for h in HEADERS) + r")\s*$", re.M)
_CIUO_CODE = re.compile(r"(?<![\d.])(\d{4})\s*[-–]")


def _clean(text: str) -> str:
    text = text.replace("\xad\n", "").replace("\xad", "").replace("\t", " ")
    text = re.sub(r"-\n(?=[a-zà-ú])", "", text)  # words hyphenated across lines
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class CboFamilyRecord:
    family_code: str
    book: str
    pages: list[int] = field(default_factory=list)
    fields: dict[str, str] = field(default_factory=dict)
    ciuo88: list[str] = field(default_factory=list)


def parse_books(paths: list[Path]) -> tuple[dict[str, CboFamilyRecord], dict[str, str]]:
    """Return family records and {book file name: sha256}."""
    import fitz  # pymupdf

    records: dict[str, CboFamilyRecord] = {}
    hashes: dict[str, str] = {}
    for path in paths:
        hashes[path.name] = sha256_file(path)
        doc = fitz.open(path)
        texts: dict[str, list[tuple[int, str]]] = {}
        for i in range(doc.page_count):
            page = doc[i].get_text()
            m = _FAMILY.search(page)
            if not m:
                continue
            body = "\n".join(ln for ln in page.splitlines() if not re.fullmatch(r"\s*\d{1,4}\s*", ln))
            texts.setdefault(m.group(1), []).append((i + 1, body))
        for fam, pages in texts.items():
            text = "\n".join(t for _, t in pages)
            rec = records.setdefault(fam, CboFamilyRecord(fam, path.name))
            rec.pages += [p for p, _ in pages]
            parts = _HEADER.split(text)
            for header, content in zip(parts[1::2], parts[2::2], strict=False):
                key = FIELD.get(header)
                if key and key not in rec.fields:
                    rec.fields[key] = _clean(content)
            if "ciuo88_text" in rec.fields and not rec.ciuo88:
                rec.ciuo88 = sorted(set(_CIUO_CODE.findall(rec.fields["ciuo88_text"])))
    return records, hashes
