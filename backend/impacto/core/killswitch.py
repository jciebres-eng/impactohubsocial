"""Interruptor de emergência: desliga escrita, login, upload ou integração durante um incidente.

POR QUE EXISTE

Durante uma invasão, um vazamento ou uma integração despejando dado errado, a decisão que salva é
PARAR — e parar antes de entender. Até a v0.22.0 a única forma de parar a plataforma era derrubar o
processo ou revogar credencial de banco, o que também derruba a auditoria. Isso inverte a
prioridade: justamente quando é mais importante registrar o que está acontecendo, o registro é a
primeira coisa que se perde.

AS QUATRO REGRAS

1. **A auditoria nunca é bloqueada.** Nem a escrita (`audit_events` segue recebendo), nem a leitura
   (as rotas de auditoria estão na lista de isenção abaixo). Um interruptor que cega quem investiga
   serve ao atacante, não à defesa.
2. **Vidro quebrado.** As rotas do próprio interruptor ficam fora do bloqueio. Um interruptor que se
   tranca do lado de fora transforma incidente em indisponibilidade permanente.
3. **O escopo `logins` não tranca a equipe.** É aplicado em `services/auth.py`, DEPOIS de
   identificar quem está entrando, e deixa a equipe interna passar. Bloquear login de todos,
   inclusive de quem responde ao incidente, é o mesmo erro da regra 2 com outra roupa.
4. **Motivo obrigatório, de no mínimo 10 caracteres** (travado no banco). "teste" não passa.

CUSTO DE LEITURA

O estado é consultado em TODA requisição. Ler o banco a cada requisição transformaria o
interruptor em gargalo, então há cache de processo com vida de 5 segundos. Isso significa que
acionar o interruptor leva até 5 segundos para valer em todos os processos — declarado de
propósito, e aceitável: a alternativa é uma consulta por requisição em condição normal, ou seja,
pagar o custo do incidente 100% do tempo para economizar 5 segundos quando ele acontece.
"""
from __future__ import annotations

import logging
import threading
import time

from ..http import ApiError
from ..observability import METRICS, log

logger = logging.getLogger("impacto.killswitch")

SCOPES = ("mutations", "logins", "uploads", "integrations", "maintenance")

CACHE_TTL_SECONDS = 5.0

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

# Isenções, no formato das outras listas desta base: caminho e MOTIVO escrito. Uma isenção sem
# motivo é um buraco que ninguém lembra de ter aberto — `test_every_exemption_has_a_reason` recusa.
EXEMPT_PREFIXES: dict[str, str] = {
    "/v1/admin/kill-switch": "vidro quebrado: a rota que libera o interruptor não pode ser bloqueada por ele",
    "/v1/admin/audit": "a auditoria é o que não se perde durante um incidente; cegar quem investiga serve ao atacante",
    "/v1/admin/privileged-access": "trilha de entrada privilegiada: mesma razão da auditoria",
    "/v1/auth/reauth": "a reautenticação é o passo que dá acesso ao próprio interruptor",
    "/v1/auth/logout": "encerrar sessão REDUZ exposição; bloquear a saída durante um incidente é o contrário do objetivo",
    "/v1/auth/refresh": "renovar sessão não cria acesso novo; bloquear derrubaria quem já está dentro respondendo",
    "/v1/me/context": "a aplicação precisa saber quem é o usuário para exibir o aviso em vez de erro sem explicação",
    "/v1/meta": "configuração pública e estado da plataforma: é como o aviso de manutenção chega à tela",
    "/v1/admin/health": "diagnóstico do próprio sistema durante o incidente: sem isto, quem responde fica sem instrumento",
    "/v1/admin/errors": "erros 5xx agregados; é a tela que mostra o que está quebrando enquanto a plataforma está parada",
}

