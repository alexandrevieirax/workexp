# Guia de contribuição

## Fluxo

1. Abra uma *issue* descrevendo o problema ou a proposta.
2. Crie um ramo, implemente, rode `pytest` (e `ruff check .` / `mypy src` quando instalados).
3. Abra um *pull request* explicando o impacto metodológico, se houver.

## Mudanças metodológicas

Qualquer alteração em fórmula, peso, limiar, léxico, fonte, modelo de embeddings, classificação, benchmark,
dicionário de capacidades, regra de crosswalk ou método curricular exige, **no mesmo PR**:

1. nova versão em `config/methodology/registry.json` (e novo `methodology_vX.Y.Z.yaml` quando aplicável);
2. seção `## [X.Y.Z]` em `docs/CHANGELOG-methodology.md`;
3. `methodology_version: X.Y.Z` no cabeçalho de `src/observatory/about/content/*.md` e texto ajustado;
4. referências novas em `docs/references/references.json` (com `peer_reviewed` e `verification_status`);
5. `python -m observatory.cli methodology-release` para gravar o fingerprint;
6. ADR em `docs/adr/` se a decisão for arquitetural.

Versões com `status: released` são imutáveis.

## Contestação de resultados

Abra uma *issue* com o rótulo `contestacao` contendo: ocupação/tarefa, versão metodológica e fingerprint
(mostrados na página da ocupação), a evidência e a justificativa. Correções de crosswalk são feitas via revisão
humana (`POST /api/crosswalks/{id}/review`), sempre com justificativa e histórico.

## Dados

Nunca adicione dados reais fabricados. Dados de teste devem ser sintéticos, marcados com `[SINTÉTICO]` e
ficar em `tests/fixtures/synthetic/`.
