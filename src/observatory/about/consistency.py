"""Governance check: a methodological change must update version, changelog, "Sobre" and references together."""

from __future__ import annotations

import json
import re

from observatory.about.render import LANGUAGES, cited_keys, load_content, references, section_ids
from observatory.capabilities.dictionary import load_dictionary
from observatory.config import get_settings
from observatory.methodology import load_methodology, load_registry, registry_path

REQUIRED_SECTIONS = 20


def check_consistency() -> list[str]:
    problems: list[str] = []
    m = load_methodology()
    reg = load_registry()
    entry = next(v for v in reg["versions"] if v["version"] == m.version)
    if entry["fingerprint"] != m.fingerprint:
        problems.append(
            f"fingerprint: methodology files changed (registry {entry['fingerprint'][:12]} ≠ computed "
            f"{m.fingerprint[:12]}). Create a new methodology_version, add a changelog section, update the 'Sobre' "
            "front matter and references, then run `python -m observatory.cli methodology-release`."
        )
    changelog = (get_settings().docs_dir / "CHANGELOG-methodology.md").read_text(encoding="utf-8")
    if not re.search(rf"^## \[{re.escape(m.version)}\]", changelog, re.M):
        problems.append(f"changelog: no section '## [{m.version}]' in docs/CHANGELOG-methodology.md")
    refs = references()
    ids_by_lang = {}
    for lang in LANGUAGES:
        fm, body = load_content(lang)
        if str(fm.get("methodology_version")) != m.version:
            problems.append(f"about[{lang}]: methodology_version {fm.get('methodology_version')} ≠ {m.version}")
        ids_by_lang[lang] = section_ids(body)
        if len(ids_by_lang[lang]) != REQUIRED_SECTIONS:
            problems.append(f"about[{lang}]: {len(ids_by_lang[lang])} sections, expected {REQUIRED_SECTIONS}")
        for k in cited_keys(body) - refs.keys():
            problems.append(f"references: about[{lang}] cites unknown key '{k}'")
    if len(set(map(tuple, ids_by_lang.values()))) > 1:
        problems.append("i18n: section anchors differ between languages")
    for k in set(m.config.get("references", [])) - refs.keys():
        problems.append(f"references: methodology YAML cites unknown key '{k}'")
    d = load_dictionary(get_settings().capabilities_dir / m.capability_dictionary_file)
    for c in d.capabilities:
        for k in set(c.references) - refs.keys():
            problems.append(f"references: capability {c.capability_id} cites unknown key '{k}'")
    return problems


def write_fingerprint() -> dict:
    m = load_methodology()
    reg = load_registry()
    for v in reg["versions"]:
        if v["version"] == m.version:
            if v["fingerprint"] not in ("PENDING", m.fingerprint) and v.get("status") == "released":
                raise RuntimeError("released versions are immutable; create a new version")
            v["fingerprint"] = m.fingerprint
    registry_path().write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"version": m.version, "fingerprint": m.fingerprint}
