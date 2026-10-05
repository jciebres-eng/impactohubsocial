# Matriz de retenção de dados (LGPD)

Para cada categoria de dado: **base legal**, **finalidade**, **prazo**, **o que acontece no fim do prazo** e **quem
tem acesso**. Complementa `LGPD_AUDIT.md` (que trata do processo) e `docs/LGPD.md` (que trata do mapeamento).

Esta matriz descreve o que o **código** faz hoje. Onde o prazo é decisão do responsável pelo tratamento e não está
implementado, está escrito assim.

## 1. O que a plataforma deliberadamente NÃO coleta

Começa por aqui porque é a parte mais importante da matriz:

| Não coletamos | Por quê |
|---|---|
| **Nome, documento ou contato de beneficiário final** | O projeto guarda **contagem** e **descrição agregada** do público. A plataforma não precisa do nome da criança para acompanhar o projeto. Dado que não existe não vaza, não precisa de retenção e não aparece em pedido de eliminação. |
| Dado de saúde, religião, orientação sexual, filiação política ou sindical | Não há campo para isso. O match lista `sensitive_attributes` entre as entradas **proibidas**. |
| Dado biométrico | A verificação biométrica **não está implementada** (501 explícito). Se for contratada, exigirá política própria antes de entrar. |
| Localização precisa de pessoa | A geolocalização é de **projeto**, com precisão configurável (município por padrão) e consentimento para precisão maior. |
| Rastreamento publicitário | Não há cookie de terceiro, não há pixel, não há rede de anúncio. |

## 2. Dado de identificação e conta

| Dado | Base legal | Finalidade | Prazo | No fim do prazo |
|---|---|---|---|---|
| E-mail, nome, senha (hash scrypt) | execução de contrato | autenticar e operar | enquanto a conta existir | eliminação da conta **anonimiza**: e-mail vira `removido-<aleatório>@anonimizado.invalid`, nome vira "Titular removido", hash de senha vira nulo, segredo de TOTP apagado |
| Segredo do segundo fator (`mfa_secret_enc`) | execução de contrato | segurança da conta | enquanto ativo | apagado na eliminação; rotação de chave descrita em `KEY_ROTATION.md` |
| Códigos de recuperação do segundo fator (hash) | execução de contrato | recuperar acesso | enquanto ativos | apagados na eliminação |
| Assunto OIDC (`oidc_subject`) | execução de contrato | login federado | enquanto ativo | apagado na eliminação |
| Consentimentos (`consents`) | obrigação legal (prova do consentimento) | demonstrar base legal | **mantido** | mantido: é a prova de que o consentimento existiu e quando foi revogado |

## 3. Dado de sessão e segurança

| Dado | Prazo | Mecanismo |
|---|---|---|
| `rate_events` (controle de taxa, com IP) | **2 dias** | `jobs.retention` apaga |
| `auth_tokens` (confirmação, convite, redefinição) | **7 dias após expirar** | `jobs.retention` apaga |
| `oidc_states` | até expirar | `jobs.retention` apaga |
| `sessions` (IP, agente de usuário) | **30 dias após expirar o refresh** | `jobs.retention` apaga; na eliminação da conta o IP e o agente são **anulados na hora** |
| `ai_usage` (uso do assistente) | **13 meses** | `jobs.retention` apaga |
| `notifications` lidas | **180 dias** | `jobs.retention` apaga |
| Analytics da Central de Conhecimento | **18 meses** | `hub.retention` apaga |

## 4. Dado institucional e de projeto

| Dado | Base legal | Prazo | Observação |
|---|---|---|---|
| Organização, projeto, orçamento, marcos | execução de contrato / legítimo interesse | enquanto a organização existir | organização com um único membro que elimina a conta vira `closed`, com contato anulado |
| Documentos do cofre | execução de contrato | enquanto não apagados | exclusão é **lógica** (`deleted_at`) e apaga o texto extraído; o arquivo em si segue a política do armazenamento |
| Ideias, diagnósticos, versões de diagnóstico | execução de contrato | enquanto a organização existir | versões são imutáveis (append-only) |
| Retratos de projeto (`project_snapshots`) | legítimo interesse (acompanhamento) | enquanto o projeto existir | append-only |
| Riscos do projeto | legítimo interesse | enquanto o projeto existir | — |

