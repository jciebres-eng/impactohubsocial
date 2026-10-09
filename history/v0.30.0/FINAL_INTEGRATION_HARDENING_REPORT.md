# FINAL_INTEGRATION_HARDENING_REPORT — v0.13.0 (2026-10-05)

Etapa do roteiro: **INTEGRATION HUB**. Nenhum trabalho de design, redesign, animação ou cosmética foi feito — era proibido nesta etapa.
Vocabulário de honestidade usado aqui: **NÃO VERIFICADO** · **ESTRUTURADO** (existe, não exercitado) · **AUTORIZAÇÃO EXTERNA NECESSÁRIA** · **HOMOLOGAÇÃO NECESSÁRIA** · **VALIDAÇÃO JURÍDICA NECESSÁRIA** · **DEPENDÊNCIA DE INFRAESTRUTURA**.

---

## 1. Resumo executivo
A plataforma ganhou uma **camada de integração desacoplada**: o núcleo passou a depender de contratos internos (`IntegrationAdapter`, `CanonicalRecord`, `IntegrationError`) e **de nenhum fornecedor**. Trocar Senior por TOTVS, ou acrescentar um ERP novo, é escrever um adapter e registrar um provedor — o domínio não muda.
Números: **13 tabelas** novas (165 no total), **36 rotas** novas (511 operações), **9 provedores** declarados, **6 adapters**, **76 testes** novos (**468 no total, 0 falhas**), **~4.300 linhas** de código e migração.
O que isso **não** é: nenhuma integração foi executada contra um sistema externo real. Tudo foi provado contra dublê. Nenhum provedor está homologado. O adapter de governo **recusa agir** porque não há credenciamento. Não existe nenhuma tela.
Veredito da etapa: **GREEN para fundação técnica, YELLOW para prontidão de integração real, RED para integração em produção.**

## 2. Estado antes (auditoria do repositório real, não dos documentos)
Auditei o código antes de escrever qualquer linha. O inventário honesto está em `INTEGRATION_INVENTORY.md`. Resumo: **existiam 12 mecanismos** úteis e **não existia camada de integração**.
Existia e foi aproveitado: `HttpClient` com guarda de SSRF e tempo limite; `defusedxml` já em uso; `FieldCipher` (Fernet com rotação); cofre de documentos (allowlist, magic bytes, zip bomb, antivírus); `storage` com URL temporária; `audit_events`; `job_runs` e o agendador; RLS em todas as tabelas; o padrão de idempotência dos `billing_events`; importador de extrato bancário; o webhook de entrada do Stripe (com dublê).
Não existia: contrato de adapter, conexões por ambiente, abstração de credencial, mapeamento de campos, correspondência de ID externo, caixa de saída de eventos, webhooks de saída, repetição classificada, disjuntor, dead-letter, replay, importação/exportação genérica, painel de operação, catálogo de provedores.
**13 lacunas** foram listadas antes de implementar; todas foram fechadas, exceto SFTP (declarado como não implementado).

## 3. Estado depois
| Dimensão | Antes | Depois |
|---|---|---|
| Acoplamento a fornecedor | código de Stripe e de banco espalhado em serviços | adapters atrás de um protocolo; nenhum SDK de ERP no domínio |
| Ambientes | implícito (variável de ambiente) | `development`/`sandbox`/`homologation`/`production` por conexão |
| Credenciais | variáveis de ambiente do processo | cifradas por conexão, **sem SELECT** para o papel da aplicação, só dica na API |
| Erros externos | genéricos | classificados em **temporário × permanente**; só o temporário repete |
| Repetição | nenhuma | espera crescente com variação, disjuntor por conexão, dead-letter, replay |
| Idempotência | só em cobrança | jobs, entrada, entrega e importação, **garantida por UNIQUE no banco** |
| Eventos de domínio | nenhum | caixa de saída com 26 eventos e assinatura HMAC |
| Arquivos | só extrato bancário | CSV/XLSX/JSON/XML com mapeamento, prévia por linha e aprovação humana |
| Operação | nenhuma visão | `GET /v1/admin/integrations/overview` responde “o que está quebrado agora” |
| Honestidade | — | maturidade por provedor, promovida só com evidência auditada |

