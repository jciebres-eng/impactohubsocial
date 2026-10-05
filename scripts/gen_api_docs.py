"""Gera docs/openapi.json e docs/API.md a partir do registro de rotas (fonte única: o código)."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DATABASE_URL", "host=invalid")
from impacto import api  # noqa: E402
from impacto.config import VERSION  # noqa: E402
from impacto.http import ROUTES  # noqa: E402
from impacto.openapi import build  # noqa: E402

api.load_all()
(ROOT / "docs" / "openapi.json").write_text(json.dumps(build(VERSION), ensure_ascii=False, indent=1), encoding="utf-8")
AUTH = {"none": "pública", "user": "usuário autenticado", "org": "membro da organização ativa", "admin": "admin da plataforma + MFA"}
lines = [f"# API REST /v1 — referência gerada do código (v{VERSION})", "",
         "Gerado por `scripts/gen_api_docs.py`. Contrato completo (schemas de entrada): `docs/openapi.json` ou `GET /v1/openapi.json`.",
         "", "## Convenções", "",
         "- Autenticação web: cookie httpOnly `__Host-impacto_at` + header `X-CSRF-Token` em métodos que alteram dados.",
         "- Autenticação mobile/API: `POST /v1/auth/login` com header `X-Auth-Mode: token` → `Authorization: Bearer <access_token>`; renovação em `/v1/auth/refresh`.",
         "- Erros: RFC 7807 (`application/problem+json`) com `code` estável, `request_id` e, em 5xx, `error_id` para suporte.",
         "- Paginação: `limit` (1–100) e `offset`; respostas trazem `has_more` e `next_offset`.",
         "- Dinheiro sempre em centavos (inteiro). Datas ISO 8601 (UTC).", "",
         f"## Operações ({len(ROUTES)})", "", "| Método | Caminho | Acesso | Restrições | Descrição |", "|---|---|---|---|---|"]
for r in sorted(ROUTES, key=lambda r: (r.path, r.method)):
    extra = []
    if r.kinds:
        extra.append("tipos: " + ", ".join(r.kinds))
    if r.min_role:
        extra.append(f"papel ≥ {r.min_role}")
    if r.feature:
        extra.append(f"plano: `{r.feature}`")
    if r.rate:
        extra.append(f"limite {r.rate[1]}/{r.rate[2]}s")
    lines.append(f"| {r.method} | `{r.path}` | {AUTH[r.auth]} | {'; '.join(extra) or '—'} | {(r.summary or r.handler.__name__.replace('_', ' ')).replace('|', '/')} |")
lines += ["", "Rotas de infraestrutura: `GET /healthz` (liveness), `GET /readyz` (banco + migrations), `GET /metrics` (Prometheus, Bearer `METRICS_TOKEN`),",
          "`GET /v1/openapi.json`, `GET /v1/meta/taxonomy`, `GET /v1/meta/config`."]
(ROOT / "docs" / "API.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(ROUTES)} operações documentadas")
