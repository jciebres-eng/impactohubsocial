# Matriz de homologação

Para cada capacidade: em que estado ela está, **como se prova**, e o que falta para o estado seguinte. Esta é a
lista que uma pessoa usa para decidir o que pode ser prometido a um cliente.

## 1. A escala

| Estado | Significa | Prova exigida |
|---|---|---|
| `scaffolded` | existe a estrutura, nada foi exercitado contra o real | código + migração |
| `contract_tested` | o contrato foi exercitado contra um duplo que segue a especificação | teste automatizado verde |
| `sandbox` | funcionou no ambiente de teste do fornecedor real | registro de chamada bem-sucedida |
| `homologated` | passou pela homologação formal do fornecedor | documento do fornecedor |
| `production_active` | está em uso real, com acompanhamento | chamada em produção + saúde |

Promoção é ato **da administração**, com evidência. Deploy nunca promove: o arquivo de configuração só mantém ou
rebaixa (`sync_integration_providers`).

## 2. Núcleo do produto

| Capacidade | Estado | Prova |
|---|---|---|
| Ideia → projeto, sem apagar a ideia | **em produção** | `test_v0150_core.IdeasTests` · `J1` |
| Máquina de situações (58 transições, gatilho no banco) | **em produção** | `test_status_guard_refuses_invalid_transition_even_in_direct_sql` |
| Linha de tempo encadeada por hash + verificação | **em produção** | `ledger_verify` · `test_transition_is_recorded_in_history_and_hash_chained_timeline` |
| Retratos comparáveis com hash de estado | **em produção** | `SnapshotTests` · `test_snapshot_of_an_unchanged_project_has_the_same_hash` |
| Riscos: declarado vs apontado por regra, varredura idempotente | **em produção** | `RiskTests` · `J6` |
| Diagnóstico com versões imutáveis e diff do servidor | **em produção** | `DiagnosticTests` · `J3` |
| Lacuna → ação, com fechamento automático | **em produção** | `test_gaps_become_actions_and_closed_gaps_close_their_actions` |
| Montagem de documento com bloqueio explicado | **em produção** | `AssemblyTests` · `J4` · teste de navegador |
| Geração PDF/DOCX/ODT própria | **em produção** | `test_complete_assembly_generates_and_registers_in_the_vault` |
| Revisão com quatro olhos | **em produção** | `test_four_eyes_the_author_cannot_approve_their_own_assembly` |
| Match com elegibilidade antes de pontuação, 4 versões, evidência | **em produção** | `MatchEngineInvariants` (8 testes) |
| Retorno humano sobre recomendação, sem treino automático | **em produção** | `MatchFeedbackTests` · `J7` |
| Inventário e rotação de chave, auditados | **em produção** | `KeyManagementTests` |
| Verificação pública sem login | **em produção** (desde v0.14.0) | `test_v0140_trust.PublicVerification` · `J1` |

## 3. Assinatura e identidade

| Capacidade | Estado | Falta para o próximo |
|---|---|---|
| Assinatura avançada da plataforma (2 camadas + selo HMAC) | **em produção** | — |
| Carimbo de tempo interno (HMAC do servidor) | **em produção** | — |
| Carimbo de tempo RFC 3161 (ACT) | `scaffolded` (501 explícito) | contrato com ACT + protocolo |
| Gov.br (assinatura avançada com certificado) | `scaffolded` (estado `unavailable`) | credenciamento + fluxo OIDC + guarda do PKCS#7 |
| ICP-Brasil (assinatura qualificada) | `scaffolded` (estado `unavailable`) | certificado A1/A3 + PAdES/CAdES + ACT + revogação + homologação |
| Identificação por documento (análise humana) | **em produção** | — |
| Identificação por credencial profissional (conselho) | **em produção** | — |
| Identificação biométrica | `scaffolded` (501 explícito) | provedor contratado + política de retenção |
| Confirmação de telefone por SMS | `scaffolded` (501 explícito) | provedor contratado |

## 4. Integration Hub

| Provedor | Estado | O que já existe | O que falta |
|---|---|---|---|
| `oidc_identity` | `contract_tested` | fluxo OIDC completo, testado com duplo | rodar contra um emissor real (Google/Microsoft/Keycloak) |
| `stripe_payments` | `contract_tested` | webhook com verificação de assinatura, idempotência | conta real + chave + webhook apontado |
| `email_smtp` | `contract_tested` | envio por SMTP | servidor SMTP real |
| `totvs` | `contract_tested` | contrato de importação/exportação | acesso a uma instância real |
| `senior_sapiens` | `contract_tested` | idem | idem |
| `bi_export` | `contract_tested` | exportação de dataset | destino real |
| `generic_rest` | `contract_tested` | conexão REST configurável | endpoint do cliente |
| `government_api` | `scaffolded` | estrutura de conexão | **credenciamento no órgão** |
| `sftp_batch` | `scaffolded` | estrutura de job agendado | servidor SFTP + chave |

**Nenhum em `production_active`.**

## 5. Infraestrutura

| Item | Estado | Observação |
|---|---|---|
| PostgreSQL 16 com RLS em 204 de 205 tabelas | **em produção** | `schema_migrations` é a única sem, por desenho |
| Migrações só para frente, com checksum e lock | **em produção** | 15 migrações; caminho de atualização testado |
| Armazenamento local | **em produção** | uma instância só |
| Armazenamento S3 | `contract_tested` | exige bucket e credencial; validação recusa configuração incompleta |
| Antivírus clamd | `scaffolded` | sem ele, documento fica `pending_scan` |
| PWA com service worker | **em produção** | `STORE_READINESS.md` |
| Aplicativo nativo (loja) | **não iniciado** | ver `MOBILE.md` |

## 6. O que NÃO está homologado e não deve ser prometido

- Qualquer integração com ERP, banco, órgão público ou provedor de identidade **contra sistema real**.
- Assinatura qualificada (ICP-Brasil) e assinatura via Gov.br.
- Carimbo de tempo com validade externa.
- Benefício fiscal calculado como garantia: o motor fiscal estima a partir de regras **publicadas com fonte, URL e
  data**, e as tabelas nascem vazias — sem regra cadastrada e aprovada, ele **não estima**.
- Preço de serviço profissional: as tabelas de honorários nascem vazias e exigem fonte, URL e data de publicação.
  A plataforma não inventa tabela de conselho.
- Operação em mais de uma instância simultânea com armazenamento local.
- Desempenho com mais de 10.000 projetos publicados por financiador sem filtro (ver `PERFORMANCE_REPORT.md` §5).

## 7. Como promover uma capacidade

1. Exercitar contra o ambiente de teste do fornecedor real e **guardar a evidência** (log, identificador de
   transação, documento).
2. Atualizar a maturidade pela administração (`PUT /v1/admin/integrations/providers/{key}` para integração;
   `PUT /v1/admin/signature-providers/{key}` para assinatura), com nota de ativação.
3. Registrar aqui, nesta matriz, com a data e a evidência.
4. Para assinatura qualificada, a promoção a `production` é **recusada** enquanto o nível criptográfico não for
   assimétrico real — não há atalho.
