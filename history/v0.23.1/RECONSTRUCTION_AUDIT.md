# RECONSTRUCTION_AUDIT — FASE 0

Auditoria do código e do banco **reais**, não da documentação. Cada linha tem a consulta ou o arquivo que a
sustenta. Classificação: 🟢 existe e funciona · 🟡 existe parcial ou espalhado · 🔴 não existe.
Prioridade: **P0** bloqueia o resto · **P1** essencial para a visão · **P2** importante · **P3** depois.

Base auditada: v0.15.0 (`b8dcb35`), 205 tabelas, 625 operações, 673 testes verdes.

---

## 0. UM PONTO QUE PRECISA SER DITO PRIMEIRO

**O pacote `plataforma-impacto-design-system` / Design System Convergência v1.0 NÃO foi recebido nesta sessão.**

Verificado: nenhum arquivo com "design system" no repositório; os anexos desta rodada são 4 arquivos de texto
(nenhum ZIP de design system). O frontend atual usa **Inter + Lora**, não IBM Plex, e tem **16 tokens** CSS.

Consequência direta, sem rodeio: as seções que mandam *"integrar o Design System Convergência"*, *"usar IBM Plex"*,
*"usar os tokens React Native existentes"* e *"criar os 50+ componentes do DS"* **não podem ser executadas** — eu
não tenho o pacote. Inventar um design system e chamá-lo de "o que você me enviou" seria exatamente o tipo de
mentira que todas as rodadas anteriores desta plataforma foram construídas para impedir.

Isto também é coerente com os outros três anexos desta mesma rodada, que dizem **"NÃO comece pelo frontend"**,
**"NÃO faça redesign"**, **"NÃO implementar cores/animações/branding"**. Então esta rodada é de **domínio,
backend, banco, APIs, motores e contratos** — e o Design System entra na rodada seguinte, quando o pacote chegar.

---

## 1. O QUE JÁ EXISTE E ESTÁ BOM (preservar, não reescrever)

| Capacidade | Estado | Evidência |
|---|---|---|
| Multi-tenant por RLS em 203 de 205 tabelas, 408 políticas | 🟢 | `DATABASE_INTEGRITY_REPORT.md`; testes por SQL direto |
| Autenticação, MFA, sessão rotativa, OIDC, CSRF | 🟢 | `test_api_auth.py`, `test_oidc.py` |
| Autorização por rota: `auth`/`kinds`/`min_role`/`staff`/`feature` | 🟢 | `http.RouteSpec` |
| Trilha encadeada por hash + 17 tabelas append-only + 5 guardas | 🟢 | `ledger_verify`, `audit_verify`, `trust_verify` |
| Match explicável com 4 versões, evidência, confiança separada | 🟢 | `MATCH_ENGINE_FINAL.md`, 8 invariantes |
| Diagnóstico com versões imutáveis e FATO/INFERÊNCIA/RECOMENDAÇÃO/DESCONHECIDO | 🟢 | `DIAGNOSTIC_ENGINE.md` |
| Máquina de situações do projeto como dado + gatilho no banco | 🟢 | `project_status_graph` (58 transições) |
| Montagem de documento com bloqueio explicado e quatro olhos | 🟢 | `DOCUMENT_ASSEMBLY.md` |
| Trust: assinatura em 2 camadas, verificação pública, custódia, revogação | 🟢 | `TRUST_ARCHITECTURE.md` |
| Integration Hub com maturidade honesta, disjuntor, carta morta | 🟢 | `INTEGRATION_CAPABILITY_MATRIX.md` |
| Entitlements centralizados (`has_access`, `check_limit`) | 🟢 | `services/entitlements.py` — **não** há `if plan ==` espalhado |
| Taxonomia ODS consolidada (17 metas, 1 fonte de verdade) | 🟢 | `ods_goals` após a 0013 |
| Denúncias (`reports`) com alvo, categoria, estado, responsável | 🟢 | `services/reports.py` |

**Conclusão:** a base não precisa ser reconstruída. O que falta é a **camada de rede** e a **composição por
persona** em cima dela.

---

## 2. O QUE EXISTE MAS ESTÁ ESPALHADO (o achado central desta auditoria)

O anexo adverte: *"não use relacionamento informal espalhado por dezenas de tabelas sem uma estratégia"*. É
exatamente o que está acontecendo.

### 2.1 Relacionamento: 6 tabelas ad-hoc, nenhuma estratégia 🟡 **P0**

