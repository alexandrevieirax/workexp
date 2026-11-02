# Fontes brutas (não versionadas)

- `onet/31.0/db_31_0_text.zip` — `python -m observatory.cli download-onet --version 31.0`
- `aei/release_2025_03_27/` — `python -m observatory.cli download-aei`
- `esco/api/` — cache das respostas da API (preenchido pelo pipeline)
- `cbo/` — **download manual** (reCAPTCHA); ver `docs/data-sources.md`
- `crosswalks/*.csv` — tabelas oficiais de correspondência (opcional; colunas
  `from_system,from_code,to_system,to_code,source`)
