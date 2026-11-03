"""Server-rendered accessible HTML for the vertical slice (Next.js frontend arrives in phase 7, same JSON API)."""

from __future__ import annotations

from html import escape as e
from typing import Any
from urllib.parse import quote

from observatory.api.i18n import t
from observatory.exposure.formulas import TASK_CLASSES

CSS = """
:root{--bg:#fbfbfa;--fg:#1d1d1f;--muted:#5f6368;--card:#ffffff;--line:#d9d9d6;--accent:#0b5cad;--warn-bg:#fff6e0;
--warn-fg:#6b4a00;--good:#00704a;--bar:#0072B2}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececec;--muted:#a3a3a8;--card:#1e1e21;--line:#3a3a3f;
--accent:#7fb6ff;--warn-bg:#3a2f12;--warn-fg:#ffd98a;--good:#5fd3a3;--bar:#56B4E9}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif}a{color:var(--accent)}.skip{position:absolute;left:-999px}.skip:focus{left:16px;top:8px;
background:var(--card);padding:8px;z-index:10}header.top{border-bottom:1px solid var(--line);background:var(--card)}
header.top .in,main{max-width:1180px;margin:0 auto;padding:12px 16px}nav a{margin-right:16px;font-weight:600}
.brand{font-weight:700;margin-right:24px}.disclaimer{background:var(--warn-bg);color:var(--warn-fg);
border-left:4px solid currentColor;padding:10px 14px;margin:16px 0;border-radius:4px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.card{background:var(--card);
border:1px solid var(--line);border-radius:8px;padding:14px}.card .v{font-size:1.9rem;font-weight:700}
.muted{color:var(--muted);font-size:.9em}.badge{display:inline-block;border:1px solid var(--line);border-radius:10px;
padding:0 8px;font-size:.78em;margin-left:4px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;
margin:8px 0 16px;font-size:.92em}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;
vertical-align:top}th{background:var(--card)}.bar{height:8px;background:var(--line);border-radius:4px;min-width:60px}
.bar>span{display:block;height:8px;background:var(--bar);border-radius:4px}details{margin:4px 0}summary{cursor:pointer}
figure{margin:16px 0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
figure img{max-width:100%;height:auto;background:#fff}pre{white-space:pre-wrap;overflow-x:auto;background:var(--card);
border:1px solid var(--line);padding:10px;border-radius:6px}.note{color:var(--muted);font-style:italic}
form.inline{display:inline}form.review{display:grid;gap:8px;max-width:760px;margin:12px 0}
fieldset{border:1px solid var(--line);border-radius:6px;padding:8px 12px}
form.review textarea{min-height:56px}.status-accepted{color:var(--good);font-weight:700}
.status-rejected{color:#b3261e;font-weight:700}.msg{border-left:4px solid var(--accent);padding:8px 12px;
background:var(--card);margin:12px 0}.msg.err{border-color:#b3261e}tr.decided-accepted{outline:2px solid var(--good)}
label.grade{margin-right:14px;white-space:nowrap}
input,button,select{font:inherit;padding:6px 8px}h1{font-size:1.6rem}h2{margin-top:2rem}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
"""

MERMAID = (
    '<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/'
    'mermaid.esm.min.mjs";mermaid.initialize({startOnLoad:true,securityLevel:"strict",'
    'theme:window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"default"});</script>'
)


def layout(title: str, body: str, lang: str = "pt-BR", mermaid: bool = False) -> str:
    s = t(lang)
    q = "?lang=en" if lang == "en" else ""
    other = ("en", "English") if lang != "en" else ("pt-BR", "Português")
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>{CSS}</style></head><body><a class="skip" href="#main">{s["skip"]}</a>
<header class="top"><div class="in"><span class="brand">{e(s["app_name"])}</span><nav aria-label="principal">
<a href="/{q}">{s["nav_home"]}</a><a href="/crosswalks{q}">{s["nav_crosswalks"]}</a>
<a href="/annotations{q}">{s["nav_annotation"]}</a>
<a href="/about{q}">{s["nav_about"]}</a>
<a href="?lang={other[0]}" lang="{other[0]}">{other[1]}</a></nav></div></header>
<main id="main"><p class="disclaimer" role="note">{e(s["disclaimer"])}</p>{body}</main>
{MERMAID if mermaid else ""}</body></html>"""


def pct_bar(v: float | None) -> str:
    if v is None:
        return "—"
    return (
        f'<div class="bar" role="img" aria-label="{v:.2f}"><span style="width:{max(0, min(1, v)) * 100:.0f}%">'
        f'</span></div><span class="muted">{v:.2f}</span>'
    )


def _score_cell(o: dict, k: str) -> str:
    if not o.get("scores"):
        return "<td>—</td>"
    lo, hi = o["intervals"][k]
    return f"<td>{pct_bar(o['scores'].get(k))}<div class=muted>[{lo:.2f}, {hi:.2f}]</div></td>"


def _home_row(o: dict, lang: str) -> str:
    q = "?lang=en" if lang == "en" else ""
    unc = o["quality"]["mean_uncertainty"] if o.get("quality") else "—"
    return (
        f"<tr><td>{e(o['taxonomy'])}</td><td><code>{e(o['code'])}</code></td>"
        f'<td><a href="/occupations/{o["id"]}{q}">{e(o["title"])}</a></td>'
        + "".join(_score_cell(o, k) for k in ("OAE", "OAP", "OAuP", "OTP"))
        + f"<td>{unc}</td></tr>"
    )


def home(occupations: list[dict], warnings: list[str], lang: str, q: str = "") -> str:
    s = t(lang)
    rows = "".join(_home_row(o, lang) for o in occupations) or f"<tr><td colspan=8>{s['no_data']}</td></tr>"
    warn = "".join(f"<li>{e(w)}</li>" for w in warnings)
    return f"""<h1>{s["occupations"]}</h1>
