# Comparação de modelos de embeddings (benchmark v0.1.0)

Regra de seleção (definida antes dos resultados): mean(MAP overall, MAP pt, occupation-pair AUC); eligible if FPR <= baseline FPR.

| Modelo | MAP | MAP en | MAP pt | nDCG@5 | P@3 | Spearman | FPR | FNR | AUC pares | Score | Tempo (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `baseline/char-ngram-hashing@v1-d2048` | 0.2743 | 0.3079 | 0.1592 | 0.3093 | 0.2796 | 0.5778 | 0.0891 | 0.2727 | 0.6 | 0.3445 | 2.3 |
| `sentence-transformers/sentence-transformers/paraphrase-multilingual-mpnet-base-v2@4328cf26390c` **(escolhido)** | 0.5543 | 0.5214 | 0.6672 | 0.6039 | 0.4516 | 0.8767 | 0.0198 | 0.0455 | 0.88 | 0.7005 | 44.1 |
| `sentence-transformers/intfloat/multilingual-e5-large@3d7cfbdacd47` (inelegível) | 0.4091 | 0.469 | 0.2041 | 0.4623 | 0.3656 | 0.5381 | 0.1683 | 0.2727 | 0.88 | 0.4977 | 80.0 |
| `sentence-transformers/BAAI/bge-m3@5617a9f61b02` | 0.4394 | 0.476 | 0.3141 | 0.4761 | 0.3656 | 0.7533 | 0.0198 | 0.1818 | 0.6 | 0.4512 | 72.8 |

- Benchmark labels are AI-drafted (not gold) and small (36 task queries, 10 occupation pairs).
- Calibration and error rates are in-sample.
- Temporal stability cannot be measured with a single snapshot; model snapshots are pinned instead.
