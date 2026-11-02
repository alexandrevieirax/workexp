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
        df = pd.read_excel(src, header=args.header_row, dtype=str)
    else:
        df = pd.read_csv(src, header=args.header_row, dtype=str, sep=None, engine="python")
    missing = [c for c in (args.from_col, args.to_col) if c not in df.columns]
    if missing:
        _print({"error": f"columns not found: {missing}", "available": list(df.columns)})
        return 1
    df = df.dropna(subset=[args.from_col, args.to_col])
    out = get_settings().raw_data_dir / "crosswalks" / f"{args.from_system}_to_{args.to_system}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["from_system", "from_code", "to_system", "to_code", "source"])
        for a, b in zip(df[args.from_col], df[args.to_col], strict=True):
            w.writerow([args.from_system, a.strip(), args.to_system, b.strip(), src.name])
    _print({"written": str(out), "rows": len(df)})
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
    ic.set_defaults(fn=cmd_import_crosswalk)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
