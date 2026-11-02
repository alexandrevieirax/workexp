# Fundamentos de pesquisa

> Documento vivo. Versão metodológica de referência: **0.1.0**.
> Todas as referências estão em `docs/references/references.json` (CSL JSON).
> **Status de verificação:** as referências foram compiladas a partir do conhecimento
> prévio do autor do rascunho (assistente de IA) e estão marcadas como
> `pending_human_check` até que uma pessoa confirme DOI, páginas e versão.
> Nenhuma referência deve ser citada externamente antes dessa conferência.

## 1. Pergunta central

Em que medida as **tarefas** que compõem uma ocupação podem ser executadas,
apoiadas ou transformadas por sistemas de IA — e o que isso implica para
perfis profissionais e currículos — **sem confundir exposição com substituição**?

## 2. Linhas de pesquisa que fundamentam o sistema

### 2.1 Abordagem baseada em tarefas (task-based approach)

- Autor, Levy & Murnane (2003) [`autor2003skill`] — decomposição do trabalho em
  tarefas rotineiras/não rotineiras, cognitivas/manuais. Base para separar a
  unidade de análise (tarefa) do título da ocupação.
- Acemoglu & Autor (2011) [`acemoglu2011skills`] — modelo de tarefas e
  alocação entre capital e trabalho; distingue deslocamento de reintegração.
- Autor & Dorn (2013) [`autor2013growth`] — Routine Task Intensity (RTI),
  usado aqui na **validação de construto** (o índice não deve apenas reproduzir RTI).

**Implicação de projeto:** a pontuação é calculada por tarefa e agregada por
pesos de importância/relevância/frequência (seção 8 da metodologia).

### 2.2 Índices de exposição ocupacional à IA

| Estudo | Unidade | Mecanismo | Uso no observatório |
|---|---|---|---|
| Felten, Raj & Seamans (2021) — AIOE [`felten2021occupational`] | habilidades O*NET | ligação aplicações de IA × habilidades por avaliação coletiva | validação de construto |
| Webb (2020) [`webb2020impact`] | tarefas O*NET | sobreposição verbo-objeto entre patentes e tarefas | validação de construto (indicador por patentes); *working paper* |
| Brynjolfsson, Mitchell & Rock (2018) — SML [`brynjolfsson2018what`] | tarefas/DWAs | rubrica de "suitability for machine learning" | inspiração da rubrica E2 |
| Eloundou et al. (2024) — "GPTs are GPTs" [`eloundou2024gpts`] | tarefas O*NET | rubrica E0/E1/E2 por humanos e por GPT-4 | validação de construto; inspira a separação exposição ≠ impacto |
| Gmyrek, Berg & Bescond (2023); Gmyrek et al. (2025) — OIT [`gmyrek2023generative`, `gmyrek2025refined`] | tarefas ISCO | pontuação por LLM + validação humana; foco em **aumento** vs automação | ancoragem internacional, ISCO |
| Frey & Osborne (2017) [`frey2017future`]; Arntz, Gregory & Zierahn (2016) [`arntz2016risk`] | ocupação vs tarefa | probabilidade de automação | contraexemplo metodológico: mostra o viés de analisar só a ocupação |

**Implicação de projeto:** nenhum desses índices é tratado como "verdade";
eles são **comparadores** na validação de construto (seção 10.2 do prompt de
requisitos). LLMs não são fonte única (princípio 1.6).

### 2.3 Uso observado

- Handa et al. (2025) — Anthropic Economic Index [`handa2025which`] —
  mapeia conversações reais com Claude a tarefas O*NET, com distinção entre
  padrões de **automação** (directive, feedback loop) e **aumento**
  (validation, task iteration, learning). *Preprint.* Dados públicos usados como
  fonte E3 (release 2025-03-27).
- Tamkin et al. (2024) — Clio [`tamkin2024clio`] — método de agregação com
  preservação de privacidade que gera os dados do Economic Index. *Preprint.*

**Cautelas registradas:** amostra de uma única família de modelos e de uma
plataforma; usuários não representam a força de trabalho; tarefas ausentes da
amostra **não** significam uso zero (ver `methodology-v0.md`, E3).

### 2.4 Evidência experimental de produtividade

- Noy & Zhang (2023) [`noy2023experimental`] — escrita profissional; ganhos
  maiores para trabalhadores de menor desempenho inicial.
- Brynjolfsson, Li & Raymond (2025) [`brynjolfsson2025generative`] —
  atendimento ao cliente; efeito de **aumento** e nivelamento.
- Peng et al. (2023) [`peng2023impact`] — programação com assistente de código. *Preprint.*
- Dell'Acqua et al. (2023) [`dellacqua2023navigating`] — "fronteira tecnológica
  irregular": a mesma ferramenta melhora tarefas dentro da fronteira e piora
  fora dela. *Working paper.* Justifica a dimensão E14 (incerteza) e a classe
  "evidência insuficiente".

### 2.5 Relatórios de organismos multilaterais e sínteses

- OECD Employment Outlook 2023 [`oecd2023employment`].
- Stanford HAI AI Index Report 2025 [`maslej2025aiindex`] — benchmarks e
  maturidade técnica (insumo para E11).
- Acemoglu (2025) [`acemoglu2025simple`] — limites macroeconômicos; lembra
  que exposição técnica ≠ adoção ≠ impacto.

### 2.6 Embeddings e recuperação semântica

- Reimers & Gurevych (2019, 2020) [`reimers2019sentence`, `reimers2020making`].
- Wang et al. (2024) — multilingual-E5 [`wang2024multilingual`]. *Preprint/relatório técnico.*
- Chen et al. (2024) — BGE-M3 [`chen2024bge`]. *Preprint.*
- Muennighoff et al. (2023) — MTEB [`muennighoff2023mteb`] — rankings
  genéricos **não** substituem o benchmark específico do domínio.
- Järvelin & Kekäläinen (2002) — nDCG [`jarvelin2002cumulated`].

### 2.7 Confiabilidade e governança

- Cohen (1960) [`cohen1960coefficient`]; Krippendorff (2018) [`krippendorff2018content`].
- Mitchell et al. (2019) — Model Cards [`mitchell2019model`].
- Gebru et al. (2021) — Datasheets for Datasets [`gebru2021datasheets`].

## 3. Hierarquia de evidências adotada

1. Artigos revisados por pares.
2. Documentos técnicos dos autores do modelo.
3. Relatórios de organismos multilaterais.
4. Documentação oficial.
5. Preprints e *working papers* — sempre marcados como `peer_reviewed: false`.

Blogs comerciais e materiais promocionais não são fundamento principal.

## 4. Lacunas conhecidas

- Não há base pública de **tarefas** CBO com importância/frequência
  comparáveis ao O*NET; a CBO descreve atividades por **família** ocupacional.
- Uso observado (E3) existe essencialmente para tarefas O*NET em inglês; para
  CBO/ESCO depende de crosswalk, o que propaga incerteza.
- Não há conjunto ouro público para pares tarefa–capacidade de IA em português;
  o conjunto inicial deste repositório é um **rascunho** que requer anotação humana.
