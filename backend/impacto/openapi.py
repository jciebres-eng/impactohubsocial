"""Geração do contrato OpenAPI 3.1 a partir do registro de rotas e dos modelos pydantic (fonte única de verdade)."""
from __future__ import annotations

import re

from .http import ROUTES

_SEC = {"none": [], "user": [{"bearer": []}, {"cookie": []}], "org": [{"bearer": []}, {"cookie": []}],
        "admin": [{"bearer": []}, {"cookie": []}]}


def build(version: str) -> dict:
    paths: dict = {}
    schemas: dict = {}
    for r in ROUTES:
        op: dict = {"summary": r.summary or r.handler.__name__.replace("_", " "), "operationId": f"{r.method.lower()}_{r.handler.__module__.split('.')[-1]}_{r.handler.__name__}",
                    "tags": list(r.tags) or [r.handler.__module__.split(".")[-1].replace("_routes", "")],
                    "security": _SEC[r.auth], "responses": {str(r.status): {"description": "OK"},
                                                            "4XX": {"description": "Erro (application/problem+json)"}}}
        notes = []
        if r.auth == "org":
            notes.append("Requer organização ativa")
        if r.kinds:
            notes.append("Tipos: " + ", ".join(r.kinds))
        if r.min_role:
            notes.append(f"Papel mínimo: {r.min_role}")
        if r.auth == "admin":
            notes.append("Administração da plataforma com MFA")
        if r.feature:
            notes.append(f"Recurso de plano: {r.feature}")
        if r.rate:
            notes.append(f"Rate limit: {r.rate[1]}/{r.rate[2]}s por IP")
        if notes:
            op["description"] = " · ".join(notes)
        params = [{"name": n, "in": "path", "required": True, "schema": {"type": "string"}} for n in re.findall(r"{(\w+)}", r.path)]
        if r.query is not None:
            js = r.query.model_json_schema()
            for name, prop in js.get("properties", {}).items():
                params.append({"name": name, "in": "query", "required": name in js.get("required", []), "schema": prop})
        if params:
            op["parameters"] = params
        if r.body is not None:
            js = r.body.model_json_schema(ref_template="#/components/schemas/{model}")
            for k, v in js.pop("$defs", {}).items():
                schemas[k] = v
            schemas[r.body.__name__] = js
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": {"$ref": f"#/components/schemas/{r.body.__name__}"}}}}
        if r.multipart:
            op["requestBody"] = {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "properties": {"file": {"type": "string", "format": "binary"}}}}}}
        paths.setdefault(r.path, {})[r.method.lower()] = op
    return {"openapi": "3.1.0", "info": {"title": "Plataforma Impacto API", "version": version,
                                          "description": "API REST /v1. Erros seguem RFC 7807. Gerado do código (fonte única)."},
            "servers": [{"url": "/"}], "paths": paths,
            "components": {"schemas": schemas, "securitySchemes": {
                "bearer": {"type": "http", "scheme": "bearer", "description": "Token opaco (mobile/API: header X-Auth-Mode: token no login)"},
                "cookie": {"type": "apiKey", "in": "cookie", "name": "__Host-impacto_at", "description": "Web: cookie httpOnly + header X-CSRF-Token"}}}}
