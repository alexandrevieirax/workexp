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

---

## Adendo — carga da CBO (2026-11-02, run `20261102T160636Z-3649df`)

Os arquivos oficiais "Estrutura CBO (CSV)" foram colocados manualmente em `data/raw/cbo/` e validados
(2.725 ocupações, 627 famílias, 7.870 sinônimos, 192.745 linhas de perfil). Ocupação **2124-05 —
Analista de desenvolvimento de sistemas** (família 2124, Analistas de tecnologia da informação): 63
atividades em 9 grandes áreas e 16 competências pessoais; 11 sinônimos.

### Ajustes exigidos pelos dados reais

- O arquivo de sinônimos usa `CODIGO;TITULO`, não `OCUPACAO;SINONIMO` como eu tinha documentado: mapeamento
  de colunas adicionado.
- 13 linhas do `PerfilOcupacional.csv` têm `;` extra no texto da atividade: reparadas e contadas.
- Área Z ("Demonstrar competências pessoais") passou a ser competência pessoal, não tarefa.

### Problemas metodológicos expostos pela CBO e corrigidos

- **CBO→ESCO aparecia como "forte" (0,83)** porque, sem amostra nula, a similaridade de tarefas caía num
  fallback que saturava em 1,0. Agora o componente fica desconhecido: 0,65, "moderada".
- **O OAE da CBO (0,754) ficava fora do próprio intervalo [0,672–0,743]**: o ruído gaussiano recortado do
  Monte Carlo só podia reduzir valores saturados. Substituído por ruído Beta com média preservada; um teste
  agora exige que todo ponto esteja dentro do intervalo.
- O motor de exposição (Monte Carlo, flags de incerteza) não estava coberto pelo fingerprint; agora está.

### Resultados atuais (metodologia 0.1.0, fingerprint `26d94e190c288112…`)

| Base | OAE | OAP | OAuP | OTP | E14 médio | Prior E6–E10 |
|---|---|---|---|---|---|---|
| O*NET 15-1252.00 | 0,75 [0,70–0,80] | 0,07 [0,05–0,10] | 0,46 [0,39–0,52] | 0,33 [0,28–0,39] | 0,48 | O*NET direto |
| ESCO software developer | 0,78 [0,71–0,85] | 0,05 [0,02–0,09] | 0,30 [0,21–0,40] | 0,22 [0,15–0,31] | 1,00 | padrão |
| CBO 2124-05 | 0,75 [0,71–0,80] | 0,05 [0,03–0,07] | 0,28 [0,23–0,33] | 0,19 [0,17–0,24] | 0,97 | padrão |

| Crosswalk | Título | Tarefas | Confiança | Classe |
|---|---|---|---|---|
| ESCO → O*NET | 1,00 | 0,13 | 0,42 | não aceito |
| CBO → O*NET | 0,01 | 0,03 | 0,29 | não aceito |
| CBO → ESCO (pt) | 1,00 | desconhecido | 0,65 | moderada |

Leitura: nas três bases o aumento supera amplamente a automação. As tarefas da CBO e da ESCO ficam em
"evidência insuficiente" porque não têm uso observado, pesos de tarefa nem priors transferidos. O CBO→O*NET
quase nulo (título 0,01) mostra a limitação central da linha de base lexical: ela não liga português a
inglês. Esse é o motivo prioritário para avaliar modelos multilíngues.

---

## Adendo 2 — modelo de embeddings multilíngue e metodologia 0.2.0 (run `20261102T171223Z-e47f52`)

Quatro modelos foram comparados no benchmark com uma regra de seleção registrada **antes** dos resultados
(ADR 0002): média de MAP geral, MAP em português e AUC dos pares de ocupações, exigindo FPR não pior que a
linha de base.

| Modelo | MAP | MAP pt | FPR | AUC pares | Score |
|---|---|---|---|---|---|
| linha de base lexical | 0,27 | 0,16 | 0,09 | 0,60 | 0,34 |
| **paraphrase-multilingual-mpnet-base-v2** | **0,55** | **0,67** | **0,02** | **0,88** | **0,70** |
| multilingual-e5-large | 0,41 | 0,20 | 0,17 (inelegível) | 0,88 | 0,50 |
| BGE-M3 | 0,44 | 0,31 | 0,02 | 0,60 | 0,45 |

