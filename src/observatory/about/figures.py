"""Reproducible, versioned figures for "Sobre", generated from code metadata and the latest assessments.

Output: artifacts/figures/<methodology_version>/ + manifest.json (title, caption, alt text, sha256, data source).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from observatory.config import get_settings  # noqa: E402
from observatory.db import models as M  # noqa: E402
from observatory.db.dictionary import render_mermaid_er  # noqa: E402
from observatory.db.session import make_engine, session_factory  # noqa: E402
from observatory.methodology import load_methodology  # noqa: E402
from observatory.provenance import sha256_file  # noqa: E402

# Okabe-Ito colour-blind-safe palette
C = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "grey": "#7F7F7F",
    "sky": "#56B4E9",
}
SVG_META = {"Creator": "observatory.about.figures", "Date": None}

PIPELINE_STAGES = [
    ("src", "Fontes oficiais<br/>CBO · ESCO · O*NET · AEI"),
    ("ingest", "Ingestão + proveniência<br/>(versão, hash, data)"),
    ("norm", "Normalização<br/>texto e escalas"),
    ("cw", "Crosswalk composto<br/>(revisão humana)"),
    ("emb", "Embeddings<br/>+ calibração no benchmark"),
    ("cap", "Dicionário de capacidades<br/>de IA versionado"),
    ("dims", "Dimensões E1–E14<br/>por tarefa"),
    ("out", "Exposição · Automação<br/>Aumento · Transformação"),
    ("agg", "Agregação ponderada<br/>+ Monte Carlo + sensibilidade"),
    ("ui", "API · Página da ocupação<br/>Área Sobre"),
]


def mermaid_flow() -> str:
    lines = ["flowchart LR"]
    lines += [f'    {k}["{label}"]' for k, label in PIPELINE_STAGES]
    order = ["src", "ingest", "norm", "cw", "dims", "out", "agg", "ui"]
    lines += [f"    {a} --> {b}" for a, b in zip(order, order[1:], strict=False)]
    lines += ["    norm --> emb", "    cap --> emb", "    emb --> dims", "    cw -. priors .-> dims"]
    return "\n".join(lines)


def mermaid_relation() -> str:
    return "\n".join(
        [
            "flowchart TB",
            '    O["Ocupação<br/>(CBO / ESCO / O*NET)"] -->|"possui (peso w)"| T["Tarefa / atividade / competência"]',
            '    T -->|"similaridade calibrada (E1)"| K["Capacidade de IA<br/>(dicionário versionado)"]',
            '    K -->|"priors E2, E11, E12, E13"| D["Dimensões da tarefa"]',
            '    U["Uso observado (AEI)"] -->|E3| D',
            '    W["Work Context / Activities O*NET"] -->|"priors E6–E10"| D',
            '    D --> R["Exposição · Automação · Aumento · Transformação · Classe"]',
            '    R -->|"Σ w·x"| I["Índices ocupacionais OAE / OAP / OAuP / OTP"]',
        ]
    )


def mermaid_curriculum() -> str:
    return "\n".join(
        [
            "flowchart LR",
            '    P["Perfil profissional / curso<br/>(fase 8)"] --> E["Extração de competências,<br/>capacidades, resultados"]',
            '    E -->|"revisão humana"| L["Ligação elemento ↔ tarefa"]',
            '    L --> X["Exposição e transformação<br/>das tarefas"]',
            '    X --> G["Cobertura e lacunas<br/>(competências emergentes)"]',
            '    G --> Rc["Recomendações rastreáveis<br/>manter · atualizar · integrar IA · ..."]',
            '    Rc -->|"exclusão só com validação humana"| H["Comitê pedagógico"]',
        ]
    )


def _latest(session, taxonomy: str) -> M.ExposureAssessment | None:
    sub = select(func.max(M.ExposureAssessment.id)).join(M.Occupation).where(M.Occupation.taxonomy == taxonomy)
    aid = session.scalar(sub)
    return session.get(M.ExposureAssessment, aid) if aid else None


def _save(fig, path: Path) -> None:
    fig.savefig(path, format="svg", bbox_inches="tight", metadata=SVG_META)
    plt.close(fig)


def build_figures(database_url: str | None = None) -> dict:
    settings = get_settings()
    m = load_methodology()
    out_dir = settings.figures_dir / m.version
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict = {"methodology_version": m.version, "fingerprint": m.fingerprint, "figures": {}}

    def register(name: str, file: str, kind: str, title: str, caption: str, alt: str, data_source: str) -> None:
        manifest["figures"][name] = {
            "file": file,
            "kind": kind,
            "title": title,
            "caption": caption,
            "alt": alt,
            "data_source": data_source,
            "methodology_version": m.version,
            "sha256": sha256_file(out_dir / file),
        }

    for name, src, title, caption, alt in [
        (
            "flow",
            mermaid_flow(),
            "Fluxo geral do modelo",
            "Etapas do pipeline, da fonte oficial à interface; gerado de PIPELINE_STAGES no código.",
            "Fluxograma: fontes, ingestão, normalização, crosswalk, embeddings, dicionário de capacidades, dimensões "
            "por tarefa, resultados, agregação e interface.",
        ),
        (
            "relation",
            mermaid_relation(),
            "Relação ocupação–tarefa–capacidade de IA",
            "Como cada evidência entra nas dimensões da tarefa e como as tarefas são agregadas na ocupação.",
            "Diagrama: ocupação possui tarefas ponderadas; tarefas se ligam a capacidades de IA; capacidades, uso "
            "observado e descritores O*NET alimentam as dimensões; resultados são somados nos índices.",
        ),
        (
            "er",
            render_mermaid_er(),
            "Arquitetura de dados (núcleo analítico)",
            "Diagrama entidade-relacionamento gerado automaticamente dos modelos SQLAlchemy.",
            "Diagrama entidade-relacionamento das tabelas de fonte, ocupação, tarefa, crosswalk, capacidade, "
            "embedding e avaliação.",
        ),
        (
            "curriculum",
            mermaid_curriculum(),
            "Da transformação da ocupação à recomendação curricular",
            "Fluxo conceitual do módulo curricular (fase 8, ainda não implementado).",
            "Fluxo: curso, extração, ligação a tarefas, exposição, lacunas, recomendações e validação humana.",
        ),
    ]:
        (out_dir / f"{name}.mmd").write_text(src, encoding="utf-8")
        register(name, f"{name}.mmd", "mermaid", title, caption, alt, "metadados do código")

    engine = make_engine(database_url or settings.database_url)
    try:
        session = session_factory(engine)()
        onet = _latest(session, "ONET")
    except Exception:  # schema not created yet
        onet = None
    if onet is None:
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return manifest

    comps = sorted(onet.components, key=lambda c: c.task_weight * c.technical_exposure)
    labels = [
        c.occupation_task.task.statement[:60] + ("…" if len(c.occupation_task.task.statement) > 60 else "")
        for c in comps
    ]
    src_label = f"assessment #{onet.id} run {onet.run_id}; {onet.occupation.taxonomy} {onet.occupation.code}"

    # calculation: contribution of each task to OAE
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(comps) + 1.4))
    ax.barh(labels, [c.task_weight * c.technical_exposure for c in comps], color=C["blue"], label="peso × exposição")
    ax.set_xlabel("Contribuição para o OAE (peso da tarefa × exposição técnica)")
    ax.set_title(f"{onet.occupation.title}: OAE = {onet.scores['OAE']:.2f}", fontsize=11)
    ax.tick_params(axis="y", labelsize=7)
    _save(fig, out_dir / "calculation.svg")
    register(
        "calculation",
        "calculation.svg",
        "image",
        "Cálculo da exposição ocupacional",
        "Cada barra é a contribuição de uma tarefa O*NET (peso normalizado × exposição técnica); a soma é o OAE.",
        f"Barras horizontais com a contribuição de {len(comps)} tarefas para o OAE de {onet.scores['OAE']:.2f}.",
        src_label,
    )

    # automation vs augmentation
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(
        [c.automation_potential for c in onet.components],
        [c.augmentation_potential for c in onet.components],
        s=[2000 * c.task_weight for c in onet.components],
        color=C["green"],
        alpha=0.6,
        edgecolor="black",
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.plot([0, 1], [0, 1], ls="--", color=C["grey"], lw=1)
    ax.set_xlabel("Potencial de automação")
    ax.set_ylabel("Potencial de aumento de capacidade")
    ax.set_title("Automação × aumento por tarefa (tamanho = peso)", fontsize=11)
    _save(fig, out_dir / "automation_augmentation.svg")
    register(
        "automation_augmentation",
        "automation_augmentation.svg",
        "image",
        "Automação versus aumento",
        "Cada ponto é uma tarefa; acima da diagonal predomina o aumento de capacidade humana.",
        "Dispersão das tarefas com automação no eixo x e aumento no eixo y; a maioria acima da diagonal.",
        src_label,
    )

    # sensitivity tornado
    rows = [r for r in onet.sensitivity["one_at_a_time"]]
    params = sorted(
        {r["parameter"] for r in rows}, key=lambda p: max(abs(r["d_OAE"]) for r in rows if r["parameter"] == p)
    )
    fig, ax = plt.subplots(figsize=(7, 0.35 * len(params) + 1.2))
    for i, p in enumerate(params):
        for r in rows:
            if r["parameter"] == p:
                ax.barh(i, r["d_OAE"], color=C["red"] if r["change"] < 0 else C["blue"])
    ax.set_yticks(range(len(params)), params, fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_xlabel(f"Variação do OAE (peso −/+{int(onet.sensitivity['relative_change'] * 100)}%)")
    ax.set_title("Sensibilidade do OAE aos pesos (um de cada vez)", fontsize=11)
    _save(fig, out_dir / "sensitivity.svg")
    register(
        "sensitivity",
        "sensitivity.svg",
        "image",
        "Análise de sensibilidade",
        "Efeito no OAE de reduzir (vermelho) ou aumentar (azul) cada peso em 20%, mantendo os demais.",
        f"Gráfico de tornado; maior variação absoluta do OAE = {onet.sensitivity['max_abs_delta_OAE']:.3f}.",
        src_label,
    )

    # uncertainty: intervals for each occupation and index
    assessments = [a for a in (_latest(session, t) for t in ("ONET", "ESCO", "CBO")) if a]
    fig, ax = plt.subplots(figsize=(8, 1.0 + 0.9 * len(assessments)))
    colors = [C["blue"], C["red"], C["green"], C["purple"]]
    for i, a in enumerate(assessments):
        for j, k in enumerate(("OAE", "OAP", "OAuP", "OTP")):
            y = i + j * 0.18
            lo, hi = a.intervals[k]
            ax.plot([lo, hi], [y, y], color=colors[j], lw=3, label=k if i == 0 else None)
            ax.plot(a.scores[k], y, "o", color="black", ms=3)
    ax.set_yticks(
        [i + 0.27 for i in range(len(assessments))],
        [f"{a.occupation.taxonomy}: {a.occupation.title[:30]}" for a in assessments],
        fontsize=8,
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel("Índice (ponto) e intervalo de 90% por Monte Carlo")
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Incerteza dos índices ocupacionais", fontsize=11)
    _save(fig, out_dir / "uncertainty.svg")
    register(
        "uncertainty",
        "uncertainty.svg",
        "image",
        "Incerteza",
        "Intervalos de 90% (Monte Carlo) para os quatro índices de cada ocupação avaliada.",
        "Segmentos horizontais com os intervalos de OAE, OAP, OAuP e OTP por ocupação.",
        "; ".join(f"assessment #{a.id}" for a in assessments),
    )

    # crosswalk components
    maps = session.scalars(select(M.OccupationSourceMapping).order_by(M.OccupationSourceMapping.id)).all()
    if maps:
        comps_names = [
            "title_similarity",
            "task_similarity",
            "skill_similarity",
            "hierarchy_consistency",
            "qualification_consistency",
        ]
        fig, ax = plt.subplots(figsize=(8, 1.2 + 0.8 * len(maps)))
        for i, mp in enumerate(maps):
            for j, cn in enumerate(comps_names):
                v = getattr(mp, cn)
                ax.barh(
                    i + j * 0.15,
                    v if v is not None else 0.5,
                    height=0.14,
                    color=list(C.values())[j],
                    hatch=None if v is not None else "//",
                    label=cn if i == 0 else None,
                    edgecolor="white",
                )
            ax.text(1.02, i + 0.3, f"{mp.mapping_confidence:.2f} ({mp.confidence_class})", fontsize=8, va="center")
        ax.set_yticks(
            [i + 0.3 for i in range(len(maps))],
            [f"{mp.source_occupation.taxonomy} → {mp.target_occupation.taxonomy}" for mp in maps],
            fontsize=8,
        )
        ax.set_xlim(0, 1.35)
        ax.set_xlabel("Componente (hachurado = desconhecido, valor neutro 0,5)")
        ax.legend(fontsize=7, loc="lower right")
        ax.set_title("Crosswalk CBO–ESCO–O*NET: componentes e confiança", fontsize=11)
        _save(fig, out_dir / "crosswalk.svg")
        register(
            "crosswalk",
            "crosswalk.svg",
            "image",
            "Crosswalk CBO–ESCO–O*NET",
            "Componentes do mapping_confidence por par; nenhum par é aceito automaticamente.",
            "Barras agrupadas com os cinco componentes de cada correspondência proposta e a confiança final.",
            "; ".join(f"mapping #{mp.id}" for mp in maps),
        )
    session.close()
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
