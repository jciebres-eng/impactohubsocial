# Vouchers (desconto e gratuidade)

## Quem faz o quê
- **Proprietário/Super Admin**: cria lotes e vouchers, define regras, revoga, vê relatórios.
- **Usuário (OSC, Empresa ou Prestador, conforme escopo)**: aplica o código no site (checkout ou "Meu plano → Tenho um código").
- **Aprovador**: segunda pessoa que aprova gratuidade acima do limiar configurável (dupla aprovação).

## Tipos
| Tipo | Efeito |
|---|---|
| `percent_off` | % de desconto em N ciclos de cobrança |
| `amount_off` | valor fixo (centavos, BRL) de desconto |
| `free_period` | N dias/meses sem cobrança no plano-alvo |
| `grant_plan` | **gratuidade**: concede o plano X por período definido (ou até data), sem cobrança |
| `grant_feature` | libera `featureKey`(s) específicas por período/limite |

## Atributos
`code_hash`, `code_hint` (últimos 4), `batch_id`, `type`, `value`, `scope` {papel(is), plano(s), tenant/CNPJ opcional}, `max_redemptions`, `per_org_limit` (padrão 1), `valid_from/until`, `duration`, `stackable` (padrão falso), `issued_by`, `approved_by`, `status` {draft, pending_approval, active, paused, revoked, exhausted, expired}, `notes`, `campaign`.

## Código
Alfabeto sem ambiguidade (sem 0/O/1/I), ≥ 12 caracteres aleatórios (CSPRNG), agrupados `XXXX-XXXX-XXXX`; armazenado **somente como hash** (HMAC com chave em vault); exibido uma vez na criação e em exportação protegida do lote. Códigos vinculados (a um CNPJ) quando a gratuidade for nominal.

## Fluxo de resgate (transação atômica)
1. Usuário autenticado informa o código → `validate` (sem efeito colateral).
2. Rate limit por IP/usuário/organização; falhas repetidas → atraso progressivo; resposta genérica.
3. `redeem`: dentro de uma transação, `SELECT … FOR UPDATE` no voucher; verificar status, janela, escopo (papel/plano/CNPJ), limites; inserir `voucher_redemption` (única por voucher+organização); criar `entitlement_grant` ou ajustar `subscription`; gravar `audit_event`.
4. Idempotência: mesma chamada com mesma chave não duplica.
5. Gratuidade (`grant_*`) não exige cartão; ao fim, rebaixa conforme `PLANS_AND_ENTITLEMENTS`.

## Regras de negócio
- Voucher **não** muda elegibilidade, score, ordenação ou posição de prestador.
- Não acumulam, exceto `stackable=true` explícito; máximo 1 desconto percentual por assinatura.
- Revogação: não retroage a cobranças já pagas; encerra benefício futuro com aviso e carência.
- Gratuidade acima do limiar (valor × duração × quantidade) → `pending_approval` por segunda pessoa.
- Lotes de campanha exportáveis (CSV protegido) para distribuição por patrocinadores/parceiros.
- Mensagens ao usuário: nunca revelar se um código "existe" ao errar.

## Relatórios do admin
Emitidos/ativos/resgatados/expirados por campanha; custo do benefício; conversão para pago; resgates por território/papel; alertas de anomalia (muitos resgates por IP/dispositivo, tentativas falhas).

## Aspectos legais e contábeis **[VALIDAR]**
Termos do voucher (validade, não transferível, revogação); tratamento contábil/fiscal de gratuidade e descontos; emissão de nota somente sobre valor efetivamente cobrado; se a gratuidade patrocinada por terceiros a OSCs tem implicações; proteção de dados no vínculo a CNPJ/pessoa.

## Testes obrigatórios
Concorrência (N resgates simultâneos do último uso → 1 sucesso); expiração; escopo errado; reuso; brute-force limitado; revogação; dupla aprovação; idempotência; auditoria completa; match idêntico com/sem voucher.