## 4. Arquitetura
Detalhe e diagrama: `INTEGRATION_ARCHITECTURE.md`. Princípio: **o núcleo fala com contratos; o adapter fala com o mundo.**
```
domínio  →  hub (jobs, eventos, correspondências, auditoria)  →  adapter  →  transporte resiliente  →  sistema externo
            ↑ contratos internos                    credencial cifrada ↑           guarda de SSRF ↑
```
Camadas: `contracts.py` (vocabulário), `transport.py` (classificação, espera, disjuntor, SSRF), `secrets.py` (credencial), `mapping.py` (campos), `links.py` (ID externo), `events.py` (saída), `inbound.py` (entrada), `hubjobs.py` (fila), `files.py` (arquivo), `hub.py` (orquestração), `adapters/` (fornecedores).
O modelo canônico saiu das entidades reais do domínio (pessoa, organização, documento, curso, certificado, evento, fatura, pagamento, parceiro, chamado) — não de um modelo genérico inventado.

## 5. Alterações
**Novos:** 11 módulos em `backend/impacto/integrations/`, 6 adapters, `api/integration_routes.py` (36 rotas) e `api/integration_schemas.py`, `migrations/0011_v0130_integration_hub.sql`, `config/integration_providers.json`, `tests/test_v0130_integrations.py`, 8 documentos.
**Modificados (mínimo):** `db/migrate.py` (sincroniza provedores sem rebaixar maturidade), `jobs.py` (trabalhador `integration_ops`), `api/__init__.py` (registro), `tests/test_architecture.py` (novos invariantes).
**Não modificados de propósito:** `http.py`, autenticação, RBAC, cobrança, Central de Conhecimento, frontend. Nenhuma biblioteca nova foi adicionada — o XLSX é lido com `zipfile` + `defusedxml` já presentes.

## 6. Integrações que já existiam (preservadas, não reescritas)
`HttpClient`/SSRF · `defusedxml` · `FieldCipher` · cofre de documentos · `storage` · `audit_events` · `job_runs`/agendador · RLS · padrão de idempotência de `billing_events` · importador de extrato bancário · webhook do Stripe · gateway de IA.
Por que preservar: são mecanismos já testados e auditados; substituí-los seria risco sem ganho. A decisão item a item está em `INTEGRATION_INVENTORY.md`.

## 7. Integrações preparadas (ESTRUTURADO — não exercitado contra sistema real)
| Provedor | Maturidade declarada | Observação honesta |
|---|---|---|
| `generic_rest`, `generic_webhook`, `file_batch`, `bi_export` | contract_tested | contrato provado contra dublê |
| `senior_sapiens` | contract_tested | híbrido REST + SOAP; a Senior expõe WebServices SOAP — **HOMOLOGAÇÃO NECESSÁRIA** |
| `totvs` | contract_tested | TOTVS **não é um produto só**: Protheus, RM e Datasul têm APIs diferentes; o adapter trata como variantes |
| `stripe_billing` | contract_tested | o webhook existe desde o v0.11.0 e **nunca** chamou a Stripe de verdade |
| `government_api` | **scaffolded** | **AUTORIZAÇÃO EXTERNA NECESSÁRIA** — exige credenciamento; o adapter **recusa agir** |
| `sftp_batch` | **scaffolded** | contrato declarado, **NÃO IMPLEMENTADO** |

## 8. Integrações realmente testadas
**Contra sistema externo real: nenhuma.** Todos os 76 testes usam `FakeTransport`, que substitui o cliente HTTP e responde por sufixo de URL, podendo simular status, corpo, erro de rede, demora e devolver os cabeçalhos recebidos.
Isso prova **o nosso lado do contrato** (autenticação montada, payload, tradução de erro, repetição, idempotência, isolamento). **Não prova** compatibilidade com Senior, TOTVS, Protheus, RM, Datasul, Gov.br, Conecta ou Stripe.

## 9. Testes executados
**468 testes, 0 falhas, 0 ignorados** — `docs/evidence/test_run_v0.13.0.log`. Banco PostgreSQL criado do zero a cada execução (11 migrações aplicadas em banco vazio, toda vez). Detalhamento por classe: `INTEGRATION_TESTING.md`.
Cobertura exigida pelo escopo e atendida: ciclo de vida; credencial; **isolamento entre organizações (IDOR) nas 13 tabelas**; mapeamento e conflito de ID; **idempotência sob concorrência real** (4 trabalhadores em paralelo → 1 execução; 4 entradas em paralelo → 1 processamento); repetição, disjuntor e dead-letter; webhooks de entrada e saída; arquivos (incluindo recusa explicada de JSON/XML e neutralização de fórmula); saúde não destrutiva e painel; **falha do sistema externo sem afetar o núcleo**; segurança (SSRF, XXE, bomba XML, injeção SOAP, mapeamento sem execução de código); contrato dos 6 adapters.
Estáticos: `ruff check impacto tests` → **All checks passed** (`docs/evidence/ruff_v0.13.0.log`) · `tsc --noEmit` → **PASS** · `node build.mjs` → **PASS** · `compileall` → **PASS** · `migrate --check` → sem pendência e sem checksum alterado.

