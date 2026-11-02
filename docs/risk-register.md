# Registro de riscos

Escala: Probabilidade (P) e Impacto (I) de 1 a 5. Revisar a cada release metodológica.

| ID | Risco | P | I | Mitigação implementada | Mitigação pendente | Responsável |
|---|---|---|---|---|---|---|
| R01 | Exposição interpretada como risco de desemprego ou substituição | 4 | 5 | Aviso fixo em toda página com pontuação; separação OAE/OAP/OAuP/OTP; seção "O que o índice não mede" | Teste de usabilidade com público-alvo | Coordenação metodológica |
| R02 | Rankings sem contexto | 4 | 4 | Dashboard exibe intervalo e incerteza junto de cada valor | Proibir exportação de ranking sem colunas de incerteza | Produto |
| R03 | LLM usado como fonte única de verdade | 3 | 5 | E1 por embeddings + priors revisáveis + uso observado; nenhuma dimensão vem só de LLM | Painel de especialistas para E2/E11 | Ciência de dados |
| R04 | Crosswalk espúrio por similaridade de título | 4 | 4 | Título pesa 0,20; nenhuma aceitação automática; falsos amigos no benchmark | Calibração com pares validados | Ontologias |
| R05 | Modelo de embeddings de linha de base (lexical) inadequado para português↔inglês | 5 | 4 | Marcado na interface; incerteza +; provedor Sentence Transformers pronto | Instalar e avaliar multilingual-e5-large e BGE-M3 | ML |
| R06 | Viés linguístico: O*NET (en) domina evidências | 5 | 3 | E3 = ausente (não zero) para CBO/ESCO; prior transferido sinalizado | Fontes de uso observado em português | Pesquisa |
| R07 | Viés geográfico: uso observado de uma plataforma e de países de alta renda | 4 | 4 | Documentado no data card do AEI | Fontes adicionais; ponderação por país | Pesquisa |
| R08 | Viés ocupacional: tarefas físicas sub-representadas nos exemplos | 3 | 3 | Benchmark com tarefas manuais e físicas | Ampliar famílias G (robótica) | Ontologias |
| R09 | Priors de capacidades de IA desatualizados | 4 | 4 | Campo `valid_until` por capacidade; alerta na interface quando vencido | Rotina semestral de revisão | Comitê |
| R10 | Dados suprimidos do O*NET usados indevidamente | 2 | 3 | `Recommend Suppress = Y` → ausente; teste automatizado | — | Engenharia de dados |
| R11 | Mistura de escalas diferentes | 2 | 4 | Normalização por escala com Scales Reference; teste que rejeita escala desconhecida | — | Engenharia de dados |
| R12 | Documentação "Sobre" divergente do código | 3 | 4 | Conteúdo gerado do YAML; teste de impressão digital | CI obrigatório | Engenharia |
| R13 | Recomendação curricular de exclusão automática | 2 | 5 | Regra: exclusão só com validação humana (módulo curricular, fase 8) | Implementar fluxo de aprovação | Coordenação pedagógica |
| R14 | Uso para avaliar pessoas individualmente | 2 | 5 | Sem dados pessoais no modelo; política de uso responsável | Termos de uso no login | Governança |
| R15 | Dados de terceiros com licença mal registrada | 3 | 3 | Licença por `source_version` | Revisão jurídica (AEI, CBO) | Governança |
| R16 | Fabricação de dados reais quando a fonte falha | 2 | 5 | Conectores falham explicitamente; sintéticos marcados e isolados em testes | — | Engenharia |
| R17 | Referências bibliográficas imprecisas | 3 | 3 | Status `pending_human_check` em todas | Conferência de DOI/páginas | Pesquisa |
| R18 | Conjunto de validação rotulado por IA tomado como ouro | 4 | 4 | Rótulos marcados `annotator: ai_draft`, `gold: false` | Anotação por ≥2 especialistas + kappa | Pesquisa |
