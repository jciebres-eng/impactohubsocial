"""Oferta comercial e aceite: separar ACESSO GRATUITO de AUTORIZAÇÃO DE COBRANÇA.

O PROBLEMA QUE ESTE MÓDULO RESOLVE

Até a v0.20.0 havia um aceite só. A pessoa marcava "li e aceito", e isso valia tanto para "concordo
com os termos de uso" quanto, implicitamente, para "pode me cobrar quando acabar o período
gratuito". A auditoria desta rodada procurou literalmente por qualquer distinção entre os dois atos
e não achou nenhuma — `payment_method_required` tinha zero ocorrências no repositório inteiro.

Enquanto for um aceite só, o fim da gratuidade vira cobrança por omissão. Aqui são dois:

    consent_status = 'free_access'  → aceitou usar de graça. NÃO autoriza cobrança.
    consent_status = 'authorized'   → autorizou debitar, neste valor, nesta frequência.

E a invariante mora no banco (gatilho `charge_requires_authorization`, migração 0043), não aqui:
um módulo pode ser contornado por outro caminho de escrita; um gatilho, não.

PARCELAMENTO NÃO É RECORRÊNCIA — E RECORRÊNCIA NÃO EXISTE MAIS (v0.27.0, ADR-341)

    one_time     cobrança única;
    installment  UMA dívida dividida em N parcelas — acaba quando a última cai.

`recurring` foi retirado do modelo: o IMPACTO não vende assinatura. A oferta comercial passou a ser a
proposta de um CONTRATO (implantação, integração, módulo institucional, inteligência territorial) cujo
valor é decidido por quem tem alçada financeira, com motivo e auditoria — nunca lido de um catálogo de
mensalidades (que não existe) e nunca enviado pela organização que vai pagar.
"""
from __future__ import annotations

from ..http import ApiError

FREQUENCIES = ("one_time", "installment")
METHODS = ("card", "boleto", "pix", "manual")
CONSENT = ("free_access", "authorized")

MAX_INSTALLMENTS = {"card": 24, "boleto": 12}


def _org_cnpj(c, org_id: str) -> str | None:
    return c.scalar("SELECT cnpj FROM organizations WHERE id = $1", org_id)


def validate_payment_terms(c, *, org_id: str, payment_method: str, billing_frequency: str,
                           installments: int | None) -> None:
    """As regras de meio de pagamento. No BACKEND, porque é aqui que elas valem.

    A principal: BOLETO PARCELADO SÓ PARA CNPJ. Parcelamento em boleto é, na prática, uma venda a
    prazo — cada parcela é um título com vencimento futuro, e a plataforma fica exposta à
    inadimplência de cada um deles sem a garantia que a bandeira de cartão oferece. Para pessoa
    física isso é concessão de crédito, com o regime de proteção ao consumidor que vem junto. A
    plataforma não concede crédito a pessoa física; para pessoa jurídica identificada por CNPJ, o
    boleto a prazo é a forma usual de faturamento B2B.

    Validar isso na tela não bastaria: a tela é uma sugestão, a API é a porta.
    """
    if payment_method not in METHODS:
        raise ApiError(422, "payment_method_invalid", f"Meio de pagamento desconhecido: {payment_method}")
    if billing_frequency not in FREQUENCIES:
        raise ApiError(422, "billing_frequency_invalid", f"Frequência desconhecida: {billing_frequency}")

    if billing_frequency == "installment":
        if installments is None or installments < 2:
            raise ApiError(422, "installments_required",
                           "Parcelamento exige o número de parcelas (mínimo 2).")
        teto = MAX_INSTALLMENTS.get(payment_method)
        if teto is None:
            raise ApiError(422, "installments_not_supported",
                           f"Não há parcelamento para {payment_method}.")
        if installments > teto:
            raise ApiError(422, "installments_above_limit",
                           f"Máximo de {teto} parcelas para {payment_method}.")
        if payment_method == "boleto" and not _org_cnpj(c, org_id):
            raise ApiError(422, "boleto_installments_require_cnpj",
                           "Boleto parcelado é exclusivo para pessoa jurídica com CNPJ "
                           "cadastrado. Para pessoa física, use cartão ou boleto à vista.")
    elif installments is not None:
        raise ApiError(422, "installments_not_applicable",
                       "Número de parcelas só se aplica a parcelamento.")


def create(c, *, org_id: str, plan_key: str, amount_cents: int, amount_reason: str, billing_frequency: str,
           payment_method: str, installments: int | None = None, free_period_months: int | None = None,
           created_by: str | None = None, expires_at=None, contract_ref: str | None = None,
           currency: str = "BRL") -> dict:
    """Monta a proposta de CONTRATO para uma organização. O valor vem de quem tem alçada, com motivo.

    A organização que vai pagar nunca chama esta função (a rota é administrativa, permissão
    `finance.approve`): aceitar `amount_cents` do cliente seria deixar o cliente escrever o próprio
    preço. O pacote (`plan_key`) diz QUAIS capacidades o contrato libera ao ser aceito.
    """
    validate_payment_terms(c, org_id=org_id, payment_method=payment_method,
                           billing_frequency=billing_frequency, installments=installments)
    if amount_cents is None or amount_cents < 0:
        raise ApiError(422, "amount_required", "Informe o valor do contrato (centavos, >= 0).")
    if not c.one("SELECT 1 FROM plans WHERE plan_key = $1 AND active", plan_key):
        raise ApiError(404, "plan_not_found", "Pacote de capacidades não encontrado.")
    row = c.one(
        "INSERT INTO commercial_offers(org_id, pricing_version, plan_key,"
        " currency, amount_cents, amount_reason, contract_ref, billing_frequency, installments, payment_method,"
        " free_period_months, created_by, expires_at)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)"
        " RETURNING id::text, amount_cents, currency, billing_frequency, payment_method,"
        "           installments, free_period_months, pricing_version, contract_ref",
        org_id, _pricing_version(), plan_key, currency, amount_cents, amount_reason, contract_ref,
        billing_frequency, installments, payment_method, free_period_months, created_by, expires_at)
    return dict(row)


