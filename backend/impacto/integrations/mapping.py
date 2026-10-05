"""Mapeamento de dados: campo externo → campo canônico, como DADO (tabela `integration_mappings`), não como código.

Antes existia um mapa fixo no importador de editais; aqui o mapeamento é por conexão, versionável e testável.
Transformações declaradas (nunca expressão arbitrária: não há `eval`, logo não há execução de código do cliente).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .contracts import CanonicalRecord, IntegrationError

_TRUE = {"1", "true", "t", "yes", "y", "sim", "s", "verdadeiro"}
_FALSE = {"0", "false", "f", "no", "n", "nao", "não", "falso", ""}


def get_path(data: Any, path: str) -> Any:
    """Lê `a.b.c` (dicionário) e `a.0.b` (lista). Caminho inexistente devolve None, nunca estoura."""
    cur = data
    for part in (path or "").split("."):
        if part == "":
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, (list, tuple)):
            if not part.isdigit() or int(part) >= len(cur):
                return None
            cur = cur[int(part)]
        else:
            return None
    return cur


def apply_transform(value: Any, transform: str, enum_map: dict | None = None) -> Any:
    """Transformações determinísticas. Valor ausente continua ausente (nunca inventa dado)."""
    if value is None:
        return None
    s = value if isinstance(value, str) else (str(value) if not isinstance(value, (dict, list)) else "")
    if transform in ("none", ""):
        return value
    if transform == "trim":
        return s.strip()
    if transform == "upper":
        return s.strip().upper()
    if transform == "lower":
        return s.strip().lower()
    if transform == "digits_only":
        return re.sub(r"\D", "", s) or None
    if transform == "date_iso":
        try:
            return date.fromisoformat(s.strip()[:10])
        except ValueError:
            raise IntegrationError("map_date", f"Data fora do formato ISO (AAAA-MM-DD): {s[:20]}", kind="permanent") from None
    if transform == "date_br":
        m = re.match(r"^\s*(\d{2})/(\d{2})/(\d{4})", s)
        if not m:
            raise IntegrationError("map_date", f"Data fora do formato brasileiro (DD/MM/AAAA): {s[:20]}", kind="permanent")
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if transform == "decimal_comma":
        try:
            return float(s.strip().replace(".", "").replace(",", "."))
        except ValueError:
            raise IntegrationError("map_decimal", f"Número inválido: {s[:20]}", kind="permanent") from None
    if transform == "cents_from_decimal":
        txt = s.strip().replace(" ", "")
        txt = txt.replace(".", "").replace(",", ".") if "," in txt else txt
        try:
            from decimal import ROUND_HALF_UP, Decimal
            return int((Decimal(txt) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))   # dinheiro: inteiro em centavos
        except Exception:  # noqa: BLE001
            raise IntegrationError("map_money", f"Valor monetário inválido: {s[:20]}", kind="permanent") from None
    if transform == "boolean":
        low = s.strip().lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise IntegrationError("map_boolean", f"Valor booleano inválido: {s[:20]}", kind="permanent")
    if transform == "enum":
        mapped = (enum_map or {}).get(s.strip())
        if mapped is None:
            raise IntegrationError("map_enum", f"Valor sem correspondência no mapeamento: {s[:40]}", kind="permanent")
        return mapped
    if transform == "split_list":
        return [x.strip() for x in s.split(",") if x.strip()]
    raise IntegrationError("map_transform", f"Transformação desconhecida: {transform}", kind="permanent")


def map_inbound(entity: str, raw: Any, mappings: list[dict]) -> tuple[CanonicalRecord, list[str]]:
    """Externo → canônico. Devolve (registro, erros). Campo obrigatório ausente é ERRO, nunca preenchido por suposição."""
    out: dict[str, Any] = {}
    errors: list[str] = []
    for m in mappings:
        if m["entity"] != entity or m["direction"] not in ("inbound", "both"):
            continue
        value = get_path(raw, m["source_path"])
        if value in (None, "") and m.get("default_value") not in (None, ""):
            value = m["default_value"]
        try:
            value = apply_transform(value, m.get("transform") or "none", m.get("enum_map") or {})
        except IntegrationError as exc:
            errors.append(f"{m['target_field']}: {exc}")
            continue
        if value in (None, "", []):
            if m.get("required"):
                errors.append(f"{m['target_field']}: campo obrigatório ausente")
            continue
        out[m["target_field"]] = value
    ext = out.pop("external_id", None)
    ver = out.pop("external_version", None)
    return CanonicalRecord(entity=entity, fields=out, external_id=str(ext) if ext else None,
                           external_version=str(ver) if ver else None), errors


def map_outbound(record: CanonicalRecord, mappings: list[dict]) -> dict:
    """Canônico → externo (usa `source_path` como caminho de destino simples, sem aninhamento)."""
    body: dict[str, Any] = {}
    for m in mappings:
        if m["entity"] != record.entity or m["direction"] not in ("outbound", "both"):
            continue
        value = record.fields.get(m["target_field"])
        if value is None and m["target_field"] == "external_id":
            value = record.external_id
        if value is None:
            continue
        body[m["source_path"].split(".")[-1]] = value
    return body
