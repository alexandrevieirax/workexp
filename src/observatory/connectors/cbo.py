"""CBO 2002 connector for the official "Estrutura CBO (CSV)" files.

The MTE portal protects downloads with reCAPTCHA, so files must be obtained manually
(docs/data-sources.md). This connector validates the expected schema and never fabricates records.
"""

from __future__ import annotations

import fnmatch
import io
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
from observatory.provenance import sha256_bytes

PROCEDURE = (
    "Open https://cbo.mte.gov.br/cbosite/pages/downloads.jsf, solve the reCAPTCHA, download "
    "'Estrutura CBO (CSV) - Arquivo ZIP' and save the zip (or its CSVs) in data/raw/cbo/. "
    "Then run: python -m observatory.cli validate-cbo"
)
SCHEMA = {
    "ocupacao": ("*ocupa*o*.csv", ["CODIGO", "TITULO"]),
    "familia": ("*familia*.csv", ["CODIGO", "TITULO"]),
    "sinonimo": ("*sinonimo*.csv", ["OCUPACAO", "SINONIMO"]),
    "perfil": (
        "*perfil*.csv",
        ["COD_FAMILIA", "COD_OCUPACAO", "SGL_GRANDE_AREA", "NOME_GRANDE_AREA", "COD_ATIVIDADE", "NOME_ATIVIDADE"],
    ),
}
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
        self._files = self._discover()
        if "ocupacao" not in self._files:
            raise SourceUnavailableError("CBO structure files not found", PROCEDURE, str(directory))
        self.tables = {k: self._read(k, data) for k, (name, data) in self._files.items()}

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
        for key, (pattern, _) in SCHEMA.items():
            for name, data in candidates:
                norm = name.lower().replace(" ", "").replace("_", "")
                if fnmatch.fnmatch(norm, pattern.replace("_", "")) and key not in found:
                    found[key] = (name, data)
        return found

    def _read(self, key: str, data: bytes) -> pd.DataFrame:
        text = _decode(data)
        sep = ";" if text.count(";") >= text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
        df.columns = [c.strip().upper() for c in df.columns]
        require_columns("CBO", self._files[key][0], list(df.columns), SCHEMA[key][1])
        return df

    def validate(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.tables.items()}

    def descriptor(self) -> SourceDescriptor:
        digest = sha256_bytes(b"".join(d for _, d in sorted(self._files.values())))
        return SourceDescriptor(
            dataset_code="CBO",
            dataset_name="Classificação Brasileira de Ocupações 2002",
            publisher="Ministério do Trabalho e Emprego (Brasil)",
            homepage="https://cbo.mte.gov.br",
            version="CBO2002-estrutura-csv",
            source_url="https://cbo.mte.gov.br/cbosite/pages/downloads.jsf",
            retrieval_method="manual_file" if not self.is_synthetic else "synthetic_fixture",
            file_sha256=digest,
            license_name="Dados públicos governamentais (confirmar termos de uso MTE)",
            license_url=None,
            notes="files: " + ", ".join(n for n, _ in self._files.values()),
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
        aliases = [(row.iloc[0]["TITULO"], "pt", "preferred")]
        if "sinonimo" in self.tables:
            syn = self.tables["sinonimo"]
            aliases += [(s, "pt", "synonym") for s in syn.loc[syn["OCUPACAO"].str.replace("-", "") == code, "SINONIMO"]]
        return ParsedOccupation(
            taxonomy="CBO",
            code=code,
            title=row.iloc[0]["TITULO"],
            description=None,
            language="pt",
            group_code=family,
            qualification_level=CBO_SKILL_LEVEL_BY_GG.get(code[0]),
            aliases=aliases,
            attributes={
                "family_code": family,
                "family_title": fam_title,
                "fields_not_available_in_source_file": NOT_IN_FILE,
            },
            is_synthetic=self.is_synthetic,
        )

    def activities(self, code: str) -> list[ParsedTask]:
        """Activities are published per family; rows may also carry the occupation code."""
        if "perfil" not in self.tables:
            return []
        code = code.replace("-", "")
        pf = self.tables["perfil"]
        rows = pf[pf["COD_OCUPACAO"].str.replace("-", "") == code]
        scope = "occupation"
        if rows.empty:
            rows = pf[pf["COD_FAMILIA"] == code[:4]]
            scope = "family"
        rows = rows.drop_duplicates(subset=["SGL_GRANDE_AREA", "COD_ATIVIDADE"])
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