def _pricing_version() -> str:
    from .free_period import pricing_version
    return pricing_version()


def accept(c, settings, *, offer_id: str, org_id: str, user_id: str, consent_status: str,
           ip: str | None = None, user_agent: str | None = None) -> dict:
    """Registra o aceite com os campos que uma disputa exige.

    `consent_status` é escolha EXPLÍCITA de quem aceita, nunca inferida da oferta. Uma oferta com
    período gratuito não autoriza cobrança sozinha — se autorizasse, a separação entre os dois
    atos seria decorativa.
    """
    if consent_status not in CONSENT:
        raise ApiError(422, "consent_status_invalid",
                       "O aceite é de acesso gratuito (free_access) ou de autorização de "
                       "cobrança (authorized).")
    of = c.one(
        "SELECT id::text AS id, org_id::text AS org_id, plan_key,"
        " free_period_id::text AS fp, billing_frequency, payment_method, pricing_version, status,"
        " expires_at FROM commercial_offers WHERE id = $1", offer_id)
    if not of or of["org_id"] != org_id:
        raise ApiError(404, "offer_not_found", "Oferta não encontrada.")
    if of["status"] != "open":
        raise ApiError(409, "offer_not_open", f"Esta oferta está {of['status']}.")
    if of["expires_at"] and c.scalar("SELECT $1::timestamptz <= now()", of["expires_at"]):
        c.run("UPDATE commercial_offers SET status = 'expired' WHERE id = $1", offer_id)
        raise ApiError(409, "offer_expired", "Esta oferta venceu. Peça uma nova.")

    if consent_status == "authorized":
        # Uma autorização vigente por organização. Duas seriam duas respostas para "o cliente
        # autorizou o quê?", e a cobrança teria de escolher uma — em silêncio.
        c.run("UPDATE offer_acceptances SET revoked_at = now(), revoked_by = $2,"
              " revoke_reason = 'substituída por autorização mais recente'"
              " WHERE org_id = $1 AND consent_status = 'authorized' AND revoked_at IS NULL",
              org_id, user_id)

    row = c.one(
        "INSERT INTO offer_acceptances(offer_id, org_id, pricing_version, plan_key,"
        " free_period_id, billing_frequency, payment_method, terms_version,"
        " privacy_version, commercial_terms_version, accepted_by, ip, user_agent, consent_status)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)"
        " RETURNING id::text, accepted_at, consent_status",
        offer_id, org_id, of["pricing_version"], of["plan_key"], of["fp"],
        of["billing_frequency"], of["payment_method"], settings.terms_version,
        settings.privacy_version, of["pricing_version"], user_id, ip, user_agent, consent_status)
    c.run("UPDATE commercial_offers SET status = 'accepted' WHERE id = $1", offer_id)
    out = dict(row)
    out["plan_key"] = of["plan_key"]
    out["billing_frequency"] = of["billing_frequency"]
    return out


def grant_for_acceptance(c, *, org_id: str, plan_key: str, acceptance_id: str, billing_frequency: str) -> None:
    """A concessão nasce do CONTRATO aceito com autorização — e morre com a revogação (`revoke_contract_grants`).

    Chamar em contexto de sistema: `entitlement_grants` só aceita escrita privilegiada (gatilho
    `trg_grants_guard`), o que é correto — a organização não escreve o próprio direito.
    """
    c.run("INSERT INTO entitlement_grants(org_id, plan_key, source, source_ref, reason)"
          " VALUES ($1,$2,'contract',$3,$4)", org_id, plan_key, acceptance_id,
          f"Contrato aceito ({billing_frequency}) — aceite {acceptance_id[:8]}")


def revoke_contract_grants(c, *, org_id: str, user_id: str, reason: str) -> int:
    return c.run("UPDATE entitlement_grants SET revoked_at = now(), revoked_by = $2, revoke_reason = $3"
                 " WHERE org_id = $1 AND source = 'contract' AND revoked_at IS NULL", org_id, user_id, reason[:500])


def revoke(c, *, org_id: str, user_id: str, reason: str) -> bool:
    """Revoga a autorização de cobrança. Direito do cliente, e um UPDATE, não um DELETE.

    A prova de que ele autorizou em março continua existindo; a de que revogou em maio entra ao
    lado. Apagar a primeira destruiria a justificativa das cobranças que já aconteceram.
    """
    return bool(c.one(
        "UPDATE offer_acceptances SET revoked_at = now(), revoked_by = $2, revoke_reason = $3"
        " WHERE org_id = $1 AND consent_status = 'authorized' AND revoked_at IS NULL"
        " RETURNING 1 AS ok", org_id, user_id, reason))


def charge_authorized(c, org_id: str) -> bool:
    return bool(c.one("SELECT 1 FROM offer_acceptances WHERE org_id = $1"
                      " AND consent_status = 'authorized' AND revoked_at IS NULL", org_id))
