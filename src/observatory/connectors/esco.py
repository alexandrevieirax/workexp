"""ESCO Web Service API connector with raw-response cache (incremental/consultation use).

Bulk loading should use the official CSV package (see docs/data-sources.md); not implemented in v0.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from observatory.connectors.base import ParsedOccupation, ParsedTask, SourceDescriptor, is_marked_synthetic
from observatory.normalization.text import split_gendered_title
from observatory.provenance import sha256_text

API = "https://ec.europa.eu/esco/api"
# ISCO-08 major group -> skill level (1..4) rescaled to 0-1; group 1 spans levels 3-4, group 0 is undefined.
ISCO_SKILL_LEVEL = {
    "1": 5 / 6,
    "2": 1.0,
    "3": 2 / 3,
    "4": 1 / 3,
    "5": 1 / 3,
    "6": 1 / 3,
    "7": 1 / 3,
    "8": 1 / 3,
    "9": 0.0,
}
SKILL_TYPES_AS_TASKS = {"http://data.europa.eu/esco/skill-type/skill"}


class EscoClient:
    def __init__(
        self,
        cache_dir: Path,
        client: httpx.Client | None = None,
        offline: bool = False,
        selected_version: str | None = None,
    ):
        self.cache_dir = cache_dir / "api"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = client
        self.offline = offline
        self.selected_version = selected_version
        self.retrievals: list[dict[str, Any]] = []
        self.is_synthetic = is_marked_synthetic(cache_dir)

    def _get(self, path: str, params: dict[str, str]) -> dict:
        if self.selected_version:
            params = {**params, "selectedVersion": self.selected_version}
        url = f"{API}/{path}?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        key = hashlib.sha1(url.encode()).hexdigest()
        cached = self.cache_dir / f"{key}.json"
        if cached.exists():
            envelope = json.loads(cached.read_text(encoding="utf-8"))
        else:
            if self.offline:
                raise FileNotFoundError(f"ESCO response not cached and offline mode is on: {url}")
            client = self.client or httpx.Client(timeout=60, follow_redirects=True)
            resp = client.get(f"{API}/{path}", params=params)
            resp.raise_for_status()
            body = resp.text
            envelope = {
                "url": url,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "sha256": sha256_text(body),
                "body": json.loads(body),
            }
            cached.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
        self.retrievals.append({k: envelope[k] for k in ("url", "retrieved_at", "sha256")})
        return envelope["body"]

    def search_occupations(self, text: str, language: str = "en", limit: int = 10) -> list[dict]:
        body = self._get("search", {"text": text, "type": "occupation", "language": language, "limit": str(limit)})
        return body.get("_embedded", {}).get("results", [])

    def occupation_raw(self, uri: str, language: str) -> dict:
        return self._get("resource/occupation", {"uri": uri, "language": language})

    def skill_raw(self, uri: str, language: str = "en") -> dict:
        return self._get("resource/skill", {"uri": uri, "language": language})

    def descriptor(self) -> SourceDescriptor:
        last = self.retrievals[-1] if self.retrievals else {}
        return SourceDescriptor(
            dataset_code="ESCO",
            dataset_name="ESCO",
            publisher="European Commission",
            homepage="https://esco.ec.europa.eu",
            version=self.selected_version or "api-default",
            source_url=API,
            retrieval_method="api",
            file_sha256=sha256_text(json.dumps(sorted(r["sha256"] for r in self.retrievals)))
            if self.retrievals
            else None,
            license_name="ESCO terms of use (CC BY 4.0 per EU reuse policy — confirm)",
            license_url="https://esco.ec.europa.eu/en/about-esco/data-science-and-esco/esco-data-terms-use",
            notes=f"{len(self.retrievals)} API responses cached; last at {last.get('retrieved_at')}",
            is_synthetic=self.is_synthetic,
        )


def _label(obj: dict, key: str, lang: str) -> Any:
    v = obj.get(key) or {}
    return v.get(lang)


def parse_occupation(raw_en: dict, raw_pt: dict | None = None, is_synthetic: bool = False) -> ParsedOccupation:
    isco, isco_method = None, None
    for link in raw_en.get("_links", {}).get("broaderIscoGroup", []):
        isco, isco_method = link.get("code") or isco, "broaderIscoGroup"
    code = raw_en.get("code") or ""
    if isco is None and code[:4].isdigit():
        # Narrower ESCO occupations link to a broader occupation, not to ISCO. By ESCO's coding convention the
        # first four digits of the occupation code are its ISCO-08 unit group (e.g. 5321.1.1 → 5321).
        isco, isco_method = code[:4], "esco_code_prefix"
    desc_en = (_label(raw_en, "description", "en") or {}).get("literal")
    aliases: list[tuple[str, str, str]] = [(raw_en["preferredLabel"]["en"], "en", "preferred")]
    aliases += [(a, "en", "alternative") for a in (_label(raw_en, "alternativeLabel", "en") or [])]
    pt_label = (raw_en.get("preferredLabel") or {}).get("pt")
    if pt_label:
        aliases += [(p, "pt", "preferred") for p in split_gendered_title(pt_label)]
    aliases += [(a, "pt", "alternative") for a in (_label(raw_en, "alternativeLabel", "pt") or [])]
    return ParsedOccupation(
        taxonomy="ESCO",
        code=raw_en["uri"],
        title=raw_en["preferredLabel"]["en"],
        description=desc_en,
        language="en",
        group_code=isco,
        qualification_level=ISCO_SKILL_LEVEL.get(isco[0]) if isco else None,
        aliases=list(dict.fromkeys(aliases)),
        attributes={
            "esco_code": raw_en.get("code"),
            "isco_group": isco,
            "isco_group_method": isco_method,
            "title_pt": pt_label,
            "description_pt": ((_label(raw_en, "description", "pt") or {}).get("literal")),
            "regulated_profession_note": raw_en.get("_links", {}).get("regulatedProfessionNote", {}).get("uri"),
            "status": raw_en.get("status"),
        },
        is_synthetic=is_synthetic,
    )


def parse_skills(raw_en: dict, raw_pt: dict | None = None) -> list[dict]:
    """Essential + optional skills with their ESCO skill type and labels in en/pt."""
    pt_titles = {}
    if raw_pt:
        for rel in ("hasEssentialSkill", "hasOptionalSkill"):
            for s in raw_pt.get("_links", {}).get(rel, []):
                pt_titles[s["uri"]] = s["title"]
    out = []
    for rel, relation in (("hasEssentialSkill", "essential"), ("hasOptionalSkill", "optional")):
        for s in raw_en.get("_links", {}).get(rel, []):
            out.append(
                {
                    "uri": s["uri"],
                    "title_en": s["title"],
                    "title_pt": pt_titles.get(s["uri"]),
                    "skill_type": s.get("skillType"),
                    "relation": relation,
                }
            )
    return out


def skills_as_tasks(skills: list[dict]) -> list[ParsedTask]:
    """ESCO has no task statements; essential skills of type 'skill/competence' are used as task-like units."""
    return [
        ParsedTask(
            original_id=s["uri"],
            statement=s["title_en"],
            language="en",
            unit_type="esco_skill",
            task_type=s["relation"],
            attributes={"title_pt": s["title_pt"], "skill_type": s["skill_type"]},
        )
        for s in skills
        if s["relation"] == "essential" and s["skill_type"] in SKILL_TYPES_AS_TASKS
    ]
