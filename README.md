# AI Occupational and Curriculum Exposure Observatory

Sistema auditável para estimar a **exposição das tarefas** de ocupações (CBO, ESCO, O*NET) a capacidades de
inteligência artificial, separando **exposição potencial, uso observado, automação, aumento de capacidade e
transformação**, com incerteza explícita e rastreabilidade até fonte, versão, modelo e commit.

> Exposição à IA **não** significa substituição de trabalhadores, desaparecimento da profissão, automação
> integral, risco de desemprego nem obsolescência de competências. A metodologia 0.2.0 **não está calibrada**.

Estado: **fase 0–1 + fatia vertical** (ver [relatório da primeira execução](docs/reports/2026-11-02-first-execution.md)).

## Início rápido (sem Docker, SQLite)

```bash
pip install -e ".[dev,ml]"
```

O extra `ml` instala PyTorch e Sentence Transformers; o modelo de embeddings da metodologia (~1 GB) é baixado
na primeira execução. Sem ele, use `slice --provider baseline` (os resultados são marcados como não oficiais).

```bash
python -m observatory.cli download-onet --version 31.0
```

```bash
python -m observatory.cli download-aei --release release_2025_03_27
```

```bash
python -m observatory.cli slice
```

```bash
python -m observatory.cli serve
```

Para avaliar os quatro conjuntos de comparação (desenvolvimento, contabilidade, eletricista, técnico de
enfermagem) e gerar `artifacts/reports/coverage_latest.md`:

```bash
python -m observatory.cli coverage
```

Abra http://127.0.0.1:8000 (ocupações), `/occupations/{id}` (página da ocupação) e `/about` (área "Sobre").
A CBO exige download manual (reCAPTCHA) — veja [docs/data-sources.md](docs/data-sources.md).

## Configuração padrão (PostgreSQL + pgvector)

```bash
docker compose up -d db
```

```bash
alembic upgrade head
```

Defina `OBS_DATABASE_URL` (ver `.env.example`). O tipo `VectorType` usa `pgvector` no PostgreSQL e JSON no SQLite.

## Modelos de embeddings

O modelo faz parte da metodologia (`embedding.provider` e `embedding.revision` no YAML). Na 0.2.0 é
`paraphrase-multilingual-mpnet-base-v2` (snapshot fixado), escolhido entre quatro candidatos por uma regra
registrada antes dos resultados ([ADR 0002](docs/adr/0002-embedding-model-selection.md)). Para repetir a
comparação:

```bash
python -m observatory.cli benchmark-models
```

A linha de base lexical offline (`--provider baseline`) continua disponível para testes e ambientes sem ML.

## Revisão humana dos crosswalks

A página `/crosswalks` lista, para cada ocupação ESCO/CBO, os candidatos O*NET ranqueados, com os cinco
componentes, os votos das fontes oficiais (e divergências), o histórico e um formulário para **aceitar** ou
**rejeitar** com justificativa. As decisões ficam no histórico do mapeamento, em `expert_review` e no log de
auditoria. Nas execuções seguintes, um candidato aceito define a ocupação O*NET de onde vêm os priors E6–E10 e
um rejeitado sai do ranking.

A revisão exige uma chave administrativa. Gere-a com o comando abaixo, que grava `OBS_ADMIN_API_KEY` no
arquivo `.env` (local, não versionado, UTF-8) e mostra a chave uma vez; depois reinicie o servidor:

```bash
python -m observatory.cli admin-key
```

Não use `echo ... >> .env` no PowerShell: ele grava o arquivo em UTF-16. O sistema agora lê esse formato, mas
o comando acima é o caminho recomendado. Valores de exemplo ou chaves com menos de 16 caracteres são recusados.

## Anotação humana do benchmark

A página `/annotations` permite que especialistas rotulem os 265 pares tarefa ↔ capacidade de IA do
benchmark: são 36 tarefas, uma por tela. Os pares incluem os do rascunho e as 3 capacidades que o modelo
considera mais próximas. A anotação é **cega** (sem a sugestão do sistema, ordem embaralhada) e usa só o nome
de quem anota. Para gerar as tarefas, ver a concordância e exportar o conjunto ouro:

