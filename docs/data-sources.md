# Fontes de dados — inventário

| Código | Fonte | Publicador | Versão usada | Acesso | Licença | Status |
|---|---|---|---|---|---|---|
| `ONET` | O*NET Database (text) | U.S. DOL / O*NET Resource Center | 31.0 (agosto/2026) | download automático | CC BY 4.0 | ✅ conector + carga |
| `ESCO` | ESCO API | Comissão Europeia | versão padrão da API na data de obtenção | API REST pública | CC BY 4.0 (ver termos ESCO) | ✅ conector API; ⏳ carga em massa (CSV oficial) |
| `CBO` | Classificação Brasileira de Ocupações 2002 | Ministério do Trabalho e Emprego | arquivo "Estrutura CBO (CSV)" | **download manual** (reCAPTCHA) | dados públicos governamentais — confirmar termos | ✅ conector de arquivo; ⏳ arquivo não obtido |
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

Esquema esperado (separador `;`, codificação ISO-8859-1 ou UTF-8; o conector
detecta). Os nomes de colunas abaixo são o layout conhecido; a validação
informa colunas ausentes em vez de adivinhar:

| Arquivo (padrão do nome) | Colunas mínimas |
|---|---|
| `*Ocupacao*.csv` | `CODIGO`, `TITULO` |
| `*Familia*.csv` | `CODIGO`, `TITULO` |
| `*Sinonimo*.csv` | `OCUPACAO`, `SINONIMO` |
| `*PerfilOcupacional*.csv` | `COD_FAMILIA`, `COD_OCUPACAO`, `SGL_GRANDE_AREA`, `NOME_GRANDE_AREA`, `COD_ATIVIDADE`, `NOME_ATIVIDADE` |

Descrição sumária, formação/experiência e condições gerais de exercício
**não** fazem parte do ZIP de estrutura; estão nas páginas de família do portal
e na publicação "CBO 2002 — Livro". O conector registra esses campos como
`not_available_in_source_file`.

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