O mpnet foi adotado como metodologia **0.2.0** (snapshot fixado). A 0.1.0 ficou `superseded`. A trava de
governança bloqueou o pipeline até a nova versão, o changelog, a área "Sobre" e as referências serem
atualizados.

### Resultados com a 0.2.0

| Base | OAE | OAP | OAuP | OTP | E14 médio |
|---|---|---|---|---|---|
| O*NET 15-1252.00 | 0,71 [0,67–0,75] | 0,07 [0,06–0,08] | 0,43 [0,39–0,48] | 0,30 [0,27–0,33] | 0,25 (antes 0,48) |
| ESCO software developer | 0,79 [0,72–0,86] | 0,05 [0,03–0,08] | 0,31 [0,22–0,40] | 0,22 [0,16–0,30] | 0,79 |
| CBO 2124-05 | 0,76 [0,72–0,80] | 0,05 [0,04–0,07] | 0,29 [0,25–0,33] | 0,20 [0,17–0,24] | 0,77 |

| Crosswalk | Título | Tarefas | Confiança 0.1.0 → 0.2.0 |
|---|---|---|---|
| ESCO → O*NET | 1,00 | 0,29 | 0,42 → 0,51 |
| CBO → O*NET | 0,01 → 1,00 | 0,03 → 0,24 | 0,29 → 0,56 |
| CBO → ESCO | 1,00 | desconhecido | 0,65 → 0,65 |

O modelo multilíngue resolveu a ligação português↔inglês: CBO→O*NET passou a vencer as 40 ocupações nulas
em similaridade de tarefas. Nenhum mapeamento chega ao limiar de 0,60 para O*NET. Há duas razões: o componente
de hierarquia continua desconhecido (sem tabela oficial ISCO↔SOC) e a reescala contra o nulo, `(s − μ)/(1 − μ)`,
é severa para equivalentes entre bases. Por isso os priors do O*NET ainda não chegam à CBO e à ESCO, e suas
tarefas seguem majoritariamente em "evidência insuficiente".

### Problemas novos registrados

- **Calibração de títulos quase degenerada** (piso 0,812, teto 0,813): com 10 pares, um falso amigo pontua
  quase como um equivalente. O título vira um degrau 0/1, e o pipeline agora emite um alerta. É preciso ampliar
  os pares de ocupações do benchmark.
- **e5-large** teve desempenho ruim em português, possivelmente pelo uso assimétrico de prefixos; a variante
  simétrica não foi testada.

### Próximos passos atualizados

1. Carregar a tabela oficial ISCO-08↔SOC e a tábua CBO↔CIUO; revisar a reescala do nulo (por exemplo, posição
   percentil ou comparação com os N melhores candidatos) antes da calibração.
2. Ampliar e anotar por humanos o benchmark (pares de ocupações, sobretudo).
3. Revisão humana dos três crosswalks pela API, o que liberaria a transferência de priors.

---

## Adendo 3 — crosswalk revisado, metodologia 0.3.0 (run `20261102T200135Z-1fea10`)

### O que mudou

- **Tabela oficial:** o O*NET publica `ESCO_to_ONET-SOC.xlsx`, que agora alimenta o componente de hierarquia
  ESCO→O*NET. Os códigos ESCO mudam entre versões: a API dá 2512.3 para "software developer", mas na tabela
  2512.3 é "software architect". A busca exige código e título.
- **Tabela BLS ISCO-08↔SOC:** não foi obtida. O site bloqueia acesso automatizado e o bloqueio não foi
  contornado. Fica como download manual, com o novo comando `import-crosswalk`.
- **Benchmark de pares de ocupações:** 148 pares (10 originais + 138 com rótulos de fontes oficiais).
  Calibração de títulos: piso 0,776, teto 0,823. Antes era 0,812–0,813, ou seja, degenerada.