## 10. Falhas encontradas (durante a construção)
1. GRANT amplo em `integration_subscriptions` **expunha a coluna do segredo** ao papel da aplicação.
2. Política de RLS de `integration_deliveries` (`FOR ALL app_priv()`) **impedia a própria emissão de evento** → 403 na gravação da entrega.
3. `integration_events` exigia privilégio no INSERT, quebrando a **caixa de saída** dentro da transação da organização.
4. Gatilho de guarda da maturidade **bloqueava a própria migração** (executada pelo dono).
5. Faltava `GRANT UPDATE (maturity, updated_at)` → a promoção pela administração devolvia 403.
6. A validação de endpoint **resolvia DNS na gravação** — impediria configurar um host ainda não provisionado e tornaria o salvamento dependente de DNS.
7. `GET /v1/integrations/jobs/{id}` consultava `audit_events.created_at`; a coluna é `at` → 500.
8. Detalhe da conexão não devolvia `last_success_at`/`health_detail` (a interface não teria como mostrar saúde).
9. O cofre de documentos recusa `.json`/`.xml` e recusa binário disfarçado de `.csv` — o importador assumia o contrário.
10. Nove defeitos **de teste** (transação abortada após erro de permissão, leitura direta de coluna negada, nome curto demais, dependência de ordem alfabética, contador global, tipo de credencial incompatível com o adapter, SSRF usando loopback que é permitido em desenvolvimento, imports não usados, asserção artificial sobre docstring).

## 11. Falhas corrigidas
Todas as 10 acima. Detalhe das escolhas:
- 1–5: corrigidas **na própria migração 0011**, que ainda não havia sido liberada (o banco foi recriado a cada correção). A partir desta liberação a 0011 é imutável.
- 6: a validação na gravação passou a ser **só de forma** (esquema HTTPS + faixa de IP literal); a guarda autoritativa de SSRF permanece no momento da chamada, onde resolve o nome e recusa rede interna. ADR 089.
- 9: **não enfraqueci o cofre**. A importação por upload ficou restrita a CSV/XLSX, com 422 `format_not_uploadable` explicando que JSON/XML entram por conexão REST/SOAP. ADR 090.
- 10: corrigidas nos testes; a asserção artificial foi substituída por uma verificação real dos cabeçalhos entregues.

## 12. Riscos restantes
| Risco | Gravidade | Mitigação / estado |
|---|---|---|
| Nenhum sistema externo real foi chamado | **Alta** | credencial de sandbox do cliente + homologação por provedor |
| DNS rebinding (resolução e conexão são passos separados) | Média | **DEPENDÊNCIA DE INFRAESTRUTURA**: bloquear rede interna no egress |
| Sem fila distribuída: trabalhador no agendador do processo | Média | `SKIP LOCKED` impede duplicação; `queue_depth` é o gatilho para trocar |
| Expurgo de jobs/eventos sem prazo | Média | **VALIDAÇÃO JURÍDICA NECESSÁRIA** |
| Base legal por assinatura de webhook não registrada | Média | **VALIDAÇÃO JURÍDICA NECESSÁRIA** |
| SFTP ausente | Baixa | declarado; implementar quando houver cliente |
| Sem teste de carga da camada | Média | antes do piloto com parceiro |
| Auditoria de dependências não executada | Média | registries bloqueados neste ambiente; obrigatória em CI |
| Sem interface | Média (produto) | etapa de design |

## 13. Dependências externas (nada disso depende de código)
Credenciais de sandbox e de produção de cada ERP · contrato/licença de WebService da Senior · definição de qual produto TOTVS o cliente usa · **credenciamento Gov.br/Conecta** · conta Stripe real e definição de preços · servidor SMTP real · host SFTP do parceiro, quando houver · egress controlado na infraestrutura · decisão jurídica sobre retenção e base legal.

