"""Política de modelo por faixa de risco, e conferência de esquema da saída.

POR QUE A FAIXA É DO USO, NÃO DO MODELO

Classificar por modelo ("gpt-x é faixa 2") amarra a política ao catálogo do provedor e envelhece a
cada lançamento. A faixa aqui é do USO: o que ela decide é tamanho de entrada e de saída, se a
chamada pode sair da instalação, se a saída exige esquema conferido e se exige revisão humana. Um
resumo é faixa 1 com qualquer modelo; uma afirmação sobre outra organização é faixa 3 com qualquer
modelo.

A faixa 4 existe para dizer que NENHUM uso com efeito jurídico ou financeiro está implementado, e
seus limites (1 caractere, 1 token) a tornam inoperante por construção: se alguém declarar um uso
nela, ele falha na primeira chamada em vez de funcionar sem a decisão humana que a faixa exige.

CONFERÊNCIA DE ESQUEMA

O gateway já tentava `json.loads` e descartava a resposta inválida — e gravava `status='ok'` de
qualquer forma, então a tabela de uso dizia que o provedor externo funcionou. A conferência aqui
devolve o motivo da recusa, e quem chama grava `status='invalid_output'`: é a diferença entre
"funcionou" e "respondeu algo que não serve".

O validador é deliberadamente pequeno — tipo, obrigatoriedade, tamanho e conjunto de valores. Não é
JSON Schema completo: implementar um validador completo à mão seria inventar uma biblioteca, e o
ambiente desta rodada não tem rota para instalar uma. O que ele cobre é o que os esquemas de saída
desta base usam, e `test_the_validator_covers_every_construct_the_schemas_use` reprova se um
esquema usar construção que o validador não entende — em vez de deixá-la passar sem conferência.
"""
from __future__ import annotations

import json
from typing import Any

#: Construções que o validador entende. Um esquema que use outra coisa é recusado na publicação,
#: não ignorado em silêncio: esquema não conferido é pior que esquema ausente, porque promete.
SUPPORTED_KEYWORDS = frozenset({
    "type", "properties", "required", "items", "enum", "maxLength", "minLength",
    "maximum", "minimum", "additionalProperties", "description", "title",
})

SUPPORTED_TYPES = frozenset({"object", "array", "string", "number", "integer", "boolean", "null"})


class PolicyViolation(Exception):
    """A chamada não pode acontecer como pedida. Carrega o motivo em português."""

    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail or {}


def load(conn, tier: int) -> dict:
    linha = conn.one(
        "SELECT tier, label, max_input_chars, max_output_tokens, allow_external,"
        "       requires_schema, requires_human_review, note"
        "  FROM ai_model_policies WHERE tier = $1", tier)
    if not linha:
        raise PolicyViolation("unknown_tier", f"Faixa de risco {tier} não existe na política",
                              {"tier": tier})
    return linha


def check_request(policy: dict, *, input_chars: int, external: bool) -> None:
    """Confere a chamada ANTES de ela sair. Depois de sair não há como desfazer."""
    if input_chars > policy["max_input_chars"]:
        raise PolicyViolation(
            "input_too_large",
            f"A entrada tem {input_chars} caracteres e a faixa "
            f"{policy['tier']} ({policy['label']}) aceita no máximo {policy['max_input_chars']}. "
            "Reduza o trecho enviado — cortar em silêncio produziria uma resposta sobre metade do "
            "texto sem que ninguém soubesse.",
            {"tier": policy["tier"], "input_chars": input_chars,
             "max_input_chars": policy["max_input_chars"]})
    if external and not policy["allow_external"]:
        raise PolicyViolation(
            "external_not_allowed",
            f"A faixa {policy['tier']} ({policy['label']}) não permite enviar a chamada para "
            "provedor externo. O resultado vem do motor local.",
            {"tier": policy["tier"]})