| Tabela | Colunas | O que é na verdade |
|---|---|---|
| `follows` | `follower_org_id, followed_org_id, created_at` | relação FOLLOW |
| `favorites` | `org_id, project_id, created_by, created_at` | relação FAVORITE (só para projeto) |
| `org_blocks` | `org_id, blocked_org_id, created_at` | relação BLOCK |
| `need_offers` | `need_id, professional_org_id, message, status` | proposta de SERVIÇO disfarçada |
| `solution_intents` | `solution_id, org_id, stage, confirmed_by_author` | proposta de REPLICAÇÃO disfarçada |
| `partnership_requests` | 21 colunas, incluindo `org_name`, `contact_email` | captação de lead da Central, **não** é relação da rede |

Nenhuma tem `visibility`, `context`, `status` uniforme, `metadata` nem trilha. Nenhuma responde "quem se relaciona
com quem, em que contexto, com que autorização". Acrescentar INVESTMENT, MENTORSHIP, VOLUNTEER e
GOVERNMENT_SUPPORT nesse modelo criaria dez tabelas de duas colunas.

### 2.2 Conversa sem contexto 🟡 **P0**

```
conversations(id, org_a, org_b, created_at)
messages(id, conversation_id, sender_org_id, sender_user_id, body, created_at, read_at, removed_at, removed_reason)
```

Problemas concretos: conversa é **só** org↔org (profissional pessoa física não conversa), **não tem contexto**
(nem `project_id`, nem `proposal_id`), **não tem tabela de participantes** (não dá para ter 3 partes), **não tem
anexo** nem mensagem de sistema. O anexo exige: *"nunca criar chat genérico sem contexto"*.

### 2.3 Notificação sem alcance de equipe 🟡 **P0** — e é o pedido explícito desta rodada

```
notifications(id, org_id, user_id, kind, title, body, link, read_at, emailed_at, created_at)
notification_prefs(user_id, grp, in_app, email)
app_notify(org, user, kind, title, body, link)   -- SECURITY DEFINER
```

O que existe: notificação por organização **ou** por pessoa, preferência por grupo, e-mail, e um padrão de
idempotência (`notify_once` + `billing_notices`) usado **só** em cobrança.

