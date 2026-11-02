"""Render the "Sobre" area from content files + live metadata (config, dictionary, registry, figures).

Every number shown in "Sobre" is read from the methodology YAML, the capability dictionary, the registry or the
latest run artifacts — never typed into the prose — so it cannot drift from the code.
"""

from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from observatory.about.markdown import render as md_render
from observatory.capabilities.dictionary import load_dictionary
from observatory.config import get_settings
from observatory.exposure.formulas import TASK_CLASSES
from observatory.methodology import load_methodology, load_registry

CONTENT_DIR = Path(__file__).parent / "content"
LANGUAGES = ("pt-BR", "en")
CITATION = re.compile(r"\[(@[\w-]+(?:;\s*@[\w-]+)*)\]")
PLACEHOLDER = re.compile(r"^\{\{([\w:]+)\}\}$", re.M)


def parse_front_matter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return yaml.safe_load(fm), body
    return {}, text


def load_content(lang: str) -> tuple[dict, str]:
    return parse_front_matter((CONTENT_DIR / f"{lang}.md").read_text(encoding="utf-8"))


def section_ids(body: str) -> list[str]:
    return re.findall(r"^##\s+.*\{#([\w-]+)\}", body, re.M)


def cited_keys(body: str) -> set[str]:
    return {k.strip().lstrip("@") for m in CITATION.findall(body) for k in m.split(";")}


@lru_cache
def references() -> dict[str, dict]:
    path = get_settings().docs_dir / "references" / "references.json"
    return {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))}


def _author_year(ref: dict) -> str:
    authors = ref.get("author", [])
    first = authors[0].get("family") or authors[0].get("literal", "?") if authors else "?"
    etal = (
        " et al."
        if len(authors) > 2 or any(a.get("literal") == "et al." for a in authors[1:])
        else (f" & {authors[1].get('family')}" if len(authors) == 2 and authors[1].get("family") else "")
    )
    year = ref.get("issued", {}).get("date-parts", [["s.d."]])[0][0]
    return f"{first}{etal}, {year}"


def format_reference(ref: dict) -> str:
    authors = "; ".join(
        a.get("literal") or f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in ref.get("author", [])
    )
    year = ref.get("issued", {}).get("date-parts", [["s.d."]])[0][0]
    venue = ref.get("container-title") or ref.get("publisher") or ""
    extra = " ".join(
        x
        for x in [
            ref.get("genre", ""),
            f"v. {ref['volume']}" if ref.get("volume") else "",
            f"n. {ref['issue']}" if ref.get("issue") else "",
            f"p. {ref['page']}" if ref.get("page") else "",
            ref.get("number", ""),
        ]
        if x
    )
    badge = "revisado por pares" if ref.get("peer_reviewed") else "não revisado por pares / preprint / relatório"
    url = f' <a href="{html.escape(ref["URL"])}">{html.escape(ref["URL"])}</a>' if ref.get("URL") else ""
    return (
        f'<li id="ref-{ref["id"]}">{html.escape(authors)} ({year}). <em>{html.escape(ref["title"])}</em>. '
        f'{html.escape(venue)} {html.escape(extra)}.{url} <span class="badge">{badge}</span> '
        f'<span class="badge muted">{html.escape(ref.get("verification_status", ""))}</span></li>'
    )


def _table(head: list[str], rows: list[list[Any]]) -> str:
    th = "".join(f'<th scope="col">{html.escape(str(h))}</th>' for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def _latest_report() -> dict | None:
    p = get_settings().reports_dir / "vertical_slice_latest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def figures_manifest(version: str) -> dict:
    p = get_settings().figures_dir / version / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"figures": {}}


def _figure(name: str, manifest: dict, version: str) -> str:
    f = manifest["figures"].get(name)
    if not f:
        return (
            f'<p class="note">Figura <code>{html.escape(name)}</code> ainda não gerada para a versão {version} '
            f"— execute <code>python -m observatory.cli figures</code>.</p>"
        )
    cap = (
        f"<figcaption><strong>Figura — {html.escape(f['title'])}.</strong> {html.escape(f['caption'])} "
        f'<span class="muted">Metodologia {html.escape(f["methodology_version"])}; dados: '
        f"{html.escape(f.get('data_source', 'metadados'))}; sha256 {f['sha256'][:12]}.</span></figcaption>"
    )
    if f["kind"] == "mermaid":
        src = (get_settings().figures_dir / version / f["file"]).read_text(encoding="utf-8")
        return (
            f'<figure><pre class="mermaid" role="img" aria-label="{html.escape(f["alt"])}">{html.escape(src)}'
            f"</pre>{cap}</figure>"
        )
    return (
        f'<figure><img src="/figures/{version}/{f["file"]}" alt="{html.escape(f["alt"])}" loading="lazy">{cap}</figure>'
    )


