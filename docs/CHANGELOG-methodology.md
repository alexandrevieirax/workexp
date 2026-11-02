# Changelog metodológico

Toda alteração de fórmula, peso, fonte, modelo de embeddings, classificação, pipeline, benchmark,
dicionário, regra de crosswalk ou método curricular exige uma nova seção aqui, uma nova entrada em
`config/methodology/registry.json`, atualização da área "Sobre" (`methodology_version` no cabeçalho dos
arquivos de conteúdo) e das referências citadas. `tests/test_about_consistency.py` verifica isso.

## [0.2.0] - 2026-11-02

Status: **não calibrada**. Substitui a 0.1.0 (marcada `superseded`). Única mudança metodológica:

- **Modelo de embeddings padrão** passa a ser
  `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`, snapshot
  `4328cf26390c98c5e3c738b4460a05b95f4911f5`, fixado em `embedding.provider`/`embedding.revision` do YAML
  (antes: linha de base lexical). Escolhido entre quatro candidatos pela regra registrada antes dos
  resultados no ADR 0002; registro em `artifacts/experiments/model-comparison-20261102T170325Z/`.
- Consequências: nova calibração piso/teto no benchmark; o fator de incerteza
  `baseline_embedding_model` deixa de ser aplicado; resultados da 0.1.0 não são comparáveis.
- Referência adicionada: Reimers & Gurevych (2020).
- Testes continuam usando a linha de base (sem download de modelos), com aviso explícito de substituição.

## [0.1.0] - 2026-11-02

Status: **não calibrada** (hipóteses iniciais).

- Fórmulas iniciais de exposição técnica, automação, aumento e transformação (seção 7 dos requisitos).
- Pesos de tarefas O*NET com α = 0,50, β = 0,30, γ = 0,20 e redistribuição proporcional de expoentes ausentes;
  `Recommend Suppress = Y` tratado como ausente.
- Priors ocupacionais E6–E10 a partir de *Work Context*/*Work Activities* do O*NET + pistas lexicais (pt/en).
- Uso observado (E3) a partir do Anthropic Economic Index, release 2025-03-27, com correspondência textual
  exata ou aproximada (razão ≥ 0,85) por mudança de taxonomia SOC 2010 → 2018.
- Dicionário de capacidades de IA v0.1.0 (10 famílias, 78 capacidades; priors não revisados).
- Crosswalk composto com cinco componentes; sem aceitação automática; similaridade de conjuntos
  reescalada contra distribuição nula de 40 ocupações O*NET aleatórias.
- Modelo de embeddings padrão: linha de base lexical `baseline/char-ngram-hashing@v1-d2048`, calibrado no
  benchmark v0.1.0 (rótulos rascunhados por IA, não ouro).
- Intervalos de 90% por Monte Carlo (1000 sorteios, semente 20261102) com ruído Beta que preserva a média,
  e sensibilidade ±20%.
- CBO: área Z do perfil ocupacional (competências pessoais) excluída das unidades de tarefa.
- Similaridade de conjuntos sem amostra nula passa a ser componente desconhecido (antes saturava em 1,0).
- Fingerprint passa a cobrir também `exposure/engine.py` e `exposure/dimensions.py`.

Revisões de desenvolvimento anteriores à publicação (status ainda `uncalibrated`, não `released`): o
fingerprint da 0.1.0 foi regravado a cada correção acima; os resultados das execuções anteriores não são
comparáveis com os atuais.
