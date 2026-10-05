"""Fundação para integrações governamentais (Gov.br, Conecta gov.br, APIs federais/estaduais/municipais).

HONESTIDADE OBRIGATÓRIA: a existência deste adapter NÃO significa integração oficial. O Conecta gov.br exige adesão,
credenciamento e autorização do órgão gestor. Estados possíveis e DISTINTOS: TECHNICALLY READY (este código) →
AUTHORIZED (credenciamento concedido) → HOMOLOGATED (testes no ambiente de homologação do governo) → PRODUCTION ACTIVE.
Só os dois primeiros podem ser declarados pela IMPACTO; os demais exigem evidência externa.
"""
from __future__ import annotations

from ..contracts import CapabilityLevel, IntegrationError
from .base import BaseAdapter


class GovernmentApiAdapter(BaseAdapter):
    key = "government_api"
    category = "government"
    api_style = "rest"
    auth_kinds = ("oauth2_client_credentials", "bearer_token", "certificate", "secret_ref")
    capabilities = {"connect": CapabilityLevel.YES, "pull": CapabilityLevel.PARTIAL, "push": CapabilityLevel.NOT_IMPLEMENTED,
                    "webhook": CapabilityLevel.NOT_IMPLEMENTED, "batch": CapabilityLevel.NOT_IMPLEMENTED,
                    "async": CapabilityLevel.NOT_IMPLEMENTED, "health": CapabilityLevel.PARTIAL}
    required_config = ("scope", "authorization_status")
    # 'authorization_status' é DECLARADO pela administração com base em documento do órgão; o código nunca o promove.
    AUTHORIZATION = ("technically_ready", "authorized", "homologated", "production_active")
    SCOPES = ("govbr", "conecta", "federal", "state", "municipal", "agency")
    entity_paths = {"organization": "/organizacoes", "person": "/pessoas", "document": "/documentos"}

    def validate_config(self, connection: dict) -> list[str]:
        problems = super().validate_config(connection)
        cfg = connection.get("config") or {}
        if cfg.get("scope") not in self.SCOPES:
            problems.append(f"config.scope deve ser um de {', '.join(self.SCOPES)}")
        if cfg.get("authorization_status") not in self.AUTHORIZATION:
            problems.append("config.authorization_status deve ser technically_ready, authorized, homologated ou production_active")
        if connection.get("environment") == "production" and cfg.get("authorization_status") != "production_active":
            problems.append("ambiente production exige authorization_status = production_active (com evidência do órgão)")
        return problems

    def pull(self, ctx, entity, *, since=None, limit=200):
        cfg = ctx.connection.get("config") or {}
        if cfg.get("authorization_status") == "technically_ready":
            raise IntegrationError("not_authorized", "Integração governamental sem credenciamento: EXTERNAL AUTHORIZATION REQUIRED",
                                   kind="permanent", status=403)
        return super().pull(ctx, entity, since=since, limit=limit)