def blocks(lang: str) -> dict[str, str]:
    m = load_methodology()
    cfg = m.config
    d = load_dictionary(get_settings().capabilities_dir / m.capability_dictionary_file)
    reg = load_registry()
    rep = _latest_report()
    manifest = figures_manifest(m.version)
    te = cfg["technical_exposure"]["weights"]
    tw = cfg["task_weights"]
    pr = cfg["process_redesign"]["weights"]
    out: dict[str, str] = {}
    out["indices_table"] = _table(
        ["Índice", "Definição", "Agregação"],
        [
            [
                "OAE — Occupational AI Exposure",
                "exposição técnica média ponderada das tarefas",
                "Σ w·technical_exposure",
            ],
            [
                "OAP — Occupational Automation Potential",
                "potencial de automação considerando barreiras",
                "Σ w·automation",
            ],
            [
                "OAuP — Occupational Augmentation Potential",
                "potencial de aumento da capacidade humana",
                "Σ w·augmentation",
            ],
            [
                "OTP — Occupational Transformation Potential",
                "potencial de mudança na forma de execução",
                "Σ w·transformation",
            ],
        ],
    ) + _table(["Classe de tarefa", "Código"], [[v, k] for k, v in TASK_CLASSES.items()])
    src_rows = []
    if rep:
        for k, v in rep["sources"].items():
            src_rows.append(
                [
                    k,
                    v.get("status"),
                    v.get("version") or v.get("release") or "—",
                    ", ".join(
                        f"{a}={b}"
                        for a, b in v.items()
                        if a in ("tasks", "occupation", "uri", "code", "activities", "essential_skills_as_tasks")
                    ),
                ]
            )
    out["sources_table"] = (
        _table(["Fonte", "Status na última execução", "Versão", "Detalhes"], src_rows)
        if src_rows
        else "<p>Nenhuma execução registrada ainda.</p>"
    )
    cw = cfg["crosswalk"]
    out["crosswalk_weights"] = (
        "<pre><code>mapping_confidence = "
        + " + ".join(f"{w:.2f}·{k}" for k, w in cw["weights"].items())
        + "</code></pre>"
        + _table(["Classe", "Mínimo"], [[c["label"], c["min"]] for c in cw["classes"]])
        + (
            f"<p>Componente desconhecido = {cw['unknown_component_value']}; aceitação automática: "
            f"{'sim' if cw['auto_accept'] else 'não'}; transferência de priors a partir da classe "
            f"<code>{cw['prior_transfer_min_class']}</code>.</p>"
        )
    )
    fam_rows = []
    for code, name in d.families().items():
        caps = [c for c in d.capabilities if c.family == code]
        fam_rows.append([code, name, len(caps), ", ".join(c.name for c in caps)])
    out["capability_summary"] = (
        f"<p>Versão <strong>{d.version}</strong> ({d.released_at}, válida até {d.valid_until}); status "
        f"<code>{d.status}</code>; revisão <code>{d.review_status}</code>; {len(d.capabilities)} capacidades; "
        f'hash {d.content_hash[:12]}. Registro completo em <a href="/api/capabilities">/api/capabilities</a>.</p>'
        + _table(["Família", "Nome", "Nº", "Capacidades"], fam_rows)
    )
    if rep and rep.get("benchmark"):
        b = rep["benchmark"]
        cal = b.get("title_pair_calibration") or {}
        tc = b.get("calibration", {})
        out["embedding_summary"] = (
            f"<p>Modelo da última execução: <code>{html.escape(b['model'])}</code>. "
            + (
                "<strong>Linha de base lexical — não é um modelo semântico.</strong> "
                if "baseline" in b["model"]
                else ""
            )
            + f"Calibração tarefa–capacidade (benchmark v{html.escape(str(tc.get('benchmark_version')))}): piso "
            f"{tc.get('floor', 0):.3f}, teto {tc.get('ceiling', 0):.3f}; calibração de títulos: piso "
            f"{cal.get('floor', 0):.3f}, teto {cal.get('ceiling', 0):.3f}. Rótulos rascunhados por IA, não ouro.</p>"
        )
        ov = b["overall"]
        out["benchmark_summary"] = (
            _table(
                ["Métrica", "Valor"],
                [
                    ["precision@3", ov.get("p@3")],
                    ["recall@5", ov.get("r@5")],
                    ["MAP", ov.get("MAP")],
                    ["nDCG@5", ov.get("ndcg@5")],
                    ["Spearman (grau × escore)", b.get("spearman_grade_vs_score")],
                    ["Taxa de falsos positivos", b.get("false_positive_rate")],
                    ["Taxa de falsos negativos", b.get("false_negative_rate")],
                ]
                + [[f"MAP ({lang_})", v.get("MAP")] for lang_, v in sorted(b.get("by_language", {}).items())],
            )
            + f'<p class="note">{html.escape(b.get("caveat", ""))}</p>'
        )
    else:
        out["embedding_summary"] = out["benchmark_summary"] = "<p>Sem execução registrada.</p>"
    out["formulas"] = (
        "<pre><code>"
        + html.escape(
            "\n".join(
                [
                    "technical_exposure = "
                    + " + ".join(f"{w:.2f}·{k}" for k, w in te.items())
                    + "   (pesos de termos ausentes redistribuídos)",
                    "automation_potential = technical_exposure · (1−E8 físico) · (1−E7 social) · (1−E9 responsabilidade)"
                    " · padronização",
                    "augmentation_potential = technical_exposure · E6 julgamento · complementaridade",
                    "transformation_potential = max(automação, aumento) · ("
                    + " + ".join(f"{w:.2f}·{k}" for k, w in pr.items())
                    + ")",
                    f"task_weight_raw = importance_norm^{tw['alpha']} · relevance_norm^{tw['beta']} · frequency_norm^{tw['gamma']}",
                    "task_weight = task_weight_raw / Σ task_weight_raw",
                    "OAE = Σ task_weight · technical_exposure ;  OAP, OAuP, OTP análogos",
                    f"E1 = média das top-{cfg['semantic_match']['top_k']} similaridades calibradas (penalidade de exemplos "
                    f"negativos = {cfg['semantic_match']['negative_penalty']})",
                    f"E6–E10 = prior ocupacional O*NET ± {cfg['lexical_adjustment']['delta']} por pistas lexicais",
                ]
            )
        )
        + "</code></pre>"
        + f"<p>Status: <code>{cfg['status']}</code>. Fonte: <code>config/methodology/"
        f"{m.config_path.name}</code>; fingerprint <code>{m.fingerprint[:16]}</code>.</p>"
    )
    uw = cfg["uncertainty"]["weights"]
    mc = cfg["aggregation"]["monte_carlo"]
    out["uncertainty_weights"] = _table(["Fonte de incerteza", "Peso"], [[k, v] for k, v in uw.items()]) + (
        f"<p>Monte Carlo: {mc['draws']} sorteios, semente {mc['seed']}, intervalo P{mc['interval'][0]}–"
        f"P{mc['interval'][1]}; ruído = {mc['dimension_noise_base_sd']} + {mc['dimension_noise_uncertainty_sd']}·E14; "
        f"Dirichlet κ = {mc['dirichlet_concentration']}.</p>"
    )
    changelog = (get_settings().docs_dir / "CHANGELOG-methodology.md").read_text(encoding="utf-8")
    out["changelog"] = _table(
        ["Versão", "Data", "Status", "Fingerprint"],
        [[v["version"], v["released_at"], v["status"], v["fingerprint"][:16]] for v in reg["versions"]],
    ) + md_render("## " + changelog.split("\n## ", 1)[1] if "\n## " in changelog else changelog)
    out["licenses"] = _table(
        ["Fonte", "Licença"],
        [
            ["O*NET 31.0", "CC BY 4.0 — https://www.onetcenter.org/license_db.html"],
            ["ESCO", "Termos de uso ESCO (reuso da Comissão Europeia) — confirmar"],
            ["CBO 2002", "Dados públicos do MTE — confirmar termos"],
            ["Anthropic Economic Index", "Ver cartão do dataset no Hugging Face — confirmar"],
            ["Código deste repositório", "Apache-2.0"],
        ],
    )
    for name in [
        "flow",
        "relation",
        "er",
        "crosswalk",
        "calculation",
        "automation_augmentation",
        "uncertainty",
        "sensitivity",
        "curriculum",
    ]:
        out[f"figure:{name}"] = _figure(name, manifest, m.version)
    return out


