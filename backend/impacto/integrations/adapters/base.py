"""Base dos adapters. Nenhuma regra de negócio da IMPACTO vive aqui — só tradução entre externo e canônico."""
from __future__ import annotations

from datetime import datetime

from ..contracts import AdapterContext, AdapterResult, CapabilityLevel, IntegrationError
from ..mapping import map_inbound, map_outbound
from ..secrets import auth_headers


class BaseAdapter:
    key = "base"
    category = "custom"
    api_style = "rest"
    auth_kinds: tuple[str, ...] = ("api_key", "bearer_token", "basic_auth")
    capabilities: dict[str, str] = {"connect": CapabilityLevel.YES, "pull": CapabilityLevel.NO, "push": CapabilityLevel.NO,
                                    "webhook": CapabilityLevel.NO, "batch": CapabilityLevel.NO,
                                    "async": CapabilityLevel.NO, "health": CapabilityLevel.YES}
    required_config: tuple[str, ...] = ()
    health_path: str = "/"
    entity_paths: dict[str, str] = {}

    # ------------------------------------------------------------------ configuração
    def validate_config(self, connection: dict) -> list[str]:
        problems = []
        if not connection.get("endpoint"):
            problems.append("endpoint é obrigatório")
        for k in self.required_config:
            if not (connection.get("config") or {}).get(k):
                problems.append(f"config.{k} é obrigatório")
        return problems

    # ------------------------------------------------------------------ helpers
    def _url(self, ctx: AdapterContext, path: str) -> str:
        base = (ctx.connection.get("endpoint") or "").rstrip("/")
        if not base:
            raise IntegrationError("no_endpoint", "Conexão sem endpoint configurado", kind="permanent")
        return base + "/" + path.lstrip("/")

    def _headers(self, ctx: AdapterContext, extra: dict | None = None) -> dict:
        h = auth_headers(ctx.connection.get("_credential_kind"), ctx.secret, ctx.username)
        h.update(extra or {})
        return h

    def _entity_path(self, entity: str) -> str:
        path = self.entity_paths.get(entity)
        if not path:
            raise IntegrationError("entity_unsupported", f"Entidade não suportada por este provedor: {entity}", kind="permanent")
        return path

    # ------------------------------------------------------------------ operações
    def health_check(self, ctx: AdapterContext) -> tuple[str, str]:
        """Somente leitura, nunca destrutivo."""
        problems = self.validate_config(ctx.connection)
        if problems:
            return "unconfigured", "; ".join(problems)[:300]
        try:
            status, _, _ = ctx.transport.call("GET", self._url(ctx, self.health_path), headers=self._headers(ctx),
                                             expected=(200, 204))
            return ("healthy", f"HTTP {status}")
        except IntegrationError as exc:
            if exc.status in (401, 403):
                return "unauthorized", str(exc)[:300]
            if exc.code == "destination_blocked":
                return "unconfigured", str(exc)[:300]
            return ("degraded" if exc.temporary else "unavailable"), str(exc)[:300]

    def pull(self, ctx: AdapterContext, entity: str, *, since: datetime | None = None, limit: int = 200) -> AdapterResult:
        if self.capabilities.get("pull") not in (CapabilityLevel.YES, CapabilityLevel.PARTIAL):
            raise IntegrationError("not_implemented", f"Leitura não implementada para {self.key}", kind="permanent")
        params = f"?limit={int(limit)}" + (f"&since={since.date().isoformat()}" if since else "")
        _, _, raw = ctx.transport.call("GET", self._url(ctx, self._entity_path(entity)) + params, headers=self._headers(ctx))
        rows = self.decode_list(raw)
        records, errors = [], []
        for row in rows[:limit]:
            rec, errs = map_inbound(entity, row, ctx.mappings)
            (errors if errs else records).append(rec if not errs else {"errors": errs})
        return AdapterResult(ok=True, records=records, stats={"read": len(rows), "mapped": len(records), "invalid": len(errors)},
                             detail=f"{len(errors)} registro(s) recusado(s) pelo mapeamento" if errors else "")

    def push(self, ctx: AdapterContext, entity: str, records: list) -> AdapterResult:
        if self.capabilities.get("push") not in (CapabilityLevel.YES, CapabilityLevel.PARTIAL):
            raise IntegrationError("not_implemented", f"Escrita não implementada para {self.key}", kind="permanent")
        sent, ids = 0, {}
        for rec in records:
            body = map_outbound(rec, ctx.mappings)
            _, _, raw = ctx.transport.call("POST", self._url(ctx, self._entity_path(entity)), headers=self._headers(ctx), json_body=body)
            ext = self.decode_id(raw)
            if ext and rec.fields.get("internal_id"):
                ids[str(rec.fields["internal_id"])] = ext
            sent += 1
        return AdapterResult(ok=True, stats={"sent": sent}, external_ids=ids)

    def handle_webhook(self, ctx: AdapterContext, headers: dict, body: bytes) -> tuple[str, str, dict]:
        raise IntegrationError("not_implemented", f"Webhook não implementado para {self.key}", kind="permanent")

    # ------------------------------------------------------------------ decodificação (sobrescrita por estilo de API)
    def decode_list(self, raw: bytes) -> list[dict]:
        import json
        try:
            data = json.loads(raw or b"{}")
        except ValueError as exc:
            raise IntegrationError("malformed_response", "Resposta não é JSON válido", kind="permanent") from exc
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        for k in ("items", "data", "results", "content", "records"):
            if isinstance(data.get(k), list):
                return [x for x in data[k] if isinstance(x, dict)]
        return [data] if isinstance(data, dict) and data else []

    def decode_id(self, raw: bytes) -> str | None:
        import json
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        for k in ("id", "codigo", "code", "external_id", "identificador"):
            if data.get(k) not in (None, ""):
                return str(data[k])[:200]
        return None
