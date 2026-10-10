"""Trilha de auditoria (hash encadeado por organização, calculado no banco) e Impact Ledger (por projeto)."""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json
from ..observability import METRICS

_SENSITIVE = {"password", "token", "secret", "code", "mfa_secret", "cnpj_lookup_raw"}

# Fragmentos que marcam um nome de campo como sensível onde quer que ele apareça. A lista exata
# acima só pega o nome inteiro: um payload com `refresh_token`, `access_token`, `api_key` ou
# `client_secret` passava inteiro para a trilha. E a trilha é append-only — o que entra não sai.
_SENSITIVE_PARTS = ("password", "senha", "token", "secret", "segredo", "api_key", "apikey",
                    "private_key", "credential", "authorization", "cookie", "session_token")

_MAX_DEPTH = 6   # payload mais fundo que isto é dado, não contexto: guarda-se a forma, não o conteúdo


def _sensitive(chave: str) -> bool:
    k = str(chave).lower()
    return k in _SENSITIVE or any(parte in k for parte in _SENSITIVE_PARTS)


def _clean(payload: dict, _depth: int = 0) -> dict:
    """Redação RECURSIVA. Até a v0.22.0 esta função só olhava o primeiro nível: um segredo
    aninhado em `{"webhook": {"secret": "..."}}` era gravado em claro numa tabela imutável."""
    if _depth >= _MAX_DEPTH:
        return {"[TRUNCADO]": f"profundidade > {_MAX_DEPTH}"}
    limpo: dict = {}
    for k, v in (payload or {}).items():
        if _sensitive(k):
            limpo[k] = "[REDACTED]"
        elif isinstance(v, dict):
            limpo[k] = _clean(v, _depth + 1)
        elif isinstance(v, (list, tuple)):
            limpo[k] = [_clean(i, _depth + 1) if isinstance(i, dict) else i for i in v]
        else:
            limpo[k] = v
    return limpo


# Ações que a operação precisa ver em tempo real, não ao abrir a tela de auditoria. Até a v0.22.0
# `auth.refresh_reuse_detected` — o sinal mais forte de roubo de sessão que a plataforma produz —
# era registrado, auditado e notificado ao TITULAR, e ninguém da operação era alertado. A lista é
# fechada de propósito: `action` tem centenas de valores e uma série por valor estoura o Prometheus.
# Cada nome aqui é produzido por código desta árvore — `test_every_security_action_is_produced_by_code`
# recusa um nome que nenhum chamador emite. Um conjunto com nome morto é o defeito de
# `LOGIN_MAX_ATTEMPTS`: configuração que parece ligada e não tem leitor. Nomes de etapas futuras
# (interruptor de emergência, exportação da trilha) entram junto com quem os emite, não antes.
SECURITY_ACTIONS = frozenset({
    "auth.login_failed", "auth.refresh_reuse_detected", "auth.session_too_old", "auth.session_idle",
    "auth.session_revoked", "auth.mfa_disabled", "auth.mfa_enabled",
    "auth.password_changed", "auth.password_reset",
    "member.role_changed", "staff.role_granted", "staff.role_revoked",
    "admin.user_status", "admin.org_status", "encryption.key_registered",
    "security.kill_switch_engaged", "security.kill_switch_released",
    # Levar a trilha para fora é a operação que mais interessa a quem quer apagar rastro depois.
    "audit.log_exported",
    # v0.35.0 (auditoria, AUTH-11): falhas de segundo fator e de reautenticação; decisões de quatro olhos sobre dinheiro.
    "auth.mfa_failed", "auth.step_up_failed", "beneficiary.verification_confirmed", "reconciliation.approved",
})

# A entrada privilegiada RECUSADA não passa por `record()`: ela é gravada em `privileged_access_log`
# (`core/access.py`), que é uma tabela à parte justamente porque registra LEITURA, e `audit_events`
# só registra alteração. Para o alerta ler uma série só, o contador é emitido com este nome.
DENIED_PRIVILEGED_ACTION = "security.privileged_access_denied"


#: Ações cuja gravidade é CRÍTICA por si: não dependem de contexto para merecer atenção imediata.
_CRITICAL = frozenset({
    "auth.refresh_reuse_detected",          # token de renovação reapresentado: indício de roubo
    "security.kill_switch_engaged",         # a plataforma foi parada
    "staff.role_granted",                   # alguém passou a poder mais do que podia
})