# A PORTA DE ENTRADA é decidida em outro lugar, de propósito.
#
# Primeira versão deste módulo tratava login como escrita qualquer: `POST /v1/auth/login` levava
# 503 no modo somente leitura. Dois problemas apareceram no teste:
#
#   1. A mensagem do modo somente leitura PROMETE "consultas seguem disponíveis" — e ninguém podia
#      entrar para consultar. A promessa e o comportamento discordavam.
#   2. Sob `maintenance`, o bloqueio valia para todos, equipe interna incluída: na porta HTTP ainda
#      não se sabe quem está entrando (`ctx.principal` é None antes de autenticar). Isto é a regra
#      do vidro quebrado violada pelo outro lado — a equipe trancada fora.
#
# Então estes caminhos passam reto aqui e são decididos em `services/auth.py::issue_session()`,
# que é por onde TODA emissão de sessão passa (senha, MFA, OIDC, convite) e o primeiro ponto em que
# a identidade é conhecida. Lá os escopos `logins` E `maintenance` são aplicados, isentando a
# equipe interna.
LOGIN_PREFIXES = ("/v1/auth/login", "/v1/auth/mfa", "/v1/auth/oidc", "/v1/auth/register",
                  "/v1/auth/verify", "/v1/auth/password")

_lock = threading.Lock()
_cache: dict = {"at": 0.0, "state": None}


def _carregar(ctx) -> dict:
    with ctx.system_tx() as c:
        linhas = c.query("SELECT scope, engaged, reason, since FROM kill_switch_state")
    return {linha["scope"]: linha for linha in linhas}


def state(ctx, *, fresh: bool = False) -> dict:
    """Estado atual por escopo. `fresh=True` ignora o cache (usado pelas rotas de administração)."""
    agora = time.monotonic()
    if not fresh:
        with _lock:
            if _cache["state"] is not None and agora - _cache["at"] < CACHE_TTL_SECONDS:
                return _cache["state"]
    try:
        novo = _carregar(ctx)
    except Exception as exc:   # noqa: BLE001
        # Falha ao LER o estado não pode derrubar a requisição nem — pior — ligar o interruptor por
        # acidente. Mantém-se o último estado conhecido; sem nenhum, segue-se liberado e registra-se.
        #
        # ESTE RAMO JÁ ESCONDEU UM DEFEITO: na primeira versão deste módulo a consulta usava
        # `c.all()`, que não existe nesta camada de banco (é `c.query()`). O resultado foi um
        # interruptor que parecia funcionar e nunca bloqueava nada — falhava, caía aqui e devolvia
        # "liberado". Por isso a falha é CONTADA, não só registrada: um interruptor que não consegue
        # ler o próprio estado é um incidente de segurança, não um aviso de log.
        METRICS.inc("impacto_kill_switch_unreadable_total")
        log(logger, logging.ERROR, "kill_switch_state_unreadable", error=str(exc)[:200])
        with _lock:
            return _cache["state"] or {s: {"scope": s, "engaged": False, "reason": None, "since": None} for s in SCOPES}
    with _lock:
        _cache["state"], _cache["at"] = novo, agora
    return novo


def invalidate() -> None:
    """Chamado após acionar ou liberar: o processo que mexeu vê o efeito na requisição seguinte."""
    with _lock:
        _cache["at"] = 0.0


def engaged(ctx, scope: str) -> bool:
    linha = state(ctx).get(scope)
    return bool(linha and linha["engaged"])


def is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


def is_login_path(path: str) -> bool:
    return any(path.startswith(p) for p in LOGIN_PREFIXES)


