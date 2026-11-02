# Metodologia v0 (methodology_version 0.1.0)

> Os valores numéricos (pesos, limiares, expoentes) **não** são reproduzidos aqui
> manualmente: a fonte única é `config/methodology/methodology_v0.1.0.yaml`, e a
> área "Sobre" os lê diretamente desse arquivo. Este documento explica o
> raciocínio. Todas as fórmulas são **hipóteses iniciais** a serem calibradas.

## 1. Definições

| Termo | Definição operacional |
|---|---|
| Exposição potencial | Grau em que o conteúdo de uma tarefa corresponde a capacidades técnicas de IA atualmente demonstradas. Não implica adoção. |
| Exposição observada | Evidência de que a tarefa já é realizada com IA em uso real (E3). |
| Automação | Execução da tarefa pela IA com intervenção humana mínima no ciclo. |
| Aumento de capacidade | A IA amplia a qualidade, velocidade ou escopo do trabalho humano, que mantém julgamento e responsabilidade. |
| Transformação | Mudança relevante na **forma de execução** da tarefa (fluxo, ferramentas, papéis), seja por automação ou aumento. |
| Barreira | Requisito físico, social, jurídico/ético ou organizacional que reduz a aplicabilidade da IA. |
| Incerteza | Medida da fragilidade da evidência que sustenta a pontuação (E14). |

**Exposição não é substituição, desemprego, desaparecimento da profissão nem
obsolescência de competências.** Essa frase aparece na interface em todas as
páginas com pontuação.

## 2. Unidade de análise

A unidade é a **tarefa** (O*NET Task Statement), o **elemento de atividade**
(atividade CBO) ou a **habilidade/competência essencial** (ESCO). Os três tipos
são preservados no campo `task.unit_type` porque não são equivalentes:

- `onet_task`: tarefa com Importância (IM, 1–5), Relevância (RT, 0–100) e
  Frequência (FT, distribuição em 7 categorias).
- `esco_skill`: competência essencial; ESCO não publica tarefas nem pesos.
- `cbo_activity`: atividade do perfil ocupacional; definida por **família**
  (4 dígitos), não por ocupação (6 dígitos).

## 3. Correspondência semântica (E1)

1. Cada capacidade de IA gera um texto de referência: definição operacional +
   exemplos positivos. Exemplos negativos geram um texto separado.
2. `s_pos = max cos(tarefa, texto_positivo)`, `s_neg = max cos(tarefa, negativo)`.
3. `s = s_pos − max(0, s_neg − s_pos)` (penaliza tarefas mais próximas do contraexemplo).
4. Calibração específica do modelo: `E1_c = clip((s − piso)/(teto − piso), 0, 1)`,
   onde piso e teto são estimados no benchmark (percentil 75 dos pares
   "não relacionados" e mediana dos "relacionados"). Similaridade bruta de
   modelos diferentes **não** é comparável.
5. `E1` da tarefa = média das `top_k` capacidades calibradas.

## 4. Dimensões E2–E13

- **E2, E11, E12, E13 (parte técnica) e complementaridade** são médias das
  propriedades das capacidades correspondentes (dicionário de capacidades),
  ponderadas pela similaridade calibrada. Essas propriedades são **priors de
  especialistas** com status `provisional` até revisão.
- **E3 (uso observado)**: percentil da participação da tarefa nas conversas do
  Anthropic Economic Index. Tarefa ausente da amostra recebe 0 **com** flag
  `absent_from_sample` e acréscimo de incerteza — ausência não é prova de não uso.
  Para tarefas ESCO/CBO, E3 = desconhecido (`missing`), não zero.
- **E6–E10 e padronização de processo**: prior ocupacional calculado a partir de
  elementos de *Work Context* e *Work Activities* do O*NET (cada escala
  normalizada separadamente por seu mínimo/máximo do *Scales Reference*),
  ajustado por pistas lexicais da tarefa (`± delta`). As listas de elementos e de
  pistas lexicais estão no YAML da metodologia. Para ocupações sem O*NET o prior é
  transferido pelo crosswalk aceito/forte, com incerteza proporcional a
  `1 − mapping_confidence`; sem crosswalk, prior neutro (0,5) e incerteza alta.
- **E4 e E5** são os resultados sintéticos (seção 5).
- **E14 (incerteza)**: média ponderada de fontes de fragilidade — ausência de uso
  observado, prior transferido ou padrão, margem pequena entre as capacidades
  correspondentes, modelo de embeddings de linha de base, priors não revisados.

## 5. Resultados sintéticos por tarefa

```
technical_exposure = Σ w_i · {E1, E2, E3, E11}            (w do YAML)
automation_potential = technical_exposure · (1−E8)(1−E7)(1−E9) · standardization
augmentation_potential = technical_exposure · E6 · complementarity
transformation_potential = max(automation, augmentation) · redesign
redesign = Σ v_i · {E12, E11}
```

E3 ausente: o peso de E3 é redistribuído proporcionalmente entre os demais
termos e o fato é registrado (`missing_flags`). Nada é imputado silenciosamente.

## 6. Pesos das tarefas (O*NET)

```
importance_norm = (IM − 1)/(5 − 1)
relevance_norm  = RT/100
frequency_norm  = (Σ_c c · p_c/100 − 1)/(7 − 1)        # valor esperado da distribuição FT
w_raw = importance_norm^α · relevance_norm^β · frequency_norm^γ
w = w_raw / Σ w_raw
```

- Escalas nunca são somadas brutas; cada uma é normalizada por seu próprio intervalo.
- Valor com `Recommend Suppress = Y` é tratado como **ausente** naquele termo;
  o expoente é redistribuído (`α' = α/(α+β)` etc.) e a flag é registrada.
