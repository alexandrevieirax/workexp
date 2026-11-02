# Relatório — primeira execução (fase 0, fase 1 e fatia vertical)

Data: 2026-11-02 · Metodologia 0.1.0 (`uncalibrated`) · Run `20261102T155405Z-a9fc3d`
· Testes: **65 aprovados, 1 pulado** (análise curricular, fase 8) · `ruff check`: sem erros.

## 1. O que foi implementado

| Item do pedido | Situação | Onde |
|---|---|---|
| Inspeção do repositório | Pasta vazia; nada removido | — |
| research-foundations, methodology-v0, data-sources, risk-register, ADR 0001 | ✅ | `docs/` |
| Estrutura do repositório | ✅ proposta para todas as fases | `docs/repository-structure.md` |
| Esquema inicial do banco | ✅ 34 tabelas, proveniência em todo registro transformado, migração Alembic 0001 (cria `vector` no PostgreSQL) | `src/observatory/db/`, `migrations/` |
| Data dictionary | ✅ gerado do código; teste falha se ficar defasado | `docs/data-dictionary.md` |
| Dicionário de capacidades de IA | ✅ 10 famílias (A–J), 78 capacidades, priors marcados como não revisados | `data/capabilities/ai_capabilities_v0.1.0.yaml` |
| Conectores | ✅ O*NET (download), ESCO (API + cache), CBO (arquivo manual + validação de esquema), Anthropic Economic Index | `src/observatory/connectors/` |
| Embeddings | ✅ camada agnóstica, cache versionado (modelo, parâmetros, idioma, tipo, hash), persistência em `embedding` | `src/observatory/embeddings/` |
| Benchmark | ✅ 36 pares tarefa–capacidade (en/pt) + 10 pares de ocupações; P@k, R@k, MAP, nDCG, Spearman, FPR/FNR, por idioma e por grupo | `data/validation/`, `src/observatory/benchmark/` |
| Crosswalk | ✅ composto (5 componentes), nulo empírico, histórico, revisão humana via API | `src/observatory/crosswalk/` |
| Motor de exposição | ✅ E1–E14, 4 saídas, 8 classes, pesos α/β/γ, Monte Carlo, sensibilidade | `src/observatory/exposure/` |
| Página da ocupação | ✅ tarefas, pesos, classes, confiança, justificativa, capacidades, evidências, barreiras, E1–E14 com origem, crosswalks, proveniência, histórico | `/occupations/{id}` |
| Área "Sobre" | ✅ 20 seções (pt-BR e en), números lidos do YAML, 9 figuras versionadas com legenda e texto alternativo | `/about` |
| Governança metodológica | ✅ fingerprint; pipeline se recusa a rodar e testes falham se versão/changelog/"Sobre"/referências não acompanham a mudança | `config/methodology/registry.json` |

## 2. Fatia vertical — resultados reais

Ocupação: **Software Developers** (O*NET 15-1252.00, O*NET 31.0) e **software developer** (ESCO,
ISCO 2512). Equivalente CBO previsto: **2124-05** — *não carregado* (ver §4).

| Base | OAE | OAP | OAuP | OTP | E14 médio | Classes (peso) |
|---|---|---|---|---|---|---|
| O*NET | 0,75 [0,69–0,78] | 0,07 [0,05–0,09] | 0,46 [0,38–0,48] | 0,33 [0,27–0,36] | 0,48 | aumento 64%, transformação significativa 36% |
| ESCO | 0,78 [0,67–0,80] | 0,05 [0,02–0,08] | 0,30 [0,19–0,35] | 0,22 [0,14–0,26] | 1,00 | evidência insuficiente 100% |

Intervalos de 90% por Monte Carlo (1000 sorteios, semente fixa); execuções repetidas dão resultados idênticos.

Leitura correta: o padrão dominante nas tarefas de desenvolvimento é **aumento de capacidade**, não automação
(OAP baixo por exigência de julgamento, interação e responsabilidade). O **nível** do OAE **não deve ser
interpretado**: com o modelo lexical de linha de base, a similaridade calibrada satura (teto de calibração 0,234).

Uso observado: 10 das 17 tarefas O*NET ligadas ao Anthropic Economic Index (5 por correspondência aproximada,
porque a release usa a taxonomia SOC 2010).