<form role="search" action="/" method="get"><label for="q">{s["search"]}</label><br>
<input id="q" name="q" value="{e(q)}" size="40"> <button>{s["search_btn"]}</button></form>
<div class="table-wrap"><table><caption class="muted">OAE / OAP / OAuP / OTP — {s["interval"]}</caption><thead><tr>
<th scope="col">{s["taxonomy"]}</th><th scope="col">{s["code"]}</th><th scope="col">{s["title"]}</th>
<th scope="col">OAE</th><th scope="col">OAP</th><th scope="col">OAuP</th><th scope="col">OTP</th>
<th scope="col">E14</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>{s["warnings"]}</h2><ul>{warn}</ul>"""


def occupation_page(o: dict, lang: str) -> str:
    s = t(lang)
    a = o.get("assessment")
    head = (
        f'<h1>{e(o["title"])} <span class="badge">{e(o["taxonomy"])}</span></h1>'
        f"<p><code>{e(o['code'])}</code> · {e(o.get('group_code') or '')}</p>"
        f"<h2>{s['description']}</h2><p>{e(o.get('description') or '—')}</p>"
    )
    if o.get("attributes", {}).get("description_pt"):
        head += f'<p lang="pt" class="muted">{e(o["attributes"]["description_pt"])}</p>'
    aliases = ", ".join(e(f"{x['label']} ({x['language']})") for x in o.get("aliases", [])[:40])
    head += f"<details><summary>{s['aliases']} ({len(o.get('aliases', []))})</summary><p>{aliases}</p></details>"
    cw_rows = "".join(
        f"<tr><td>{e(c['other_taxonomy'])} <code>{e(c['other_code'])}</code><br>{e(c['other_title'])}</td>"
        f"<td>{c['mapping_confidence']:.2f} <span class=badge>{e(c['confidence_class'])}</span></td>"
        f"<td>{_fmt(c['title_similarity'])} / {_fmt(c['task_similarity'])} / {_fmt(c['skill_similarity'])} / "
        f"{_fmt(c['hierarchy_consistency'])} / {_fmt(c['qualification_consistency'])}</td>"
        f"<td>{e(c['status'])}</td><td><details><summary>regras</summary><ul>"
        + "".join(f"<li>{e(r)}</li>" for r in c["rules"])
        + "</ul></details></td></tr>"
        for c in o.get("crosswalks", [])
    )
    head += (
        f"<h2>{s['crosswalks']}</h2><div class=table-wrap><table><thead><tr><th scope=col>Ocupação</th>"
        f"<th scope=col>mapping_confidence</th><th scope=col>título / tarefas / habilidades / hierarquia / "
        f"qualificação</th><th scope=col>{s['status']}</th><th scope=col>Método</th></tr></thead><tbody>"
        f"{cw_rows or '<tr><td colspan=5>—</td></tr>'}</tbody></table></div>"
        "<p class=muted>Revisão (aceitar, rejeitar, editar, dividir, mesclar) via "
        "<code>POST /api/crosswalks/{id}/review</code> com chave administrativa e justificativa obrigatória.</p>"
    )
    if not a:
        return head + f"<p>{s['no_data']}</p>"
    cards = "".join(
        f"<div class=card><div class=muted>{k}</div><div class=v>{a['scores'][k]:.2f}</div>"
        f"<div class=muted>{s['interval']}: [{a['intervals'][k][0]:.2f}, {a['intervals'][k][1]:.2f}]</div></div>"
        for k in ("OAE", "OAP", "OAuP", "OTP")
    )
    q = a["quality"]
    quality = "".join(f"<tr><th scope=row>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in q.items())
    lim = "".join(f"<li>{e(x)}</li>" for x in a["limitations"])
    tasks = "".join(_task_row(c, s) for c in sorted(a["components"], key=lambda c: -c["task_weight"]))
    sens = sorted(a["sensitivity"]["one_at_a_time"], key=lambda r: -abs(r["d_OAE"]))[:6]
    sens_rows = "".join(
        f"<tr><td>{e(r['parameter'])}</td><td>{r['change']:+.0%}</td><td>{r['d_OAE']:+.4f}</td>"
        f"<td>{r['d_OAP']:+.4f}</td><td>{r['d_OAuP']:+.4f}</td><td>{r['d_OTP']:+.4f}</td></tr>"
        for r in sens
    )
    pv = a["pipeline_version"]
    prov = [
        ("Fonte", f"{o['source']['dataset']} {o['source']['version']} — {o['source']['retrieval_method']}"),
        ("URL", o["source"]["source_url"]),
        ("Data de obtenção", o["source"]["retrieval_date"]),
        ("SHA-256 da fonte", o["source"]["file_sha256"]),
        ("Licença", o["source"]["license"]),
        ("Metodologia", f"{a['methodology_version']} · fingerprint {a['methodology_fingerprint'][:16]}"),
        ("Dicionário de capacidades", a["capability_version"]),
        ("Modelo de embeddings", a["embedding_model"]),
        (
            "Calibração",
            f"piso {a['embedding_calibration']['floor']:.3f} · teto "
            f"{a['embedding_calibration']['ceiling']:.3f} · benchmark "
            f"{a['embedding_calibration']['benchmark_version']}",
        ),
        (
            "Pipeline",
            f"commit {pv.get('git_commit') or 'sem commit'} · árvore {pv['source_tree_sha256'][:16]}"
            f"{' · alterações não commitadas' if pv.get('git_dirty') else ''}",
        ),
        ("Execução", f"{a['run_id']} · {a['created_at']}"),
    ]
    prov_rows = "".join(f"<tr><th scope=row>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in prov)
    hist = "".join(
        f"<tr><td>{h['id']}</td><td>{e(h['created_at'])}</td><td>{e(h['methodology_version'])}</td>"
        f"<td>{e(h['embedding_model'])}</td><td>{h['scores']['OAE']:.3f}</td></tr>"
        for h in o["history"]
    )
    lq = "?lang=en" if lang == "en" else ""
    return (
        head
        + f"""<h2>{s["scores"]}</h2><div class=cards>{cards}</div>
