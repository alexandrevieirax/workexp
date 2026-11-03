"""Command-line entry point: python -m observatory.cli <command>."""

from __future__ import annotations

import argparse
import json
import sys

from observatory.config import get_settings


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def cmd_slice(args) -> int:
    from observatory.about.figures import build_figures
    from observatory.pipeline.vertical_slice import SliceConfig, run

    rep = run(
        SliceConfig(
            provider=args.provider, offline=args.offline, cbo_code=args.cbo, onet_code=args.onet, esco_uri=args.esco
        )
    )
    build_figures()
    _print(
        {
            "run_id": rep.run_id,
            "sources": rep.sources,
            "scores": {k: v.get("scores") for k, v in rep.occupations.items() if isinstance(v, dict)},
            "warnings": rep.warnings,
        }
    )
    return 0


def cmd_coverage(args) -> int:
    from observatory.about.figures import build_figures
    from observatory.pipeline.coverage import run_coverage

    result = run_coverage(provider=args.provider, offline=args.offline)
    build_figures()
    print((get_settings().reports_dir / "coverage_latest.md").read_text(encoding="utf-8"))
    print(f"{len(result['sets'])} occupation sets assessed")
    return 0


def _annotation_tasks_path():
    return get_settings().validation_dir / "annotation_tasks_v0.1.0.json"


def cmd_prepare_annotation(args) -> int:
    """Blinded annotation tasks: draft pairs + the methodology model's top-k, shuffled, draft labels hidden."""
    import json

    from observatory.benchmark.metrics import load_benchmark
    from observatory.capabilities.dictionary import load_dictionary
    from observatory.embeddings.providers import Embedder, get_provider
    from observatory.exposure.dimensions import CapabilityIndex
    from observatory.methodology import load_methodology
    from observatory.validation.annotation import prepare_tasks

    s = get_settings()
    m = load_methodology()
    emb_cfg = m.config.get("embedding", {})
    embedder = Embedder(get_provider(args.provider or emb_cfg.get("provider", "baseline"), emb_cfg.get("revision")))
    index = CapabilityIndex(load_dictionary(s.capabilities_dir / m.capability_dictionary_file), embedder)
    _, items = load_benchmark(s.validation_dir / "benchmark_v0.1.0.jsonl")
    tasks = prepare_tasks(index, items, m.config["semantic_match"]["negative_penalty"], args.top_k)
    _annotation_tasks_path().write_text(json.dumps(tasks, indent=1, ensure_ascii=False), encoding="utf-8")
    _print(
        {
            "tasks": len(tasks["tasks"]),
            "pairs": sum(len(t["pairs"]) for t in tasks["tasks"]),
            "path": str(_annotation_tasks_path()),
        }
    )
    return 0


def cmd_annotation_agreement(args) -> int:
    from observatory.db.session import make_engine, session_factory
    from observatory.validation.annotation import agreement, load_tasks

    s = session_factory(make_engine(get_settings().database_url))()
    _print(agreement(s, load_tasks(_annotation_tasks_path())))
    return 0


def cmd_build_gold(args) -> int:
    """Gold labels go to data/validation/gold/ (outside the fingerprinted *.jsonl set): using them for calibration
    is a deliberate methodological change that requires a new methodology_version."""
    from observatory.db.session import make_engine, session_factory
    from observatory.validation.annotation import build_gold, load_tasks

    s = session_factory(make_engine(get_settings().database_url))()
    out = get_settings().validation_dir / "gold"
    out.mkdir(exist_ok=True)
    _print(build_gold(s, load_tasks(_annotation_tasks_path()), out / "benchmark_gold.jsonl", args.min_annotators))
    return 0


def cmd_build_annotation_page(args) -> int:
    """Write the self-contained claude.ai annotation page (no draft labels) to --out."""
    from pathlib import Path

    from observatory.capabilities.dictionary import load_dictionary
    from observatory.methodology import load_methodology
    from observatory.validation.annotation import load_tasks, render_page

    s = get_settings()
    m = load_methodology()
    d = load_dictionary(s.capabilities_dir / m.capability_dictionary_file)
    caps = {
        c.capability_id: {"name": c.name, "definition": c.definition, "examples": c.examples} for c in d.capabilities
    }
    out = Path(args.out)
    out.write_text(render_page(load_tasks(_annotation_tasks_path()), caps), encoding="utf-8")
    print(out)
    return 0


def cmd_import_annotations(args) -> int:
    """Import annotations exported from the claude.ai page (JSON: {user id: {"items": {...}}})."""
    import json
    from pathlib import Path

    from observatory.db.session import make_engine, session_factory
    from observatory.validation.annotation import import_remote, load_tasks

    s = session_factory(make_engine(get_settings().database_url))()
    summary = import_remote(s, load_tasks(_annotation_tasks_path()), json.loads(Path(args.file).read_text("utf-8")))
    s.commit()
    _print(summary)
    return 0


