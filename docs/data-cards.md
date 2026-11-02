# Data cards

Formato inspirado em Gebru et al. (2021). Hash e data de cada arquivo usados ficam em `source_version`.

## O*NET 31.0 (text)

- **Publicador:** National Center for O*NET Development / U.S. DOL. **Licença:** CC BY 4.0.
- **Conteúdo usado:** ocupações, tarefas (Core/Supplemental), ratings IM/RT/FT com N, erro padrão, IC e
  `Recommend Suppress`; Work Context; Work Activities; Knowledge; Abilities; Essential/Transferable Skills;
  Job Zones; Tasks→DWAs.
- **Coleta original:** questionários com trabalhadores (Incumbent) e analistas (Analyst).
- **Cuidados:** escalas diferentes (1–5, 0–100, categorias 1–7) nunca são somadas brutas; suprimidos =
  ausentes; taxonomia SOC 2018 difere da usada por algumas bases secundárias (ex.: AEI usa SOC 2010).
- **Representatividade:** mercado de trabalho dos EUA.

## ESCO (API)

- **Publicador:** Comissão Europeia. **Licença:** termos de uso ESCO (confirmar).
- **Conteúdo usado:** URI, rótulos preferidos/alternativos (en/pt), descrição, grupo ISCO-08, competências
  essenciais e opcionais com tipo.
- **Cuidados:** ESCO não publica tarefas nem pesos; competências essenciais do tipo *skill/competence* são
  usadas como unidades tarefa-equivalentes, com pesos uniformes. Versão da API registrada como `api-default`
  (pendente: fixar `selectedVersion`).
- **Representatividade:** mercado europeu; tradução pt é de Portugal.

## CBO 2002

- **Publicador:** Ministério do Trabalho e Emprego. **Status:** conector pronto; arquivo **não obtido**
  (download protegido por reCAPTCHA).
- **Cuidados:** atividades são descritas por família ocupacional; descrição sumária, formação e condições de
  exercício não vêm no ZIP de estrutura.

## Anthropic Economic Index (release 2025-03-27)

- **Publicador:** Anthropic (Hugging Face). **Licença:** verificar no cartão do dataset.
- **Conteúdo usado:** `task_pct_v2.csv` (participação por tarefa) e `automation_vs_augmentation_by_task.csv`.
- **Coleta:** conversas do Claude.ai agregadas com preservação de privacidade (Clio); preprint.
- **Cuidados:** uma plataforma e família de modelos; usuários não representam a força de trabalho; tarefas
  ausentes ≠ uso zero; ligação com O*NET 31.0 por texto (exato ou aproximado ≥ 0,85).

## Benchmark de validação v0.1.0

- **Conteúdo:** 36 pares tarefa–capacidade (28 en, 8 pt) e 10 pares de ocupações (incluindo falsos amigos).
- **Rótulos:** rascunho gerado por IA (`annotator: ai_draft`, `is_gold: false`). **Não usar como ouro.**
  Próximo passo: anotação por ≥ 2 especialistas, κ de Cohen / α de Krippendorff.
- **Exclusão deliberada:** a ocupação avaliada na fatia (15-1252.00) não está no benchmark.

## Dados sintéticos

Somente em `tests/fixtures/synthetic/`; marcados com `[SINTÉTICO]`, códigos `99-*` e arquivo-marcador
`SYNTHETIC_DATA_DO_NOT_USE`, que faz os conectores gravarem `is_synthetic = true`.
