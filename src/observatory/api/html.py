"""Server-rendered accessible HTML for the vertical slice (Next.js frontend arrives in phase 7, same JSON API)."""

from __future__ import annotations

from html import escape as e
from typing import Any

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
form.inline{display:inline}input,button,select{font:inherit;padding:6px 8px}h1{font-size:1.6rem}h2{margin-top:2rem}
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
<a href="/{q}">{s["nav_home"]}</a><a href="/about{q}">{s["nav_about"]}</a>
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