def enforce(ctx, spec) -> None:
    """Ponto de estrangulamento: roda em toda requisição, depois de `authorize`.

    Depois de `authorize` de propósito: quem não tem acesso recebe 401/403 antes de descobrir que a
    plataforma está em manutenção. Estado de incidente não é informação pública.
    """
    caminho = ctx.request.url.path
    if is_exempt(caminho) or is_login_path(caminho):
        return
    atual = state(ctx)

    def ligado(escopo: str) -> bool:
        linha = atual.get(escopo)
        return bool(linha and linha["engaged"])

    # `maintenance` é o mais amplo: recusa até leitura. A equipe interna continua passando, porque
    # é ela que precisa olhar o sistema enquanto o resto está parado.
    if ligado("maintenance") and not _é_equipe(ctx):
        _recusar(ctx, "maintenance", "A plataforma está em manutenção. Nenhuma operação está disponível neste momento.")
    escrita = ctx.request.method in UNSAFE
    if escrita and ligado("mutations"):
        _recusar(ctx, "mutations", "A plataforma está em modo somente leitura. Consultas seguem disponíveis; "
                                   "nenhuma alteração está sendo aceita neste momento.")
    if escrita and spec.multipart and ligado("uploads"):
        _recusar(ctx, "uploads", "O envio de arquivos está suspenso neste momento. O restante da plataforma segue disponível.")
    if ligado("integrations") and _é_integração(spec):
        _recusar(ctx, "integrations", "As integrações externas estão suspensas neste momento.")


def _é_equipe(ctx) -> bool:
    p = ctx.principal
    return bool(p and (p.is_platform_admin or p.staff_roles))


def _é_integração(spec) -> bool:
    return spec.path.startswith("/v1/integrations") or spec.path.startswith("/v1/admin/integrations")


def _recusar(ctx, scope: str, mensagem: str) -> None:
    METRICS.inc("impacto_kill_switch_blocked_total", scope=scope)
    # O MOTIVO do incidente não vai na resposta: é informação de operação. Quem precisa dele lê em
    # `GET /v1/admin/kill-switch`, que exige permissão.
    raise ApiError(503, "platform_halted", mensagem, {"scope": scope})


def record(ctx, *, scope: str, action: str, reason: str) -> dict:
    """Aciona ou libera. O INSERT no histórico é o que muda o estado — o gatilho aplica.

    Não existe caminho para ligar o interruptor sem deixar o evento: o estado só é escrito pelo
    gatilho `trg_kill_switch_apply`, e a política de RLS de `kill_switch_state` só aceita UPDATE
    com `app_system()`, que é o contexto do próprio gatilho.
    """
    if scope not in SCOPES:
        raise ApiError(422, "invalid_scope", f"Escopo desconhecido: {scope}", {"allowed": list(SCOPES)})
    if action not in ("engage", "release"):
        raise ApiError(422, "invalid_action", "Ação deve ser 'engage' ou 'release'")
    if len(reason.strip()) < 10:
        raise ApiError(422, "reason_required",
                       "Descreva o motivo em pelo menos 10 caracteres. O motivo é o que a investigação "
                       "posterior vai ler para entender por que a plataforma foi parada.")
    with ctx.system_tx() as c:
        c.run("INSERT INTO kill_switch_events(scope, action, reason, actor_user_id, request_id, ip)"
              " VALUES ($1,$2,$3,$4,$5,$6)",
              scope, action, reason.strip(), ctx.principal.user_id, ctx.request_id, ctx.ip)
        atual = c.one("SELECT scope, engaged, reason, since FROM kill_switch_state WHERE scope = $1", scope)
        from ..services.audit import record as auditar
        auditar(c, org_id=None, actor=ctx.principal.user_id,
                action=f"security.kill_switch_{'engaged' if action == 'engage' else 'released'}",
                object_type="kill_switch", object_id=scope, payload={"reason": reason.strip()},
                ip=ctx.ip, request_id=ctx.request_id)
    invalidate()
    log(logger, logging.WARNING, "kill_switch", scope=scope, action=action,
        actor=ctx.principal.user_id, request_id=ctx.request_id)
    return atual


def history(ctx, *, limit: int = 100) -> list[dict]:
    with ctx.system_tx() as c:
        return c.query("SELECT e.id, e.scope, e.action, e.reason, e.created_at, e.request_id,"
                     "       u.email AS actor_email"
                     "  FROM kill_switch_events e LEFT JOIN users u ON u.id = e.actor_user_id"
                     " ORDER BY e.id DESC LIMIT $1", limit)
