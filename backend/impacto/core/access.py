"""Motor único de decisão de acesso: AccessContext e AccessDecision.

O QUE EXISTIA ANTES

A decisão de acesso era a função `authorize()` em `http.py` — 27 linhas, quatro eixos que não se
combinavam (`auth`, `kinds`, `min_role`, `feature`), e um atalho: `ctx.admin_mode = True` desligava
`require_role`, `require_feature` e `check_limit` de uma vez e ligava `app.platform_admin` na RLS.

Para a equipe INTERNA havia um booleano só, `users.is_platform_admin`. Quem o tivesse alcançava as
193 rotas `auth="admin"` — receita, custo de IA, fatura, tabela de preço — sem nenhum papel
financeiro no caminho. Três papéis nomeados existiam (`editor`, `reviewer`, `support`) e os três
eram de conteúdo.

O QUE ESTE MÓDULO FAZ

Reúne, numa estrutura só, tudo que uma decisão de acesso precisa saber, e devolve decisões
EXPLICÁVEIS — com motivo, origem e o que faltou. Explicável importa por dois motivos: a tela precisa
dizer à pessoa por que não pode (e o que fazer a respeito), e a auditoria precisa reconstruir por
que alguém pôde.

O QUE ELE NÃO FAZ

Não substitui as travas do banco. RLS, gatilhos de imutabilidade e a exigência de autorização de
cobrança continuam valendo e são a última palavra — este módulo decide ANTES, com mensagem melhor.
Um motor de decisão em Python que fosse a única proteção seria contornável pelo próximo caminho de
escrita que alguém criasse.

ORDEM DE AVALIAÇÃO — importa, e é esta:

    autenticado? → sessão válida? → MFA quando exigido → papel interno ou organização ativa
    → tipo de organização → papel na organização → permissão interna → recurso do plano → limite

Permissão interna vem ANTES de recurso do plano de propósito: alguém da equipe interna agindo em
nome de um cliente não deve ser barrado pelo plano DELE, e a pergunta "esta pessoa pode ver
dinheiro?" não depende de qual plano o cliente assinou.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..http import ApiError
from ..observability import METRICS

# Permissões que exigem reautenticação recente, por serem irreversíveis ou financeiras. A lista é
# aqui, e não no banco, porque é regra de SEGURANÇA: mudá-la deve aparecer no diff e passar por
# revisão de código, não por um UPDATE em produção.
STEP_UP_PERMISSIONS = frozenset({
    "finance.approve", "finance.write", "accounting.close", "accounting.write",
    "billing.refund", "instruction.approve", "instruction.create",
    "treasury.write", "fiscal.issue", "fiscal.cancel",
    # Encontradas pelo próprio teste da lista: mexer em centro de custo ou em orçamento é mudar a
    # configuração que classifica e limita gasto. Quem muda a régua muda o resultado de todas as
    # medições feitas depois.
    "budget.write", "cost_center.write",
    "security.keys.write", "security.audit.export",
    "admin.users.write", "admin.organizations.write", "maintenance.execute",
    # Encontradas por AUDITORIA INDEPENDENTE desta versão. Estavam numa lista de isenção cujo
    # comentário dizia "o resto sim" e as isentava — isto é, o comentário contradizia a lista:
    #   `billing.write`      → `POST /v1/admin/invoices/{id}/paid` marca fatura de CLIENTE como
    #                          paga, e `manual-subscription` concede assinatura. Uma sessão de
    #                          cobrança sequestrada dava baixa em fatura sem confirmar identidade,
    #                          enquanto mudar o preço de um plano exigia.
    #   `free_period.write`  → concede gratuidade. É conceder privilégio comercial.
    "billing.write", "free_period.write",
    # v0.23.0: parar a plataforma interrompe o trabalho de todas as organizações ao mesmo tempo. É
    # a operação mais destrutiva alcançável sem acesso ao banco, e a mais atraente para quem
    # sequestrou uma sessão interna — negação de serviço com as credenciais da própria vítima.
    "security.kill_switch",
})

# Papéis que NÃO alteram nada. Usado para recusar, por desenho, qualquer permissão de escrita
# concedida a eles por engano numa migração futura.
READ_ONLY_ROLES = frozenset({"audit", "analyst"})


@dataclass
class AccessDecision:
    """Resposta do motor. Sempre com motivo; nunca só um booleano."""
    allowed: bool
    reason: str
    source: str = "engine"
    required_permission: str | None = None
    required_plan: str | None = None
    required_role: str | None = None
    remaining: int | None = None
    pay_per_use_available: bool = False
    step_up_required: bool = False

    def as_dict(self) -> dict:
        d = {"allowed": self.allowed, "reason": self.reason, "source": self.source}
        for k in ("required_permission", "required_plan", "required_role", "remaining"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.pay_per_use_available:
            d["pay_per_use_available"] = True
        if self.step_up_required:
            d["step_up_required"] = True
        return d

    def raise_if_denied(self) -> None:
        if self.allowed:
            return
        # 402 quando o caminho é COMERCIAL (falta plano ou franquia) e 403 quando é de AUTORIZAÇÃO.
        # A distinção é a diferença entre "compre" e "você não deveria estar aqui", e a tela trata
        # as duas de formas muito diferentes.
        if self.reason in ("feature_not_in_plan", "plan_limit_reached"):
            raise ApiError(402, self.reason, _MESSAGES[self.reason], self.as_dict())
        if self.step_up_required:
            raise ApiError(401, "step_up_required", _MESSAGES["step_up_required"], self.as_dict())
        # `forbidden()` não carrega detalhes, e aqui os detalhes SÃO a mensagem útil: a tela
        # precisa saber qual permissão faltou para dizer a quem pedir.
        raise ApiError(403, self.reason, _MESSAGES.get(self.reason, "Operação não permitida"),
                       self.as_dict())


_MESSAGES = {
    "unauthenticated": "Autenticação necessária",
    "no_active_org": "Selecione ou crie uma organização",
    "wrong_org_kind": "Recurso indisponível para este tipo de organização",
    "insufficient_role": "Seu papel nesta organização não permite esta operação",
    "admin_only": "Área restrita à administração da plataforma",
    "mfa_required": "Esta área exige MFA ativo e verificado nesta sessão",
    "permission_denied": "Seu papel na equipe não inclui esta permissão",
    "read_only_role": "Seu papel é somente de leitura",
    "feature_not_in_plan": "Recurso não incluído no seu plano",
    "plan_limit_reached": "Limite do plano atingido",
    "email_not_verified": "Confirme seu e-mail para realizar esta ação",
    "step_up_required": "Confirme sua identidade para continuar",
}


@dataclass
class AccessContext:
    """Tudo que decide um acesso, reunido uma vez por requisição.

    Montado a partir do `Principal` (sessão, já carregado pelo roteador) mais UMA consulta ao banco
    para permissões internas e estado comercial. Uma consulta, e não cinco: isto roda em toda
    requisição autenticada.
    """
    user_id: str
    email: str
    # identidade
    is_platform_admin: bool = False
    staff_roles: tuple[str, ...] = ()
    permissions: frozenset[str] = frozenset()
    mfa_enabled: bool = False
    mfa_verified: bool = False
    email_verified: bool = False
    reauth_at: object | None = None        # datetime da última reautenticação nesta sessão
    # organização ativa
    org_id: str | None = None
    org_kind: str | None = None
    org_name: str | None = None
    role: str | None = None
    # comercial
    plans: tuple[str, ...] = ()
    features: frozenset[str] = frozenset()
    limits: dict = field(default_factory=dict)
    commercial_state: str | None = None     # v0.27.0: FREE_ACCESS | FREE_GRANT | GRANT_EXPIRING | CONTRACTED (sem assinatura)
    free_period_end: object | None = None
    charge_authorized: bool = False

    # -- identidade interna ---------------------------------------------------------------------

    @property
    def is_staff(self) -> bool:
        return bool(self.staff_roles) or self.is_platform_admin

    @property
    def is_read_only_staff(self) -> bool:
        """Só papéis de leitura. `audit` que também seja `finance` não é somente leitura."""
        return bool(self.staff_roles) and set(self.staff_roles) <= READ_ONLY_ROLES

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_role(self, minimum: str) -> bool:
        from ..http import ROLE_ORDER
        return (self.role is not None
                and ROLE_ORDER.index(self.role) >= ROLE_ORDER.index(minimum))

    # -- decisões -------------------------------------------------------------------------------

    def can(self, *, permission: str | None = None, feature: str | None = None,
            min_role: str | None = None, kinds: tuple[str, ...] | None = None,
            needs_org: bool = False) -> AccessDecision:
        """A decisão composta. Devolve, não levanta — para que a tela possa perguntar sem errar."""
        if kinds and self.org_kind not in kinds:
            return AccessDecision(False, "wrong_org_kind")
        if needs_org and not self.org_id:
            return AccessDecision(False, "no_active_org")
        if min_role and not self.has_role(min_role):
            return AccessDecision(False, "insufficient_role", required_role=min_role)
        if permission:
            if not self.has_permission(permission):
                return AccessDecision(False, "permission_denied", source="staff_roles",
                                      required_permission=permission)
            if permission.split(".")[-1] not in ("read", "export") and self.is_read_only_staff:
                # Cinto e suspensório: se uma migração futura conceder escrita a `audit` por
                # engano, a recusa continua acontecendo aqui.
                return AccessDecision(False, "read_only_role", source="staff_roles",
                                      required_permission=permission)
            if permission in STEP_UP_PERMISSIONS and not self._reauth_fresh():
                return AccessDecision(False, "permission_denied", source="step_up",
                                      required_permission=permission, step_up_required=True)
        if feature and not self._has_feature(feature):
            return AccessDecision(False, "feature_not_in_plan", source="plan",
                                  required_plan=_cheapest_plan_with(feature))
        return AccessDecision(True, "allowed", source="engine")

    def _has_feature(self, feature: str) -> bool:
        return "*" in self.features or feature in self.features

    def _reauth_fresh(self, window_seconds: int = 900) -> bool:
        """Reautenticação vale por 15 minutos.

        Janela, e não "uma vez por sessão": uma sessão de 30 dias com reautenticação feita no
        primeiro dia não prova nada sobre quem está no teclado no trigésimo.
        """
        if self.reauth_at is None:
            return False
        from datetime import UTC, datetime
        delta = datetime.now(UTC) - self.reauth_at
        return delta.total_seconds() <= window_seconds


def _cheapest_plan_with(feature: str) -> str | None:
    """Qual o pacote de MENOR nível que inclui este recurso — para a mensagem dizer o que fazer.

    Lê a configuração, não o banco: a mensagem é informativa, e uma consulta a mais em todo 402 de
    pacote sairia caro justamente no caminho que já está sendo recusado. v0.27.0: sem preço (ADR-341),
    a ordem é a do tier (free < plus < premium < gov).
    """
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).resolve().parents[3] / "config" / "plans.json")
                     .read_text(encoding="utf-8"))
    ordem = {"free": 0, "plus": 1, "premium": 2, "gov": 3}
    candidatos = [(ordem.get(p.get("tier", "free"), 9), k)
                  for k, p in cfg["plans"].items() if feature in (p.get("features") or [])]
    return min(candidatos)[1] if candidatos else None


# ------------------------------------------------------------------------------------------------
# Construção
# ------------------------------------------------------------------------------------------------

def build(ctx) -> AccessContext:
    """Monta o contexto de acesso da requisição. UMA consulta ao banco.

    Guardado em `ctx` pelo chamador: montar duas vezes na mesma requisição seria pagar a consulta
    duas vezes para obter a mesma resposta.
    """
    p = ctx.principal
    if not p:
        raise ApiError(401, "unauthenticated", _MESSAGES["unauthenticated"])

    ac = AccessContext(
        user_id=p.user_id, email=p.email,
        is_platform_admin=p.is_platform_admin, staff_roles=tuple(p.staff_roles or ()),
        mfa_enabled=p.mfa_enabled, mfa_verified=p.mfa_verified,
        email_verified=p.email_verified,
        org_id=p.org_id, org_kind=p.org_kind, org_name=p.org_name, role=p.role)

    with ctx.system_tx() as c:
        perms = c.scalar("SELECT staff_permissions_of($1)", p.user_id) or []
        ac.permissions = frozenset(perms)
        ac.reauth_at = c.scalar("SELECT reauth_at FROM sessions WHERE id = $1", p.session_id)
        if ac.org_id:
            from ..services.entitlements import effective
            ent = effective(c, ac.org_id, ac.org_kind)
            ac.plans = tuple(ent.get("plans") or ())
            ac.features = frozenset(ent.get("features") or ())
            ac.limits = dict(ent.get("limits") or {})
            row = c.one(
                "SELECT org_commercial_state($1) AS state, free_period_end($1) AS ends_at,"
                " EXISTS (SELECT 1 FROM offer_acceptances WHERE org_id = $1"
                "         AND consent_status = 'authorized' AND revoked_at IS NULL) AS auth",
                ac.org_id)
            if row:
                ac.commercial_state = row["state"]
                ac.free_period_end = row["ends_at"]
                ac.charge_authorized = bool(row["auth"])
    return ac


def of(ctx) -> AccessContext:
    """O contexto desta requisição, montado na primeira chamada e reaproveitado."""
    cached = getattr(ctx, "_access", None)
    if cached is None:
        cached = build(ctx)
        ctx._access = cached
    return cached


def require(ctx, permission: str) -> AccessContext:
    """Exige a permissão ou levanta. Para uso DENTRO do handler, quando a exigência é condicional."""
    ac = of(ctx)
    ac.can(permission=permission).raise_if_denied()
    return ac


# ------------------------------------------------------------------------------------------------
# Registro de acesso privilegiado
# ------------------------------------------------------------------------------------------------

def log_privileged(ctx, permission: str | None, *, denied: bool = False) -> None:
    """Registra a entrada privilegiada, inclusive de LEITURA e inclusive quando é RECUSADA.

    Numa investigação a pergunta é "quem olhou", não só "quem mudou" — e `audit_events` só registra
    alteração. Falha de registro NÃO derruba a requisição: perder a trilha de uma leitura é ruim,
    recusar a operação de quem está trabalhando por causa disso é pior.

    A TENTATIVA recusada entra também. Auditoria independente desta versão apontou que o registro
    acontecia só depois da conferência passar: alguém da equipe sondando cinquenta rotas
    financeiras e levando 403 em todas não deixava rastro em lugar nenhum — nem aqui, porque não
    chegava, nem em `audit_events`, que só registra alteração. Uma tentativa de olhar também é um
    olhar, e uma sequência de tentativas recusadas é o sinal que uma investigação procura.
    """
    if denied:
        from ..services.audit import DENIED_PRIVILEGED_ACTION
        METRICS.inc("impacto_security_events_total", action=DENIED_PRIVILEGED_ACTION)
    try:
        with ctx.system_tx() as c:
            c.run("INSERT INTO privileged_access_log(user_id, roles_used, permission, method, path,"
                  " org_scope, request_id, ip) VALUES ($1,$2::text[],$3,$4,$5,$6,$7,$8)",
                  ctx.principal.user_id,
                  list(ctx.principal.staff_roles or ()) + (
                      ["platform_admin"] if ctx.principal.is_platform_admin else [])
                  + (["DENIED"] if denied else []),
                  permission, ctx.request.method, ctx.request.url.path,
                  ctx.principal.org_id, ctx.request_id, ctx.ip)
    except Exception:
        import logging

        from ..observability import log
        log(logging.getLogger("impacto.access"), logging.WARNING,
            "privileged_access_log_failed", request_id=ctx.request_id)


# ------------------------------------------------------------------------------------------------
# Confirmação de identidade — UMA implementação
# ------------------------------------------------------------------------------------------------

def verify_identity(ctx, *, password: str | None = None, mfa_code: str | None = None,
                    stamp: bool = True, always_password: bool = False) -> None:
    """Confirma quem está no teclado. Levanta se não confirmar.

    POR QUE ISTO EXISTE

    Havia três cópias desta verificação — `trust_routes.py`, `document_routes.py` e
    `privacy_routes.py` — cada uma conferindo a senha no próprio handler, cada uma com o seu
    `raise`, e nenhuma lembrando do resultado. Três cópias de uma regra de segurança divergem: basta
    alguém endurecer uma e esquecer as outras duas.

    DOIS CAMINHOS DE ENTRADA, UM CAMINHO DE VERIFICAÇÃO

      1. a sessão já foi reautenticada há menos de 15 minutos → passa;
      2. a requisição trouxe a senha (e o código de MFA, quando houver) → verifica e carimba.

    O primeiro caminho é o que permite uma pessoa aprovar cinco instruções de pagamento seguidas sem
    digitar a senha cinco vezes — que é o comportamento que faz alguém colar a senha num bilhete.
    """
    # ASSINATURA É DIFERENTE. `always_password=True` ignora o atalho da janela: assinar um
    # documento é ato de vontade POR DOCUMENTO, e um carimbo feito quinze minutos antes, em outra
    # operação, não é a vontade de assinar este. Quem assina digita a senha, sempre — e, nas rotas
    # de assinatura, também um código de uso único amarrado ao hash exato do conteúdo.
    ac = of(ctx)
    if not always_password and ac._reauth_fresh():
        return
    if password is None:
        raise ApiError(401, "step_up_required", _MESSAGES["step_up_required"],
                       {"reason": "step_up_required", "step_up_required": True})

    from ..db.pool import DbContext
    from ..security import totp
    from ..security.passwords import verify_password
    with ctx.pool.tx(DbContext(system=True)) as c:
        u = c.one("SELECT password_hash, mfa_enabled_at IS NOT NULL AS mfa, mfa_secret_enc"
                  " FROM users WHERE id = $1", ctx.user_id)
        if not u or not verify_password(password, u["password_hash"]):
            raise ApiError(401, "reauth_failed", "Senha incorreta.")
        if u["mfa"]:
            # Quem tem segundo fator precisa usá-lo. Aceitar só a senha aqui ofereceria o fator
            # mais fraco justamente na operação mais perigosa.
            if not mfa_code:
                raise ApiError(401, "mfa_code_required",
                               "Sua conta tem segundo fator: informe o código do aplicativo.")
            if not totp.verify_once(c, ctx.principal.user_id,
                                    ctx.app.cipher.decrypt(u["mfa_secret_enc"]), mfa_code):
                raise ApiError(401, "reauth_failed", "Código de verificação incorreto.")
        if stamp:
            c.run("UPDATE sessions SET reauth_at = now() WHERE id = $1", ctx.principal.session_id)
    ctx._access = None     # o contexto em cache não sabe do carimbo novo
