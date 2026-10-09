#!/usr/bin/env python3
"""Fase piloto — MEDIÇÃO REAL do que pode ser medido nesta instalação (v0.28.0).

Mede, com o motor local de similaridade e perfis sintéticos: latência por comparação, por análise de originalidade
contra 50 e 200 candidatos, tamanho da entrada em caracteres e a aproximação de tokens (4 caracteres/token) que
um provedor externo cobraria SE as operações de assistência fossem externas. Não mede custo de provedor (não há
provedor configurado nem tabela de preço) nem infraestrutura: esses campos ficam como NÃO MEDIDO.

Escreve docs/evidence/ai_pilot_v0280.json, lido por scripts/make_ai_cost_model.py.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from impacto.engines.similarity import engine as E  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "ai_pilot_v0280.json"
WORDS = ("leitura crianças escola bairro reforço oficina mediadores acervo biblioteca contraturno horta alimentos famílias "
         "capacitação jovens esporte saúde mulheres renda cooperativa reciclagem água território comunidade cultura música "
         "teatro oficinas formação professores indicadores frequência evasão aprendizagem".split())


def synth(i: int, rng: random.Random) -> dict:
    def txt(n):
        return " ".join(rng.choice(WORDS) for _ in range(n))
    return {"id": f"p{i}", "title": txt(4), "summary": txt(40), "problem": txt(35), "objectives": txt(30), "methodology": txt(30),
            "causes": [rng.choice(["educacao", "saude", "cultura", "meio_ambiente"])], "ods": [rng.choice([1, 3, 4, 11])],
            "territory": rng.choice(["BR-MT-5103403", "BR-MT-5107602", "BR-PA-1501402"]), "uf": rng.choice(["MT", "PA"]), "city": None,
            "beneficiaries_description": txt(8), "beneficiaries_count": rng.randint(10, 500),
            "starts_on": date(2026, rng.randint(1, 12), 1), "ends_on": date(2027, rng.randint(1, 12), 1),
            "budget_total_cents": rng.randint(50_000, 5_000_000),
            "budget_items": [{"description": txt(2), "category": None, "total_cents": rng.randint(1000, 100000)} for _ in range(rng.randint(1, 6))],
            "calls": [], "funders": [], "indicator_names": [txt(3) for _ in range(rng.randint(0, 4))], "lat": None, "lng": None,
            "org_name": f"OSC {i}", "visibility": "published"}


def main() -> int:
    rng = random.Random(2027)
    pool = [synth(i, rng) for i in range(201)]
    subject = pool[0]
    chars = sum(len(str(subject.get(k) or "")) for k in ("title", "summary", "problem", "objectives", "methodology", "beneficiaries_description"))
    # 1) uma comparação
    t = []
    for c in pool[1:51]:
        t0 = time.perf_counter()
        E.compare(subject, c)
        t.append((time.perf_counter() - t0) * 1000)
    # 2) originalidade contra 50 e 200
    t50 = []
    for _ in range(5):
        t0 = time.perf_counter()
        E.originality(subject, pool[1:51])
        t50.append((time.perf_counter() - t0) * 1000)
    t200 = []
    for _ in range(3):
        t0 = time.perf_counter()
        E.originality(subject, pool[1:201])
        t200.append((time.perf_counter() - t0) * 1000)
    out = {
        "measured_on": date.today().isoformat(), "engine_version": E.ENGINE_VERSION,
        "what_is_measured": "latência de CPU do motor LOCAL com perfis sintéticos nesta máquina; tamanho de entrada; aproximação de tokens",
        "what_is_not_measured": ["custo de provedor externo (nenhum configurado; tabela de preço vazia)", "infraestrutura por operação",
                                  "tarifa de pagamento", "impostos", "qualidade em base real"],
        "input_chars_subject": chars, "approx_tokens_subject": chars // 4,
        "pair_compare_ms": {"p50": round(statistics.median(t), 2), "p95": round(sorted(t)[int(len(t) * 0.95) - 1], 2), "n": len(t)},
        "originality_50_ms": {"p50": round(statistics.median(t50), 1), "max": round(max(t50), 1), "n": len(t50)},
        "originality_200_ms": {"p50": round(statistics.median(t200), 1), "max": round(max(t200), 1), "n": len(t200)},
        "assist_ops_estimated_tokens": {"summarize_project": {"chars_in": chars, "tokens_in_approx": chars // 4, "max_tokens_out_policy": 2000},
                                        "note": "operações de assistência: tokens de entrada = caracteres/4 (aproximação declarada); saída limitada pela faixa de risco"},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{OUT.name}: par {out['pair_compare_ms']} · 50 cand {out['originality_50_ms']} · 200 cand {out['originality_200_ms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
