# Comparação entre ocupações — metodologia 0.4.0

Gerado em 2026-11-03T13:33:33.779448+00:00. Intervalos de 90% por Monte Carlo. Exposição não é risco de desemprego.

| Conjunto | Perfil | Base | Ocupação | OAE | OAP | OAuP | OTP | E14 | Priors | Classe predominante |
|---|---|---|---|---|---|---|---|---|---|---|
| desenvolvimento-de-sistemas | cognitiva (TI) | ONET | Software Developers | 0.71 [0.67–0.75] | 0.07 | 0.43 | 0.30 | 0.25 | onet_direct | augmentation (81%) |
| desenvolvimento-de-sistemas | cognitiva (TI) | ESCO | software developer | 0.78 [0.74–0.82] | 0.06 | 0.43 | 0.31 | 0.49 | crosswalk_transfer (15-1252.00) | augmentation (87%) |
| desenvolvimento-de-sistemas | cognitiva (TI) | CBO | Analista de desenvolvimento de sistemas | 0.69 [0.65–0.73] | 0.06 | 0.35 | 0.24 | 0.48 | crosswalk_transfer (15-1253.00) | augmentation (95%) |
| contabilidade | cognitiva (não TI) | ONET | Accountants and Auditors | 0.63 [0.56–0.68] | 0.06 | 0.29 | 0.20 | 0.24 | onet_direct | augmentation (76%) |
| contabilidade | cognitiva (não TI) | ESCO | accountant | 0.64 [0.59–0.68] | 0.05 | 0.28 | 0.18 | 0.35 | crosswalk_transfer (13-2011.00) | augmentation (60%) |
| contabilidade | cognitiva (não TI) | CBO | Contador | 0.63 [0.57–0.68] | 0.05 | 0.30 | 0.20 | 0.43 | crosswalk_transfer (13-2011.00) | augmentation (84%) |
| eletricista | manual | ONET | Electricians | 0.50 [0.44–0.56] | 0.00 | 0.27 | 0.14 | 0.24 | onet_direct | augmentation (52%) |
| eletricista | manual | ESCO | domestic electrician | 0.48 [0.42–0.54] | 0.00 | 0.26 | 0.13 | 0.35 | crosswalk_transfer (47-2111.00) | augmentation (60%) |
| eletricista | manual | CBO | Eletricista de instalações (edifícios) | 0.54 [0.47–0.60] | 0.00 | 0.29 | 0.16 | 0.44 | crosswalk_transfer (47-2111.00) | augmentation (75%) |
| tecnico-de-enfermagem | saúde, regulamentada | ONET | Licensed Practical and Licensed Vocational Nurses | 0.44 [0.38–0.49] | 0.01 | 0.22 | 0.13 | 0.24 | onet_direct | point_support (80%) |
| tecnico-de-enfermagem | saúde, regulamentada | ESCO | nurse assistant | 0.48 [0.42–0.53] | 0.01 | 0.25 | 0.15 | 0.39 | crosswalk_transfer (31-1133.00) | point_support (53%) |
| tecnico-de-enfermagem | saúde, regulamentada | CBO | Técnico de enfermagem | 0.45 [0.39–0.50] | 0.00 | 0.23 | 0.13 | 0.41 | crosswalk_transfer (29-2061.00) | point_support (69%) |

## Crosswalks

| Conjunto | Origem | Melhor candidato | Confiança | Ambíguo | Decisão humana |
|---|---|---|---|---|---|
| desenvolvimento-de-sistemas | ESCO→O*NET | ONET:15-1299.08 | 0.88 (strong) | sim | 15-1252.00: accepted |
| desenvolvimento-de-sistemas | CBO→O*NET | ONET:15-1253.00 | 0.85 (strong) | sim | 15-1253.00: accepted |
| desenvolvimento-de-sistemas | CBO→ESCO | — | 0.70 (moderate; hierarquia 1.0) | — | — |
| contabilidade | ESCO→O*NET | ONET:13-2011.00 | 1.00 (very_strong) | não | — |
| contabilidade | CBO→O*NET | ONET:13-2011.00 | 0.87 (strong) | não | — |
| contabilidade | CBO→ESCO | — | 0.70 (moderate; hierarquia 1.0) | — | — |
| eletricista | ESCO→O*NET | ONET:47-2111.00 | 0.94 (very_strong) | não | — |
| eletricista | CBO→O*NET | ONET:47-2111.00 | 0.82 (strong) | não | — |
| eletricista | CBO→ESCO | — | 0.70 (moderate; hierarquia 1.0) | — | — |
| tecnico-de-enfermagem | ESCO→O*NET | ONET:31-1133.00 | 0.93 (very_strong) | não | — |
| tecnico-de-enfermagem | CBO→O*NET | ONET:29-2061.00 | 0.86 (strong) | não | — |
| tecnico-de-enfermagem | CBO→ESCO | — | 0.57 (not_accepted_automatically; hierarquia 0.0) | — | — |