## 14. Segurança
Revisão completa, vetor a vetor, com o que é provado por teste e o que é por inspeção: `INTEGRATION_SECURITY.md`. Resumo: **GREEN** em SSRF, XXE/bomba XML, injeção em SOAP, falsificação e reenvio de webhook, vazamento de credencial, IDOR, escalonamento de privilégio, arquivo malicioso, injeção de fórmula e negação de serviço por sistema externo. **YELLOW** em injeção em log e travessia de caminho (por inspeção) e em DNS rebinding (risco residual). **RED** em auditoria de dependências e pentest.
Garantia estrutural que vale destacar: **a coluna do segredo não é legível pelo papel da aplicação**, nem em contexto de sistema — a leitura passa por uma função SECURITY DEFINER. Um erro futuro de código não consegue devolver o segredo por engano.

## 15. LGPD (técnico; não é parecer jurídico)
`LGPD_AUDIT.md` §camada de integração. **GREEN**: inventário dos fluxos, minimização na saída (payload montado pelo servidor; datasets de colunas fixas) e na entrada (**importação nunca cria pessoa nem organização**), controle de acesso por RLS e papel, segredo de terceiro protegido, rastreabilidade sem segredo, eliminação. **YELLOW**: base legal por assinatura de webhook, retenção de jobs/eventos, transferência internacional (depende do provedor conectado). Ambos exigem decisão humana — não são defeitos de código.

## 16. Performance
Medido: a suíte completa roda em ~228 s com banco recriado. As consultas do painel de operação são agregações com filtro por data e índices das chaves estrangeiras usadas; a estatística de latência é calculada sobre 7 dias.
**NÃO VERIFICADO**: comportamento com volume de produção, número de conexões simultâneas por organização, tamanho máximo real de importação em uso. O limite declarado hoje é 20.000 linhas / 400.000 células / 60 MB descomprimidos por arquivo, e 2 MB por webhook de entrada.
Decisão consciente: o trabalho pesado nunca acontece dentro da requisição HTTP — a requisição enfileira, o trabalhador executa.

## 17. Observabilidade
Cada chamada externa gera um traço com host, status e duração — **sem corpo e sem segredo**. Cada job guarda tentativas, código e tipo de erro, duração e correlação. Cada operação relevante (criar conexão, gravar credencial, ativar, verificar saúde, aprovar importação, promover maturidade, reenviar entrega) vai para `audit_events` com quem, qual organização, qual conexão e qual resultado. A pergunta operacional “qual integração está quebrada agora?” tem **uma** resposta: `GET /v1/admin/integrations/overview`.
Falta: exportação para um coletor externo (métricas e traços saem só pelo log estruturado) — **DEPENDÊNCIA DE INFRAESTRUTURA**.

## 18. Próximos passos
1. **Design** (próxima etapa do roteiro): as 12 telas do §11 do `DESIGN_HANDOFF.md`.
2. Homologar um provedor real de cada vez, começando pelo que o primeiro cliente usa, com credencial de sandbox.
3. Decisões humanas: retenção, base legal por assinatura, credenciamento de governo, preços.
4. Infraestrutura: egress controlado, coletor de métricas, e fila dedicada **se** `queue_depth` crescer.
5. CI com `npm audit`/`pip-audit` (bloqueados neste ambiente).
6. Teste de carga antes do piloto.

## 19. Handoff de design
`DESIGN_HANDOFF.md` ganhou a **seção 11** com: as 12 entidades, **todos os estados** (listas fechadas — conexão, saúde, job, entrega, entrada, correspondência, importação, maturidade, ambiente), as 12 telas necessárias, os padrões obrigatórios (segredo nunca aparece; ambiente sempre visível; erro temporário × permanente legível; maturidade não maquiada; conflito exige decisão; aprovação é humana) e o que **não** desenhar como pronto.
A camada de integração é hoje o maior bloco de UI inexistente do produto — e é API pura, pronta para receber tela sem mudar contrato.

## 20. Prontidão para produção
| Dimensão | Classificação |
|---|---|
| Fundação técnica da integração | **GREEN** |
| Segurança da camada | **GREEN** (com 2 YELLOW declarados e pentest pendente) |
| Testes | **GREEN** (468, 0 falhas) |
| Integração com sistema externo real | **YELLOW** — nada executado; **HOMOLOGAÇÃO NECESSÁRIA** |
| Integração com governo | **RED** — **AUTORIZAÇÃO EXTERNA NECESSÁRIA** |
| SFTP | **RED** — não implementado |
| Interface | **RED** — não existe |
| Escala/carga | **YELLOW** — **DEPENDÊNCIA DE INFRAESTRUTURA**, não testado em volume |
| LGPD | **YELLOW** — **VALIDAÇÃO JURÍDICA NECESSÁRIA** |
| **Veredito** | **pronta para receber design e para piloto controlado com um parceiro; não pronta para produção aberta** |