## 5. Dado que NÃO é apagado, e por quê

| Dado | Por quê se mantém | O que é feito |
|---|---|---|
| `ledger_entries` (trilha encadeada) | integridade da prestação de contas; apagar uma entrada quebraria a verificação de todas as seguintes | mantido; o ator fica **pseudonimizado** quando a conta é eliminada (o `user_id` continua, mas o usuário já está anonimizado) |
| `audit_events` | obrigação legal e segurança | mantido, pseudonimizado |
| `commitments`, `expenses`, `invoices`, `payment_records` | obrigação legal (fiscal/contábil) | mantidos, pseudonimizados |
| `signatures` e `signature_revocations` | a assinatura precisa continuar verificável por terceiro | mantidas; são append-only por desenho |
| `project_transitions` | histórico de decisão | mantido, pseudonimizado |

O registro de eliminação (`privacy_requests`) diz isso textualmente: *"Dados pessoais anonimizados; registros de
auditoria e financeiros mantidos pseudonimizados"*. Não há promessa de apagar o que a lei manda guardar.

## 6. Direitos do titular — o que funciona hoje

| Direito | Rota | O que faz |
|---|---|---|
| Acesso e portabilidade | `GET /v1/privacy/export` | baixa um JSON com os dados do titular; registra o pedido |
| Eliminação / anonimização | `POST /v1/privacy/delete-account` | exige senha e confirmação; **recusa** se o titular é único dono de organização com outros membros (409 `transfer_ownership_first`); anonimiza, revoga sessões, apaga tokens |
| Revogação de consentimento opcional | `POST /v1/privacy/consents` | só consentimento opcional (comunicação); consentimento necessário à execução do contrato não é "revogável" sem encerrar a conta |
| Informação sobre o tratamento | `GET /v1/legal/privacidade` | política vigente, versionada |

## 7. Compartilhamento com terceiros

| Com quem | O que vai | Base |
|---|---|---|
| Verificação pública (qualquer pessoa com o código) | **apenas** os campos curados em `verifiable_records.public_fields`: signatário, papel, declaração, versão assinada, versão atual, hash, estado | ato do titular (ele cria o registro verificável) |
| Financiador com relação com o projeto | metadados de documento (tipo, situação, validade) via função restrita; **não** o conteúdo | execução de contrato |
| Diretório público de profissionais | o que o profissional publicou; geolocalização só com consentimento | consentimento |
| Provedor de e-mail (SMTP) | endereço e conteúdo da mensagem | execução de contrato |
| Provedor de pagamento (quando configurado) | o necessário para a cobrança | execução de contrato |
| Provedor de IA externo (quando configurado) | o texto enviado ao assistente | consentimento/contrato — e o padrão é o motor **local**, sem rede |

Nenhum dado é vendido, nenhum é usado para treinar modelo. O retorno humano sobre recomendações de match fica
disponível para calibração **com revisão humana** e sem dado pessoal (`calibration_dataset()` não devolve e-mail
nem identificador de organização).

## 8. Pendências honestas desta matriz

| Item | Situação |
|---|---|
| Prazo de retenção de documento do cofre após encerramento da organização | **não implementado**: hoje o documento fica. Definir prazo é decisão do responsável pelo tratamento, e a implementação é um job de retenção a acrescentar. |
| Eliminação do arquivo no armazenamento (S3/disco) ao excluir documento | exclusão é lógica; a remoção física do objeto é operação de infraestrutura e **não** está automatizada |
| Encarregado de dados (DPO) nomeado e canal publicado | decisão da organização que opera a plataforma, não do código |
| Relatório de impacto à proteção de dados (RIPD) | não produzido nesta versão |
| Registro de operações de tratamento (ROPA) formal | este documento é a base; o ROPA formal é documento jurídico a produzir |

Essas pendências estão aqui, e não escondidas, porque dizer "estamos em conformidade com a LGPD" sem elas seria
afirmação que não se sustenta em auditoria.
