# TRUST_ARCHITECTURE — camada de confiança, identidade e assinatura digital (v0.14.0)

Auditoria prévia: `TRUST_INVENTORY.md`. Identidade: `TRUST_IDENTITY.md`. Assinatura: `DIGITAL_SIGNATURE.md`.
Verificação pública: `PUBLIC_VERIFICATION.md`. Segurança: `TRUST_SECURITY.md`. Testes: `TRUST_TESTING.md`.

## 1. Princípio
**A página pública nunca lê tabela privada.** O que um terceiro pode ver é curado no momento em que o registro público é
criado e fica em uma única tabela (`verifiable_records.public_fields`). Mudar o domínio nunca passa a vazar dado novo por
engano, e o que é público fica auditável em um lugar só.

Três consequências de projeto:
1. **Assinatura é append-only.** Revogar é um fato novo (`signature_revocations`), nunca um UPDATE. Nada é apagado.
2. **Ninguém se promove.** Identidade, credencial profissional, situação de apoio e publicação de tabela de honorários são
   colunas guardadas no banco (`guard_columns`): só a administração ou uma função privilegiada alteram.
3. **O que não existe recusa.** Biometria, SMS e carimbo RFC 3161 devolvem erro explicando a dependência externa — não
   simulam, não registram "verificado" sem verificação.

```
                               IMPACTO
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
      NÚCLEO DO DOMÍNIO    INTEGRATION HUB        CAMADA DE CONFIANÇA
                                  │                    │
                    ┌─────────────┴──────┐   ┌─────────┼──────────┬──────────────┐
                    ▼                    ▼   ▼         ▼          ▼              ▼
             provedor de identidade   assinatura   IDENTIDADE  DOCUMENTOS   ASSINATURAS
             (recusa sem autorização) qualificada      │            │            │
                                      (ausente)   níveis +     hash +       2 camadas +
                                                  conferência  custódia +   revogação +
                                                  humana       carimbo      acordos
                                                        │            │            │
                                                        └────────────┴────────────┘
                                                                     ▼
                                                        VERIFICAÇÃO PÚBLICA (sem login)
                                                        código legível + QR + revogação
```

## 2. Módulos (`backend/impacto/trust/`)
| Módulo | Responsabilidade |
|---|---|
| `codes.py` | código público `IMP-XXXX-XXXX-XXXX`, alfabeto sem caracteres ambíguos, aleatório (não sequencial), e normalização do que a pessoa digita |
| `qr.py` | gerador de QR Code próprio (ISO/IEC 18004, versões 1–10, nível M): Reed-Solomon, intercalação, máscaras por penalidade, SVG |
| `integrity.py` | reconta o SHA-256 do arquivo guardado e compara com o registrado no upload |
| `timestamps.py` | carimbo interno (selo HMAC do servidor); RFC 3161 **recusa** sem ACT contratada |
| `custody.py` | cadeia de custódia por objeto; o encadeamento é calculado por gatilho no banco |
| `verifiable.py` | registro público: criação, curadoria do payload, consulta pública, revogação, substituição |
| `challenges.py` | segunda camada da assinatura (código de uso único ligado ao hash do conteúdo) |
| `identity.py` | níveis de identidade, envio de documento, decisão humana |
| `credentials.py` | catálogo de conselhos e fluxo documental da credencial profissional |
| `agreements.py` | acordos multiassinatura e acompanhamento longitudinal |

## 3. O que foi PRESERVADO (não reescrito)
`documents.sha256` e versionamento · cofre (magic bytes, conteúdo ativo em PDF, zip bomb, antivírus) · `signatures`
(estendida com `challenge_id` e `identity_level`, nunca substituída) · `professional_credentials` (estendida) ·
`auth_tokens` · `consents` · `FieldCipher` · `chain_heads`/`ts_canonical`/`forbid_mutation`/`guard_columns` ·
`audit_events` e `ledger_entries` (já encadeados por hash desde a 0002) · `users.locale` (existia e nunca era usada) ·
`organizations.ods`/`esg_focus` e `projects.ods` (arrays que agora têm catálogo) · Integration Hub.
Motivo: são mecanismos testados e auditados. Substituí-los seria risco sem ganho.

## 4. Fluxos
**Assinar e publicar o código**
```
documento no cofre → POST /v1/signatures/challenge  (código por e-mail, amarrado ao hash)
                   → POST /v1/signatures            (senha + código; grava assinatura + custódia)
                   → POST /v1/verifiable-records    (código público + QR + carimbo interno)
                   → PDF com QR impresso            (POST /v1/drafts/{id}/export)
```
**Verificar (terceiro, sem conta)**
```
GET /v1/public/verify/{code} → status · integridade (hash declarado × arquivo guardado) · versão assinada × versão atual
                             · quem assinou (papel; nome só em assinatura profissional) · carimbos · cadeia de custódia
```
**Acordo entre partes**
```
rascunho → partes definidas → publicar (hash congelado) → cada parte assina em duas camadas
        → todas as obrigatórias assinaram → vigente → entregas acompanhadas ao longo do tempo
        → código público do acordo
```
**Nova versão do documento**
O registro anterior vira `superseded` (continua verificável, dizendo que existe versão mais nova) e o novo nasce `active`.
A assinatura antiga permanece ligada à versão que ela realmente assinou.

## 5. Modelo canônico
26 tabelas novas (191 no total), todas com RLS. Grupos: identidade (`identity_verifications`, `identity_documents`),
conselhos e credenciais (`professional_councils`, `credential_verifications`), custódia (`trust_events`),
verificação pública (`verifiable_records`, `trust_timestamps`), assinatura (`signature_challenges`,
`signature_revocations`), acordos (`signed_agreements`, `signed_agreement_parties`, `signed_agreement_milestones`),
taxonomia (`sdg_goals`, `esg_pillars`, `social_determinants`, `impact_tags`), idioma (`locales`, `translations`),
financiamento (`funding_quotas`, `quota_pledges`, `campaigns`), honorários (`fee_tables`, `fee_items`,
`professional_services`) e diagnóstico guiado (`diagnosis_stages`, `diagnosis_progress`).
Detalhe coluna a coluna: `DATABASE_SCHEMA.md`.

## 6. Limites declarados
Assinatura qualificada ICP-Brasil/gov.br **não implementada** (dependência externa + homologação) · biometria e prova de
vida **não implementadas** (exigem provedor contratado; nenhum vetor biométrico é armazenado) · carimbo RFC 3161
**não implementado** (exige ACT) · SMS **não implementado** (sem provedor) · consulta on-line a conselho profissional
**não existe** (nenhuma API pública contratada) · edição on-line de Office/LibreOffice exige servidor WOPI
(**dependência externa**) · emblemas oficiais da ONU **não acompanham** a plataforma (marca protegida).
