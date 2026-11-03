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

- **Publicador:** Ministério do Trabalho e Emprego. **Status:** "Estrutura CBO (CSV)" obtida manualmente
  (reCAPTCHA) em 2026-11-02 e carregada; SHA-256 em `source_version`.
- **Conteúdo usado:** ocupações, famílias, sinônimos, perfil ocupacional (grandes áreas e atividades).
- **Cuidados:** atividades vêm por ocupação no arquivo, mas são definidas no nível da família; área Z
  (competências pessoais) não é tratada como tarefa; 13 linhas com `;` extra reparadas e contadas; não há
  importância/frequência das atividades (pesos uniformes); descrição sumária, formação e condições de
  exercício não vêm no arquivo de estrutura.
- **Representatividade:** mercado brasileiro; versão estrutural sem data de revisão explícita no arquivo.

## Anthropic Economic Index (release 2025-03-27)

- **Publicador:** Anthropic (Hugging Face). **Licença:** verificar no cartão do dataset.
- **Conteúdo usado:** `task_pct_v2.csv` (participação por tarefa) e `automation_vs_augmentation_by_task.csv`.
- **Coleta:** conversas do Claude.ai agregadas com preservação de privacidade (Clio); preprint.
- **Cuidados:** uma plataforma e família de modelos; usuários não representam a força de trabalho; tarefas
  ausentes ≠ uso zero; ligação com O*NET 31.0 por texto (exato ou aproximado ≥ 0,85).

## Benchmark de validação v0.1.0

- **Conteúdo:** 36 pares tarefa–capacidade (28 en, 8 pt) e 10 pares de ocupações (incluindo falsos amigos).
- **Rótulos:** rascunho gerado por IA (`annotator: ai_draft`, `is_gold: false`). **Não usar como ouro.**
- **Anotação humana:** a página `/annotations` coleta rótulos cegos (sem a sugestão do sistema, ordem
  embaralhada) para 265 pares. Eles incluem 66 pares sugeridos pelo modelo que não estavam no rascunho, para
  detectar relações esquecidas. Os rótulos ficam em `validation_sample` (um por anotador e par, com data e
  comentário). A concordância é medida pelo κ de Cohen ponderado (quadrático) e pelo α de Krippendorff
  (intervalar), com os limiares de Krippendorff: ≥ 0,80 confiável; 0,667–0,80 apenas conclusões provisórias.
- **Exclusão deliberada:** a ocupação avaliada na fatia (15-1252.00) não está no benchmark.

## Dados sintéticos

Somente em `tests/fixtures/synthetic/`; marcados com `[SINTÉTICO]`, códigos `99-*` e arquivo-marcador
`SYNTHETIC_DATA_DO_NOT_USE`, que faz os conectores gravarem `is_synthetic = true`.
