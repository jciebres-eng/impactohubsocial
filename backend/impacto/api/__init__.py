"""Registro das rotas da API (cada módulo usa o decorador ``impacto.http.route``)."""
import importlib

MODULES = ["auth_routes", "org_routes", "call_routes", "project_routes", "application_routes", "execution_routes",
           "document_routes", "ai_routes", "billing_routes", "admin_routes", "insight_routes", "privacy_routes",
           "impact_routes", "procurement_routes", "finance_routes", "network_routes", "geo_routes", "report_routes", "ops_routes", "solution_routes", "solution_flow_routes", "institutional_routes", "institutional_admin_routes", "institutional_extra_routes", "monetization_routes", "knowledge_routes", "content_admin_routes", "integration_routes", "trust_routes", "platform_routes",
           "lifecycle_routes", "diagnostic_routes", "assembly_routes",
           # v0.21.0 — camada comercial: oferta, aceite, período gratuito, uso
           "commercial_routes",
           # v0.22.0 — contexto de acesso, permissão granular, reautenticação
           "access_routes",
           # v0.16.0 — camada de rede
           "network_core_routes", "network_hub_routes",
           # v0.17.0 — camada econômica
           "program_routes", "legal_routes",
           # v0.18.0 — equidade, frameworks e confiança
           "equity_routes", "territory_routes", "framework_routes", "claim_routes", "reputation_routes", "seal_routes", "lookup_routes", "responsibility_routes",
           # v0.19.0 — primeiro acesso e retorno de contexto
           "firstrun_routes",
           # v0.20.0 — denúncia com os quatro níveis separados (a Central de Relatórios
           # continua em report_routes, que já estava na lista desde a v0.10.0)
           "complaint_routes"]
_loaded = False


def load_all() -> None:
    global _loaded
    if _loaded:
        return
    for m in MODULES:
        try:
            importlib.import_module(f"{__name__}.{m}")
        except ModuleNotFoundError as e:
            if e.name != f"{__name__}.{m}":
                raise
    _loaded = True
