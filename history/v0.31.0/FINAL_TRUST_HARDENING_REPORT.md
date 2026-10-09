# FINAL_TRUST_HARDENING_REPORT — v0.14.0 (2026-10-05)

Etapa do roteiro: **TRUST / IDENTITY / SIGNATURE** (4 de 12). Camada obrigatória de engenharia antes do design.
Nenhum redesign, nenhuma animação, nenhuma identidade visual alterada — era proibido nesta etapa.
Vocabulário: **IMPLEMENTADO** · **PARCIAL** · **ESTRUTURADO** · **NÃO IMPLEMENTADO** · **DEPENDÊNCIA EXTERNA** ·
**HOMOLOGAÇÃO NECESSÁRIA** · **AUTORIZAÇÃO EXTERNA NECESSÁRIA** · **VALIDAÇÃO JURÍDICA NECESSÁRIA**.

---

## 1. Resumo executivo
A plataforma passou a produzir documentos **conferíveis por terceiros**: qualquer pessoa com o código impresso (ou o QR)
abre `/verificar` sem ter conta e descobre se o documento é genuíno, **qual versão foi assinada**, se a integridade
permanece intacta, quem assinou e se foi revogado. Essa era a característica que o proprietário fez questão de ter, e é
o que diferencia a IMPACTO de um repositório de arquivos.
Para sustentar isso, a assinatura virou **duas camadas** (senha + código de uso único amarrado ao hash do conteúdo), cada
documento ganhou **cadeia de custódia encadeada por hash**, e identidade e credencial profissional passaram a ter
**decisão humana registrada** — sem que ninguém consiga promover a si mesmo.
Números: **26 tabelas** novas (191 no total), **63 rotas** novas (574 operações), **96 testes** novos (**564 no total,
0 falhas**), 13 telas, ~7.500 linhas.
**Veredito:** GREEN para a fundação técnica; YELLOW para o que depende de validação externa (formatos no Office, QR em
leitor comercial, retenção jurídica); RED para assinatura qualificada, biometria, SMS e carimbo de ACT — **nenhum deles
está implementado, e a plataforma recusa explicitamente em vez de simular**.

## 2. Estado antes (auditoria do código real, não dos documentos)
`TRUST_INVENTORY.md` tem o inventário completo. Em resumo: **existiam 16 mecanismos** aproveitáveis e **20 lacunas**.
Já existia (e foi preservado): hash SHA-256 de todo documento · versionamento · cofre com antivírus e validação binária ·
**cadeia de hash de auditoria e do razão desde a migração 0002** · assinatura avançada com reautenticação por senha e
selo HMAC · credencial profissional como modelo · tokens por e-mail · MFA · cifragem de campo · consentimento ·
geração de PDF · Integration Hub.
Não existia: **verificação pública**, código/QR, revogação, carimbo, segunda camada, identidade da pessoa, biometria,
catálogo de conselhos, cadeia de custódia **por documento**, acordo multiassinatura, taxonomia ODS/ESG, idioma, tema,
exportação em formatos de escritório, cotas, honorários, geo de organização, diagnóstico guiado.
Uma descoberta importante da auditoria: `signatures.method` aceitava `icp_brasil` e `govbr` desde a v0.7.0, mas
**nenhum código produzia esses valores** — era enum sem implementação, classificado como **ESTRUTURADO**, e continua assim.

## 3. Estado depois
| Dimensão | Antes | Depois |
|---|---|---|
| Conferência por terceiro | impossível (tudo exigia login e mesma organização) | **página pública com código e QR** |
| Camadas da assinatura | 1 (senha) | **2** (senha + código amarrado ao hash) |
| Revogação | inexistente | fato novo, com motivo e data visíveis publicamente |
| Custódia | por organização e por projeto | **também por documento/rascunho/acordo**, append-only |
| Identidade da pessoa | só e-mail confirmado | 6 níveis, com conferência humana e trilha |
| Credencial profissional | modelo sem fluxo | fluxo documental completo, com catálogo de 20 conselhos |
| Acordo entre partes | inexistente | multiassinatura com hash congelado e acompanhamento |
| Carimbo de tempo | inexistente | interno assinado (ACT declarada como ausente) |
| Formatos de saída | PDF, CSV, JSON | **+ docx, xlsx, odt, ods, xml**, e PDF com QR |
| Idioma | coluna nunca usada | 3 idiomas com **cobertura declarada** |

