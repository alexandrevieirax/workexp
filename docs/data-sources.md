# Fontes de dados — inventário

| Código | Fonte | Publicador | Versão usada | Acesso | Licença | Status |
|---|---|---|---|---|---|---|
| `ONET` | O*NET Database (text) | U.S. DOL / O*NET Resource Center | 31.0 (agosto/2026) | download automático | CC BY 4.0 | ✅ conector + carga |
| `ESCO` | ESCO API | Comissão Europeia | versão padrão da API na data de obtenção | API REST pública | CC BY 4.0 (ver termos ESCO) | ✅ conector API; ⏳ carga em massa (CSV oficial) |
| `CBO` | Classificação Brasileira de Ocupações 2002 | Ministério do Trabalho e Emprego | arquivo "Estrutura CBO (CSV)" | **download manual** (reCAPTCHA) | dados públicos governamentais — confirmar termos | ✅ conector de arquivo + carga (obtido em 2026-11-02) |
| `AEI` | Anthropic Economic Index | Anthropic (Hugging Face `Anthropic/EconomicIndex`) | release_2025_03_27 | download automático | verificar no cartão do dataset | ✅ conector + carga (E3) |

A data e o hash SHA-256 de cada arquivo são gravados em `source_version`
no momento da carga; nada é reconstruído a partir de memória.

## O*NET 31.0

- URL: `https://www.onetcenter.org/dl_files/database/db_31_0_text.zip`
- Diretório: `data/raw/onet/31.0/db_31_0_text.zip`
- Arquivos usados: `Occupation Data`, `Task Statements`, `Task Ratings`,
  `Task Categories`, `Scales Reference`, `Work Context`, `Work Activities`,
  `Knowledge`, `Essential Skills`, `Transferable Skills`, `Abilities`,
  `Job Zones`, `Tasks to DWAs`, `Emerging Tasks`, `Alternate/Job Titles`.
- **Mudança de estrutura no 31.0:** o arquivo `Skills.txt` das versões
  anteriores foi substituído por `Essential Skills.txt` e
  `Transferable Skills.txt`. O conector aceita ambos os layouts.
- Preservados por linha: N, erro padrão, IC inferior/superior,
  `Recommend Suppress`, `Not Relevant`, data e `Domain Source`.

## ESCO

- API: `https://ec.europa.eu/esco/api/resource/occupation?uri=…&language=…`
- Cache bruto: `data/raw/esco/api/<sha1(uri)>.json` (resposta integral).
- Carga em massa (pendente): baixar o pacote CSV oficial no portal ESCO
  (`https://esco.ec.europa.eu/en/use-esco/download`), versão e idioma
  escolhidos manualmente; colocar em `data/raw/esco/<versão>/`.
- Campos: URI, preferredLabel, alternativeLabel, description, código ISCO,
  broaderIscoGroup, hasEssentialSkill, hasOptionalSkill (com `skillType`).
- Ocupações ESCO mais específicas apontam para uma ocupação "mãe" (`broaderOccupation`), não para o grupo
  ISCO. Nesses casos o grupo ISCO-08 vem dos quatro primeiros dígitos do código ESCO, pela convenção da
  própria ESCO (5321.1.1 → 5321), e o método fica em `isco_group_method = esco_code_prefix`.

## CBO

O portal `cbo.mte.gov.br/cbosite/pages/downloads.jsf` protege os downloads com
**reCAPTCHA**. O sistema não contorna CAPTCHAs. Procedimento:

1. Acesse o portal da CBO → *Downloads* → "Estrutura CBO (CSV) – Arquivo ZIP".
2. Salve o ZIP em `data/raw/cbo/` (qualquer nome terminado em `.zip`) **ou**
   extraia os CSVs nessa pasta.
3. Execute `python -m observatory.cli validate-cbo` para validar o esquema.
4. Execute `python -m observatory.cli slice`.

