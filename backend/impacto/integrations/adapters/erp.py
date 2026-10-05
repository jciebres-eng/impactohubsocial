"""Fundação de adapters de ERP. Nada aqui está HOMOLOGADO: são contratos testados contra dublês claramente identificados.

Senior/Sapiens: a documentação oficial da Senior expõe WebServices (SOAP/XML) além de REST — por isso o adapter é HÍBRIDO
e nunca assume REST-only. Acesso direto ao banco do ERP NÃO é estratégia: se algum dia for necessário, deve ser tratado
como exceção controlada ("LEGACY/DIRECT-DB"), fora deste adapter.
TOTVS não é um único produto: Protheus, RM e Datasul têm APIs distintas; a variante vem da configuração da conexão.
"""
from __future__ import annotations

from datetime import datetime

from ..contracts import AdapterResult, CapabilityLevel, IntegrationError
from ..mapping import map_inbound
from ..xmlsafe import parse, soap_envelope, soap_fault, to_dict
from .base import BaseAdapter


class SeniorSapiensAdapter(BaseAdapter):
    key = "senior_sapiens"
    category = "erp"
    api_style = "hybrid"                     # REST quando disponível; SOAP/XML quando necessário
    auth_kinds = ("basic_auth", "bearer_token", "secret_ref")
    capabilities = {"connect": CapabilityLevel.YES, "pull": CapabilityLevel.PARTIAL, "push": CapabilityLevel.PARTIAL,
                    "webhook": CapabilityLevel.NOT_IMPLEMENTED, "batch": CapabilityLevel.PARTIAL,
                    "async": CapabilityLevel.NOT_IMPLEMENTED, "health": CapabilityLevel.YES}
    required_config = ("mode",)              # mode: rest | soap
    entity_paths = {"person": "/pessoas", "organization": "/empresas", "invoice": "/titulos", "payment": "/baixas", "document": "/documentos"}
    # operações SOAP conhecidas da fundação (nomes neutros; os reais dependem do módulo/versão contratados e são configuráveis)
    soap_operations = {"person": "ConsultarPessoas", "organization": "ConsultarEmpresas", "invoice": "ConsultarTitulos", "document": "ConsultarDocumentos"}

    def validate_config(self, connection: dict) -> list[str]:
        problems = super().validate_config(connection)
        cfg = connection.get("config") or {}
        if cfg.get("mode") not in ("rest", "soap"):
            problems.append("config.mode deve ser 'rest' ou 'soap'")
        if cfg.get("mode") == "soap" and not cfg.get("soap_namespace"):
            problems.append("config.soap_namespace é obrigatório no modo SOAP")
        return problems

    def _soap_call(self, ctx, operation: str, params: dict) -> dict:
        cfg = ctx.connection.get("config") or {}
        op = (cfg.get("soap_operations") or {}).get(operation, operation)
        envelope = soap_envelope(op, params, namespace=cfg["soap_namespace"])
        headers = self._headers(ctx, {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": op})
        status, _, raw = ctx.transport.call("POST", self._url(ctx, cfg.get("soap_path", "/g5-senior-services")),
                                            headers=headers, data=envelope, expected=(200, 500))
        root = parse(raw)
        fault = soap_fault(root)
        if fault or status == 500:
            raise IntegrationError("soap_fault", fault or "Fault SOAP sem descrição", kind="permanent" if fault else "temporary", status=status)
        return to_dict(root)

    def pull(self, ctx, entity: str, *, since: datetime | None = None, limit: int = 200) -> AdapterResult:
        cfg = ctx.connection.get("config") or {}
        if cfg.get("mode") == "rest":
            return super().pull(ctx, entity, since=since, limit=limit)
        op = self.soap_operations.get(entity)
        if not op:
            raise IntegrationError("entity_unsupported", f"Entidade não suportada via SOAP: {entity}", kind="permanent")
        data = self._soap_call(ctx, op, {"dataInicial": since.date().isoformat() if since else "", "quantidade": str(limit)})
        rows = _flatten_rows(data)
        records, invalid = [], 0
        for row in rows[:limit]:
            rec, errs = map_inbound(entity, row, ctx.mappings)
            if errs:
                invalid += 1
            else:
                records.append(rec)
        return AdapterResult(ok=True, records=records, stats={"read": len(rows), "mapped": len(records), "invalid": invalid})

    def health_check(self, ctx) -> tuple[str, str]:
        problems = self.validate_config(ctx.connection)
        if problems:
            return "unconfigured", "; ".join(problems)[:300]
        if (ctx.connection.get("config") or {}).get("mode") == "soap":
            try:
                # consulta mínima somente leitura; Fault de autenticação vira 'unauthorized'
                self._soap_call(ctx, self.soap_operations["organization"], {"quantidade": "1"})
                return "healthy", "SOAP respondeu"
            except IntegrationError as exc:
                if exc.status in (401, 403) or "autentic" in str(exc).lower() or "credenc" in str(exc).lower():
                    return "unauthorized", str(exc)[:300]
                return ("degraded" if exc.temporary else "unavailable"), str(exc)[:300]
        return super().health_check(ctx)


def _flatten_rows(data: dict) -> list[dict]:
    """Encontra a lista de registros dentro da resposta SOAP convertida (primeira lista de dicionários)."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                return v
            if isinstance(v, dict):
                found = _flatten_rows(v)
                if found:
                    return found
    return []


class TotvsAdapter(BaseAdapter):
    """Fundação TOTVS: a variante (`config.product`) escolhe caminhos e estilo. Nenhuma regra do Protheus entra no núcleo."""
    key = "totvs"
    category = "erp"
    api_style = "rest"
    auth_kinds = ("basic_auth", "bearer_token", "oauth2_client_credentials", "secret_ref")
    capabilities = {"connect": CapabilityLevel.YES, "pull": CapabilityLevel.PARTIAL, "push": CapabilityLevel.PARTIAL,
                    "webhook": CapabilityLevel.NOT_IMPLEMENTED, "batch": CapabilityLevel.NOT_IMPLEMENTED,
                    "async": CapabilityLevel.NOT_IMPLEMENTED, "health": CapabilityLevel.YES}
    required_config = ("product",)
    PRODUCTS = {
        # caminhos de fundação, configuráveis por conexão (config.paths sobrescreve)
        "protheus": {"health": "/api/framework/v1/health", "person": "/api/crm/v1/customers", "invoice": "/api/fin/v1/receivables", "organization": "/api/crm/v1/customers"},
        "rm": {"health": "/api/framework/v1/health", "person": "/api/rh/v1/employees", "invoice": "/api/fin/v1/receivables", "organization": "/api/glb/v1/companies"},
        "datasul": {"health": "/api/framework/v1/health", "person": "/api/hcm/v1/employees", "invoice": "/api/fin/v1/receivables", "organization": "/api/glb/v1/companies"},
    }

    def validate_config(self, connection: dict) -> list[str]:
        problems = super().validate_config(connection)
        if (connection.get("config") or {}).get("product") not in self.PRODUCTS:
            problems.append("config.product deve ser protheus, rm ou datasul")
        return problems

    def _paths(self, ctx) -> dict:
        cfg = ctx.connection.get("config") or {}
        base = dict(self.PRODUCTS.get(cfg.get("product"), {}))
        base.update(cfg.get("paths") or {})
        return base

    def _url(self, ctx, path: str) -> str:
        paths = self._paths(ctx)
        return super()._url(ctx, paths.get(path, path))

    def _entity_path(self, entity: str) -> str:
        return entity

    def health_check(self, ctx) -> tuple[str, str]:
        problems = self.validate_config(ctx.connection)
        if problems:
            return "unconfigured", "; ".join(problems)[:300]
        try:
            status, _, _ = ctx.transport.call("GET", self._url(ctx, "health"), headers=self._headers(ctx), expected=(200, 204))
            return "healthy", f"{(ctx.connection.get('config') or {}).get('product')} HTTP {status}"
        except IntegrationError as exc:
            if exc.status in (401, 403):
                return "unauthorized", str(exc)[:300]
            return ("degraded" if exc.temporary else "unavailable"), str(exc)[:300]