def cmd_methodology_status(args) -> int:
    from observatory.about.consistency import check_consistency

    problems = check_consistency()
    _print({"ok": not problems, "problems": problems})
    return 1 if problems else 0


def cmd_methodology_release(args) -> int:
    """Record the current fingerprint in the registry — only allowed when docs are consistent."""
    from observatory.about.consistency import check_consistency, write_fingerprint

    problems = [p for p in check_consistency() if "fingerprint" not in p]
    if problems:
        _print({"refused": True, "problems": problems})
        return 1
    _print({"released": write_fingerprint()})
    return 0


def cmd_data_dictionary(args) -> int:
    from observatory.db.dictionary import render_data_dictionary

    path = get_settings().docs_dir / "data-dictionary.md"
    path.write_text(render_data_dictionary(), encoding="utf-8")
    print(path)
    return 0


def cmd_validate_cbo(args) -> int:
    from observatory.connectors.cbo import CboFiles

    _print(CboFiles(get_settings().raw_data_dir / "cbo").validate())
    return 0


def cmd_download_onet(args) -> int:
    from observatory.connectors.onet import download

    print(download(args.version, get_settings().raw_data_dir / "onet" / args.version))
    return 0


def cmd_download_aei(args) -> int:
    from observatory.connectors.aei import download

    print(download(args.release, get_settings().raw_data_dir / "aei"))
    return 0


def cmd_figures(args) -> int:
    from observatory.about.figures import build_figures

    _print(build_figures())
    return 0


def cmd_benchmark_models(args) -> int:
    from datetime import UTC, datetime

    from observatory.benchmark.compare import compare
    from observatory.capabilities.dictionary import load_dictionary
    from observatory.methodology import load_methodology

    s = get_settings()
    m = load_methodology()
    out = s.experiments_dir / f"model-comparison-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    report = compare(
        args.providers,
        load_dictionary(s.capabilities_dir / m.capability_dictionary_file),
        s.validation_dir / "benchmark_v0.1.0.jsonl",
        m.config,
        out,
    )
    print((out / "comparison.md").read_text(encoding="utf-8"))
    print("chosen:", report["chosen"])
    return 0


def cmd_import_crosswalk(args) -> int:
    """Convert a manually downloaded official correspondence table to the canonical CSV the crosswalk reads."""
    import csv
    from pathlib import Path

    import pandas as pd

    src = Path(args.file)
    if src.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(src, sheet_name=args.sheet or 0, header=args.header_row, dtype=str)
    else:
        df = pd.read_csv(src, header=args.header_row, dtype=str, sep=None, engine="python")
    missing = [c for c in (args.from_col, args.to_col) if c not in df.columns]
    if missing:
        _print({"error": f"columns not found: {missing}", "available": list(df.columns)})
        return 1
    df = df.dropna(subset=[args.from_col, args.to_col])

    def norm(code: str, width: int | None, pad: int | None) -> str:
        code = code.strip().removesuffix(".0")  # Excel may store codes as numbers
        code = code.zfill(pad) if pad and code.isdigit() else code  # restore leading zeros (e.g. ISCO 0110)
        return code[:width] if width else code

    out = get_settings().raw_data_dir / "crosswalks" / f"{args.from_system}_to_{args.to_system}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["from_system", "from_code", "to_system", "to_code", "source"])
        for a, b in zip(df[args.from_col], df[args.to_col], strict=True):
            w.writerow(
                [
                    args.from_system,
                    norm(a, args.from_truncate, args.from_pad),
                    args.to_system,
                    norm(b, args.to_truncate, args.to_pad),
                    src.name,
                ]
            )
    _print({"written": str(out), "rows": len(df)})
    return 0