```bash
python -m observatory.cli prepare-annotation
```

```bash
python -m observatory.cli annotation-agreement
```

```bash
python -m observatory.cli build-gold
```

**Anotação remota (claude.ai).** Para especialistas fora da sua máquina, a mesma anotação existe como uma
página do claude.ai, sem servidor:

```bash
python -m observatory.cli build-annotation-page --out anotacao-benchmark.html
```

A página publicada tem as seguintes regras:

- cada especialista grava só as próprias respostas (`annotations/<id>`), e ninguém, nem o dono, pode alterá-las;
- só o dono lê todas as respostas;
- o rascunho da IA não vai para a página.

Os especialistas precisam de conta no claude.ai e de um convite **por e-mail como Editor**, e a página não pode
estar compartilhada por link público. Depois, exporte os documentos de `annotations` para um JSON
`{id: {"items": ...}}` e importe-os com o comando abaixo. Cada pessoa vira "claude.ai anotador N", na mesma
ordem do painel do dono.

```bash
python -m observatory.cli import-annotations --file respostas.json
```

`/annotations/agreement` mostra o kappa de Cohen ponderado por par de anotadores, o alfa de Krippendorff do grupo
e a comparação de cada pessoa com o rascunho da IA. O conjunto ouro (mediana de pelo menos 2 anotadores) vai
para `data/validation/gold/`, fora do fingerprint: usá-lo na calibração é uma mudança metodológica deliberada,
que exige nova versão.

## Governança metodológica

Pesos, limiares e listas de elementos ficam em [`config/methodology/`](config/methodology/). Qualquer mudança
em fórmulas, pesos, léxico ou dicionário de capacidades altera o *fingerprint*; o pipeline se recusa a rodar e
`tests/test_about_consistency.py` falha até que versão, changelog, área "Sobre" e referências sejam atualizados.

```bash
python -m observatory.cli methodology-status
```

## Estrutura do repositório

```
config/methodology/      YAML da metodologia, léxico, registro de versões (fingerprint)
data/capabilities/       Dicionário versionado de capacidades de IA
data/validation/         Benchmark do domínio (rótulos rascunho, não ouro)
data/raw/                Fontes oficiais baixadas (não versionadas)
docs/                    Fundamentos, metodologia, fontes, riscos, ADRs, model/data cards, changelog, referências
migrations/              Alembic
src/observatory/
  connectors/            O*NET, ESCO (API), CBO (arquivo), Anthropic Economic Index
  db/                    Modelo SQLAlchemy com proveniência, dicionário de dados gerado
  normalization/         Texto e escalas (uma escala por vez, nunca somadas brutas)
  embeddings/            Provedores (linha de base, Sentence Transformers, API externa) + cache
  capabilities/          Carga/validação do dicionário + detecção de vazamento
  crosswalk/             Crosswalk composto com nulo empírico; sem aceitação automática
  exposure/              Dimensões E1–E14, fórmulas, pesos, Monte Carlo, sensibilidade
  benchmark/             Métricas (P@k, R@k, MAP, nDCG, Spearman, FPR/FNR)
  methodology/           Registro e fingerprint
  about/                 Conteúdo "Sobre" (pt-BR, en), renderização dinâmica, figuras, consistência
  api/                   FastAPI (JSON + HTML acessível)
  pipeline/              Ingestão e fatia vertical
tests/                   pytest (fixtures sintéticas marcadas)
frontend/                Next.js (fase 7) — ver frontend/README.md
```

Planejamento das próximas fases: [docs/repository-structure.md](docs/repository-structure.md).

## Documentação

[Fundamentos](docs/research-foundations.md) · [Metodologia v0](docs/methodology-v0.md) ·
[Fontes](docs/data-sources.md) · [Dicionário de dados](docs/data-dictionary.md) ·
[Riscos](docs/risk-register.md) · [ADR 0001](docs/adr/0001-system-architecture.md) ·
[Model card](docs/model-card.md) · [Data cards](docs/data-cards.md) ·
[Changelog metodológico](docs/CHANGELOG-methodology.md) · [Contribuição](CONTRIBUTING.md)

## Licença

Código: Apache-2.0. Dados: licença de cada fonte (ver área "Sobre" → Licenças).
