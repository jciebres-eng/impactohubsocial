"""BI / exportação: datasets CONTROLADOS por organização. Nunca acesso direto ao banco.

Cada dataset é uma consulta fixa, filtrada pela organização da sessão (RLS) e com colunas públicas do domínio —
sem segredo, sem dado de outra organização, sem campo sensível desnecessário (LGPD: minimização).
"""
from __future__ import annotations

from ..contracts import CapabilityLevel
from .base import BaseAdapter

# dataset → (descrição, SQL parametrizado por org_id). Só colunas do domínio; nada de credencial/token/hash.
DATASETS = {
    "projects": ("Projetos da organização",
                 "SELECT id::text AS id, title, status, territory, budget_total_cents, beneficiaries_count, created_at FROM projects WHERE org_id = $1 ORDER BY created_at"),
    "applications": ("Candidaturas enviadas ou recebidas",
                     "SELECT id::text AS id, status, created_at, updated_at FROM applications WHERE osc_org_id = $1 OR funder_org_id = $1 ORDER BY created_at"),
    "documents": ("Documentos (metadados, sem conteúdo)",
                  "SELECT id::text AS id, kind, filename, status, validation_status, valid_until, created_at FROM documents WHERE org_id = $1 AND deleted_at IS NULL ORDER BY created_at"),
    "invoices": ("Faturas de assinatura",
                 "SELECT id::text AS id, description, amount_cents, currency, status, due_on, paid_at, created_at FROM invoices WHERE org_id = $1 ORDER BY created_at"),
    "support_tickets": ("Chamados de suporte (sem conteúdo das mensagens)",
                        "SELECT id::text AS id, number, category, priority, status, created_at, resolved_at FROM support_tickets WHERE org_id = $1 ORDER BY created_at"),
    "integration_jobs": ("Execuções de integração",
                         "SELECT id::text AS id, operation, entity, direction, status, attempts, error_code, started_at, finished_at FROM integration_jobs WHERE org_id = $1 ORDER BY created_at"),
}


class BiExportAdapter(BaseAdapter):
    key = "bi_export"
    category = "bi"
    api_style = "file"
    auth_kinds = ()
    capabilities = {"connect": CapabilityLevel.YES, "pull": CapabilityLevel.YES, "push": CapabilityLevel.NO,
                    "webhook": CapabilityLevel.NO, "batch": CapabilityLevel.YES,
                    "async": CapabilityLevel.YES, "health": CapabilityLevel.YES}

    def validate_config(self, connection: dict) -> list[str]:
        return []                            # não há endpoint: a saída é um arquivo gerado pela própria plataforma

    def health_check(self, ctx):
        return "healthy", f"{len(DATASETS)} datasets disponíveis"
