"""Benchmark de preço: referência consultada, nunca preço decidido.

§47–48 e §89 pedem pesquisa de preços de produtos comparáveis, registro de SOURCE, DATE, PRODUCT,
PLAN, PRICE, CURRENCY e FEATURES, e tratamento do resultado como **BENCHMARK** — explicitamente não
como preço final. E pedem que a configuração de preço seja centralizada, nunca espalhada pelo
frontend, com a marca `PRICE_FINALIZATION_REQUIRED`.

A SEPARAÇÃO QUE ESTE MÓDULO EXISTE PARA MANTER

`config/price_benchmark.json` é o que o MERCADO cobra. `config/plans.json` é o que a Impacto Trust
cobra. São dois arquivos, e nenhuma linha de código lê o primeiro para preencher o segundo — há
teste que reprova a suíte se isso mudar.

A razão não é formal. Um benchmark que vira preço por conveniência produz um preço que ninguém
decidiu: ele apenas apareceu, copiado de empresas com outro produto, outro custo e outro cliente. O
preço da Impacto Trust é decisão do proprietário, e enquanto ela não for tomada os planos pagos
continuam com preço nulo — exibidos como "sob consulta", que é a verdade.

O QUE A PESQUISA ENCONTROU, E QUE É INFORMAÇÃO EM SI: um terço dos fornecedores comparáveis não
publica preço algum, inclusive os dois mais próximos do que esta plataforma faz. Fornecedor que não
publica entra na tabela com preço nulo e o motivo. Omiti-lo faria o mercado parecer mais
transparente do que é.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG = Path(__file__).resolve().parents[3] / "config" / "price_benchmark.json"

#: Os sete campos que §89 exige de cada linha.
REQUIRED_FIELDS = ("source", "source_date", "product", "plan", "price", "currency", "features")


def load() -> dict[str, Any]:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def benchmark() -> dict[str, Any]:
    """A tabela consultada, com a advertência que a torna utilizável sem virar preço."""
    doc = load()
    publicados = [e for e in doc["entries"] if e.get("price") is not None]
    sem_preco = [e for e in doc["entries"] if e.get("price") is None]
    valores = sorted(e["price"] for e in publicados)
    return {
        "collected_on": doc["collected_on"],
        "PRICE_FINALIZATION_REQUIRED": doc["PRICE_FINALIZATION_REQUIRED"],
        "entries": doc["entries"],
        "published": len(publicados),
        "not_published": len(sem_preco),
        "range_usd": ({"min": valores[0], "max": valores[-1],
                       "median": valores[len(valores) // 2]} if valores else None),
        "findings": doc["findings"],
        "decision_required": doc["decision_required"],
        "warning": ("BENCHMARK, NÃO PREÇO. Cada linha foi lida na página de preço do próprio "
                    "fornecedor na data declarada. Nenhum valor aqui define, sugere ou limita o "
                    "preço desta plataforma: a decisão é do proprietário. Preço publicado é preço "
                    "de LISTA — desconto por volume, por setor sem fins lucrativos e por contrato "
                    "plurianual é regra no mercado e não aparece aqui."),
    }
