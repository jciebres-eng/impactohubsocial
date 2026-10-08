# MASTER EXECUTION STATUS — IMPACTO v0.23.0

**Branch:** `audit/v0.23.0-completion` · **Base:** `chore/v0.19.0-vocabulary-firstrun-ops`
**Vocabulário de estado:** `TODO` `IN_PROGRESS` `BLOCKED` `FAILED` `FIXED` `PASS` `REGRESSION` `DONE` `WAIVED`

A **REGRA SUPREMA** do pacote de execução governa este arquivo: uma tarefa só é `DONE` quando as dez
condições valem — implementada, com teste automatizado onde cabe, teste **executado**, resultado
**PASS**, regressão relevante rodada, isolamento/segurança verificados onde cabe, documentação
atualizada, evidência guardada, Git atualizado com commit rastreável, e **nenhum bloqueador oculto**.

Nada aqui é marcado `PASS` por não ter sido executado. O que não rodou está `BLOCKED`, com causa
escrita em `BLOCKERS.md`.

---

## Portões

| Gate | Escopo | Estado | Evidência |
|---|---|---|---|
| **0** | Inventário | **DONE** | 1.795 arquivos rastreados conciliados com o manifesto; 16 diferenças, todas declaradas |
| **1** | Ambiente | **DONE** | PostgreSQL 16.15, Python 3.13.16, Chromium presente; npm 403 e PyPI indisponível declarados |
| **2** | Release | **DONE** | divergência de versão **real** encontrada e corrigida; 13 testes travam os quatro declarantes |
| **3** | API — 888 operações | **DONE** | `API_AUTHORIZATION_MATRIX.csv`; **883 invocadas por HTTP, 0 responderam 5xx** (5 puladas com motivo); + 33 testes de autorização, 221 chamadas de recusa |
| **4** | Motores — 42 | **DONE** | `ENGINE_VALIDATION_MATRIX.csv`, 42/42, 0 FAILED |
| **5** | Segurança | **DONE** (9 PASS · 1 BLOCKED) | `SECURITY_GATE.md`, 165 testes; SCA bloqueado (D-SUP2) |
| **6** | Dados / Infra | **DONE** | `DATA_INFRA_GATE.md`, ciclo completo executado contra PostgreSQL real |
| **7** | Integrações | **DONE** (14 BLOCKED declarados) | `FRONTEND_GATE.md`, 129 testes; homologação exige credencial de fornecedor (D-INT1..14) |
| **8** | Frente | **DONE** (6 pendências de acessibilidade declaradas) | `FRONTEND_GATE.md`, typecheck + build + 91 E2E |
| **9** | Jornadas por persona | **DONE** | `PERSONA_E2E_MATRIX.csv`, 49 passos em 7 jornadas, 5 personas; 20 navegador + 29 travessia (v0.24.1: o gerador deixou de perder evidência por casamento exato acidental) |
| **10** | Release | **DONE** | regressão completa, Git limpo, relatórios, ZIPs |

---

## Matrizes obrigatórias

| Matriz | Linhas | Estados | Travada por |
|---|---|---|---|
| `API_AUTHORIZATION_MATRIX.csv` | 888 | 888 PASS | regeração byte a byte + cobertura do roteador |
| `ENGINE_VALIDATION_MATRIX.csv` | 42 | 42 PASS | regeração + cobertura do registro de motores |
| `INTEGRATION_HOMOLOGATION_MATRIX.csv` | 14 | 14 BLOCKED | regeração + `BLOCKERS.md` obrigatório |
| `PERSONA_E2E_MATRIX.csv` | 49 | 49 PASS | regeração + 5 personas + mínimo de passos por jornada |

**Modalidade dos 49 passos:** 19 de navegador (Chromium real) + 30 de travessia de API, em **7
jornadas**. Um passo não é uma jornada: não são 49 jornadas independentes completas.

Nenhuma célula de nenhuma matriz contém `OPEN`, `PENDENTE`, `ABERTO` ou `TBD` — conferido por teste.

---

## Bloqueios (todos externos, nenhum resolvível por código)

| ID | O que bloqueia | Quem desbloqueia |
|---|---|---|
| **D-SUP1** | `npm ci`, lockfile, `@types/react`, typecheck pelo `tsconfig.json` oficial | qualquer rede com acesso ao registry npm |
| **D-SUP2** | SCA contra base de vulnerabilidade viva | qualquer rede com acesso a PyPI/OSV |
| **D-INT1..14** | homologação das 14 integrações (`sandbox`, `homologated`) | contratação de cada fornecedor + credencial de sandbox |

---

## Validações que permanecem fora de alcance, e por quê

Não são bloqueios de engenharia: são verificações que exigem uma pessoa, um dispositivo ou um
terceiro, e **nenhuma delas é afirmada neste release**.

| Validação | Por quê |
|---|---|
| Teste de intrusão por terceiro | exige contratação; nenhum teste automatizado substitui |
| `axe-core` | registry npm 403 |
| Leitor de tela real (NVDA/VoiceOver/Orca) | exige sistema operacional com o leitor e operação manual |
| Segundo navegador (Firefox/WebKit) | só Chromium instalado |
| Zoom de texto a 200%, daltonismo, navegação por voz | não exercitados |
| Homologação fiscal, Stripe real, KYC, gov.br, ICP-Brasil, ACT, biometria, SMS | **proibido simular** pela regra permanente do projeto |

---

## Commits desta rodada

| Commit | Escopo |
|---|---|
| `9ca75f1` | Gates 0-4: as quatro matrizes, derivadas do código e travadas por teste |
| `b4c6958` | Gate 5: dez conferências de segurança, nove executadas e uma declarada bloqueada |
| `5d0ce11` | Gate 6: dados e infraestrutura, executados contra PostgreSQL real do zero |
| `7b286d7` | Gates 7 e 8: integrações inertes, modal testado, achado de tabela que não resistiu |
| `67bc6aa` | Regressão completa: quatro testes que vazavam estado entre arquivos |
