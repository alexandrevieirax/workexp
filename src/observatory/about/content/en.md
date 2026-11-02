---
methodology_version: 0.2.0
language: en
---

## 1. Purpose {#objetivo}

The observatory estimates, in an explainable and auditable way, **how far the tasks** that make up CBO, ESCO
and O*NET occupations correspond to current AI capabilities, and what that implies for professional profiles
and curricula. It supports educational planning and research; it does **not** assess individuals.

## 2. Definition of AI exposure {#definicao}

Exposure is the degree to which a task's content matches demonstrated AI capabilities, combined with evidence
of observed usage and technology maturity [@eloundou2024gpts; @felten2021occupational]. We distinguish potential
exposure, observed exposure [@handa2025which], automation, augmentation and transformation.

## 3. What the index measures {#mede}

{{indices_table}}

## 4. What the index does not measure {#nao-mede}

- Unemployment risk, worker replacement or disappearance of occupations.
- Actual adoption by organizations.
- Individual competence or employability.
- Skill obsolescence; highly exposed tasks may require **more** training [@dellacqua2023navigating].
- Causality [@acemoglu2025simple].

## 5. Conceptual architecture {#arquitetura}

The unit of analysis is the **task** [@autor2003skill; @acemoglu2011skills].

{{figure:flow}}

{{figure:relation}}

{{figure:er}}

## 6. Data sources {#fontes}

{{sources_table}}

## 7. Harmonization {#harmonizacao}

No mapping is auto-accepted in the current version; titles alone weigh only 20%.

{{crosswalk_weights}}

{{figure:crosswalk}}

## 8. AI capability dictionary {#dicionario}

{{capability_summary}}

## 9. Embedding model {#embeddings}

{{embedding_summary}}

Generic leaderboards do not replace the domain benchmark [@muennighoff2023mteb]. Version 0.2.0 compared the
lexical baseline, paraphrase-multilingual-mpnet-base-v2 [@reimers2020making], multilingual-E5-large
[@wang2024multilingual] and BGE-M3 [@chen2024bge] under a selection rule fixed before the results (ADR 0002).

## 10. Formulas {#formulas}

{{formulas}}

{{figure:calculation}}

{{figure:automation_augmentation}}

## 11. Validation {#validacao}

Semantic, construct and predictive validation [@cohen1960coefficient; @krippendorff2018content;
@felten2021occupational; @eloundou2024gpts; @webb2020impact; @autor2013growth].

{{benchmark_summary}}

## 12. Uncertainty {#incertezas}

{{uncertainty_weights}}

{{figure:uncertainty}}

{{figure:sensitivity}}

## 13. Limitations {#limitacoes}

Uncalibrated weights; lexical baseline embeddings; unreviewed capability priors; single-platform observed
usage; uniform weights for ESCO/CBO; CBO activities defined per occupational family.

## 14. Ethics {#etica}

No individual scoring, no layoff recommendations, no sensitive attributes, uncertainty always shown
[@mitchell2019model; @gebru2021datasheets].

## 15. Curriculum application {#curricular}

Phase 8. No competency is ever removed automatically.

{{figure:curriculum}}

## 16. Version history {#versoes}

{{changelog}}

## 17. References {#referencias}

{{references}}

## 18. Glossary {#glossario}

- **Task**, **AI capability**, **prior**, **crosswalk**, **methodological fingerprint** — see the pt-BR glossary.

## 19. Licenses {#licencas}

{{licenses}}

## 20. Contribution and contestation {#contestacao}

Open an issue with occupation/task, methodology version, evidence and rationale (see `CONTRIBUTING.md`).
