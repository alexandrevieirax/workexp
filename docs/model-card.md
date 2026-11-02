# Model card — Exposure engine (metodologia 0.2.0)

Formato inspirado em Mitchell et al. (2019).

| Item | Valor |
|---|---|
| Nome | AI Occupational Exposure Engine |
| Versão metodológica | 0.2.0 (status `uncalibrated`) — fingerprint em `config/methodology/registry.json` |
| Tipo | Índice composto baseado em regras + similaridade de embeddings + priors de especialistas + uso observado |
| Componentes aprendidos | Nenhum treinado neste repositório; embeddings pré-treinados `paraphrase-multilingual-mpnet-base-v2` (snapshot `4328cf26390c`), escolhido no ADR 0002 |
| Saídas | Por tarefa: E1–E14, exposição técnica, automação, aumento, transformação, classe, confiança, justificativa. Por ocupação: OAE, OAP, OAuP, OTP com intervalo de 90%, cobertura, qualidade, sensibilidade |

## Uso pretendido

Planejamento educacional, atualização curricular e pesquisa sobre transformação de tarefas.

## Usos fora do escopo (proibidos)

Avaliar, ranquear ou selecionar **pessoas**; recomendar demissões; estimar empregabilidade individual;
apresentar exposição como probabilidade de desemprego; usar sem exibir incerteza e limitações.

## Fatores e vieses conhecidos

- **Linguístico:** fontes de evidência majoritariamente em inglês. Com o modelo da 0.2.0 o MAP em português
  (0,67) supera o do inglês (0,52); com a linha de base lexical era 0,16. A calibração de títulos de ocupações
  é quase degenerada (só 10 pares).
- **Geográfico:** uso observado vem de uma plataforma (Claude.ai) e de seus usuários.
- **Ocupacional:** exemplos do dicionário concentrados em trabalho cognitivo; robótica com menos evidência.
- **Temporal:** capacidades de IA mudam rapidamente; cada capacidade tem `valid_until`.

## Métricas (benchmark v0.1.0, rótulos rascunho por IA — não ouro)

paraphrase-multilingual-mpnet-base-v2: MAP 0,55 (en 0,52; pt 0,67) · nDCG@5 0,60 · P@3 0,45 · Spearman 0,88 ·
FPR 0,02 · FNR 0,05 · AUC dos pares de ocupações 0,88 (limiar 0,5; erros *in-sample*). Linha de base lexical:
MAP 0,27, FPR 0,09. Comparação completa no ADR 0002.
Valores atualizados ficam em `artifacts/experiments/benchmark-<run>/metrics.json` e na área "Sobre".

## Limitações

Ver `docs/methodology-v0.md` e a seção "Limitações" da área "Sobre". O **nível** absoluto do OAE ainda não é
interpretável (pesos não calibrados, E1 calibrado em 36 consultas rascunhadas); a estrutura é o que importa:
quais tarefas, quais barreiras, onde está a incerteza.

## Responsáveis e contestação

Ver `CONTRIBUTING.md`.
