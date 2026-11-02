# Model card — Exposure engine v0.1.0

Formato inspirado em Mitchell et al. (2019).

| Item | Valor |
|---|---|
| Nome | AI Occupational Exposure Engine |
| Versão metodológica | 0.1.0 (status `uncalibrated`) — fingerprint em `config/methodology/registry.json` |
| Tipo | Índice composto baseado em regras + similaridade de embeddings + priors de especialistas + uso observado |
| Componentes aprendidos | Nenhum treinado neste repositório; embeddings pré-definidos (padrão: linha de base lexical) |
| Saídas | Por tarefa: E1–E14, exposição técnica, automação, aumento, transformação, classe, confiança, justificativa. Por ocupação: OAE, OAP, OAuP, OTP com intervalo de 90%, cobertura, qualidade, sensibilidade |

## Uso pretendido

Planejamento educacional, atualização curricular e pesquisa sobre transformação de tarefas.

## Usos fora do escopo (proibidos)

Avaliar, ranquear ou selecionar **pessoas**; recomendar demissões; estimar empregabilidade individual;
apresentar exposição como probabilidade de desemprego; usar sem exibir incerteza e limitações.

## Fatores e vieses conhecidos

- **Linguístico:** fontes de evidência majoritariamente em inglês; desempenho do benchmark em português
  (MAP 0,16) bem abaixo do inglês (0,31) com o modelo padrão.
- **Geográfico:** uso observado vem de uma plataforma (Claude.ai) e de seus usuários.
- **Ocupacional:** exemplos do dicionário concentrados em trabalho cognitivo; robótica com menos evidência.
- **Temporal:** capacidades de IA mudam rapidamente; cada capacidade tem `valid_until`.

## Métricas (benchmark v0.1.0, rótulos rascunho por IA — não ouro)

Linha de base lexical: P@3 0,28 · R@5 0,30 · MAP 0,27 · nDCG@5 0,31 · Spearman 0,58 ·
FPR 0,09 · FNR 0,27 (limiar 0,5; erros *in-sample*, pois a calibração usa os mesmos itens).
Valores atualizados ficam em `artifacts/experiments/benchmark-<run>/metrics.json` e na área "Sobre".

## Limitações

Ver `docs/methodology-v0.md` e a seção "Limitações" da área "Sobre". Com o modelo lexical, a similaridade
calibrada (E1) satura facilmente; o **nível** absoluto do OAE não é interpretável, só a estrutura (quais tarefas,
quais barreiras, onde está a incerteza).

## Responsáveis e contestação

Ver `CONTRIBUTING.md`.