- **Componente de tarefas e habilidades:** `Φ(z) × proximidade ao melhor candidato`, contra 150 ocupações
  nulas. Uma versão intermediária só com Φ(z) saturava: classificou como "forte" o falso amigo 51-9162
  (programador de máquinas CNC). Ela foi descartada antes da publicação, e os registros dessa rodada foram
  removidos do banco com registro no log de auditoria.
- **Busca de candidatos:** alvos da tabela oficial mais as 8 ocupações O*NET mais próximas. As 5 melhores são
  gravadas para revisão. Quando há empate, os priors são combinados com penalidade de incerteza.
- **Bug corrigido no fingerprint:** `crosswalk/engine.py` e `exposure/engine.py` colidiam pelo nome do arquivo.

### Resultados

| Fonte | Melhor candidato O*NET | Confiança | Situação | Priors E6–E10 |
|---|---|---|---|---|
| ESCO software developer | 15-1299.08 Computer Systems Engineers/Architects | 0,93 | não ambíguo (margem 0,05) | transferidos |
| CBO 2124-05 | 15-1253.00 QA Analysts e 15-1299.08 (empate) | 0,80 / 0,79 | ambíguo (margem 0,005) | média dos dois |

| Base | OAE | OAP | OAuP | OTP | E14 médio (0.2.0 → 0.3.0) |
|---|---|---|---|---|---|
| O*NET 15-1252.00 | 0,71 [0,67–0,75] | 0,07 | 0,43 | 0,30 | 0,25 → 0,25 |
| ESCO | 0,79 [0,73–0,84] | 0,04 | 0,43 [0,36–0,51] | 0,31 | 0,79 → 0,56 |
| CBO 2124-05 | 0,76 [0,72–0,80] | 0,05 | 0,40 [0,36–0,44] | 0,27 | 0,77 → 0,64 |

As tarefas da ESCO e da CBO saíram de "evidência insuficiente" (cerca de 80–93% do peso) para "aumento de
capacidade" (87–94%). As três bases agora concordam: aumento claramente acima da automação.

### Limitação que o resultado expõe

Distinguir **ocupações vizinhas da mesma família** continua frágil. O equivalente canônico de "software
developer"/"Analista de desenvolvimento de sistemas" é 15-1252.00 (Software Developers), mas ele ficou em 3º
nos dois casos. A margem da ESCO (0,05) passou o limiar de ambiguidade (0,03), então a escolha automática foi
para 15-1299.08. Como as ocupações de computação têm descritores de contexto parecidos, o efeito nos priors é
pequeno, mas o mapeamento deve ser **revisado por uma pessoa**, que pode aceitar 15-1252.00 pela API.
Possíveis ajustes, a validar no conjunto ouro:

- elevar a margem de ambiguidade;
- comparar tarefas ESCO→O*NET pelas descrições das competências, e não só pelos títulos;
- dar peso à multiplicidade da tabela oficial.

### Pendências que dependem de você

- Baixar manualmente a tabela BLS ISCO-08↔SOC e a tábua CBO↔CIUO (reCAPTCHA) e importar com
  `python -m observatory.cli import-crosswalk`.
- Revisar os mapeamentos propostos (`POST /api/crosswalks/{id}/review`).

---

## Adendo 4 — tabelas ISCO do ILO e hierarquia por cadeia, metodologia 0.3.1 (run `20261102T202544Z-90ed9f`)

As tabelas que você baixou em `data/raw/crosswalks/isco/` são do **ILO**: correspondência ISCO-08↔ISCO-88
(nos dois sentidos), estrutura ISCO-08/88/68/58 e o índice ISCO-08. **Não** são a tabela da BLS ISCO-08↔SOC.

O que foi feito:

- A correspondência ISCO-08↔ISCO-88 (678 linhas) foi importada no formato canônico, com os zeros à esquerda
  restaurados (o Excel guardava 0110 como 110). A ponte SOC 2010 → O*NET-SOC 2019, do O*NET, também foi importada.
- O motor de crosswalk passou a percorrer **cadeias de tabelas oficiais** (até 3 saltos). Se nenhuma cadeia
  liga os dois sistemas, a hierarquia fica "desconhecida". Nada é inferido por códigos parecidos.
- Tentei obter a correspondência COD↔CBO do IBGE/CONCLA: o site responde 403 a acesso automatizado.

