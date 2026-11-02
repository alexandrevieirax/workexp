"""Builders for clearly SYNTHETIC source files (tests only). See README.md in this folder."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx

TAG = "[SINTÉTICO]"
ONET_CODE = "99-0001.00"
ONET_OTHER = [f"99-00{i:02d}.00" for i in range(2, 9)]

SCALES = """Scale ID\tScale Name\tMinimum\tMaximum
CX\tContext\t1\t5
CT\tContext\t1\t3
FT\tFrequency of Task (Categories 1-7)\t0\t100
IM\tImportance\t1\t5
LV\tLevel\t0\t7
RT\tRelevance of Task\t0\t100
"""

TASKS = [
    ("1", "Write and maintain computer programs from written specifications."),
    ("2", "Prepare status reports for project managers."),
    ("3", "Install network cables inside office walls."),
    ("4", "Translate user manuals into other languages."),
]


def _tsv(header: list[str], rows: list[list]) -> str:
    return "\t".join(header) + "\n" + "\n".join("\t".join(str(c) for c in r) for r in rows) + "\n"


def build_onet_zip(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    occs = [ONET_CODE, *ONET_OTHER]
    occ_rows = [[c, f"{TAG} Occupation {c}", f"{TAG} synthetic description"] for c in occs]
    task_rows, rating_rows, dwa_rows = [], [], []
    for c in occs:
        for tid, text in TASKS:
            task_id = f"{c[3:7]}{tid}"
            task_rows.append(
                [c, task_id, text if c == ONET_CODE else f"{text} ({c})", "Core", 10, "08/2026", "Synthetic"]
            )
            base = ["n/a", "n/a", "n/a", "n/a"]
            rating_rows.append(
                [c, task_id, "IM", "n/a", 1.0 + int(tid), 30, 0.1, *base[:2], "N", "08/2026", "Synthetic"]
            )
            rating_rows.append(
                [c, task_id, "RT", "n/a", 100 - 10 * int(tid), 30, 1.0, *base[:2], "N", "08/2026", "Synthetic"]
            )
            dist = [5, 5, 10, 20, 30, 20, 10] if tid != "4" else [0] * 7
            for cat, pct in enumerate(dist, 1):
                if tid == "4":
                    continue  # task 4 has no frequency data
                rating_rows.append(
                    [
                        c,
                        task_id,
                        "FT",
                        cat,
                        pct,
                        30,
                        1.0,
                        "n/a",
                        "n/a",
                        "Y" if (tid == "3" and cat == 1) else "N",
                        "08/2026",
                        "Synthetic",
                    ]
                )
            dwa_rows.append([c, task_id, f"4.A.9.{tid}", "08/2026", "Synthetic"])
    wc = []
    for c in occs:
        for eid, name, val in [
            ("4.C.2.d.1.g", "Hands", 2.0),
            ("4.C.2.d.1.b", "Standing", 1.5),
            ("4.C.2.a.3", "Proximity", 2.0),
            ("4.C.1.a.4", "Contact", 3.5),
            ("4.C.1.b.1.f", "Public", 2.0),
            ("4.C.1.a.2.l", "Face", 3.0),
            ("4.C.3.a.1", "Consequence", 2.5),
            ("4.C.1.c.1", "Safety", 1.5),
            ("4.C.1.c.2", "Outcomes", 3.0),
            ("4.C.3.a.2.a", "Impact", 2.5),
            ("4.C.3.a.4", "Freedom", 4.0),
            ("4.C.3.a.2.b", "Decisions", 2.5),
            ("4.C.3.b.8", "Priorities", 4.0),
            ("4.C.1.b.1.e", "Team", 4.5),
            ("4.C.3.b.7", "Repeating", 3.0),
            ("4.C.3.b.2", "Automation", 2.0),
        ]:
            wc.append(
                [
                    c,
                    eid,
                    f"{TAG} {name}",
                    "CX",
                    "n/a",
                    val,
                    30,
                    0.1,
                    val - 0.2,
                    val + 0.2,
                    "N",
                    "n/a",
                    "08/2026",
                    "Synthetic",
                ]
            )
    wa = []
    for c in occs:
        for eid in [
            "4.A.3.a.1",
            "4.A.3.a.2",
            "4.A.3.b.4",
            "4.A.4.a.5",
            "4.A.4.a.7",
            "4.A.4.a.4",
            "4.A.2.b.1",
            "4.A.2.b.2",
            "4.A.4.b.1",
        ]:
            wa.append(
                [c, eid, f"{TAG} activity {eid}", "IM", 2.5, 30, 0.1, 2.3, 2.7, "N", "n/a", "08/2026", "Synthetic"]
            )
    files = {
        "Read Me.txt": "O*NET 99.0 Database\nSYNTHETIC TEST FIXTURE — NOT REAL DATA\n",
        "Scales Reference.txt": SCALES,
        "Occupation Data.txt": _tsv(["O*NET-SOC Code", "Title", "Description"], occ_rows),
        "Task Statements.txt": _tsv(
            ["O*NET-SOC Code", "Task ID", "Task", "Task Type", "Incumbents Responding", "Date", "Domain Source"],
            task_rows,
        ),
        "Task Ratings.txt": _tsv(
            [
                "O*NET-SOC Code",
                "Task ID",
                "Scale ID",
                "Category",
                "Data Value",
                "N",
                "Standard Error",
                "Lower CI Bound",
                "Upper CI Bound",
                "Recommend Suppress",
                "Date",
                "Domain Source",
            ],
            rating_rows,
        ),
        "Job Zones.txt": _tsv(
            ["O*NET-SOC Code", "Job Zone", "Date", "Domain Source"], [[c, 4, "08/2026", "Synthetic"] for c in occs]
        ),
        "Work Context.txt": _tsv(
            [
                "O*NET-SOC Code",
                "Element ID",
                "Element Name",
                "Scale ID",
                "Category",
                "Data Value",
                "N",
                "Standard Error",
                "Lower CI Bound",
                "Upper CI Bound",
                "Recommend Suppress",
                "Not Relevant",
                "Date",
                "Domain Source",
            ],
            wc,
        ),
        "Work Activities.txt": _tsv(
            [
                "O*NET-SOC Code",
                "Element ID",
                "Element Name",
                "Scale ID",
                "Data Value",
                "N",
                "Standard Error",
                "Lower CI Bound",
                "Upper CI Bound",
                "Recommend Suppress",
                "Not Relevant",
                "Date",
                "Domain Source",
            ],
            wa,
        ),
        "Tasks to DWAs.txt": _tsv(["O*NET-SOC Code", "Task ID", "DWA Element ID", "Date", "Domain Source"], dwa_rows),
        "GWAs to IWAs to DWAs.txt": _tsv(
            ["GWA Element ID", "IWA Element ID", "DWA Element ID", "DWA Element Name"],
            [["4.A", "4.A.9", f"4.A.9.{t}", f"{TAG} work activity {t}"] for t, _ in TASKS],
        ),
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(f"db_99_0_text/{name}", content)
    return path


def build_cbo_dir(directory: Path, with_perfil: bool = True, drop_column: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    occ_header = ["CODIGO", "TITULO"]
    if drop_column in occ_header:
        occ_header.remove(drop_column)
    (directory / "CBO2002 - Ocupacao.csv").write_text(
        ";".join(occ_header) + "\n" + ";".join(["999901", f"{TAG} Analista sintético"][: len(occ_header)]) + "\n",
        encoding="latin-1",
    )
    (directory / "CBO2002 - Familia.csv").write_text(
        f"CODIGO;TITULO\n9999;{TAG} Família sintética\n", encoding="latin-1"
    )
    (directory / "CBO2002 - Sinonimo.csv").write_text(f"OCUPACAO;SINONIMO\n999901;{TAG} Sinônimo\n", encoding="latin-1")
    if with_perfil:
        rows = [
            ["9999", "999901", "A", "PLANEJAR", "1", "Elaborar relatórios de status do projeto"],
            ["9999", "999901", "A", "PLANEJAR", "2", "Desenvolver programas de computador"],
            ["9999", "999901", "B", "EXECUTAR", "1", "Instalar cabos de rede"],
        ]
        (directory / "CBO2002 - PerfilOcupacional.csv").write_text(
            "COD_GRANDE_GRUPO;COD_SUBGRUPO_PRINCIPAL;COD_SUBGRUPO;COD_FAMILIA;COD_OCUPACAO;SGL_GRANDE_AREA;"
            "NOME_GRANDE_AREA;COD_ATIVIDADE;NOME_ATIVIDADE\n"
            + "\n".join("9;99;999;" + ";".join(r) for r in rows)
            + "\n",
            encoding="latin-1",
        )
    return directory


ESCO_URI = "http://data.europa.eu/esco/occupation/00000000-synthetic"


def esco_payload(language: str) -> dict:
    title = {"en": f"{TAG} software maker", "pt": f"{TAG} Fazedor de software/Fazedora de software"}
    return {
        "uri": ESCO_URI,
        "code": "9999.1",
        "status": "released",
        "preferredLabel": {"en": f"{TAG} software maker", "pt": f"{TAG} Fazedor de software/Fazedora de software"},
        "alternativeLabel": {"en": [f"{TAG} program writer"], "pt": [f"{TAG} Escritor de programas"]},
        "description": {"en": {"literal": f"{TAG} writes programs."}, "pt": {"literal": f"{TAG} escreve programas."}},
        "_links": {
            "broaderIscoGroup": [{"uri": "http://data.europa.eu/esco/isco/C2512", "code": "2512"}],
            "hasEssentialSkill": [
                {
                    "uri": "s1",
                    "title": {"en": "write computer programs", "pt": "escrever programas"}[language],
                    "skillType": "http://data.europa.eu/esco/skill-type/skill",
                },
                {
                    "uri": "s2",
                    "title": {"en": "prepare project reports", "pt": "preparar relatórios"}[language],
                    "skillType": "http://data.europa.eu/esco/skill-type/skill",
                },
                {
                    "uri": "k1",
                    "title": {"en": "programming languages", "pt": "linguagens de programação"}[language],
                    "skillType": "http://data.europa.eu/esco/skill-type/knowledge",
                },
            ],
            "hasOptionalSkill": [],
        },
        "title": title[language],
    }


def esco_mock_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        lang = request.url.params.get("language", "en")
        return httpx.Response(200, text=json.dumps(esco_payload(lang)))

    return httpx.Client(transport=httpx.MockTransport(handler))


def build_aei_dir(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "task_pct_v2.csv").write_text(
        "task_name,pct\n"
        "write and maintain computer programs from written specifications.,2.0\n"
        "prepare status report for project managers.,0.5\n"
        "some other synthetic task.,0.1\n",
        encoding="utf-8",
    )
    (directory / "automation_vs_augmentation_by_task.csv").write_text(
        "task_name,feedback_loop,directive,task_iteration,validation,learning,filtered\n"
        "write and maintain computer programs from written specifications.,0.1,0.4,0.3,0.1,0.0,0.1\n",
        encoding="utf-8",
    )
    return directory
