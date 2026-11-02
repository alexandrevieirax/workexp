# Estrutura proposta do repositório (todas as fases)

Itens marcados ✅ existem; ⏳ são planejados para a fase indicada.

```
.
├── .github/workflows/ci.yml           ✅ pytest em cada push/PR
├── .pre-commit-config.yaml            ✅ ruff + higiene
├── alembic.ini, migrations/           ✅ esquema inicial (0001)
├── config/methodology/                ✅ YAML, léxico, registro
├── data/
│   ├── capabilities/                  ✅ dicionário v0.1.0
│   ├── validation/                    ✅ benchmark v0.1.0 (rascunho)  ⏳ F6 conjunto ouro anotado
│   └── raw/{onet,esco,cbo,aei,crosswalks}/   (não versionado)
├── docs/
│   ├── adr/                           ✅ 0001  ⏳ uma ADR por decisão relevante
│   ├── reports/                       ✅ relatórios de execução
│   └── ...                            ✅ metodologia, fontes, riscos, cards, changelog, referências
├── src/observatory/
│   ├── connectors/                    ✅ O*NET, ESCO API, CBO, AEI  ⏳ F1 ESCO CSV em massa, tábua CBO↔ISCO
│   ├── db/                            ✅
│   ├── normalization/                 ✅
│   ├── crosswalk/                     ✅ composto  ⏳ F2 busca de candidatos top-N, split/merge na UI
│   ├── embeddings/                    ✅  ⏳ F4 avaliação e5/BGE-M3, índices HNSW por modelo
│   ├── capabilities/                  ✅  ⏳ F3 painel de revisão dos priors
│   ├── exposure/                      ✅  ⏳ F6 calibração, validação de construto (AIOE, GPT, RTI)
│   ├── benchmark/                     ✅  ⏳ F6 κ/α de concordância, estabilidade temporal
│   ├── curriculum/                    ⏳ F8 extração (PDF/DOCX/XLSX/CSV), ligação, índices, recomendações
│   ├── orchestration/                 ⏳ F9 Prefect/Dagster
│   ├── about/                         ✅
│   ├── api/                           ✅  ⏳ F7 autenticação, papéis, exportações PDF/DOCX/XLSX
│   └── pipeline/                      ✅ fatia vertical
├── frontend/                          ⏳ F7 Next.js + TypeScript + Tailwind + i18n + Playwright
└── tests/                             ✅
```