Resultado: **idêntico à 0.3.0**. Faltam os dois elos que fecham as cadeias:

| Cadeia | Elo que falta | Onde obter |
|---|---|---|
| ESCO/ISCO-08 → SOC 2010 → O*NET-SOC 2019 | ISCO-08 ↔ SOC 2010 | BLS, "ISCO-08 to 2010 SOC crosswalk" (`bls.gov/soc`) |
| CBO 2002 → ISCO-88 → ISCO-08 (ESCO) | CBO 2002 ↔ CIUO-88 (ou COD ↔ CBO) | MTE "Tábua de conversão" (reCAPTCHA) ou IBGE/CONCLA |

Com esses arquivos em `data/raw/crosswalks/`, basta rodar `import-crosswalk` (exemplos em
`docs/data-sources.md`) e a fatia vertical. O componente de hierarquia deixa de ser desconhecido para
CBO→O*NET e CBO→ESCO, e passa a ter uma segunda fonte oficial para ESCO→O*NET.

---

## Adendo 5 — cadeias oficiais fechadas, metodologia 0.3.2 (run `20261102T205907Z-b168d0`)

Fontes adicionadas (baixadas manualmente por você):

- **BLS ISCO-08 → SOC 2010** (`ISCO_SOC_Crosswalk.xls`): 1.125 linhas importadas.
- **Livros oficiais da CBO 2002** (MTE, 3ª ed., 2010, vol. 1–2): o novo extrator `import-cbo-books` lê o campo
  "CÓDIGO INTERNACIONAL CIUO 88" de cada família, que é a correspondência publicada pelo próprio MTE.
  601 de 627 famílias, 738 ligações, todas validadas contra a lista ILO de unidades ISCO-88. Família 2124 → 2131
  ("Creadores y analistas de sistemas informáticos"). Os livros também dão às ocupações CBO a descrição
  sumária, a formação e experiência, as condições gerais de exercício e os recursos de trabalho.
- O volume 3 e as pastas `publico-geral`/`usuario-medio` trazem a tábua **CBO 94 → CBO 2002**, conversão entre
  versões da própria CBO; não servem para ligar ao ISCO e não foram usados.

Mudanças metodológicas (0.3.2):

- **Hierarquia por votos de fontes oficiais**, com divergências registradas.
- **Cadeias de até 4 saltos.** A primeira execução tinha um bug: a busca podia desviar por um sistema já
  visitado (ISCO-08 → ISCO-88 → *outra* unidade ISCO-08 → …), o que afrouxava a correspondência e deu
  hierarquia 1,0 a 15-1299.08. Corrigi antes da publicação (há teste de regressão) e removi os registros
  daquela execução, com registro no log de auditoria.

### Resultados

| Crosswalk | Antes (0.3.1) | 0.3.2 | Hierarquia |
|---|---|---|---|
| ESCO → 15-1252.00 Software Developers | 0,878 (3º) | 0,878, **empatado em 1º** | 1,0 (as duas fontes concordam) |
| ESCO → 15-1299.08 | 0,929 (1º) | 0,879 | 0,5 (tabela O*NET: sim; cadeia BLS: não) |
| CBO 2124-05 → melhor O*NET (15-1253.00) | 0,796 | 0,846 | 1,0 (antes desconhecido) |
| CBO 2124-05 → ESCO | 0,65 | 0,70 | 1,0 (antes desconhecido) |

| Base | OAE | OAP | OAuP | E14 médio | Priors |
|---|---|---|---|---|---|
| O*NET | 0,71 | 0,07 | 0,43 | 0,25 | diretos |
| ESCO | 0,79 | 0,05 | 0,43 | 0,63 | média de 15-1299.08 e 15-1252.00 (empate) |
| CBO 2124-05 | 0,76 | 0,05 | 0,40 | 0,62 | média de 15-1253.00 e 15-1299.08 (empate) |

Os escores mudam pouco (as ocupações de computação têm contextos de trabalho parecidos), mas a proveniência
melhorou. A ESCO agora inclui o equivalente canônico 15-1252.00 na média, e a hierarquia CBO deixou de ser
desconhecida. O empate em ambos os casos é real e está sinalizado: uma revisão humana deve escolher o
equivalente pela API.