def render_about(lang: str = "pt-BR") -> dict[str, Any]:
    fm, body = load_content(lang)
    b = blocks(lang)
    refs = references()
    keys = cited_keys(body) | set(load_methodology().config.get("references", []))
    b["references"] = (
        '<ol class="refs">' + "".join(format_reference(refs[k]) for k in sorted(keys) if k in refs) + "</ol>"
    )
    # Blocks are injected after Markdown rendering so multi-line HTML (figures, tables) is never re-parsed.
    body = PLACEHOLDER.sub(lambda mm: f"<!--block:{mm.group(1)}-->", body)
    html_body = md_render(body)
    html_body = re.sub(
        r"<!--block:([\w:]+)-->",
        lambda mm: b.get(mm.group(1), f"<p>[bloco desconhecido: {mm.group(1)}]</p>"),
        html_body,
    )

    def cite(mm: re.Match) -> str:
        parts = [k.strip().lstrip("@") for k in mm.group(1).split(";")]
        return (
            "("
            + "; ".join(
                f'<a href="#ref-{k}">{html.escape(_author_year(refs[k]))}</a>' if k in refs else f"<mark>{k}?</mark>"
                for k in parts
            )
            + ")"
        )

    html_body = CITATION.sub(cite, html_body)
    return {
        "front_matter": fm,
        "html": html_body,
        "sections": section_ids(load_content(lang)[1]),
        "cited": sorted(keys),
    }