def severity_of(action: str, status: str = "success") -> str:
    """Gravidade DERIVADA, num lugar só.

    Pedir gravidade a cada um dos 319 chamadores produziria 319 critérios diferentes — e o mais
    provável é que quase tudo ficasse em `info`, porque é o que se escreve sem pensar. Derivar da
    ação e do resultado mantém um critério único e faz o evento NOVO nascer com a gravidade certa.
    """
    if action in _CRITICAL:
        return "critical"
    if status in ("denied", "failed"):
        return "warning"
    if action in SECURITY_ACTIONS:
        return "warning"
    return "info"


def actor_type_of(principal) -> str:
    """Pessoa, administrador ou sistema. IA, automação e integração são declaradas pelo chamador."""
    if principal is None:
        return "system"
    if getattr(principal, "is_platform_admin", False) or getattr(principal, "staff_roles", None):
        return "admin"
    return "user"


def record(conn: Connection, *, org_id: str | None, actor: str | None, action: str,
           object_type: str | None = None, object_id: Any = None, payload: dict | None = None,
           ip: str | None = None, request_id: str | None = None,
           actor_type: str | None = None, session_id: str | None = None,
           user_agent: str | None = None, correlation_id: str | None = None,
           parent_event_id: int | None = None, resource_name: str | None = None,
           severity: str | None = None, status: str = "success", source: str = "api",
           before: dict | None = None, after: dict | None = None) -> int:
    """Grava um evento na trilha e devolve o id — o id é o que permite pendurar um evento filho.

    Os campos novos da v0.23.0 têm padrão de propósito: os 319 chamadores existentes continuam
    chamando como antes e passam a gravar `actor_type`, `severity`, `status`, `source`,
    `session_id`, `user_agent` e `correlation_id` SEM alteração nenhuma, porque quem os preenche é
    `Ctx.audit()` — o ponto de estrangulamento por onde todos passam.

    `before`/`after` são a exceção: dizem de QUE para QUE, e isso nenhum ponto central sabe. Só o
    chamador que leu a linha antes de mudá-la tem essa informação.
    """
    # `actor_type` derivado quando o chamador não diz: havendo ator, é pessoa; não havendo, é
    # sistema. A primeira versão tinha `"system"` como padrão fixo, e os chamadores que gravam
    # direto em `record()` (registro de conta, por exemplo) marcavam como SISTEMA uma ação que uma
    # pessoa acabara de fazer — exatamente o engano que o campo existe para evitar.
    if actor_type is None:
        actor_type = "user" if actor else "system"
    identificador = conn.scalar(
        "INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, ip,"
        " request_id, payload, actor_type, session_id, user_agent, correlation_id,"
        " parent_event_id, resource_name, severity, status, source, before_state, after_state)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18::jsonb,$19::jsonb)"
        " RETURNING id",
        org_id, actor, action, object_type, None if object_id is None else str(object_id), ip,
        request_id, Json(_clean(payload or {})), actor_type, session_id,
        (user_agent or None) and user_agent[:400], (correlation_id or None) and correlation_id[:64],
        parent_event_id, (resource_name or None) and resource_name[:300],
        severity or severity_of(action, status), status, source,
        None if before is None else Json(_clean(before)),
        None if after is None else Json(_clean(after)))
    # Ponto de estrangulamento: toda a plataforma passa por aqui para auditar. Emitir a métrica
    # aqui — e não em cada chamador — é o que garante que nenhum evento de segurança novo nasça
    # invisível para o alerta. `categoria` é o prefixo da ação: cardinalidade baixa por construção.
    METRICS.inc("impacto_audit_events_total", categoria=action.split(".", 1)[0])
    if action in SECURITY_ACTIONS:
        METRICS.inc("impacto_security_events_total", action=action)
    if status != "success":
        METRICS.inc("impacto_audit_denied_total", categoria=action.split(".", 1)[0], status=status)
    return identificador


def ledger(conn: Connection, *, project_id: str, org_id: str, actor: str | None, entry_type: str,
           amount_cents: int | None = None, ref_type: str | None = None, ref_id: Any = None, payload: dict | None = None) -> dict:
    return conn.one("INSERT INTO ledger_entries(project_id, org_id, actor_user_id, entry_type, amount_cents, ref_type, ref_id, payload)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) RETURNING id, seq, entry_hash",
                    project_id, org_id, actor, entry_type, amount_cents, ref_type, None if ref_id is None else str(ref_id),
                    Json(payload or {}))