def cmd_import_cbo_books(args) -> int:
    """Extract family fields and the MTE family → CIUO 88 correspondence from the official CBO books (PDF)."""
    import csv
    import json
    from pathlib import Path

    from observatory.connectors.cbo_books import parse_books

    s = get_settings()
    paths = [Path(f) for f in args.files]
    records, hashes = parse_books(paths)
    out_cw = s.raw_data_dir / "crosswalks" / "CBO2002_to_ISCO88.csv"
    with open(out_cw, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["from_system", "from_code", "to_system", "to_code", "source"])
        for fam, rec in sorted(records.items()):
            for code in rec.ciuo88:
                w.writerow(["CBO2002", fam, "ISCO88", code, f"{rec.book} p.{rec.pages[0]}"])
    out_fam = s.raw_data_dir / "cbo" / "cbo_books_families.json"
    out_fam.write_text(
        json.dumps(
            {
                "source_files": hashes,
                "families": {
                    f: {"book": r.book, "pages": r.pages, "ciuo88": r.ciuo88, **r.fields}
                    for f, r in sorted(records.items())
                },
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    _print(
        {
            "families": len(records),
            "with_ciuo88": sum(1 for r in records.values() if r.ciuo88),
            "crosswalk": str(out_cw),
            "family_fields": str(out_fam),
        }
    )
    return 0


def cmd_admin_key(args) -> int:
    """Generate a strong admin key, store it in .env (UTF-8) and print it once."""
    import secrets

    from observatory.config import write_admin_key

    key = secrets.token_urlsafe(24)
    path = write_admin_key(key)
    print(f"Chave administrativa gravada em {path}")
    print(f"Chave: {key}")
    print("Guarde-a: ela é pedida no formulário de revisão. Reinicie o servidor para aplicar.")
    return 0


def cmd_serve(args) -> int:
    import uvicorn

    uvicorn.run("observatory.api.app:app", host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252
    p = argparse.ArgumentParser(prog="observatory")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("slice", help="run the vertical slice end to end")
    s.add_argument("--provider", default=None, help="override the methodology embedding provider")
    s.add_argument("--offline", action="store_true", help="use cached ESCO responses only")
    s.add_argument("--cbo", default="212405")
    s.add_argument("--onet", default="15-1252.00")
    s.add_argument("--esco", default="http://data.europa.eu/esco/occupation/f2b15a0e-e65a-438a-affb-29b9d50b77d1")
    s.set_defaults(fn=cmd_slice)
    cv = sub.add_parser("coverage", help="run the slice for the default occupation sets and compare them")
    cv.add_argument("--provider", default=None)
    cv.add_argument("--offline", action="store_true")
    cv.set_defaults(fn=cmd_coverage)
    pa = sub.add_parser("prepare-annotation", help="build blinded annotation tasks for the benchmark")
    pa.add_argument("--provider", default=None)
    pa.add_argument("--top-k", type=int, default=3)
    pa.set_defaults(fn=cmd_prepare_annotation)
    sub.add_parser("annotation-agreement", help="inter-annotator agreement").set_defaults(fn=cmd_annotation_agreement)
    bg = sub.add_parser("build-gold", help="export human consensus labels")
    bg.add_argument("--min-annotators", type=int, default=2)
    bg.set_defaults(fn=cmd_build_gold)
    bp = sub.add_parser("build-annotation-page", help="write the claude.ai annotation page")
    bp.add_argument("--out", required=True)
    bp.set_defaults(fn=cmd_build_annotation_page)
    ia = sub.add_parser("import-annotations", help="import annotations exported from the claude.ai page")
    ia.add_argument("--file", required=True)
    ia.set_defaults(fn=cmd_import_annotations)
    sub.add_parser("methodology-status").set_defaults(fn=cmd_methodology_status)
    sub.add_parser("methodology-release").set_defaults(fn=cmd_methodology_release)
    sub.add_parser("data-dictionary").set_defaults(fn=cmd_data_dictionary)
    sub.add_parser("validate-cbo").set_defaults(fn=cmd_validate_cbo)
    sub.add_parser("figures").set_defaults(fn=cmd_figures)
    d = sub.add_parser("download-onet")
    d.add_argument("--version", default="31.0")
    d.set_defaults(fn=cmd_download_onet)
    a = sub.add_parser("download-aei")
    a.add_argument("--release", default="release_2025_03_27")
    a.set_defaults(fn=cmd_download_aei)
    bm = sub.add_parser("benchmark-models", help="compare embedding providers on the domain benchmark")
    bm.add_argument(
        "--providers",
        nargs="+",
        default=[
            "baseline",
            "sentence-transformers:sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            "sentence-transformers:intfloat/multilingual-e5-large",
            "sentence-transformers:BAAI/bge-m3",
        ],
    )
    bm.set_defaults(fn=cmd_benchmark_models)
    ic = sub.add_parser("import-crosswalk", help="convert an official correspondence table to the canonical CSV")
    ic.add_argument("--file", required=True)
    ic.add_argument("--from-system", required=True, help="e.g. ISCO08, CBO2002, SOC2010")
    ic.add_argument("--from-col", required=True)
    ic.add_argument("--to-system", required=True, help="e.g. SOC2018, ISCO88")
    ic.add_argument("--to-col", required=True)
    ic.add_argument("--header-row", type=int, default=0)
    ic.add_argument("--sheet", default=None, help="worksheet name (Excel files)")
    ic.add_argument("--from-truncate", type=int, default=None, help="keep only the first N characters of from codes")
    ic.add_argument("--to-truncate", type=int, default=None, help="keep only the first N characters of to codes")
    ic.add_argument("--from-pad", type=int, default=None, help="left-pad numeric from codes with zeros to N digits")
    ic.add_argument("--to-pad", type=int, default=None, help="left-pad numeric to codes with zeros to N digits")
    ic.set_defaults(fn=cmd_import_crosswalk)
    cb = sub.add_parser("import-cbo-books", help="parse the official CBO books (PDF) for CIUO 88 links and fields")
    cb.add_argument("files", nargs="+", help="e.g. data/raw/crosswalks/livro-1-portal-cbo.pdf cbo2002_liv2.pdf")
    cb.set_defaults(fn=cmd_import_cbo_books)
    sub.add_parser("admin-key", help="generate the admin key used to record reviews").set_defaults(fn=cmd_admin_key)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
