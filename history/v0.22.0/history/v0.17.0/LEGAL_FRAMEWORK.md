# Arcabouço legal: onze minutas, nenhuma vigente

> Escrito na v0.17.0. Este documento explica o que o software faz com documento legal e aceite. Ele
> **não** é parecer jurídico, e as minutas que descreve **não** foram revisadas por advogado(a).

## 1. O estado verdadeiro, em uma frase

Há onze documentos legais registrados em `legal_documents`, todos em situação `draft` — **MINUTA /
DRAFT FOR LEGAL REVIEW** — e **nenhum aceite é registrável no banco** enquanto isso for verdade.

| Chave | Documento | Exige aceite | Situação |
|---|---|---|---|
| `terms_of_use` | Termos de Uso | sim | minuta |
| `privacy_policy` | Política de Privacidade | sim | minuta |
| `cookies` | Política de Cookies | não | minuta |
| `subscription` | Contrato de Assinatura (SaaS) | não | minuta |
| `marketplace` | Termos do Marketplace | não | minuta |
| `intermediation` | Termos de Intermediação | não | minuta |
| `payment` | Contrato de Pagamento | não | minuta |
| `cancellation` | Política de Cancelamento | não | minuta |
| `refund` | Política de Reembolso | não | minuta |
| `b2b` | Contrato Institucional (B2B/ESG) | não | minuta |
| `b2g` | Contrato com o Poder Público | não | minuta |

`GET /v1/legal/registry` devolve exatamente esta tabela, com `blocking_product` listando os documentos
que exigem aceite e não estão aprovados — hoje, os dois primeiros.

## 2. Por que o banco se recusa a registrar aceite de minuta

"O usuário aceitou os termos" é uma das afirmações mais fáceis de falsificar em qualquer produto, e uma
das mais caras quando é falsa. Dizê-la sobre um rascunho que nenhum advogado leu é afirmação falsa **com
aparência de prova** — pior que não ter registro nenhum.

Então a recusa está no banco, não na interface:

- `acceptance_stamp()` levanta exceção se o documento não estiver `approved` **e** vigente, com a
  mensagem dizendo qual documento e em que situação ele está;
- `approved_needs_review` (CHECK) recusa aprovação sem `reviewed_by`, `reviewed_at` e
  `review_reference` — aprovar sem dizer quem revisou, quando e sob qual referência é o mesmo que não
  revisar;
- `effective_needs_approved` (CHECK) recusa vigência que anteceda a aprovação;
- `legal_doc_status_guard()` impede a situação voltar atrás e supera a versão aprovada anterior quando
  uma nova é aprovada.

**Isso trava o produto de propósito.** Destravar não é programar: é contratar a revisão jurídica. A
alternativa — coletar aceite de rascunho — foi recusada.

## 3. O que a prova de aceite guarda

| Campo | Para quê |
|---|---|
| `document_id` + `doc_key` + `version` | qual documento, em qual versão |
| `body_sha256` | **o hash do texto aceito**, copiado do documento pelo gatilho |
| `user_id` (+ `org_id`) | quem aceitou, em nome de quem |
| `accepted_at`, `ip`, `user_agent`, `source` | quando e de onde |

O hash é o que torna a prova verificável: sem ele, "aceitou os termos" não diz **quais** termos. E ele é
**copiado do documento pelo gatilho**, nunca informado pelo cliente — cliente que informa hash pode
informar o hash de outro texto.

Texto de versão existente é **imutável** (`legal_doc_text_immutable()`): corrigir é publicar versão
nova. É assim que o aceite de ontem continua provando o texto de ontem, e que uma versão nova volta a
aparecer como pendente para quem já havia aceitado a anterior.

## 4. O conflito entre append-only e direito de eliminação

A prova é append-only. Mas ela guarda IP e agente de usuário, que são dado pessoal, e a exclusão de
conta anonimiza o titular. Com um gatilho que proíbe qualquer alteração, a anonimização seria recusada:
o produto teria de escolher entre a prova e o direito do titular.

A escolha foi **estreitar** o append-only em vez de afrouxá-lo. `acceptance_anonymize_only()` permite
exatamente uma alteração — apagar IP e agente de usuário — e recusa todas as outras; o GRANT de coluna
recusa antes ainda, porque o app só tem `UPDATE (ip, user_agent)`. A prova sobrevive sem eles: ela é o
documento, a versão, o hash do texto e o titular pseudonimizado.

Retenção: IP e agente de usuário de aceite com mais de 18 meses são apagados pelo job de retenção. O
corpo bruto de webhook de cobrança, que pode conter nome e e-mail do pagador, é esvaziado no mesmo
prazo — o evento fica, por idempotência; o conteúdo sai.

## 5. A fonte do texto é o repositório

Os onze textos vivem em `docs/legal/*.md`. A migração `0023_v0170_legal.sql` é **gerada** desses
arquivos por `scripts/gen_legal_registry.py`, e há teste que recalcula o sha256 de cada arquivo e o
compara com o banco. Contrato digitado duas vezes diverge um dia, e ninguém descobre qual foi aceito.

Para publicar uma versão nova: edite o arquivo, rode `python3 scripts/gen_legal_registry.py`, incremente
a versão na lista `DOCS` do gerador e aplique a migração. `python3 scripts/gen_legal_registry.py --check`
falha se o banco e os arquivos estiverem dessincronizados.

## 6. O que cada minuta declara que o software NÃO faz

Esta é a parte das minutas que não pode ser maquiada, e está em todas elas:

- **sem provedor de pagamento configurado** — nenhuma cobrança real foi processada;
- **sem nota fiscal** — não há provedor fiscal nem inscrição municipal;
- **sem SLA** — nenhuma disponibilidade foi medida em operação nem contratada;
- **sem assinatura qualificada, ICP-Brasil, gov.br, certificado digital ou biometria** (minuta B2G);
- **sem integração com SICONV/Transferegov, SIAFI, Portal da Transparência, e-SIC ou sistema de compras**;
- **sem custódia ou processamento de aporte** — e por isso sem success fee e sem take rate;
- **sem relatório pronto para CVM, GRI, SASB ou ISSB** (minuta B2B).

## 7. O que o proprietário precisa contratar

1. **Advogado(a)** para revisar as onze minutas. Sem isso, nenhum aceite é coletável e nenhuma receita
   sai do amarelo.
2. **Contador(a)** para regime tributário, município de prestação, código de serviço e emissão de NFS-e.
3. **Encarregado(a) de dados (LGPD art. 41)**, nomeado — hoje é um campo `{{ }}` nas minutas.
4. Decisão sobre razão social, CNPJ, endereço, foro e canais de contato, que também são `{{ }}`.

A pergunta que atravessa todas as minutas e que só o jurídico responde: **a organização contratante é
consumidora para fins do CDC?** A resposta muda cancelamento, reembolso, limite de responsabilidade e
foro. Nenhuma minuta assume uma resposta.
