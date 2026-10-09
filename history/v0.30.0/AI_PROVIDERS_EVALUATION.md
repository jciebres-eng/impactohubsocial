# AVALIAÇÃO DE PROVEDORES, BYOK E ALTERNATIVAS — v0.28.0 (ADR-351)

Conferido na documentação oficial em 08/10/2026 (fontes ao final). Nada aqui presume suporte técnico que a
documentação não afirme.

## 1. Fatos verificados sobre a API da Anthropic (Claude)

* **Autenticação:** chave de API (`Authorization: Bearer <chave>`; o cabeçalho legado `x-api-key` continua
  aceito), Workload Identity Federation (token curto obtido em `POST /v1/oauth/token` a partir do JWT de um
  provedor de identidade da própria infraestrutura) ou App Attest (apps iOS/macOS). O gateway do IMPACTO usa
  `x-api-key` + `anthropic-version` — compatível.
* **Cobrança:** a API é cobrada pelo Console (limites de gasto na página de Billing), separada dos planos
  de consumidor. O Help Center é explícito: *"Claude paid plans and the Claude Console are separate products"*
  e *"A paid Claude subscription enhances your chat experience, and the Claude API is billed separately."*
  (Max e Team incluem créditos mensais de API para a PRÓPRIA conta do assinante, não para aplicações de terceiros.)
* **Consequência para o IMPACTO:** **o e-mail/assinatura Claude.ai do cliente não paga nem autoriza chamadas feitas
  pelo IMPACTO.** Não existe "login com conta Claude" que transfira o custo de API ao cliente. O IMPACTO não pede,
  não armazena e não usa senha, sessão, cookie ou token de assinatura de Claude.ai (verificado: nenhuma rota do
  backend faz isso; `test_v0280_ai_usage_control` e `test_architecture` cobrem o perímetro de segredos).

## 2. Modos avaliados

| Modo | Descrição | Situação na v0.28.0 | Por quê |
| --- | --- | --- | --- |
| **A. Provedor contratado pelo IMPACTO** | chave da plataforma (`AI_API_KEY`), nunca no navegador; medição por usuário/organização/projeto/operação; orçamento; kill switch por provedor | **implementado** (gateway desde a v0.13.0; medição e custeio por operação nesta versão); provedor **não configurado** nesta instalação (`AI_PROVIDER=local`) | é o único modo em que o IMPACTO controla custo, política de risco, redação de dado pessoal e conciliação |
| **B. BYOK (chave do cliente)** | cliente informa a própria chave de API; o fornecedor cobra o cliente; o IMPACTO cobra só os serviços próprios | **NÃO LIBERADO** (documentado) | exigiria: cofre por tenant com criptografia e mascaramento; teste de conectividade sem revelar o segredo; revogação; proibição de fallback silencioso para a chave da plataforma; cache isolado por chave; redação de dado pessoal mantida; termos do fornecedor para uso por terceiros. O proprietário pediu cota, crédito e patrocínio primeiro; BYOK entra quando houver demanda institucional que justifique o suporte |
| **C. Patrocínio institucional** | financiador/governo/empresa custeia operações de organizações elegíveis | **implementado** (`ai_sponsorships`, ADR-348) | é receita (crédito comprado por quem pode pagar) em vez de custo (gratuidade) — e inclui quem não pode pagar |
| **D. Provedor alternativo / modelo local** | `openai_compatible` (qualquer servidor compatível, inclusive modelo open-weight hospedado); motor local determinístico | `openai_compatible` **suportado** pelo gateway; **motor local** cobre classificação de documento, resumo extrativo, estruturação por regras e TODA a similaridade | modelo local não é "grátis": custa CPU/infra (medido no piloto: desprezível para similaridade) e manutenção; roteamento por finalidade: categoria A/D local; B pode ir a externo com faixa de risco 1 |
| **E. Conexão de identidade (OAuth com conta Claude)** | — | **não aplicável** | não existe mecanismo oficial que atribua custo e autorização de API por login de consumidor (§1) |

## 3. Comparação das alternativas (critérios do pedido)

| Critério | A. API do IMPACTO + créditos | B. BYOK | C. Patrocínio | D. Alternativo/local | F. Híbrido adotado (A + C + D-local; B futuro) |
| --- | --- | --- | --- | --- | --- |
| Custo de implantação | médio (feito) | alto (cofre, isolamento, suporte) | baixo (feito) | baixo (feito para local) | — |
| Custo operacional | custo de modelo + suporte | suporte a chaves de clientes | nenhum adicional | CPU | — |
| Facilidade de uso | alta (prévia + confirmação) | baixa (cliente gerencia chave) | alta | alta | alta |
| Segurança | chave fora do navegador; redação; faixa | risco de vazamento por log/cache; fallback indevido | igual a A | sem saída de dado | — |
| Qualidade | depende do modelo contratado | idem | — | determinística, explicável, limitada | — |
| Latência | rede do provedor | idem | — | < 1 ms por par | — |
| Escalabilidade | limitada por orçamento | limitada por cada cliente | — | linear em candidatos | — |
| Dependência de fornecedor | alta (um provedor) | distribuída | — | nenhuma | média |
| Controle financeiro | total (execuções, estimado × medido) | parcial (custo fora do IMPACTO) | total | total | total |
| Restrições contratuais | termos do provedor | termos do provedor + do cliente | termos de crédito | nenhuma | — |
| Adequação aos perfis | todos | institucional avançado | OSC beneficiadas | todos | todos |

**Escolha:** híbrido A + C + D-local, com B documentado como futuro. Não foram criadas cinco arquiteturas em
produção: uma camada de uso (`usage_control`), um gateway, um motor local.

## 4. O que a interface diz (e o que não diz)

* "A análise utilizará a sua conexão de API configurada" **não aparece**: não há BYOK.
* Sem provedor configurado, a prévia diz "motor local, nada sai da instalação" e o custo externo é zero medido.
* Com provedor configurado e sem preço cadastrado, a prévia diz "não disponível (sem preço vigente do provedor)"
  — nunca zero.

## Fontes

* Claude API overview — autenticação e billing: https://platform.claude.com/docs/en/api/overview
* Claude API — métodos de autenticação (API keys, Workload Identity Federation, App Attest): https://platform.claude.com/docs/en/manage-claude/authentication
* Help Center — "I have a paid Claude subscription… why do I have to pay separately to use the Claude API and Console": https://support.claude.com/en/articles/9876003