A cadeia CBO → O*NET é larga: a CIUO-88 2131 corresponde a várias unidades ISCO-08 e, por elas, a várias
ocupações O*NET de computação. Por isso o componente de hierarquia confirma a família, mas não escolhe entre
vizinhos; essa escolha vem das tarefas e da revisão humana.

---

## Adendo 6 — decisões humanas aplicadas e comparação entre quatro ocupações (metodologia 0.3.2)

### Revisão de crosswalks

Decisões registradas por Alexandre na página `/crosswalks`:

- ESCO "software developer" → 15-1252.00 Software Developers.
- CBO 2124-05 → 15-1253.00 Software QA Analysts and Testers. É a sugestão automática da página; minha
  recomendação era 15-1252.00.

Na execução seguinte, os priors passaram a vir das ocupações aceitas. A incerteza média caiu de 0,63 para
0,57 (ESCO) e de 0,62 para 0,56 (CBO).

A chave administrativa não carregava porque a instrução `echo ... >> .env` grava UTF-16 no PowerShell. Isso foi
corrigido: o comando `admin-key` gera a chave, o `.env` é lido em qualquer codificação e o texto de exemplo é
recusado.

### Cobertura: `python -m observatory.cli coverage`

Quatro conjuntos CBO + ESCO + O*NET (tabela completa em `artifacts/reports/coverage_latest.md`):

| Conjunto | O*NET OAE | ESCO OAE | CBO OAE | OAP (3 bases) | Classe predominante no O*NET |
|---|---|---|---|---|---|
| Desenvolvimento de sistemas | 0,71 | 0,79 | 0,76 | 0,06–0,07 | aumento (81%) |
| Contabilidade | 0,63 | 0,71 | 0,74 | 0,06 | aumento (76%) |
| Eletricista de instalações | 0,50 | 0,59 | 0,66 | 0,00 | aumento (52%) |
| Técnico de enfermagem | 0,44 | 0,59 | 0,56 | 0,01 | apoio pontual (80%) |

**O que funciona:** no O*NET, o índice ordena os perfis de forma plausível (cognitivo > manual e saúde). A
automação é praticamente nula onde há presença física e responsabilidade.

**Viés encontrado:** CBO e ESCO ficam sistematicamente 0,08–0,16 acima do O*NET. A causa provável é que
as tarefas CBO/ESCO não têm uso observado (E3 ausente), e o peso de E3 é redistribuído para E1/E2/E11, que
tendem a ser altos. Nas tarefas O*NET, a ausência na amostra entra como 0 e puxa o índice para baixo. Correção
proposta para a próxima versão: dar às tarefas CBO/ESCO a distribuição de uso observado da ocupação O*NET
equivalente (aceita ou transferida), com a incerteza correspondente, em vez de redistribuir o peso.

**Crosswalks novos:**

- Contabilidade, eletricista e técnico de enfermagem: CBO e ESCO ligam ao O*NET esperado (13-2011, 47-2111,
  29-2061), sem ambiguidade.
- **ESCO "nurse assistant" → 31-1133 Psychiatric Aides (0,93)** foi escolhido automaticamente. O equivalente
  natural é 31-1131 Nursing Assistants (0,82). Precisa de revisão humana.
- **CBO técnico de enfermagem × ESCO nurse assistant:** hierarquia 0 e confiança 0,57, não aceito. Isso reflete
  uma diferença real: no Brasil a profissão é de nível técnico (CIUO-88 3231 → ISCO-08 3221), e a ESCO só tem
  ocupação individual no grupo 5321 (auxiliares).

**Correção no conector ESCO:** ocupações ESCO mais específicas não trazem o vínculo com o grupo ISCO. O grupo
passa a ser obtido pelo prefixo do código ESCO (convenção da própria ESCO, ex.: 5321.1.1 → 5321), com o
método registrado em `isco_group_method`.

**Limitação:** as figuras da área "Sobre" mostram a última ocupação avaliada. Figuras por ocupação ficam para
a interface da fase 7.
