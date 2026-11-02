---
methodology_version: 0.3.0
language: pt-BR
---

## 1. Objetivo do sistema {#objetivo}

O observatório estima, de forma explicável e auditável, **em que medida as tarefas** que compõem ocupações
das bases CBO, ESCO e O*NET correspondem a capacidades atuais de inteligência artificial, e o que isso implica
para perfis profissionais e currículos. Ele apoia o planejamento educacional e a pesquisa; **não** avalia pessoas.

## 2. Definição de exposição à IA {#definicao}

Exposição é o grau em que o conteúdo de uma tarefa corresponde a capacidades técnicas de IA demonstradas,
combinado com evidências de uso observado e de maturidade tecnológica [@eloundou2024gpts; @felten2021occupational].
Distinguimos:

- **exposição potencial** — correspondência técnica (E1, E2, E11);
- **exposição observada** — uso real registrado (E3) [@handa2025which];
- **automação** — execução com mínima intervenção humana (OAP);
- **aumento de capacidade** — a IA amplia o trabalho humano, que mantém julgamento e responsabilidade (OAuP);
- **transformação** — mudança relevante na forma de execução (OTP).

## 3. O que o índice mede {#mede}

{{indices_table}}

## 4. O que o índice não mede {#nao-mede}

- Não mede risco de desemprego, substituição de trabalhadores nem desaparecimento de profissões.
- Não mede adoção efetiva nas organizações brasileiras.
- Não mede competência, desempenho ou empregabilidade de pessoas.
- Não implica obsolescência de competências: uma tarefa muito exposta pode exigir **mais** formação
  (supervisão, validação, governança) [@dellacqua2023navigating].
- Não estabelece causalidade [@acemoglu2025simple].

## 5. Arquitetura conceitual {#arquitetura}

A unidade de análise é a **tarefa** [@autor2003skill; @acemoglu2011skills]. Cada tarefa é comparada com o
dicionário de capacidades de IA, recebe 14 dimensões (E1–E14), quatro resultados sintéticos e uma classe.
O índice da ocupação é a soma ponderada das tarefas.

{{figure:flow}}

{{figure:relation}}

{{figure:er}}

## 6. Fontes de dados {#fontes}

{{sources_table}}

A CBO exige download manual (reCAPTCHA no portal do MTE); o sistema não contorna CAPTCHAs e não fabrica
registros. Procedimento em `docs/data-sources.md`.

## 7. Processo de harmonização {#harmonizacao}

O crosswalk CBO–ESCO–O*NET combina cinco componentes com pesos configuráveis. Nenhuma correspondência é
aceita automaticamente; todas nascem como `proposed` e exigem revisão humana com justificativa e histórico.
Títulos semelhantes não bastam: o título pesa apenas 20%. Cada ocupação ESCO/CBO é comparada com vários
candidatos do O*NET: os da tabela oficial ESCO→O*NET-SOC publicada pelo O*NET e os mais próximos por título e
descrição. Quando os melhores empatam, o mapeamento é marcado como ambíguo e a escolha fica para revisão
humana.

{{crosswalk_weights}}

{{figure:crosswalk}}

## 8. Dicionário de capacidades de IA {#dicionario}

{{capability_summary}}

## 9. Modelo de embeddings {#embeddings}

{{embedding_summary}}

Rankings genéricos não substituem o benchmark do domínio [@muennighoff2023mteb]. Na versão 0.2.0 foram
comparados, com regra de seleção registrada antes dos resultados (ADR 0002), a linha de base lexical,
paraphrase-multilingual-mpnet-base-v2 [@reimers2020making], multilingual-E5-large [@wang2024multilingual] e
BGE-M3 [@chen2024bge]. O modelo escolhido tem o *snapshot* fixado na configuração; a escolha é provisória até
existir um conjunto ouro anotado por especialistas.

## 10. Fórmulas {#formulas}

{{formulas}}

{{figure:calculation}}

{{figure:automation_augmentation}}

## 11. Validação {#validacao}

Três níveis: (1) semântica — conjunto ouro, concordância entre avaliadores (κ de Cohen, α de Krippendorff)
[@cohen1960coefficient; @krippendorff2018content]; (2) de construto — comparação com AIOE, índices baseados
em GPT, patentes e Routine Task Intensity [@felten2021occupational; @eloundou2024gpts; @webb2020impact;
@autor2013growth]; (3) preditiva/externa — quando houver dados de adoção. Situação atual:

{{benchmark_summary}}

## 12. Incertezas {#incertezas}

Cada tarefa recebe E14 (incerteza) a partir de fontes explícitas de fragilidade. O índice ocupacional traz
intervalo de 90% por Monte Carlo e análise de sensibilidade de ±20% em cada peso.

{{uncertainty_weights}}

{{figure:uncertainty}}

{{figure:sensitivity}}

## 13. Limitações {#limitacoes}

- Pesos e limiares são hipóteses iniciais **não calibradas**.
- O modelo de embeddings padrão é uma linha de base lexical, frágil entre idiomas.
- Priors do dicionário de capacidades ainda não foram revisados por especialistas.
- O uso observado vem de uma única plataforma e família de modelos; tarefas ausentes da amostra não
  significam uso zero.
- ESCO e CBO não publicam importância/frequência de tarefas: pesos uniformes.
- A CBO descreve atividades por família ocupacional, não por ocupação.

## 14. Aspectos éticos {#etica}

O sistema não classifica pessoas, não recomenda demissões, não usa atributos pessoais sensíveis e não
apresenta exposição como risco certo de desemprego. Rankings são sempre exibidos com intervalo e incerteza.
Documentação: model card, data cards e registro de riscos [@mitchell2019model; @gebru2021datasheets].

## 15. Aplicação curricular {#curricular}

Na fase 8, elementos curriculares (competências, capacidades, resultados de aprendizagem) serão relacionados
às tarefas e estas às capacidades de IA, gerando índices de cobertura e recomendações rastreáveis.
Nenhuma competência será excluída automaticamente: exclusão exige validação humana.

{{figure:curriculum}}

## 16. Histórico de versões {#versoes}

{{changelog}}

## 17. Referências científicas {#referencias}

{{references}}

## 18. Glossário {#glossario}

- **Tarefa**: unidade de trabalho descrita pela fonte (O*NET Task, atividade CBO, competência ESCO).
- **Capacidade de IA**: função técnica operacionalmente definida no dicionário versionado.
- **Prior**: valor inicial de especialista, revisável, usado na ausência de medição direta.
- **Crosswalk**: correspondência entre ocupações de taxonomias diferentes.
- **Fingerprint metodológico**: hash que liga resultados à configuração, às fórmulas e ao dicionário.

## 19. Licenças {#licencas}

{{licenses}}

## 20. Canal de contribuição e contestação {#contestacao}

Qualquer pessoa pode contestar uma pontuação, um crosswalk ou uma referência abrindo uma *issue* no
repositório com: ocupação/tarefa, versão metodológica, evidência e justificativa. Correções seguem a
política descrita em `CONTRIBUTING.md` e geram nova versão quando alteram a metodologia.
