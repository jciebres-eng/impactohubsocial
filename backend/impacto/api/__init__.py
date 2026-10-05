"""Registro das rotas da API (cada módulo usa o decorador ``impacto.http.route``)."""
import importlib

MODULES = ["auth_routes", "org_routes", "call_routes", "project_routes", "application_routes", "execution_routes",
           "document_routes", "ai_routes", "billing_routes", "admin_routes", "insight_routes", "privacy_routes",
           "impact_routes", "procurement_routes", "finance_routes", "network_routes", "geo_routes", "report_routes", "ops_routes", "solution_routes", "solution_flow_routes", "institutional_routes", "institutional_admin_routes"]
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
