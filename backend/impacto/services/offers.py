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

PARCELAMENTO NÃO É RECORRÊNCIA

São três `billing_frequency` distintos e nenhum é sinônimo do outro:

    one_time     cobrança única;
    installment  UMA dívida dividida em N parcelas — acaba quando a última cai;
    recurring    cobrança que se repete enquanto a assinatura existir — não acaba sozinha.

Confundir os dois últimos é o que faz alguém achar que comprou em 12x e descobrir que assinou
12 meses.
"""
from __future__ import annotations

from ..http import ApiError

FREQUENCIES = ("one_time", "installment", "recurring")
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
                       "Número de parcelas só se aplica a parcelamento. Recorrência não é "
                       "parcelamento: ela se repete em vez de terminar.")

    if billing_frequency == "recurring" and payment_method == "boleto":
        # Boleto não debita sozinho — alguém precisa pagar cada um. Chamar isso de recorrência
        # faria a plataforma prometer um automatismo que o meio de pagamento não tem.
        raise ApiError(422, "boleto_not_recurring",
                       "Boleto não tem débito automático. Para cobrança recorrente use cartão; "
                       "para pagar em boleto, escolha cobrança única ou parcelamento.")


def create(c, *, org_id: str, plan_key: str, interval: str | None, billing_frequency: str,
           payment_method: str, installments: int | None = None,
           free_period_months: int | None = None, created_by: str | None = None,
           expires_at=None) -> dict:
    """Monta uma oferta a partir do CATÁLOGO. O valor nunca vem do chamador.

    Receber `amount_cents` como argumento seria abrir a porta para uma oferta com preço que não
    existe em `plan_price_versions` — e aí o catálogo deixaria de ser a fonte única no exato
    momento em que ele mais importa, que é quando alguém vai pagar.
    """
    validate_payment_terms(c, org_id=org_id, payment_method=payment_method,
                           billing_frequency=billing_frequency, installments=installments)
    iv = interval or "month"
    preco = c.one(
        "SELECT id::text AS id, amount_cents, currency FROM plan_price_versions"
        " WHERE plan_key = $1 AND interval = $2 AND effective_until IS NULL", plan_key, iv)
    if not preco:
        raise ApiError(409, "price_not_defined",
                       "Este plano não tem preço de tabela para contratação online. "
                       "Solicite proposta comercial.")
    row = c.one(
        "INSERT INTO commercial_offers(org_id, pricing_version, plan_key, price_version_id,"
        " currency, amount_cents, billing_frequency, interval, installments, payment_method,"
        " free_period_months, created_by, expires_at)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)"
        " RETURNING id::text, amount_cents, currency, billing_frequency, payment_method,"
        "           installments, free_period_months, pricing_version",
        org_id, _pricing_version(), plan_key, preco["id"], preco["currency"],
        preco["amount_cents"], billing_frequency,
        iv if billing_frequency == "recurring" else None,
        installments, payment_method, free_period_months, created_by, expires_at)
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
        "SELECT id::text AS id, org_id::text AS org_id, plan_key, price_version_id::text AS pv,"
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
        " price_version_id, free_period_id, billing_frequency, payment_method, terms_version,"
        " privacy_version, commercial_terms_version, accepted_by, ip, user_agent, consent_status)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)"
        " RETURNING id::text, accepted_at, consent_status",
        offer_id, org_id, of["pricing_version"], of["plan_key"], of["pv"], of["fp"],
        of["billing_frequency"], of["payment_method"], settings.terms_version,
        settings.privacy_version, of["pricing_version"], user_id, ip, user_agent, consent_status)
    c.run("UPDATE commercial_offers SET status = 'accepted' WHERE id = $1", offer_id)
    return dict(row)


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
