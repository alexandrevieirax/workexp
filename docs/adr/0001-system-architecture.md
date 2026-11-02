# ADR 0001 — Arquitetura do sistema

- **Status:** aceito (v0, revisável)
- **Data:** 2026-11-02

## Contexto

O sistema precisa ser auditável (proveniência até fonte/versão/modelo/commit),
executar sem API paga, e evoluir por fases. O ambiente de desenvolvimento
inicial (Windows, Python 3.14) não possui Docker, PostgreSQL nem PyTorch.

## Decisões

1. **Monorepo Python** com pacote `observatory` em `src/`, organizado por
   domínio: `connectors`, `db`, `normalization`, `embeddings`, `capabilities`,
   `crosswalk`, `exposure`, `benchmark`, `methodology`, `about`, `api`, `pipeline`.
2. **PostgreSQL 16 + pgvector** é o banco padrão (`docker-compose.yml`).
   **SQLite** é suportado para testes e desenvolvimento local; o tipo
   `VectorType` usa `pgvector.Vector` no PostgreSQL e JSON no SQLite.
3. **Alembic** para migrações; a migração inicial cria a extensão `vector`
   quando o dialeto é PostgreSQL.
4. **Armazenamentos separados** (configuráveis em `observatory.config`):
   banco transacional (`DATABASE_URL`), documentos brutos (`data/raw`),
   embeddings em tabela própria (`embedding`), artefatos de modelos
   (`artifacts/models`), logs (`logs/`), experimentos (`artifacts/experiments`,
   formato compatível com MLflow file store — MLflow é opcional).
5. **Metodologia como dados**: pesos, limiares e listas de elementos ficam em
   YAML versionado (`config/methodology/`). O código lê o YAML; a área "Sobre"
   também. Uma impressão digital (SHA-256 do YAML + módulo de fórmulas +
   dicionário de capacidades) amarra a versão.
6. **Provedores de embeddings por interface** (`EmbeddingProvider`). Linha de
   base offline determinística (`char-ngram-hashing`) para o MVP sem
   downloads; `SentenceTransformerProvider` opcional (`pip install .[ml]`).
7. **Frontend:** a fatia vertical usa páginas HTML renderizadas pelo FastAPI
   (sem dependências JS além de Mermaid via CDN para diagramas). O frontend
   Next.js + TypeScript (fase 7) consumirá a mesma API JSON `/api/*`, que é o
   contrato estável. Motivo: entregar a fatia testável sem `npm install` e sem
   duplicar lógica.
8. **Orquestração:** a fatia usa um pipeline Python simples e idempotente
   (`observatory.pipeline`). Prefect/Dagster entram na fase 9 envolvendo as
   mesmas funções.
9. **Sem aceitação automática de crosswalk** na v0.

## Consequências

- Testes rodam em SQLite em memória, sem serviços externos.
- Recursos específicos do PostgreSQL (índices HNSW por modelo) são criados
  apenas no PostgreSQL e documentados.
- Similaridades do modelo de linha de base são lexicais; a interface exibe
  esse fato e a incerteza aumenta. Antes de conclusões substantivas, avaliar
  multilingual-e5-large/BGE-M3 no benchmark.

## Alternativas consideradas

- Next.js já na fatia: adiado (custo de build, sem ganho para validar o motor).
- Somente SQLite: rejeitado como padrão (sem busca vetorial escalável).
- LLM para pontuar tarefas: rejeitado como fonte única (princípio 1.6);
  poderá ser um avaliador adicional comparado ao conjunto ouro.