<p><a href="/api/occupations/{o["id"]}/assessment">{s["export"]}</a> · <a href="/about{lq}#formulas">fórmulas</a></p>
<h2>{s["tasks"]}</h2><div class=table-wrap><table><thead><tr><th scope=col>Tarefa</th><th scope=col>{s["weight"]}</th>
<th scope=col>{s["class"]}</th><th scope=col>{s["exposure"]}</th><th scope=col>{s["automation"]}</th>
<th scope=col>{s["augmentation"]}</th><th scope=col>{s["transformation"]}</th><th scope=col>{s["confidence"]}</th>
</tr></thead><tbody>{tasks}</tbody></table></div>
<h2>{s["quality"]}</h2><div class=table-wrap><table><tbody>{quality}</tbody></table></div>
<h2>{s["limitations"]}</h2><ul>{lim}</ul>
<h2>{s["sensitivity"]}</h2><div class=table-wrap><table><thead><tr><th scope=col>Parâmetro</th><th scope=col>Δ</th>
<th scope=col>ΔOAE</th><th scope=col>ΔOAP</th><th scope=col>ΔOAuP</th><th scope=col>ΔOTP</th></tr></thead>
<tbody>{sens_rows}</tbody></table></div>
<h2>{s["provenance"]}</h2><div class=table-wrap><table><tbody>{prov_rows}</tbody></table></div>
<h2>{s["history"]}</h2><div class=table-wrap><table><thead><tr><th scope=col>#</th><th scope=col>Data</th>
<th scope=col>Metodologia</th><th scope=col>Embeddings</th><th scope=col>OAE</th></tr></thead><tbody>{hist}</tbody>
</table></div>"""
    )


def _fmt(v: float | None) -> str:
    return "?" if v is None else f"{v:.2f}"


def _task_row(c: dict, s: dict) -> str:
    caps = "".join(
        f"<li>{e(m['capability_id'])} {e(m['name'])} — {m['calibrated_similarity']:.2f} "
        f"<span class=muted>(bruta {m['raw_similarity']:.2f})</span></li>"
        for m in c["matched_capabilities"]
    )
    ev = "".join(
        f"<li>{e(x['source'])}: {x['pct_of_conversations']}% das conversas; padrão de automação "
        f"{x.get('automation_pattern_share')}, aumento {x.get('augmentation_pattern_share')} "
        f"({e(x.get('match_method', ''))} {x.get('match_score', '')}; não revisado por pares)</li>"
        for x in c["evidence"] or []
    )
    bars = "".join(f"<li>{e(b['name'])} = {b['value']:.2f}</li>" for b in c["barriers"] or [])
    dims = "".join(
        f"<tr><th scope=row>{k}</th><td>{'—' if v is None else f'{v:.3f}'}</td><td><code>"
        f"{e(_short(c['dimension_sources'].get(k)))}</code></td></tr>"
        for k, v in c["dimensions"].items()
    )
    missing = ", ".join(c["missing_flags"] or []) or "—"
    detail = (
        f"<details><summary>{s['justification']}</summary><p>{e(c['justification'])}</p>"
        f"<h4>{s['capabilities']}</h4><ul>{caps or '<li>—</li>'}</ul><h4>{s['evidence']}</h4>"
        f"<ul>{ev or '<li>—</li>'}</ul><h4>{s['barriers']}</h4><ul>{bars or '<li>—</li>'}</ul>"
        f"<h4>{s['dimensions']}</h4><div class=table-wrap><table><tbody>{dims}</tbody></table></div>"
        f"<p class=muted>Peso: {e(_short(c['dimension_sources'].get('weight')))} · ausências: {e(missing)}</p>"
        f"</details>"
    )
    return (
        f"<tr><td>{e(c['statement'])}{detail}</td><td>{c['task_weight']:.3f}</td>"
        f"<td>{e(TASK_CLASSES[c['task_class']])}</td><td>{pct_bar(c['technical_exposure'])}</td>"
        f"<td>{pct_bar(c['automation_potential'])}</td><td>{pct_bar(c['augmentation_potential'])}</td>"
        f"<td>{pct_bar(c['transformation_potential'])}</td><td>{c['confidence']:.2f}</td></tr>"
    )


def _short(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        return "; ".join(f"{k}={_short(x)}" for k, x in v.items() if x not in (None, [], {}))
    if isinstance(v, list):
        return ",".join(_short(x) for x in v)
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def about_page(about: dict, lang: str) -> str:
    toc = "".join(f'<li><a href="#{sid}">{sid}</a></li>' for sid in about["sections"])
    return (
        f"<h1>{t(lang)['about']}</h1><p class=muted>methodology_version {about['front_matter']['methodology_version']}"
        f'</p><nav aria-label="sumário"><details><summary>Sumário</summary><ol>{toc}</ol></details></nav>'
        + about["html"]
    )


REVIEW_TEXT = {
    "pt-BR": {
        "title": "Revisão humana dos crosswalks",
        "intro": "Para cada ocupação da CBO e da ESCO, o sistema propõe ocupações equivalentes no O*NET. Nenhuma é "
        "aceita automaticamente. Sua decisão define de qual ocupação O*NET vêm os dados de contexto de trabalho "
        "(priors E6–E10) nas próximas execuções, e fica registrada com seu nome e justificativa.",
        "key_ok": "Chave administrativa configurada. Digite-a no formulário para registrar a decisão.",
        "key_missing": "A gravação está desativada porque não há chave administrativa configurada. Para gerar uma, "
        "rode o comando abaixo no terminal, na pasta do projeto, e reinicie o servidor:",
        "question": "Qual ocupação do O*NET é a equivalente de",
        "suggestion": "Sugestão automática",
        "suggestion_note": "É um cálculo do sistema para ajudar, não uma decisão. Confira os motivos e escolha.",
        "why": "Por quê",
        "decided": "Decisão registrada",
        "by": "por",
        "candidate": "1. Escolha a ocupação O*NET",
        "decision": "2. Decisão",
        "accept_opt": "É a equivalente (aceitar)",
        "reject_opt": "Não é equivalente (rejeitar)",
        "who": "3. Seu nome",
        "justification": "4. Justificativa (mínimo de 10 caracteres)",
        "justification_hint": "Ex.: As tarefas centrais e a qualificação são as mesmas; "
        "as duas fontes oficiais confirmam.",
        "key": "5. Chave administrativa",
        "submit": "Registrar decisão",
        "details": "Ver todos os candidatos e os detalhes técnicos",
        "conf": "confiança",
        "official_yes": "fontes oficiais confirmam",
        "official_split": "fontes oficiais divergem",
        "official_no": "fontes oficiais não confirmam",
        "official_none": "sem fonte oficial aplicável",
        "saved": "Decisão registrada",
        "reason_both": "as fontes oficiais disponíveis confirmam a correspondência ({n})",
        "reason_split": "as fontes oficiais divergem ({votes})",
        "reason_title": "o título é equivalente",
        "reason_qual": "o nível de qualificação é o mesmo",
        "reason_qual_diff": "o nível de qualificação é diferente",
        "reason_tasks": "as tarefas são {pct:.0f}% tão parecidas quanto as da ocupação mais parecida",
        "reason_conf": "confiança composta {c:.3f} (a mais alta é {b:.3f})",
        "ambiguous": "Os primeiros candidatos estão praticamente empatados (diferença de {m:.3f}); por isso a "
        "escolha precisa de revisão humana.",
        "cols": (
            "Pos.",
            "Candidato",
            "Confiança",
            "Título / tarefas / habilidades / hierarquia / qualificação",
            "Fontes oficiais",
            "Situação",
            "Regras e histórico",
        ),
        "none": "Nenhum mapeamento proposto. Execute o pipeline.",
        "unknown": "desconhecido",
    },
    "en": {
        "title": "Human review of crosswalks",
        "intro": "For each CBO and ESCO occupation the system proposes equivalent O*NET occupations. None is accepted "
        "automatically. Your decision sets which O*NET occupation provides the work-context data (E6–E10 priors) "
        "in later runs and is recorded with your name and justification.",
        "key_ok": "Admin key configured. Type it in the form to record the decision.",
        "key_missing": "Recording is disabled because no admin key is configured. To create one, run the command "
        "below in a terminal, in the project folder, and restart the server:",
        "question": "Which O*NET occupation is equivalent to",
        "suggestion": "Automatic suggestion",
        "suggestion_note": "A system calculation to help you, not a decision. Check the reasons and choose.",
        "why": "Why",
        "decided": "Recorded decision",
        "by": "by",
        "candidate": "1. Choose the O*NET occupation",
        "decision": "2. Decision",
        "accept_opt": "It is equivalent (accept)",
        "reject_opt": "It is not equivalent (reject)",
        "who": "3. Your name",
        "justification": "4. Justification (at least 10 characters)",
        "justification_hint": "E.g.: Core tasks and qualification match; both official sources confirm.",
        "key": "5. Admin key",
        "submit": "Record decision",
        "details": "See all candidates and technical details",
        "conf": "confidence",
        "official_yes": "official sources confirm",
        "official_split": "official sources disagree",
        "official_no": "official sources do not confirm",
        "official_none": "no applicable official source",
        "saved": "Decision recorded",
        "reason_both": "the available official sources confirm the correspondence ({n})",
        "reason_split": "the official sources disagree ({votes})",
        "reason_title": "the title is equivalent",
        "reason_qual": "the qualification level is the same",
        "reason_qual_diff": "the qualification level differs",
        "reason_tasks": "its tasks are {pct:.0f}% as similar as the most similar occupation's",
        "reason_conf": "composite confidence {c:.3f} (highest is {b:.3f})",
        "ambiguous": "The top candidates are practically tied (difference {m:.3f}), so the choice needs human review.",
        "cols": (
            "Rank",
            "Candidate",
            "Confidence",
            "Title / tasks / skills / hierarchy / qualification",
            "Official sources",
            "Status",
            "Rules and history",
        ),
        "none": "No proposed mappings. Run the pipeline.",
        "unknown": "unknown",
    },
}


def _rt(lang: str) -> dict:
    return REVIEW_TEXT.get(lang, REVIEW_TEXT["pt-BR"])


def official_label(m: dict, r: dict) -> str:
    votes = (m.get("official") or {}).get("votes") or {}
    if not votes:
        return r["official_none"]
    vals = set(votes.values())
    if vals == {1.0}:
        return r["official_yes"]
    if len(vals) > 1:
        return r["official_split"]
    return r["official_no"]


SOURCE_NAMES = {
    "pt-BR": {
        "onet_esco_table": "tabela ESCO→O*NET publicada pelo O*NET",
        "official_table_chain": "cadeia de tabelas oficiais (MTE/ILO/BLS/O*NET)",
    },
    "en": {
        "onet_esco_table": "ESCO→O*NET table published by O*NET",
        "official_table_chain": "chain of official tables (MTE/ILO/BLS/O*NET)",
    },
}


def reasons(m: dict, best_conf: float, r: dict) -> list[str]:
    out = []
    names = SOURCE_NAMES["en" if r is REVIEW_TEXT["en"] else "pt-BR"]
    votes = (m.get("official") or {}).get("votes") or {}
    if votes and set(votes.values()) == {1.0}:
        out.append(r["reason_both"].format(n="; ".join(names.get(k, k) for k in votes)))
    elif len(set(votes.values())) > 1:
        yes = "sim" if r is REVIEW_TEXT["pt-BR"] else "yes"
        no = "não" if r is REVIEW_TEXT["pt-BR"] else "no"
        out.append(
            r["reason_split"].format(
                votes="; ".join(f"{names.get(k, k)}: {yes if v else no}" for k, v in votes.items())
            )
        )
    if (m.get("title_similarity") or 0) >= 0.9:
        out.append(r["reason_title"])
    q = m.get("qualification_consistency")
    if q is not None:
        out.append(r["reason_qual"] if q >= 0.99 else r["reason_qual_diff"])
    rel = ((m.get("null") or {}).get("tasks") or {}).get("relative_to_best")
    if rel is not None:
        out.append(r["reason_tasks"].format(pct=100 * rel))
    out.append(r["reason_conf"].format(c=m["mapping_confidence"], b=best_conf))
    return out


def _tech_table(g: dict, q: str, lang: str) -> str:
    r = _rt(lang)
    keys = (
        "title_similarity",
        "task_similarity",
        "skill_similarity",
        "hierarchy_consistency",
        "qualification_consistency",
    )
    rows = []
    for i, m in enumerate(g["mappings"], 1):
        comps = " / ".join("?" if m[k] is None else f"{m[k]:.2f}" for k in keys)
        title = e(m["other_title"])
        tgt = f'<a href="/occupations/{m["target_id"]}{q}">{title}</a>' if m["target_assessed"] else title
        hist = "".join(
            f"<li>{e(h['at'][:19])} · {e(h['action'])} · {e(h['actor'])}"
            + (f" — {e(h['justification'])}" if h["justification"] else "")
            + "</li>"
            for h in m["history"]
        )
        rules = "".join(f"<li>{e(x)}</li>" for x in m["rules"])
        rows.append(
            f'<tr class="decided-{e(m["status"])}"><td>{i}</td><td><code>{e(m["other_code"])}</code><br>{tgt}</td>'
            f'<td>{m["mapping_confidence"]:.3f}<br><span class="badge">{e(m["confidence_class"])}</span></td>'
            f"<td>{comps}</td><td>{e(official_label(m, r))}</td>"
            f'<td><span class="badge status-{e(m["status"])}">{e(m["status"])}</span></td>'
            f"<td><details><summary>{r['cols'][6]}</summary><ul>{rules}</ul><ol>{hist}</ol></details></td></tr>"
        )
    head = "".join(f'<th scope="col">{h}</th>' for h in r["cols"])
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def _group_form(g: dict, q: str, lang: str, key_ok: bool, values: dict) -> str:
    r = _rt(lang)
    gid = g["source"]["id"]
    chosen = str(values.get("mapping_id") or (g["recommended"]["id"] if g["recommended"] else ""))
    opts = []
    for m in g["candidates"]:
        mid = str(m["id"])
        checked = " checked" if mid == chosen else ""
        opts.append(
            f'<div><input type="radio" id="c{mid}" name="mapping_id" value="{mid}" required{checked}> '
            f'<label for="c{mid}"><code>{e(m["other_code"])}</code> {e(m["other_title"])} — {r["conf"]} '
            f"{m['mapping_confidence']:.3f} — {e(official_label(m, r))}</label></div>"
        )
    act = values.get("action", "accept")
    dis = "" if key_ok else " disabled"
    return (
        f'<form class="review" method="post" action="/crosswalks/review{q}">'
        f"<fieldset><legend>{r['candidate']}</legend>{''.join(opts)}</fieldset>"
        f"<fieldset><legend>{r['decision']}</legend>"
        f'<div><input type="radio" id="a{gid}" name="action" value="accept"{" checked" if act == "accept" else ""}> '
        f'<label for="a{gid}">{r["accept_opt"]}</label></div>'
        f'<div><input type="radio" id="x{gid}" name="action" value="reject"{" checked" if act == "reject" else ""}> '
        f'<label for="x{gid}">{r["reject_opt"]}</label></div></fieldset>'
        f'<label for="r{gid}">{r["who"]}</label>'
        f'<input id="r{gid}" name="reviewer" required minlength="2" autocomplete="name" '
        f'value="{e(values.get("reviewer", ""))}">'
        f'<label for="j{gid}">{r["justification"]}</label>'
        f'<textarea id="j{gid}" name="justification" required minlength="10" '
        f'placeholder="{e(r["justification_hint"])}">{e(values.get("justification", ""))}</textarea>'
        f'<label for="k{gid}">{r["key"]}</label>'
        f'<input id="k{gid}" name="api_key" type="password" required autocomplete="off"{dis}>'
        f'<div><button type="submit"{dis}>{r["submit"]}</button></div></form>'
    )


def review_page(
    groups: list[dict],
    lang: str,
    key_ok: bool,
    message: str | None = None,
    error: bool = False,
    error_group: int | None = None,
    values: dict | None = None,
) -> str:
    r = _rt(lang)
    q = "?lang=en" if lang == "en" else ""
    parts = [f"<h1>{r['title']}</h1><p>{e(r['intro'])}</p>"]
    if key_ok:
        parts.append(f'<p class="msg" role="note">{r["key_ok"]}</p>')
    else:
        parts.append(
            f'<div class="msg err" role="note"><p>{r["key_missing"]}</p>'
            "<pre><code>python -m observatory.cli admin-key</code></pre></div>"
        )
    if message and error_group is None:
        parts.append(f'<p class="msg{" err" if error else ""}" role="alert">{e(message)}</p>')
    if not groups:
        return "".join(parts) + f"<p>{r['none']}</p>"
    for g in groups:
        src = g["source"]
        gid = src["id"]
        best = g["candidates"][0]["mapping_confidence"] if g["candidates"] else 0.0
        box = []
        if g["decided"]:
            d = g["decided"]
            box.append(
                f'<p class="msg" role="status"><strong>{r["decided"]}:</strong> {e(d["status"])} '
                f"<code>{e(d['other_code'])}</code> {e(d['other_title'])} {r['by']} {e(d['reviewer'] or '')} — "
                f"{e(d['justification'] or '')}</p>"
            )
        if g["recommended"]:
            rec = g["recommended"]
            why = "".join(f"<li>{e(x)}</li>" for x in reasons(rec, best, r))
            box.append(
                f'<div class="card"><p><strong>{r["suggestion"]}:</strong> <code>{e(rec["other_code"])}</code> '
                f"{e(rec['other_title'])}</p><p>{r['why']}:</p><ul>{why}</ul>"
                f'<p class="muted">{r["suggestion_note"]}</p></div>'
            )
        if g["ambiguous"]:
            box.append(f'<p class="muted">{r["ambiguous"].format(m=g["margin"])}</p>')
        if message and error_group == gid:
            box.append(f'<p class="msg err" role="alert">{e(message)}</p>')
        vals = values if error_group == gid else {}
        parts.append(
            f'<section aria-labelledby="g{gid}"><h2 id="g{gid}">{r["question"]} '
            f'“{e(src["title"])}” <span class="badge">{e(src["taxonomy"])}</span>?</h2>'
            f'<p class="muted"><code>{e(src["code"])}</code></p>{"".join(box)}'
            f"{_group_form(g, q, lang, key_ok, vals)}"
            f"<details><summary>{r['details']}</summary>{_tech_table(g, q, lang)}</details></section>"
        )
    return "".join(parts)


ANNOT_TEXT = {
    "pt-BR": {
        "title": "Anotação do benchmark",
        "intro": "Você vai julgar se uma capacidade de IA é capaz de realizar ou apoiar diretamente uma tarefa de "
        "trabalho. São 36 tarefas, cada uma com cerca de 7 capacidades. Suas respostas formam o conjunto de "
        "referência (padrão-ouro) usado para medir e calibrar o sistema.",
        "blind": "Para não influenciar sua resposta, a sugestão do sistema não é mostrada e a ordem é embaralhada.",
        "how": "Como julgar: Relacionada = a capacidade realiza ou apoia diretamente uma parte central da tarefa. "
        "Parcialmente = ajuda numa parte secundária ou sob condições. Não relacionada = não ajuda na tarefa. "
        "Use “Não sei” quando não tiver segurança: a resposta não é gravada.",
        "name": "Seu nome (o mesmo em todas as sessões)",
        "start": "Começar",
        "progress": "Progresso",
        "task": "Tarefa",
        "lang": "idioma",
        "examples": "Exemplos",
        "g2": "Relacionada",
        "g1": "Parcialmente",
        "g0": "Não relacionada",
        "na": "Não sei",
        "comment": "Comentário (opcional)",
        "save": "Salvar e ir para a próxima",
        "skip": "Pular esta tarefa",
        "done": "Você anotou todas as tarefas. Obrigado!",
        "saved": "Anotação salva.",
        "agreement": "Concordância entre anotadores",
        "see_agreement": "Ver concordância",
        "annotators": "Anotadores",
        "items": "Tarefas anotadas (por alguém)",
        "pairs2": "Pares com 2 ou mais anotações",
        "alpha": "Alfa de Krippendorff (intervalar)",
        "pairwise": "Kappa de Cohen ponderado (quadrático) entre pares de anotadores",
        "vs_draft": "Cada anotador comparado ao rascunho da IA",
        "missing": "pares marcados como relacionados que não estavam no rascunho",
        "interp": {
            "reliable": "confiável (≥ 0,80)",
            "tentative": "só para conclusões provisórias (0,667–0,80)",
            "unreliable": "insuficiente (< 0,667): revisar critérios antes de usar como ouro",
            "insufficient": "dados insuficientes: são necessários pelo menos 2 anotadores nos mesmos pares",
        },
        "gold_hint": "Quando houver concordância suficiente, exporte o conjunto ouro com:",
        "n": "pares em comum",
    },
    "en": {
        "title": "Benchmark annotation",
        "intro": "You will judge whether an AI capability can perform or directly support a work task. There are "
        "36 tasks, each with about 7 capabilities. Your answers form the reference (gold) set used to measure and "
        "calibrate the system.",
        "blind": "To avoid influencing you, the system's suggestion is hidden and the order is shuffled.",
        "how": "How to judge: Related = performs or directly supports a central part of the task. Partially = helps "
        "with a secondary part or under conditions. Unrelated = does not help. Use “Don't know” when unsure: "
        "it is not recorded.",
        "name": "Your name (the same in every session)",
        "start": "Start",
        "progress": "Progress",
        "task": "Task",
        "lang": "language",
        "examples": "Examples",
        "g2": "Related",
        "g1": "Partially",
        "g0": "Unrelated",
        "na": "Don't know",
        "comment": "Comment (optional)",
        "save": "Save and go to the next",
        "skip": "Skip this task",
        "done": "You have annotated every task. Thank you!",
        "saved": "Annotation saved.",
        "agreement": "Inter-annotator agreement",
        "see_agreement": "See agreement",
        "annotators": "Annotators",
        "items": "Tasks annotated (by anyone)",
        "pairs2": "Pairs with 2+ annotations",
        "alpha": "Krippendorff's alpha (interval)",
        "pairwise": "Quadratic-weighted Cohen's kappa per annotator pair",
        "vs_draft": "Each annotator compared with the AI draft",
        "missing": "pairs marked related that were not in the draft",
        "interp": {
            "reliable": "reliable (≥ 0.80)",
            "tentative": "tentative conclusions only (0.667–0.80)",
            "unreliable": "insufficient (< 0.667): revise criteria before using as gold",
            "insufficient": "not enough data: at least 2 annotators on the same pairs are needed",
        },
        "gold_hint": "When agreement is sufficient, export the gold set with:",
        "n": "common pairs",
    },
}


def _at(lang: str) -> dict:
    return ANNOT_TEXT.get(lang, ANNOT_TEXT["pt-BR"])


def annotation_page(
    lang: str,
    annotator: str | None,
    task: dict | None,
    done: int,
    total: int,
    caps: dict,
    message: str | None = None,
    error: bool = False,
) -> str:
    a = _at(lang)
    q = "&lang=en" if lang == "en" else ""
    parts = [f"<h1>{a['title']}</h1>"]
    if message:
        parts.append(
            f'<p class="msg{" err" if error else ""}" role="{"alert" if error else "status"}">{e(message)}</p>'
        )
    if not annotator:
        parts.append(
            f"<p>{e(a['intro'])}</p><p>{e(a['blind'])}</p><p>{e(a['how'])}</p>"
            f'<form class="review" method="get" action="/annotations">'
            f'<label for="ann">{a["name"]}</label><input id="ann" name="annotator" required minlength="2" '
            f'maxlength="64" autocomplete="name">'
            + ('<input type="hidden" name="lang" value="en">' if lang == "en" else "")
            + f'<div><button type="submit">{a["start"]}</button></div></form>'
            f'<p><a href="/annotations/agreement{q.replace("&", "?")}">{a["see_agreement"]}</a></p>'
        )
        return "".join(parts)
    pct = 100 * done / total if total else 0
    parts.append(
        f'<p>{a["progress"]}: {done}/{total} <span class="bar" role="img" aria-label="{pct:.0f}%" '
        f'style="display:inline-block;width:200px;vertical-align:middle"><span style="width:{pct:.0f}%"></span>'
        f"</span> · {e(annotator)}</p><details><summary>{a['how'][:40]}…</summary><p>{e(a['how'])}</p>"
        f"<p>{e(a['blind'])}</p></details>"
    )
    if task is None:
        parts.append(
            f'<p class="msg" role="status">{a["done"]}</p>'
            f'<p><a href="/annotations/agreement{q.replace("&", "?")}">{a["see_agreement"]}</a></p>'
        )
        return "".join(parts)
    rows = []
    for cap_id in task["pairs"]:
        c = caps[cap_id]
        ex = "; ".join(c["examples"][:2])
        radios = "".join(
            f'<label class="grade"><input type="radio" name="label_{cap_id}" value="{v}" required> {a[k]}</label> '
            for v, k in (("2", "g2"), ("1", "g1"), ("0", "g0"), ("na", "na"))
        )
        rows.append(
            f"<fieldset><legend><strong>{e(c['name'])}</strong></legend><p>{e(c['definition'])}</p>"
            f'<p class="muted">{a["examples"]}: {e(ex)}</p><div role="radiogroup">{radios}</div></fieldset>'
        )
    parts.append(
        f'<section aria-labelledby="task"><h2 id="task">{a["task"]}</h2>'
        f'<p class="card" lang="{e(task["language"])}"><strong>{e(task["text"])}</strong></p>'
        f'<p class="muted">{a["lang"]}: {e(task["language"])} · {e(task["item_id"])}</p>'
        f'<form class="review" method="post" action="/annotations{q.replace("&", "?")}">'
        f'<input type="hidden" name="annotator" value="{e(annotator)}">'
        f'<input type="hidden" name="item_id" value="{e(task["item_id"])}">{"".join(rows)}'
        f'<label for="cm">{a["comment"]}</label><textarea id="cm" name="comment"></textarea>'
        f'<div><button type="submit">{a["save"]}</button></div></form>'
        f'<p><a href="/annotations?annotator={quote(annotator)}&skip={quote(task["item_id"])}{q}">{a["skip"]}</a></p>'
        "</section>"
    )
    return "".join(parts)


def agreement_page(stats: dict, lang: str) -> str:
    a = _at(lang)

    def num(x: float | None) -> str:
        return "—" if x is None else f"{x:.3f}"

    pair_rows = (
        "".join(
            f"<tr><td>{e(p['a'])} × {e(p['b'])}</td><td>{p['n']}</td><td>{num(p['kappa'])}</td></tr>"
            for p in stats["pairwise"]
        )
        or '<tr><td colspan="3">—</td></tr>'
    )
    draft_rows = (
        "".join(
            f"<tr><td>{e(d['annotator'])}</td><td>{d['n']}</td><td>{num(d['kappa'])}</td>"
            f"<td>{d['related_pairs_missing_from_draft']}</td></tr>"
            for d in stats["vs_ai_draft"]
        )
        or '<tr><td colspan="4">—</td></tr>'
    )
    return (
        f"<h1>{a['agreement']}</h1>"
        f'<div class="table-wrap"><table><tbody>'
        f'<tr><th scope="row">{a["annotators"]}</th><td>{e(", ".join(stats["annotators"]) or "—")}</td></tr>'
        f'<tr><th scope="row">{a["items"]}</th><td>{stats["items_annotated"]}/{stats["total_items"]}</td></tr>'
        f'<tr><th scope="row">{a["pairs2"]}</th><td>{stats["pairs_with_2plus"]}</td></tr>'
        f'<tr><th scope="row">{a["alpha"]}</th><td>{num(stats["krippendorff_alpha"])} — '
        f"{e(a['interp'][stats['interpretation']])}</td></tr></tbody></table></div>"
        f'<h2>{a["pairwise"]}</h2><div class="table-wrap"><table><thead><tr><th scope="col">'
        f'{a["annotators"]}</th><th scope="col">{a["n"]}</th><th scope="col">kappa</th></tr></thead>'
        f"<tbody>{pair_rows}</tbody></table></div>"
        f'<h2>{a["vs_draft"]}</h2><div class="table-wrap"><table><thead><tr><th scope="col">'
        f'{a["annotators"]}</th><th scope="col">{a["n"]}</th><th scope="col">kappa</th>'
        f'<th scope="col">{a["missing"]}</th></tr></thead><tbody>{draft_rows}</tbody></table></div>'
        f"<p>{a['gold_hint']}</p><pre><code>python -m observatory.cli build-gold</code></pre>"
    )
