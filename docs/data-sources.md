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

Descrição sumária, formação/experiência e condições gerais de exercício
**não** fazem parte do ZIP de estrutura; estão nas páginas de família do portal
e na publicação "CBO 2002 — Livro". O conector registra esses campos como
`not_available_in_source_file`.

## Tabelas oficiais de correspondência (crosswalks)

| Tabela | Publicador | Status | Uso |
|---|---|---|---|
| `ESCO_to_ONET-SOC.xlsx` | O*NET Resource Center | ✅ baixada (2026-11-02), `data/raw/crosswalks/source/` | hierarquia ESCO→O*NET e candidatos |
| `2010_to_2019_Crosswalk.csv` | O*NET Resource Center | ✅ baixada; ainda não usada | ponte SOC 2010→2018 (ex.: ligar o AEI por ID de tarefa) |
| ISCO-08↔SOC 2010 | BLS | ⏳ **download manual** (o site bloqueia acesso automatizado) | hierarquia genérica |
| Tábua de conversão CBO 2002↔CIUO-88 | MTE | ⏳ **download manual** (reCAPTCHA) | hierarquia CBO→ISCO |

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