- Todos ausentes em uma tarefa: flag `uniform_fallback`. Se **todas** as tarefas
  da ocupação estão nessa situação, os pesos são uniformes; se só algumas, elas
  recebem a média dos pesos brutos das tarefas avaliadas
  (`weight_set_to_rated_mean`) — do contrário receberiam o peso máximo.
- `importance_norm = 0` (IM = 1) gera peso zero: decisão explícita, a tarefa
  ainda é exibida.
- ESCO e CBO: peso uniforme (`uniform_unweighted_source`), sinalizado.

## 7. Índices ocupacionais

`OAE`, `OAP`, `OAuP`, `OTP` = somas ponderadas das quatro saídas por tarefa.

Indicadores complementares:
- **Intervalo de 90%** por Monte Carlo (ruído nas dimensões com desvio proporcional a E14,
  amostrado de uma Beta com média igual ao valor — limitada a [0, 1] sem viés; pesos das
  fórmulas por Dirichlet concentrada no valor do YAML; expoentes α, β, γ perturbados);
  semente fixa para reprodutibilidade. Ruído gaussiano recortado foi descartado porque
  empurrava valores saturados para dentro e deixava o ponto fora do próprio intervalo.
- **Cobertura**: fração do peso das tarefas com E1 válido e prior não-padrão.
- **Qualidade das fontes**: fração de ratings não suprimidos e com N ≥ limite.
- **Qualidade do crosswalk**: melhor `mapping_confidence` disponível.
- **Divergência entre bases**: diferença de OAE entre ocupações mapeadas.
- **Sensibilidade**: variação de ±20% em cada peso (um por vez) e efeito no OAE.

## 8. Classificação das tarefas

Regras ordenadas (limiares no YAML):
1. E14 ≥ limite → *Evidência insuficiente*.
2. exposição técnica < limite_baixo → *Baixa aplicabilidade atual*.
3. automação ≥ limite_alto e padronização ≥ limite → *Potencialmente automatizável em contexto estruturado*.
4. automação ≥ limite_médio → *Automação elevada sob supervisão*.
5. automação ≥ limite_parcial → *Automação parcial*.
6. aumento ≥ limite e transformação ≥ limite → *Transformação significativa*.
7. aumento ≥ limite → *Aumento de capacidade humana*.
8. caso contrário → *Apoio pontual*.

## 9. Crosswalk

`mapping_confidence = Σ pesos · {título, tarefas, habilidades, hierarquia, qualificação}`.
Similaridade de tarefas (e de habilidades/DWAs) = média do melhor par (bidirecional)
entre conjuntos, **reescalada contra uma distribuição nula empírica**: o mesmo conjunto
de origem comparado com `null_sample_size` ocupações aleatórias da taxonomia de destino
(semente fixa). `componente = (s − média_nula)/(1 − média_nula)`, recortado em [0, 1]:
0 = tão parecido quanto uma ocupação aleatória; 1 = conjuntos idênticos. A posição de `s`
na distribuição nula também é registrada. Sem amostra nula (< 5 ocupações; pares CBO–ESCO na
v0) o componente é **desconhecido** (valor neutro, sinalizado) e a similaridade bruta é apenas
registrada. Antes, usava-se a calibração tarefa–capacidade, que saturava em 1,0 e chegou a
classificar CBO→ESCO como "forte" (0,83) sem base — por isso foi removida.
**Desde a 0.3.0** a similaridade de conjuntos é
`Φ((s − média_nula)/dp_nula) × clip((s − média_nula)/(s_melhor − média_nula))`, contra 150 ocupações O*NET
aleatórias (excluídos os candidatos). O primeiro fator mede se o candidato é mais parecido que o acaso; o
segundo mede o quão perto está do melhor candidato. Só o primeiro saturava para qualquer ocupação vizinha. Cada ocupação ESCO/CBO é comparada com vários **candidatos**: os alvos da
tabela oficial ESCO→O*NET-SOC e as 8 ocupações O*NET mais próximas por título e descrição. Os candidatos são
ranqueados pela confiança composta; se o segundo estiver a menos de 0,03 do primeiro, o mapeamento é
**ambíguo**: se todos os empatados forem fortes, os priors são a média deles (`crosswalk_pooled`, com
fragilidade extra); caso contrário não há transferência sem revisão humana. A calibração de títulos usa 148 pares com
rótulos de fontes oficiais (`data/validation/occupation_pairs_v0.2.0.jsonl`).
**Decisões humanas** (página `/crosswalks` ou `POST /api/crosswalks/{id}/review`) são procuradas por
(taxonomia e código de origem, código de destino), não pelo identificador da linha, porque cada execução cria
novas propostas. Elas são herdadas pelas novas linhas, com histórico `carry`. Um candidato **aceito** define
de onde vêm os priors, independentemente do ranking automático; um **rejeitado** sai do ranking antes do
cálculo de ambiguidade.
Hierarquia: para ESCO→O*NET, pertencimento à tabela oficial do O*NET (código **e** título, pois os códigos ESCO
mudam entre versões); nos demais pares, consistência de grupos ISCO/SOC quando houver tabela oficial;
desconhecido = 0,5 (neutro), sinalizado. Correspondências < 0,60 nunca são
aceitas automaticamente; nenhuma é aceita automaticamente na v0 — todas nascem
`proposed` e exigem revisão humana.

## 10. O que muda a versão metodológica

Qualquer alteração no YAML da metodologia, no módulo de fórmulas
(`src/observatory/exposure/formulas.py`) ou no dicionário de capacidades altera
a impressão digital (`fingerprint`). O teste `tests/test_about_consistency.py`
falha se o registro de versões, o changelog, a área "Sobre" e as referências
não forem atualizados em conjunto.