Esquema verificado nos arquivos oficiais obtidos em 2026-11-02 (separador `;`,
ISO-8859-1, CRLF). A validação informa colunas ausentes em vez de adivinhar:

| Arquivo (sufixo do nome) | Colunas | Linhas |
|---|---|---|
| `Ocupacao.csv` | `CODIGO`, `TITULO` | 2.725 |
| `Familia.csv` | `CODIGO`, `TITULO` | 627 |
| `Sinonimo.csv` | `CODIGO` (ocupação), `TITULO` (sinônimo) → mapeados para `OCUPACAO`, `SINONIMO` | 7.870 |
| `PerfilOcupacional.csv` | `COD_GRANDE_GRUPO` … `COD_FAMILIA`, `COD_OCUPACAO`, `SGL_GRANDE_AREA`, `NOME_GRANDE_AREA`, `COD_ATIVIDADE`, `NOME_ATIVIDADE` | 192.745 |

`Grande Grupo.csv`, `SubGrupo Principal.csv` e `SubGrupo.csv` estão presentes e
ainda não são usados. Regras de transformação registradas:

- **`cbo_semicolon_in_last_field`** — 13 linhas do `PerfilOcupacional.csv` oficial têm
  `;` dentro ou ao fim do texto da atividade (última coluna). O excedente é reunido na
  última coluna e `;` finais são removidos; a contagem fica em `source_version.notes`.
- **Área Z** (`DEMONSTRAR COMPETÊNCIAS PESSOAIS`) contém atributos pessoais, não
  atividades: é gravada como `skill` do tipo `personal_competency` e **excluída das
  unidades de tarefa**. A área Y (`COMUNICAR-SE`) contém atividades e permanece.
- Espaços finais dos títulos são removidos.

Descrição sumária, formação/experiência, condições gerais de exercício e recursos de trabalho **não** fazem
parte do ZIP de estrutura. Quando `cbo_books_families.json` existe (gerado por `import-cbo-books`), o conector os
preenche no nível da família (`description_scope: family`) e a versão da fonte passa a ser
`CBO2002-estrutura-csv+livros-3a-ed-2010`.

## Tabelas oficiais de correspondência (crosswalks)

| Tabela | Publicador | Status | Uso |
|---|---|---|---|
| `ESCO_to_ONET-SOC.xlsx` | O*NET Resource Center | ✅ baixada (2026-11-02), `data/raw/crosswalks/source/` | hierarquia ESCO→O*NET e candidatos |
| `2010_to_2019_Crosswalk.csv` | O*NET Resource Center | ✅ importada como `SOC2010_to_ONETSOC2019.csv` (SOC 2010 truncado a 7 caracteres) | elo SOC 2010 → O*NET-SOC 2019 |
| `Correspondence_EN_ISCO_08_to_ISCO_88.xlsx` | ILO | ✅ baixada manualmente em `data/raw/crosswalks/isco/` e importada como `ISCO08_to_ISCO88.csv` (678 linhas, zeros à esquerda restaurados) | elo ISCO-08 ↔ ISCO-88 |
| Estrutura ISCO (`ISCO.xlsx`, `isco.csv`, índice, versão árabe) | ILO | ✅ baixada manualmente; ainda não usada | rótulos e níveis de competência ISCO |
| `ISCO_SOC_Crosswalk.xls` (ISCO-08 → SOC 2010, ago/2012, atualizada em jun/2015) | BLS | ✅ baixada manualmente e importada como `ISCO08_to_SOC2010.csv` (1.125 linhas) | elo ESCO/ISCO → O*NET |
| Livros CBO 2002, 3ª ed. 2010, volumes 1 e 2 (PDF) | MTE | ✅ baixados manualmente; `import-cbo-books` gera `CBO2002_to_ISCO88.csv` (601 famílias, 738 ligações) e `data/raw/cbo/cbo_books_families.json` | elo CBO → ISCO-88 e campos da família |
| Livro CBO volume 3 (estrutura, tábua de conversão, índice) | MTE | ✅ baixado; não usado (a tábua é CBO 94 → CBO 2002) | — |
| Tábuas "público geral" / "usuário médio" (CBO 94 → CBO 2002) | MTE | ✅ baixadas; não usadas | conversão entre versões da CBO |
| `soc_2000_to_2010_crosswalk.xls` | BLS | ✅ baixada; não usada | — |

