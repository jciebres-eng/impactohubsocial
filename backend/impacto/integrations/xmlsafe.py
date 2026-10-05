"""XML/SOAP seguro para ERPs legados (Senior/Sapiens e afins frequentemente expõem WebService XML).

Usa `defusedxml` (já era dependência do projeto, usada na leitura de RSS): bloqueia XXE, entidades externas e
"billion laughs". Limita tamanho e profundidade antes de parsear — arquivo externo é sempre não confiável.
"""
from __future__ import annotations

from typing import Any

from .contracts import IntegrationError

MAX_XML_BYTES = 8 * 1024 * 1024
MAX_DEPTH = 40
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"


def parse(raw: bytes) -> Any:
    """Parseia XML não confiável. Qualquer DTD/entidade externa é recusada pelo defusedxml."""
    if not raw:
        raise IntegrationError("xml_empty", "Resposta XML vazia", kind="permanent")
    if len(raw) > MAX_XML_BYTES:
        raise IntegrationError("xml_too_large", f"XML acima do limite de {MAX_XML_BYTES} bytes", kind="permanent")
    from defusedxml import ElementTree as ET
    from defusedxml.common import DefusedXmlException
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except DefusedXmlException as exc:
        raise IntegrationError("xml_unsafe", "XML recusado: contém DTD ou entidade externa", kind="permanent") from exc
    except ET.ParseError as exc:
        raise IntegrationError("xml_malformed", f"XML malformado: {exc}", kind="permanent") from exc
    _check_depth(root, 1)
    return root


def _check_depth(node, depth: int) -> None:
    if depth > MAX_DEPTH:
        raise IntegrationError("xml_too_deep", f"XML com profundidade acima de {MAX_DEPTH}", kind="permanent")
    for child in node:
        _check_depth(child, depth + 1)


def _escape(value: Any) -> str:
    s = "" if value is None else str(value)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def soap_envelope(operation: str, params: dict, *, namespace: str) -> bytes:
    """Monta o envelope SOAP 1.1. Os valores são escapados (sem injeção de XML por conteúdo externo)."""
    if not operation.replace("_", "").isalnum():
        raise IntegrationError("soap_operation", "Nome de operação SOAP inválido", kind="permanent")
    body = "".join(f"<ns:{k}>{_escape(v)}</ns:{k}>" for k, v in params.items() if k.replace("_", "").isalnum())
    return (f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<soapenv:Envelope xmlns:soapenv="{SOAP_ENV}" xmlns:ns="{_escape(namespace)}">'
            f"<soapenv:Body><ns:{operation}>{body}</ns:{operation}></soapenv:Body></soapenv:Envelope>").encode()


def soap_fault(root) -> str | None:
    """Mensagem de Fault do SOAP, quando houver."""
    for tag in (f"{{{SOAP_ENV}}}Fault", "Fault"):
        node = root.find(f".//{tag}")
        if node is not None:
            return (node.findtext("faultstring") or node.findtext(f"{{{SOAP_ENV}}}faultstring") or "Fault SOAP")[:300]
    return None


def to_dict(node) -> dict:
    """Converte um nó XML em dicionário simples (texto e filhos), sem namespaces, para o mapeamento."""
    def name(tag: str) -> str:
        return tag.split("}")[-1]
    out: dict[str, Any] = {}
    for child in node:
        key = name(child.tag)
        value = to_dict(child) if len(child) else (child.text or "").strip()
        if key in out:
            if not isinstance(out[key], list):
                out[key] = [out[key]]
            out[key].append(value)
        else:
            out[key] = value
    return out