## 4. Arquitetura
`TRUST_ARCHITECTURE.md`. Princípio: **a página pública nunca lê tabela privada** — o que é público é curado na criação e
gravado em `verifiable_records.public_fields`. Três consequências: assinatura append-only (revogar é fato novo);
ninguém se promove (colunas guardadas no banco); e o que não existe recusa, não simula.
Módulos: `codes` · `qr` · `integrity` · `timestamps` · `custody` · `verifiable` · `challenges` · `identity` ·
`credentials` · `agreements`.

## 5. Alterações
**Novos:** 10 módulos em `backend/impacto/trust/`, `services/formats.py`, `api/trust_routes.py` e `api/platform_routes.py`
(63 rotas), `api/trust_schemas.py`, `migrations/0012_v0140_trust_layer.sql`, `config/i18n.json`,
`tests/test_v0140_trust.py`, `tests/test_e2e_v0140_trust.py`, 6 páginas de frontend, 11 documentos.
**Modificados (mínimo):** `api/document_routes.py` (segunda camada na assinatura + exportação em 3 formatos),
`api/schemas.py` (campo `code`), `db/migrate.py` (sincronização de traduções), `services/directory.py` (geo e ODS no
card), `integrations/files.py` (8 formatos de exportação), `web/src/app.tsx` e `styles.css` (rotas, navegação e
`data-theme` **sem token de cor novo**), `tests/support.py`, `tests/test_api_workflow.py` (4 chamadas adaptadas ao
contrato novo), `tests/test_architecture.py`.
**Não tocados de propósito:** `http.py`, autenticação, RBAC, cobrança, Central de Conhecimento, Integration Hub.

## 6. Capacidades que já existiam (preservadas)
Listadas em `TRUST_INVENTORY.md` §3. Decisão: estender, nunca substituir. `signatures` ganhou três colunas e continua
append-only; `professional_credentials` ganhou três colunas e manteve o gatilho que força o estado inicial;
`chain_heads` e `guard_columns` da 0002 passaram a servir também à camada nova.

## 7. Capacidades preparadas, não exercitadas contra o mundo real
| Capacidade | Classificação | Observação honesta |
|---|---|---|
| Adapter de identidade no Integration Hub | **ESTRUTURADO** | `identity_verifications.provider_key` referencia o provedor; nenhum provedor ativo |
| `signatures.method = icp_brasil / govbr` | **ESTRUTURADO** desde a v0.7.0 | nenhum código produz esses valores |
| `trust_timestamps.kind = rfc3161` | **ESTRUTURADO** | coluna do token existe; emissão recusa com 501 |
| `signature_challenges.channel = sms` | **ESTRUTURADO** | domínio aceita; a API recusa com 501 |

## 8. O que foi realmente testado
**564 testes, 0 falhas** — `docs/evidence/test_run_v0.14.0.log`. Banco criado do zero a cada execução (12 migrações).
Detalhamento classe a classe: `TRUST_TESTING.md`.
Destaques: verificação pública sem dado pessoal (provado no corpo da resposta **e** na página renderizada no navegador) ·
arquivo adulterado detectado · cadeia irreescrevível pela aplicação **e** pelo contexto de sistema · adulteração como
dono do banco detectada no `seq` exato · 4 assinaturas simultâneas com o mesmo código ⇒ **1** · 4 reservas simultâneas
não estouram a cota · autopromoção bloqueada no banco · biometria/SMS/RFC 3161 recusando · contraste AA medido no tema
escuro manual.

## 9. Testes executados
Suíte completa + `ruff` (All checks passed) + `tsc --noEmit` (PASS) + `node build.mjs` (PASS) + `compileall` (PASS) +
`gen_api_docs` (574 operações) + migração em banco vazio a cada rodada.

## 10. Falhas encontradas durante a construção
1. **Gatilho de capacidade de cotas passava em silêncio** — `SELECT ... FOR UPDATE` aplica a política de UPDATE; a cota
   sumia para quem apoia e os `NULL` anulavam todas as checagens. Dava para reservar cota inexistente (`remaining: -1`).
2. **Payload público só continha as assinaturas visíveis** a quem pediu o código — num acordo entre organizações, a
   página pública sairia com um signatário em vez de dois.