As tabelas canônicas formam um grafo percorrido em até 4 saltos. Hoje funcionam as cadeias
ISCO-08 → SOC 2010 → O*NET-SOC 2019, CBO 2002 → ISCO-88 → ISCO-08 (ESCO) e
CBO 2002 → ISCO-88 → ISCO-08 → SOC 2010 → O*NET-SOC 2019.

**Livros da CBO.** Cada página de família traz o campo "CÓDIGO INTERNACIONAL CIUO 88": é a correspondência
publicada pelo próprio MTE. O extrator (`observatory.connectors.cbo_books`) lê também a descrição sumária, a
formação e experiência, as condições gerais de exercício e os recursos de trabalho. Todos os 738 códigos
extraídos foram validados contra a lista ILO de unidades ISCO-88. As 22 famílias criadas ou reorganizadas
depois da edição de 2010 (ex.: 2251–2253) ficam sem ligação.

```bash
python -m observatory.cli import-cbo-books data/raw/crosswalks/livro-1-portal-cbo.pdf data/raw/crosswalks/cbo2002_liv2.pdf
```

Comandos para quando os arquivos estiverem na pasta (ajuste os nomes de coluna ao arquivo baixado):

```bash
python -m observatory.cli import-crosswalk --file data/raw/crosswalks/<arquivo_bls>.xls --from-system ISCO08 --from-col "ISCO-08 Code" --from-pad 4 --to-system SOC2010 --to-col "2010 SOC Code"
```

```bash
python -m observatory.cli import-crosswalk --file data/raw/crosswalks/<tabua_cbo>.csv --from-system CBO2002 --from-col "<coluna CBO>" --to-system ISCO88 --to-col "<coluna CIUO>" --to-pad 4
```

A tabela ESCO→O*NET mapeia uma ocupação ESCO a várias ocupações O*NET (ex.: "software developer" → 8).
Os códigos ESCO mudam entre versões da ESCO: o conector exige código **e** título.

Para tabelas baixadas manualmente:

```bash
python -m observatory.cli import-crosswalk --file <arquivo> --from-system ISCO08 --from-col "<coluna>" --to-system SOC2010 --to-col "<coluna>"
```

O comando grava `data/raw/crosswalks/<de>_to_<para>.csv` no formato canônico
(`from_system, from_code, to_system, to_code, source`).

## Anthropic Economic Index

- `task_pct_v2.csv`: participação percentual de cada tarefa O*NET (texto em
  minúsculas) nas conversas amostradas.
- `automation_vs_augmentation_by_task.csv`: proporções de padrões de interação
  por tarefa (exibidas como evidência; não entram na fórmula v0).
- A release usa a taxonomia O*NET-SOC 2010 (ex.: 15-1132.00/15-1133.00 para
  desenvolvedores); os IDs de tarefa não coincidem com O*NET 31.0 (15-1252.00).
  Ligação por texto normalizado: igualdade exata ou, na falta, correspondência
  aproximada (`difflib`, razão ≥ 0,85, pré-filtro Jaccard ≥ 0,4). O método, a razão
  e o texto casado ficam registrados; correspondências aproximadas elevam E14.
  Tarefas sem correspondência ficam `absent_from_sample` (não "uso zero").
- `onet_task_statements.csv` da release é baixado para auditoria do mapeamento.

## Dados sintéticos

`tests/fixtures/synthetic/` contém arquivos **sintéticos** (títulos prefixados
com `[SINTÉTICO]`, `is_synthetic = true`) usados exclusivamente em testes.
Eles nunca são carregados pelo pipeline real.
