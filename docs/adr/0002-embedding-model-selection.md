# ADR 0002 — Seleção do modelo de embeddings

- **Status:** aceito (regra registrada antes da execução; decisão preenchida após os resultados)
- **Data:** 2026-11-02

## Contexto

A linha de base lexical (`baseline/char-ngram-hashing@v1-d2048`) não liga português a inglês: o título
CBO 2124-05 → O*NET 15-1252.00 teve similaridade calibrada 0,01, nenhum crosswalk passou de "moderado" e
as tarefas CBO/ESCO ficaram em "evidência insuficiente". Os requisitos pedem avaliar pelo menos
multilingual-e5-large, BGE-M3 e um terceiro modelo multilíngue, sem escolher por ranking genérico.

## Candidatos

| Especificação | Dimensão | Observação |
|---|---|---|
| `baseline` | 2048 | piso que todo candidato deve superar |
| `sentence-transformers:sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | 768 | multilíngue alternativo, menor |
| `sentence-transformers:intfloat/multilingual-e5-large` | 1024 | prefixos `query:`/`passage:` |
| `sentence-transformers:BAAI/bge-m3` | 1024 | apenas o vetor denso |

Modelo comercial: não avaliado (sem credenciais; o MVP não exige API paga).

## Regra de seleção (fixada antes dos resultados)

`selection_score = média(MAP geral, MAP pt, AUC dos pares de ocupações)`; elegível somente se a taxa de
falsos positivos não for pior que a da linha de base. O MAP em português entra explicitamente porque a CBO é
em português. Em empate (diferença < 0,01), prefere-se o modelo menor/mais rápido.

## Resultados

Ver a seção "Decisão" (preenchida após `python -m observatory.cli benchmark-models`) e
`artifacts/experiments/model-comparison-*/comparison.md`.

## Decisão

Execução de 2026-11-02 (`artifacts/experiments/model-comparison-20261102T170325Z/`), CPU:

| Modelo | MAP | MAP en | MAP pt | nDCG@5 | Spearman | FPR | FNR | AUC pares | Score | Tempo (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| linha de base lexical | 0,27 | 0,31 | 0,16 | 0,31 | 0,58 | 0,09 | 0,27 | 0,60 | 0,34 | 2 |
| **paraphrase-multilingual-mpnet-base-v2** | **0,55** | 0,52 | **0,67** | **0,60** | **0,88** | **0,02** | **0,05** | **0,88** | **0,70** | 44 |
| multilingual-e5-large (inelegível: FPR) | 0,41 | 0,47 | 0,20 | 0,46 | 0,54 | 0,17 | 0,27 | 0,88 | 0,50 | 80 |
| BGE-M3 | 0,44 | 0,48 | 0,31 | 0,48 | 0,75 | 0,02 | 0,18 | 0,60 | 0,45 | 73 |

Escolhido: **paraphrase-multilingual-mpnet-base-v2**, snapshot `4328cf26390c98c5e3c738b4460a05b95f4911f5`,
adotado na metodologia 0.2.0. A vantagem é grande em português (MAP 0,67), justamente onde a linha de base
falhava, e o modelo é o menor e o mais rápido dos três.

Ressalvas: o resultado ruim do e5-large em português pode refletir o uso assimétrico de prefixos
`query:`/`passage:` (tarefas como consulta, capacidades como passagem) com exemplos majoritariamente em
inglês; não foi testada a variante simétrica. Com 36 consultas de rótulos rascunhados por IA, diferenças
pequenas não são confiáveis — reavaliar quando houver conjunto ouro.

## Consequências

- Mudar o modelo padrão é mudança metodológica: nova `methodology_version`, recalibração no benchmark,
  vetores recalculados (o cache é chaveado por modelo e snapshot).
- O benchmark tem rótulos rascunhados por IA e é pequeno; a escolha é **provisória** até o conjunto ouro.