3. **Recursão infinita de política de RLS** entre `signed_agreements` e `signed_agreement_parties`.
4. **Colisão de nome**: `agreements` já existia desde a 0008 (convênio de licenciamento) — domínio completamente
   diferente. O banco recusou a migração.
5. **Três guardas meus bloqueavam transições legítimas de autosserviço** (identidade → `under_review`, credencial →
   `document_submitted`, registro → `superseded`).
6. **`UPDATE` em `signatures`** para gravar o nível de identidade — a tabela é append-only desde a 0002.
7. **`trust_timestamps` e `trust_events` exigiam privilégio** no INSERT, quebrando a gravação na transação do fato.
8. **Unicidade do endereço da campanha** checada sob RLS: duas organizações conseguiam o mesmo endereço.
9. **Gatilho `trg_touch` em tabelas sem `updated_at`** (falha só em tempo de execução).
10. **Leitor de docx/odt não desfazia entidades XML** (`&amp;` voltava literal).
11. **Páginas novas do frontend passavam o erro cru para o `StateView`**, que espera texto — a mensagem da API não aparecia.
12. **Página de preferências sem `<h1>`** (quebrava a hierarquia de cabeçalhos).
13. **Documentos ficam em `pending_scan`** quando não há antivírus configurado; meu código exigia `clean` e travava o
    fluxo de identidade em qualquer instalação sem clamd.

## 11. Falhas corrigidas
Todas as 13. Decisões relevantes:
- (1) a função virou **SECURITY DEFINER** com checagem explícita de `NULL`, e passou a somar **todas** as reservas.
  Generalizado em ADR 103: **guarda de integridade não pode depender de visibilidade por RLS**.
- (2) o payload público passou a ser montado em **contexto de sistema** — é o servidor curando o que é público, e só o
  que `build_public_fields` monta entra.
- (3) travessia entre as duas tabelas passou por funções **SECURITY DEFINER** (ADR 104).
- (4) renomeado para `signed_agreements` — o nome ficou melhor, inclusive.
- (5) os avanços de estado viraram **passos privilegiados explícitos** (`mark_under_review`, `mark_submitted`), mantendo
  a coluna guardada. `superseded_by` saiu da guarda, com justificativa no próprio SQL.
- (6) o nível de identidade passou a ser gravado **no INSERT**, via `identity_level()` (SECURITY DEFINER).
- (13) passou a usar `usable_statuses()`, que **já existia** exatamente para isso — aceita `pending_scan` quando não há
  antivírus, e nunca `infected`/`rejected`. **O cofre não foi enfraquecido.**

## 12. Riscos restantes
| Risco | Gravidade | Estado |
|---|---|---|
| Nenhuma assinatura qualificada (ICP-Brasil/gov.br) | **Alta** para atos que a lei exige | **AUTORIZAÇÃO EXTERNA + HOMOLOGAÇÃO** |
| Formatos nunca abertos no Office/LibreOffice | Média | teste manual obrigatório antes do piloto |
| QR nunca lido por leitor comercial | Média | idem |
| Rotação da chave invalida selos antigos | Média | **DEPENDÊNCIA DE INFRAESTRUTURA** |
| Retenção de custódia, identidade e registros públicos | Média | **VALIDAÇÃO JURÍDICA NECESSÁRIA** |
| Conferência documental sujeita a erro humano | Média | mitigado por justificativa obrigatória e trilha; treinar a equipe |
| Sem pentest e sem teste de carga | Média | antes do piloto aberto |
| Auditoria de dependências | Média | registros bloqueados; obrigatória em CI |
| Documento de identidade guardado no cofre | Média | prazo de descarte a definir com o jurídico |

## 13. Dependências externas (nada disso depende de código)
Certificado ICP-Brasil e biblioteca PAdES/CAdES · credenciamento gov.br · provedor de biometria e prova de vida ·
Autoridade de Carimbo de Tempo · provedor de SMS · servidor WOPI para edição on-line · autorização de uso dos emblemas da
ONU · tabelas oficiais de honorários dos conselhos (documento + data) · gerenciador de segredos · decisão jurídica sobre
retenção e sobre o que cada organização aceita como assinatura.

