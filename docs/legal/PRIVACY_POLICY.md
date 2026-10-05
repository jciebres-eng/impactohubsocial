# Política de Privacidade — Plataforma Impacto

> **MINUTA — [VALIDAR JURÍDICO]**. Redigida a partir do tratamento de dados que o código v0.7.0 efetivamente realiza.
> Bases legais, prazos de retenção e transferências internacionais **precisam ser confirmados por advogado(a)/DPO** antes da
> publicação. Campos `{{ }}` dependem do proprietário.

Versão da minuta: 2026-10-04

Esta política explica como tratamos dados pessoais conforme a **LGPD (Lei nº 13.709/2018)**.

## 1. Controlador e encarregado
Controlador: `{{RAZÃO SOCIAL}}`, CNPJ `{{CNPJ}}`. Encarregado(a): `{{NOME}}` — `{{E-MAIL}}`.
Para dados de beneficiários e equipes inseridos por uma OSC, **a OSC é controladora** e a Plataforma atua como operadora.

## 2. Dados tratados (inventário real)
| Categoria | Exemplos | Origem | Finalidade | Base legal proposta [VALIDAR] |
|---|---|---|---|---|
| Conta | nome, e-mail, hash de senha (scrypt), segredo TOTP cifrado, códigos de recuperação (hash) | usuário | autenticação e segurança | execução de contrato (art. 7º, V) |
| Sessão e segurança | hash de tokens, IP, user-agent, tentativas de login, eventos de auditoria | sistema | prevenção a fraude, auditoria | legítimo interesse (art. 7º, IX) / obrigação legal |
| Organização | razão social, CNPJ, endereço, causas, certificações | usuário | perfil, compatibilidade, KYB | execução de contrato |
| Documentos | estatutos, certidões, atas, comprovantes | usuário | candidatura, diligência, prestação de contas | execução de contrato |
| Projetos e execução | orçamento, marcos, despesas, evidências, indicadores | usuário | acompanhamento e relatórios | execução de contrato |
| Credenciais profissionais | conselho, número, UF, nome do titular | profissional | verificação e assinatura | execução de contrato |
| Cobrança | plano, status, identificadores do provedor de pagamento (sem dados de cartão) | provedor de pagamento | faturamento | execução de contrato / obrigação legal |
| Uso de IA | contagem de caracteres e de tokens, provedor, modelo, latência, **hash** do conteúdo (o texto não é registrado em log) | sistema | controle de custo e cota | legítimo interesse |

Dados de **beneficiários** devem ser inseridos de forma agregada (contagens), sem identificação individual. A Plataforma
**não solicita** dados sensíveis (art. 5º, II); se um documento os contiver, a OSC é responsável pela base legal.

## 3. Compartilhamento
- **Entre organizações**: somente o que o titular publica (projeto publicado) ou libera em diligência (documentos).
  O isolamento entre organizações é aplicado no banco de dados (Row-Level Security do PostgreSQL), não apenas na interface.
- **Operadores (suboperadores)** — apenas os ativados pelo proprietário na configuração:
  hospedagem `{{PROVEDOR CLOUD/REGIÃO}}`; armazenamento de arquivos S3-compatível `{{PROVEDOR}}`; e-mail transacional
  `{{PROVEDOR SMTP}}`; pagamentos `{{Stripe ou outro}}`; login corporativo OIDC (opcional, do cliente); IA generativa
  `{{Anthropic / compatível OpenAI / nenhum}}`. O padrão da instalação é **IA local por regras, sem envio a terceiros**.
- **IA de terceiros**: quando ativada, o texto é enviado **após remoção automática por padrões** de CPF, e-mail, telefone, CEP e RG (a remoção automática é
  uma camada de proteção, não garantia absoluta; nomes próprios não são removidos).
- Autoridades: mediante obrigação legal ou ordem judicial.

## 4. Transferência internacional
Ocorre se o proprietário ativar provedores fora do Brasil (ex.: IA, pagamentos). Mecanismo (art. 33): `{{cláusulas-padrão ANPD / outro}}` **[VALIDAR]**.

## 5. Retenção
| Dado | Prazo proposto [VALIDAR] |
|---|---|
| Conta ativa | enquanto durar a conta |
| Conta eliminada | anonimização imediata dos dados pessoais; registros de auditoria/ledger mantidos de forma pseudonimizada |
| Registros de acesso | 6 meses (Marco Civil, art. 15) |
| Documentos fiscais/prestação de contas | `{{5 a 10 anos conforme o instrumento}}` |
| Rascunhos e uploads abandonados | `{{N}}` dias |

## 6. Direitos do titular (art. 18)
Na área **Minha conta → Privacidade**: exportar dados (JSON), solicitar eliminação. Demais pedidos (correção, informação
sobre compartilhamento, revogação de consentimento, oposição) pelo e-mail do encarregado. Prazo de resposta: `{{15 dias}}`.

## 7. Segurança (medidas implementadas no código)
Senhas com scrypt; verificação em duas etapas (TOTP); sessões com cookies httpOnly e proteção CSRF; bloqueio após
tentativas falhas; limitação de taxa; isolamento por organização no banco (RLS); arquivos privados com antivírus e
bloqueio de conteúdo ativo; trilha de auditoria encadeada por hash; cabeçalhos de segurança (CSP). Incidentes serão
comunicados à ANPD e aos titulares conforme art. 48 e Resolução CD/ANPD nº 15/2024 **[VALIDAR]**.

## 8. Cookies
Ver `COOKIES.md`. A Plataforma usa apenas cookies estritamente necessários; não há cookies de publicidade nem de análise de terceiros.

## 9. Crianças e adolescentes
O cadastro é destinado a maiores de 18 anos que representam organizações. Projetos podem beneficiar crianças, mas
os dados devem ser agregados.

## 10. Alterações
Mudanças serão comunicadas por e-mail e na Plataforma. Data da última atualização no topo.
