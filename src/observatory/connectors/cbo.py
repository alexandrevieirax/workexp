"""CBO 2002 connector for the official "Estrutura CBO (CSV)" files.

The MTE portal protects downloads with reCAPTCHA, so files must be obtained manually
(docs/data-sources.md). This connector validates the expected schema and never fabricates records.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

from observatory.connectors.base import (
    ParsedOccupation,
    ParsedTask,
    SourceDescriptor,
    SourceUnavailableError,
    is_marked_synthetic,
    require_columns,
)
from observatory.normalization.text import strip_accents
from observatory.provenance import sha256_bytes

PROCEDURE = (
    "Open https://cbo.mte.gov.br/cbosite/pages/downloads.jsf, solve the reCAPTCHA, download "
    "'Estrutura CBO (CSV) - Arquivo ZIP' and save the zip (or its CSVs) in data/raw/cbo/. "
    "Then run: python -m observatory.cli validate-cbo"
)
# File-name suffix (normalized: lowercase, no accents/spaces/underscores) -> required columns.
SCHEMA = {
    "ocupacao": ("ocupacao.csv", ["CODIGO", "TITULO"]),
    "familia": ("familia.csv", ["CODIGO", "TITULO"]),
    "sinonimo": ("sinonimo.csv", ["OCUPACAO", "SINONIMO"]),
    "perfil": (
        "perfilocupacional.csv",
        ["COD_FAMILIA", "COD_OCUPACAO", "SGL_GRANDE_AREA", "NOME_GRANDE_AREA", "COD_ATIVIDADE", "NOME_ATIVIDADE"],
    ),
}
# The official Sinonimo.csv ships as CODIGO;TITULO (occupation code; synonym). Mapped to canonical names.
COLUMN_ALIASES = {"sinonimo": {"CODIGO": "OCUPACAO", "TITULO": "SINONIMO"}}
# Perfil Ocupacional area "Z" ("DEMONSTRAR COMPETÊNCIAS PESSOAIS") lists personal attributes (e.g. "Demonstrar
# capacidade de raciocínio abstrato"), not work activities: kept as personal competencies, excluded from task units.
PERSONAL_COMPETENCY_AREAS = {"Z"}
NOT_IN_FILE = ["descricao_sumaria", "formacao_experiencia", "condicoes_gerais_exercicio", "recursos_trabalho"]
# CBO 2002 grandes grupos follow the ISCO-88 skill-level logic; same 0-1 rescaling as ESCO.
CBO_SKILL_LEVEL_BY_GG = {
    "1": 5 / 6,
    "2": 1.0,
    "3": 2 / 3,
    "4": 1 / 3,
    "5": 1 / 3,
    "6": 1 / 3,
    "7": 1 / 3,
    "8": 1 / 3,
    "9": 1 / 3,
}


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("cannot decode CBO file")


class CboFiles:
    def __init__(self, directory: Path, is_synthetic: bool = False):
        self.directory = directory
        self.is_synthetic = is_synthetic or (directory.exists() and is_marked_synthetic(directory))
        self.repaired_rows: dict[str, int] = {}
        self._files = self._discover()
        if "ocupacao" not in self._files:
            raise SourceUnavailableError("CBO structure files not found", PROCEDURE, str(directory))
        self.tables = {k: self._read(k, data) for k, (name, data) in self._files.items()}
        books = directory / "cbo_books_families.json"
        self.books = json.loads(books.read_text(encoding="utf-8")) if books.exists() else None

    def _discover(self) -> dict[str, tuple[str, bytes]]:
        found: dict[str, tuple[str, bytes]] = {}
        if not self.directory.exists():
            return found
        candidates: list[tuple[str, bytes]] = []
        for p in sorted(self.directory.iterdir()):
            if p.suffix.lower() == ".csv":
                candidates.append((p.name, p.read_bytes()))
            elif p.suffix.lower() == ".zip":
                with zipfile.ZipFile(p) as z:
                    candidates += [(Path(n).name, z.read(n)) for n in z.namelist() if n.lower().endswith(".csv")]
        for key, (suffix, _) in SCHEMA.items():
            for name, data in candidates:
                norm = strip_accents(name).lower().replace(" ", "").replace("_", "")
                if norm.endswith(suffix) and key not in found:
                    found[key] = (name, data)
        return found

    def _read(self, key: str, data: bytes) -> pd.DataFrame:
        text = _decode(data)
        sep = ";" if text.count(";") >= text.count(",") else ","
        lines = [ln for ln in text.splitlines() if ln.strip()]
        header = [c.strip().upper() for c in lines[0].split(sep)]
        rows, repaired = [], 0
        for ln in lines[1:]:
            parts = ln.split(sep, len(header) - 1)  # extra separators stay inside the last (free-text) column
            if len(parts) < len(header):
                raise ValueError(f"[CBO] {self._files[key][0]}: row with {len(parts)} fields: {ln[:80]!r}")
            if sep in parts[-1] or parts[-1].endswith(sep):
                repaired += 1
                parts[-1] = parts[-1].rstrip(sep).strip()
            rows.append(parts)
        self.repaired_rows[key] = repaired
        df = pd.DataFrame(rows, columns=header, dtype=str)
        df = df.rename(columns=COLUMN_ALIASES.get(key, {}))
        df = df.apply(lambda col: col.str.strip())
        require_columns("CBO", self._files[key][0], list(df.columns), SCHEMA[key][1])
        return df

    def validate(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.tables.items()}

    def descriptor(self) -> SourceDescriptor:
        payload = b"".join(d for _, d in sorted(self._files.values()))
        books = sorted((self.books or {}).get("source_files", {}).items())
        if books:  # the family fields from the official books are part of the source
            payload += "".join(f"{n}:{h}" for n, h in books).encode()
        digest = sha256_bytes(payload)
        return SourceDescriptor(
            dataset_code="CBO",
            dataset_name="Classificação Brasileira de Ocupações 2002",
            publisher="Ministério do Trabalho e Emprego (Brasil)",
            homepage="https://cbo.mte.gov.br",
            version="CBO2002-estrutura-csv" + ("+livros-3a-ed-2010" if books else ""),
            source_url="https://cbo.mte.gov.br/cbosite/pages/downloads.jsf",
            retrieval_method="manual_file" if not self.is_synthetic else "synthetic_fixture",
            file_sha256=digest,
            license_name="Dados públicos governamentais (confirmar termos de uso MTE)",
            license_url=None,
            notes="files: "
            + ", ".join(n for n, _ in self._files.values())
            + f"; rule cbo_semicolon_in_last_field repaired rows: {self.repaired_rows}"
            + (f"; family fields and CIUO 88 parsed from books: {', '.join(n for n, _ in books)}" if books else ""),
            is_synthetic=self.is_synthetic,
        )

    def occupation(self, code: str) -> ParsedOccupation:
        code = code.replace("-", "")
        occ = self.tables["ocupacao"]
        row = occ[occ["CODIGO"].str.replace("-", "") == code]
        if row.empty:
            raise KeyError(f"CBO {code} not found")
        family = code[:4]
        fam_title = None
        if "familia" in self.tables:
            fam = self.tables["familia"]
            fr = fam[fam["CODIGO"] == family]
            fam_title = fr.iloc[0]["TITULO"] if not fr.empty else None
        book = (self.books or {}).get("families", {}).get(family)
        aliases = [(row.iloc[0]["TITULO"], "pt", "preferred")]
        if "sinonimo" in self.tables:
            syn = self.tables["sinonimo"]
            aliases += [(s, "pt", "synonym") for s in syn.loc[syn["OCUPACAO"].str.replace("-", "") == code, "SINONIMO"]]
        return ParsedOccupation(
            taxonomy="CBO",
            code=code,
            title=row.iloc[0]["TITULO"],
            description=book.get("descricao_sumaria") if book else None,
            language="pt",
            group_code=family,
            qualification_level=CBO_SKILL_LEVEL_BY_GG.get(code[0]),
            aliases=aliases,
            attributes={
                "family_code": family,
                "family_title": fam_title,
                "fields_not_available_in_source_file": [] if book else NOT_IN_FILE,
                **(
                    {
                        "description_scope": "family",
                        "formacao_experiencia": book.get("formacao_experiencia"),
                        "condicoes_gerais_exercicio": book.get("condicoes_gerais_exercicio"),
                        "recursos_trabalho": book.get("recursos_trabalho"),
                        "ciuo88": book.get("ciuo88"),
                        "book_source": f"{book['book']} p.{book['pages'][0]}-{book['pages'][-1]}",
                    }
                    if book
                    else {}
                ),
            },
            is_synthetic=self.is_synthetic,
        )

    def _profile_rows(self, code: str) -> tuple[pd.DataFrame, str]:
        """Activities are published per family; rows may also carry the occupation code."""
        code = code.replace("-", "")
        pf = self.tables["perfil"]
        rows = pf[pf["COD_OCUPACAO"].str.replace("-", "") == code]
        scope = "occupation"
        if rows.empty:
            rows = pf[pf["COD_FAMILIA"] == code[:4]]
            scope = "family"
        return rows.drop_duplicates(subset=["SGL_GRANDE_AREA", "COD_ATIVIDADE"]), scope

    def personal_competencies(self, code: str) -> list[dict]:
        if "perfil" not in self.tables:
            return []
        rows, scope = self._profile_rows(code)
        rows = rows[rows["SGL_GRANDE_AREA"].isin(PERSONAL_COMPETENCY_AREAS)]
        return [
            {
                "original_id": f"{code[:4]}:{r['SGL_GRANDE_AREA']}:{r['COD_ATIVIDADE']}",
                "label": r["NOME_ATIVIDADE"],
                "scope": scope,
            }
            for _, r in rows.iterrows()
        ]

    def activities(self, code: str) -> list[ParsedTask]:
        if "perfil" not in self.tables:
            return []
        code = code.replace("-", "")
        rows, scope = self._profile_rows(code)
        rows = rows[~rows["SGL_GRANDE_AREA"].isin(PERSONAL_COMPETENCY_AREAS)]
        return [
            ParsedTask(
                original_id=f"{code[:4]}:{r['SGL_GRANDE_AREA']}:{r['COD_ATIVIDADE']}",
                statement=r["NOME_ATIVIDADE"],
                language="pt",
                unit_type="cbo_activity",
                task_type=r["NOME_GRANDE_AREA"],
                attributes={"scope": scope, "area_code": r["SGL_GRANDE_AREA"]},
            )
            for _, r in rows.iterrows()
        ]