def validate(schema: dict | None, value: Any, *, path: str = "$") -> list[str]:
    """Devolve a lista de problemas. Lista vazia significa que a saída serve.

    Devolver LISTA e não booleano é deliberado: `status='invalid_output'` sem dizer o que estava
    errado deixa quem opera sem ação possível, e a resposta do modelo não fica guardada.
    """
    if schema is None:
        return []
    problemas: list[str] = []
    esperado = schema.get("type")

    if esperado == "object":
        if not isinstance(value, dict):
            return [f"{path}: esperado objeto, veio {_nome(value)}"]
        for campo in schema.get("required", []):
            if campo not in value:
                problemas.append(f"{path}.{campo}: campo obrigatório ausente")
        propriedades = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for campo in value:
                if campo not in propriedades:
                    problemas.append(f"{path}.{campo}: campo não previsto no esquema")
        for campo, sub in propriedades.items():
            if campo in value:
                problemas += validate(sub, value[campo], path=f"{path}.{campo}")
        return problemas

    if esperado == "array":
        if not isinstance(value, list):
            return [f"{path}: esperado lista, veio {_nome(value)}"]
        item = schema.get("items")
        for i, elemento in enumerate(value):
            problemas += validate(item, elemento, path=f"{path}[{i}]")
        return problemas

    if esperado == "string":
        if not isinstance(value, str):
            return [f"{path}: esperado texto, veio {_nome(value)}"]
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problemas.append(f"{path}: texto com {len(value)} caracteres, máximo {schema['maxLength']}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            problemas.append(f"{path}: texto com {len(value)} caracteres, mínimo {schema['minLength']}")
    elif esperado in ("number", "integer"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problemas.append(f"{path}: esperado número, veio {_nome(value)}")
        else:
            if esperado == "integer" and isinstance(value, float) and value != int(value):
                problemas.append(f"{path}: esperado inteiro, veio {value}")
            if "maximum" in schema and value > schema["maximum"]:
                problemas.append(f"{path}: {value} acima do máximo {schema['maximum']}")
            if "minimum" in schema and value < schema["minimum"]:
                problemas.append(f"{path}: {value} abaixo do mínimo {schema['minimum']}")
    elif esperado == "boolean" and not isinstance(value, bool):
        problemas.append(f"{path}: esperado booleano, veio {_nome(value)}")

    if "enum" in schema and value not in schema["enum"]:
        problemas.append(f"{path}: {value!r} fora dos valores previstos ({schema['enum']})")
    return problemas


def schema_is_supported(schema: dict | None) -> list[str]:
    """Construções do esquema que o validador NÃO entende. Vazio significa esquema conferível."""
    if schema is None:
        return []
    fora: list[str] = []

    def andar(no: Any, caminho: str) -> None:
        if not isinstance(no, dict):
            return
        for chave in no:
            if chave not in SUPPORTED_KEYWORDS:
                fora.append(f"{caminho}.{chave}")
        tipo = no.get("type")
        if tipo is not None and tipo not in SUPPORTED_TYPES:
            fora.append(f"{caminho}.type={tipo}")
        for campo, sub in (no.get("properties") or {}).items():
            andar(sub, f"{caminho}.properties.{campo}")
        if "items" in no:
            andar(no["items"], f"{caminho}.items")

    andar(schema, "$")
    return fora


def extract_json(text: str) -> tuple[Any, str | None]:
    """Extrai o JSON da resposta do modelo. Devolve (valor, motivo da falha)."""
    if not text:
        return None, "resposta vazia"
    inicio, fim = text.find("{"), text.rfind("}")
    if inicio < 0 or fim <= inicio:
        inicio, fim = text.find("["), text.rfind("]")
    if inicio < 0 or fim <= inicio:
        return None, "a resposta não contém JSON"
    try:
        return json.loads(text[inicio:fim + 1]), None
    except ValueError as exc:
        return None, f"JSON inválido: {exc}"


def _nome(value: Any) -> str:
    return {str: "texto", int: "número", float: "número", bool: "booleano",
            list: "lista", dict: "objeto", type(None): "nulo"}.get(type(value), type(value).__name__)
