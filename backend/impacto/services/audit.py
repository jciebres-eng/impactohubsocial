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
})

# A entrada privilegiada RECUSADA não passa por `record()`: ela é gravada em `privileged_access_log`
# (`core/access.py`), que é uma tabela à parte justamente porque registra LEITURA, e `audit_events`
# só registra alteração. Para o alerta ler uma série só, o contador é emitido com este nome.
DENIED_PRIVILEGED_ACTION = "security.privileged_access_denied"


def record(conn: Connection, *, org_id: str | None, actor: str | None, action: str, object_type: str | None = None,
           object_id: Any = None, payload: dict | None = None, ip: str | None = None, request_id: str | None = None) -> None:
    conn.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, ip, request_id, payload)"
             " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)",
             org_id, actor, action, object_type, None if object_id is None else str(object_id), ip, request_id,
             Json(_clean(payload or {})))
    # Ponto de estrangulamento: toda a plataforma passa por aqui para auditar. Emitir a métrica
    # aqui — e não em cada chamador — é o que garante que nenhum evento de segurança novo nasça
    # invisível para o alerta. `categoria` é o prefixo da ação: cardinalidade baixa por construção.
    METRICS.inc("impacto_audit_events_total", categoria=action.split(".", 1)[0])
    if action in SECURITY_ACTIONS:
        METRICS.inc("impacto_security_events_total", action=action)


def ledger(conn: Connection, *, project_id: str, org_id: str, actor: str | None, entry_type: str,
           amount_cents: int | None = None, ref_type: str | None = None, ref_id: Any = None, payload: dict | None = None) -> dict:
    return conn.one("INSERT INTO ledger_entries(project_id, org_id, actor_user_id, entry_type, amount_cents, ref_type, ref_id, payload)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) RETURNING id, seq, entry_hash",
                    project_id, org_id, actor, entry_type, amount_cents, ref_type, None if ref_id is None else str(ref_id),
                    Json(payload or {}))