Crosswalk ESCO → O*NET: `mapping_confidence` = **0,42** (não aceito automaticamente). As tarefas da ESCO
são mais parecidas com as do O*NET do que com as de 40 ocupações aleatórias (posição 1,0 na distribuição
nula), mas o modelo lexical não sustenta equivalência forte; por isso os priors do O*NET **não** foram
transferidos à ESCO e a incerteza ficou máxima. Um especialista pode aceitar o mapeamento pela API
(com justificativa), e a próxima execução transfere os priors.

Benchmark (linha de base lexical): MAP 0,27 (en 0,31; pt 0,16), nDCG@5 0,31, Spearman 0,58,
FPR 0,09, FNR 0,27 — erros *in-sample* e rótulos rascunhados por IA.

## 3. Decisões tomadas (reversíveis, registradas)

1. SQLite como padrão local e PostgreSQL+pgvector como padrão de implantação: não há Docker/PostgreSQL nesta máquina (ADR 0001).
2. Páginas HTML servidas pelo FastAPI na fatia; o Next.js fica para a fase 7 e consumirá a mesma API.
3. Embeddings de linha de base lexical e offline como padrão, para não exigir download nem API paga; Sentence Transformers fica opcional (`.[ml]`).
4. Ocupação da fatia: desenvolvedor de software, porque as três bases cobrem essa ocupação e há uso observado.
5. Competências essenciais da ESCO do tipo *skill/competence* tratadas como unidades tarefa-equivalentes, com peso uniforme e sinalização.
6. Escala harmonizada de qualificação: Job Zone e grupos ISCO/CBO convertidos ao nível de competência ISCO (0–1).
7. Correspondência aproximada com o AEI (razão ≥ 0,85), com método e escore registrados.
8. Nenhum crosswalk é aceito automaticamente na v0.
9. Marcador explícito `SYNTHETIC_DATA_DO_NOT_USE` para dados sintéticos.

## 4. Problemas encontrados e corrigidos durante a execução

- **Vazamento de dados:** exemplos do dicionário de capacidades copiavam tarefas O*NET da ocupação avaliada.
  Foram substituídos por paráfrases e há um detector automático (`find_leakage`) no pipeline e nos testes.
- **Saturação do crosswalk:** os componentes de tarefas e habilidades davam 1,0 com a calibração tarefa–capacidade.
  Passaram a ser reescalados contra uma distribuição nula empírica.
- **Mudança de taxonomia no AEI:** a correspondência exata casava 5 de 17 tarefas; a aproximada casou 10.
- **Bugs que os testes pegaram:** o histórico de revisão de crosswalk voltava desatualizado na resposta; dados sintéticos não eram marcados `is_synthetic`; o renderizador de Markdown reprocessava HTML das figuras; o bloco de referências não era injetado.

## 5. Limitações

- Metodologia não calibrada; pesos e limiares são hipóteses.
- Modelo de embeddings lexical (frágil entre idiomas e para sinônimos).
- Priors do dicionário de capacidades e rótulos do benchmark foram **rascunhados por IA** e não foram revisados.
- Referências bibliográficas com `verification_status: pending_human_check` (DOIs e páginas não conferidos).
- ESCO consultada pela versão padrão da API (`api-default`); a versão exata ainda não foi fixada.
- Sem tabela oficial ISCO↔SOC carregada: o componente de hierarquia fica "desconhecido" (0,5).
- Exportação apenas em JSON; PDF/DOCX/XLSX ficam para as fases 7–8.
- Testes de acessibilidade são estruturais (lang, h1, alt, scope, skip link); falta auditoria com axe/Playwright.

## 6. Pendências

1. **CBO:** baixar manualmente “Estrutura CBO (CSV)” em `cbo.mte.gov.br` (reCAPTCHA) para `data/raw/cbo/`
   e rodar `python -m observatory.cli validate-cbo` e depois `slice`.
2. Tabelas oficiais de correspondência (BLS ISCO-08↔SOC; tábua de conversão CBO↔CIUO) em `data/raw/crosswalks/`.
3. Anotação humana do benchmark (≥ 2 especialistas, κ/α).
4. Revisão dos priors do dicionário por painel.

## 7. Próximos passos (fase 2 → 4)

- Instalar `.[ml]` e comparar multilingual-e5-large, BGE-M3 e paraphrase-multilingual-mpnet no benchmark.
- Busca de candidatos top-N no crosswalk e interface de revisão (aceitar/rejeitar/editar/dividir/mesclar).
- Expandir para ≥ 3 ocupações completas (entregável 26) e fixar a versão ESCO (`selectedVersion`).
- Validação de construto contra AIOE, índice GPT (Eloundou et al.) e RTI.