## 14. Segurança
`TRUST_SECURITY.md`. **GREEN** em autopromoção, duas camadas, custódia, integridade, dado pessoal na página pública,
falsificação de assinatura de outra parte, supervenda de cotas, honorário sem fonte, IDOR, injeção em XML e em planilha,
enumeração de código. **YELLOW** em injeção em log, leitura de docx/odt e rotação de chave. **RED** em pentest e
auditoria de dependências.

## 15. LGPD (técnico; não é parecer jurídico)
`LGPD_AUDIT.md` §camada de confiança. **GREEN**: minimização na identificação (nenhum número, imagem ou biometria é
armazenado), minimização na página pública (payload curado, não filtrado na saída), consentimento datado para
localização, rastreabilidade sem conteúdo do documento. **YELLOW**: retenção sem prazo definido, eliminação a pedido
versus valor probatório da assinatura, e dado de terceiro dentro do documento enviado.

## 16. Performance
A suíte completa roda em ~260 s com banco recriado. A verificação pública faz: 1 consulta ao registro, 1 ao documento,
1 recontagem do arquivo (I/O), 1 consulta de carimbos, 1 de verificação de cadeia e 1 UPDATE de contador.
**NÃO VERIFICADO**: comportamento com volume de produção. A recontagem do arquivo a cada consulta pública é o ponto que
mais vai doer com arquivo grande e código muito consultado — a mitigação natural é cache por `(código, hash)`, e isso
está registrado como melhoria, não feito.

## 17. Observabilidade
Cada fato da camada entra na cadeia de custódia **e** em `audit_events` (que já era encadeado). O contador de consultas
públicas por registro mostra se um documento está circulando. Decisões humanas (identidade, credencial, confirmação de
apoio, publicação de honorário) ficam com autor e justificativa.
Falta: métrica agregada de verificações por período e alerta para `integrity_failed` — hoje o fato é registrado mas não
dispara aviso. Registrado como próximo passo.

## 18. Próximos passos
1. **Design** (próxima etapa): §12 do `DESIGN_HANDOFF.md`, com destaque para a página pública de verificação.
2. Testes manuais obrigatórios: abrir docx/xlsx/odt/ods no Office e no LibreOffice; ler o QR com leitor comercial.
3. Decisões humanas: retenção, base legal, o que cada organização aceita como assinatura, autorização dos emblemas da ONU.
4. Infraestrutura: gerenciador de segredos com versionamento de chave; alerta para `integrity_failed`.
5. Se houver exigência legal de assinatura qualificada, contratar certificado/credenciamento — o adapter entra pelo
   Integration Hub.
6. CI com `npm audit`/`pip-audit`; pentest; teste de carga.

## 19. Handoff de design
`DESIGN_HANDOFF.md` §12: 13 telas implementadas, todos os estados em listas fechadas, **10 invariantes que o design não
pode suavizar** e os 5 lugares onde o design agrega mais. O pedido do proprietário (menus horizontais retráteis e área de
trabalho ampla em vez de menu lateral) está registrado em §12.5 — **não foi implementado de propósito**, porque é
reestruturação de navegação, ou seja, design.

## 20. Prontidão para produção
| Dimensão | Classificação |
|---|---|
| Fundação técnica da camada de confiança | **GREEN** |
| Verificação pública por terceiro | **GREEN** |
| Assinatura avançada em duas camadas | **GREEN** |
| Cadeia de custódia e integridade | **GREEN** |
| Identidade e credencial (conferência humana) | **GREEN** |
| Testes | **GREEN** (564, 0 falhas) |
| Prontidão para design | **GREEN** |
| Formatos de escritório e QR | **YELLOW** — validação manual pendente |
| Retenção e base legal | **YELLOW** — **VALIDAÇÃO JURÍDICA NECESSÁRIA** |
| Rotação de chave / segredos | **YELLOW** — **DEPENDÊNCIA DE INFRAESTRUTURA** |
| Assinatura qualificada (ICP-Brasil/gov.br) | **RED** — **AUTORIZAÇÃO EXTERNA + HOMOLOGAÇÃO** |
| Biometria, prova de vida, SMS, carimbo de ACT | **RED** — **NÃO IMPLEMENTADOS** (recusam explicitamente) |
| Edição on-line de Office/LibreOffice | **RED** — **DEPENDÊNCIA EXTERNA** (servidor WOPI) |
| Pentest e carga | **RED** — não executados |
| **Veredito** | **pronta para a etapa de design e para piloto controlado; não pronta para produção aberta** |
