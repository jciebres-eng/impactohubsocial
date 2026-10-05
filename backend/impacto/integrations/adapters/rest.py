"""Adapter REST genérico: atende "organização com API própria" sem escrever código novo.

Caminhos por entidade vêm da CONFIGURAÇÃO da conexão (`config.paths`), e o mapeamento de campos é dado.
"""
from __future__ import annotations

from ..contracts import CapabilityLevel
from .base import BaseAdapter


class GenericRestAdapter(BaseAdapter):
    key = "generic_rest"
    category = "custom"
    api_style = "rest"
    auth_kinds = ("api_key", "bearer_token", "basic_auth", "oauth2_client_credentials", "secret_ref")
    capabilities = {"connect": CapabilityLevel.YES, "pull": CapabilityLevel.YES, "push": CapabilityLevel.YES,
                    "webhook": CapabilityLevel.PARTIAL, "batch": CapabilityLevel.NO,
                    "async": CapabilityLevel.NO, "health": CapabilityLevel.YES}

    def validate_config(self, connection: dict) -> list[str]:
        problems = super().validate_config(connection)
        if not (connection.get("config") or {}).get("paths"):
            problems.append("config.paths é obrigatório (ex.: {\"person\": \"/pessoas\"})")
        return problems

    def _entity_path(self, entity: str) -> str:  # noqa: D102 - caminhos vêm da conexão
        return entity

    def _url(self, ctx, path: str) -> str:
        paths = (ctx.connection.get("config") or {}).get("paths") or {}
        real = paths.get(path, path if path.startswith("/") else "/" + path)
        return super()._url(ctx, real)

    @property
    def health_path(self) -> str:  # noqa: D102
        return "/"

    def health_check(self, ctx):
        cfg = (ctx.connection.get("config") or {})
        probe = cfg.get("health_path") or "/"
        try:
            status, _, _ = ctx.transport.call("GET", super()._url(ctx, probe), headers=self._headers(ctx), expected=(200, 204))
            return "healthy", f"HTTP {status}"
        except Exception as exc:  # noqa: BLE001
            from ..contracts import IntegrationError
            if isinstance(exc, IntegrationError):
                if exc.status in (401, 403):
                    return "unauthorized", str(exc)[:300]
                return ("degraded" if exc.temporary else "unavailable"), str(exc)[:300]
            return "unknown", str(exc)[:300]

    def handle_webhook(self, ctx, headers: dict, body: bytes) -> tuple[str, str, dict]:
        """Webhook genérico: assinatura HMAC compartilhada (mesmo formato da saída da IMPACTO) + id do evento no cabeçalho."""
        import json

        from ..contracts import IntegrationError
        from ..events import verify
        sig = headers.get("x-impacto-signature") or headers.get("X-Impacto-Signature") or ""
        if not ctx.secret or not verify(ctx.secret, body, sig):
            raise IntegrationError("bad_signature", "Assinatura ausente ou inválida", kind="permanent", status=403)
        eid = (headers.get("x-event-id") or headers.get("X-Event-Id") or "").strip()
        if not eid:
            raise IntegrationError("missing_event_id", "Cabeçalho X-Event-Id é obrigatório", kind="permanent", status=400)
        try:
            payload = json.loads(body or b"{}")
        except ValueError as exc:
            raise IntegrationError("malformed_payload", "Corpo não é JSON válido", kind="permanent", status=400) from exc
        etype = str(payload.get("type") or headers.get("x-event-type") or "external.event")[:100]
        return eid[:200], etype, payload if isinstance(payload, dict) else {"data": payload}