O que **não** existe, e o usuário pediu nominalmente ("notificações para toda a equipe envolvida em cada evolução
ou modificação ou alteração de etapas do processo ou documentos juntados"):

- **fan-out para a equipe**: `app_notify(org, NULL, …)` grava **uma** linha com `user_id` nulo. Quem olha
  `/v1/notifications` vê, mas não há notificação por pessoa, nem por papel, nem por participação no projeto;
- **atores e participantes**: nada liga notificação a "quem está no projeto";
- **idempotência geral** (só cobrança tem);
- **prioridade, digest, agrupamento**;
- **ação na notificação** (`actionable`);
- **evento de domínio como fonte** — hoje cada chamador decide se notifica, e 5 módulos fazem isso de 3 maneiras
  diferentes (`notify_user`, `notify_once`, `notify_counterpart`).

### 2.4 Proposta: três fluxos paralelos, nenhum motor 🟡 **P1**

`need_offers` (profissional → necessidade), `solution_intents` (replicação), `applications` (OSC → edital, este
sim com máquina de estados completa). Falta o motor único de proposta com os 7 tipos e os 10 estados que o anexo
descreve, e falta INVESTMENT/SPONSORSHIP/MENTORSHIP/VOLUNTEER por completo.

### 2.5 Preço: estrutura existe, regra nova não cabe nela 🟡 **P1**

```
plans(plan_key, version, role, name, price_cents, interval, limits, features, tier, public, active)
plan_prices(plan_key, interval, amount_cents, active)        -- 10 linhas, TODAS com amount_cents NULL
```

Medido: **nenhum preço definido** (coerente com o ADR 018: "preço `null` até o proprietário definir"). A regra
desta rodada é concreta e é decisão do proprietário, então pode ser implementada — mas `plan_prices` não tem
`currency`, `introductory_price`, `introductory_periods`, `effective_from/until`, `tax_behavior` nem
`provider_price_id`. E a plataforma inteira formata em **BRL** (`format.ts: money()`), enquanto a regra nova é em
**USD**.

---

## 3. O QUE NÃO EXISTE 🔴

| # | Falta | Prioridade | Por que importa |
|---|---|---|---|
| L1 | `relationships` unificada (tipo, contexto, visibilidade, estado, trilha) | **P0** | é o eixo da rede; sem ela cada relação nova é uma tabela nova |
| L2 | Conversa com **contexto** + participantes + anexo + mensagem de sistema | **P0** | negociação sem contexto não é negociação |
| L3 | **Fan-out de notificação para a equipe** do projeto, com idempotência e prioridade | **P0** | pedido explícito desta rodada |
| L4 | Eventos de domínio como fonte única de timeline/notificação/auditoria | **P1** | hoje cada chamador decide, de 3 formas |
| L5 | `proposals` (7 tipos, 10 estados, versão, expiração, anexo, trilha) | **P1** | investimento, patrocínio, mentoria, voluntariado não existem |
| L6 | **Workspace Context** (identidade ativa, papéis, capacidades, próximas ações) | **P1** | sem ele, "workspace por persona" vira 4 dashboards |
| L7 | Persona/Capability explícitos (hoje: papel + tipo de org + entitlement) | **P1** | INVESTOR/DONOR/MENTOR/VOLUNTEER não são representáveis |
| L8 | Marketplace com `publication_state` (draft→review→approved→published→paused→expired→archived) | **P1** | risco real de projeto privado aparecer por erro de consulta |
| L9 | **Recommendation** separada de Match | **P1** | "há compatibilidade" ≠ "esta é a ação recomendada" |
| L10 | **Impact Readiness** por dimensão (documento/projeto/captação/governança/execução/evidência) | **P2** | o diagnóstico já calcula 8 dimensões; falta a agregação por finalidade |
| L11 | `impact_updates` (relatório periódico com ciclo de revisão) | **P2** | prestação de contas periódica não existe como entidade |
| L12 | Perfil público com `@username`, projeção curada, Open Graph, QR | **P2** | "LinkedIn de Impacto" pedido |
| L13 | Experiência profissional confirmada pela organização (declarado→confirmado→contestado) | **P2** | sem isso o portfólio é autodeclaração |
| L14 | Escada de sanção proporcional (orientação→…→banimento) com motivo e revisão | **P2** | `reports` resolve, mas não há enforcement registrado |
| L15 | Registro central de taxonomias versionadas | **P2** | rótulos espalhados em frontend e serviços |
| L16 | `investments` separando intenção/compromisso/pagamento | **P2** | `commitments` existe para projeto; falta para a rede |
| L17 | Preço com introdutório, moeda, vigência e imposto | **P1** | regra comercial desta rodada |
| L18 | Territórios como entidade (hoje é string `BR-UF-IBGE`) | **P3** | governo precisa de necessidade/lacuna por território |

---

## 4. O QUE ESTÁ ERRADO (não só faltando)

| # | Problema | Gravidade |
|---|---|---|
| E1 | `partnership_requests` guarda `contact_email`/`contact_phone` de lead junto do domínio de parceria — mistura captação da Central com relação da rede | média |
| E2 | `conversations(org_a, org_b)` impede conversa com pessoa física e conversa de 3 partes; ordem dos campos é convenção, não restrição | **alta** |
| E3 | Três helpers de notificação com assinaturas diferentes, um só com idempotência | média |
| E4 | `favorites` só aceita projeto — favoritar organização, profissional ou oportunidade exigiria outra tabela | média |
| E5 | `plan_prices` sem moeda: a plataforma assume BRL no frontend e a regra nova é USD | **alta** |
| E6 | Nenhuma `publication_state` em projeto: a visibilidade é `visibility` + `status`, e o feed filtra por consulta — um `WHERE` errado expõe rascunho | **alta** |

---

## 5. ORDEM DE IMPLEMENTAÇÃO

```
FASE 1  domínio da rede      relationships · conversations v2 · proposals · notifications fan-out
                              marketplace listings · impact_updates · personas/capabilities
                              taxonomies · usernames · sanctions · investments · territories
FASE 2  motores              relationship · proposal · notification · workspace context
                              recommendation · readiness
FASE 3  API                  rotas por motor + workspace + perfil público + marketplace
FASE 4  billing              preço introdutório, moeda, vigência, imposto, aviso de mudança
FASE 5  frontend funcional   workspaces, marketplace, propostas, mensagens, notificações, perfil
FASE 6  testes               invariantes, matriz de isolamento, 7 jornadas E2E, volume
FASE 7  documentação         os 18 documentos pedidos
FASE 8  release              v0.16.0, snapshot, ZIP, manifesto, git, backup, restauração
```

**Versão:** esta rodada sai como **v0.16.0**, não v0.15.0. A v0.15.0 já foi liberada, empacotada e marcada
(`b8dcb35`, ZIP sha256 `14e19b50…`). A regra do proprietário é explícita: *"aumentar a versão coerentemente,
snapshot dos documentos anteriores em `history/vX/`, nunca sobrescrever em silêncio."* Capacidade nova grande ⇒
MINOR. O anexo pedia o nome `v0.15.0-impact-network-core` porque foi escrito antes de a v0.15.0 existir.
