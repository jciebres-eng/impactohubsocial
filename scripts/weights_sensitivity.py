#!/usr/bin/env python3
"""Análise de sensibilidade dos pesos de relevância da busca (config/solution_weights.json → search_relevance).
Para cada peso, multiplica por 0,5 e por 1,5 (os demais intactos; a pontuação renormaliza sobre os sinais aplicáveis) e mede, nas consultas de
qualidade, se o resultado esperado continua entre os 3 primeiros. NÃO prova que os pesos são "ótimos": mostra o quão estáveis eles são num corpus
sintético pequeno. Calibração real exige dados de uso. Uso: cd backend && TEST_ADMIN_DATABASE_URL=... PYTHONPATH=. python3 ../scripts/weights_sensitivity.py"""
import copy
import json
import uuid
from pathlib import Path

from impacto.engines.solutions import scoring as SC
from tests.support import new_account, server
from tests.test_v090_solutions import mk

server()
a, b, fu = new_account("osc"), new_account("osc"), new_account("company")
t = uuid.uuid4().hex[:5]
S = {
    "arte_caps": mk(a, title=f"Oficinas de arte no CAPS {t}", summary="Oficinas de artes plásticas e música para usuários do Centro de Atenção Psicossocial.", themes=["saude", "cultura"], population=["saude_mental"], institutions=["caps"], ods=[3], uf="MT"),
    "arteterapia": mk(a, title=f"Arteterapia comunitária {t}", summary="Grupos de arteterapia para pessoas em sofrimento psíquico, em parceria com a rede de saúde mental.", themes=["saude", "cultura"], population=["saude_mental"], ods=[3], uf="SP"),
    "idosos": mk(a, title=f"Cuidado ativo para idosos {t}", summary="Grupos de convivência e atividade física para pessoas idosas.", themes=["pessoa_idosa", "saude"], population=["idosos"], ods=[3, 10], uf="MT"),
    "rural": mk(b, title=f"Escola do campo conectada {t}", summary="Educação rural com transporte escolar e conteúdos adaptados ao campo.", themes=["educacao"], population=["rural", "criancas"], ods=[4], uf="PA"),
    "mulheres": mk(b, title=f"Rede de acolhimento a mulheres {t}", summary="Acolhimento e orientação jurídica para mulheres em situação de violência doméstica.", themes=["igualdade_genero"], population=["mulheres", "violencia_mulheres"], ods=[5, 16], uf="BA"),
    "pcd": mk(b, title=f"Tecnologia assistiva para PcD {t}", summary="Oficinas de tecnologia assistiva e acessibilidade digital para pessoas com deficiência.", themes=["pessoa_com_deficiencia", "inclusao_digital"], population=["pcd"], ods=[10, 9], uf="RS"),
    # distratores: parecidos em tema, fora da intenção
    "d1": mk(b, title=f"Festival de arte urbana {t}", summary="Festival anual de grafite e música nas praças.", themes=["cultura"], population=["jovens"], ods=[11], uf="MT"),
    "d2": mk(a, title=f"Saúde da família no campo {t}", summary="Equipes de saúde itinerantes em áreas rurais.", themes=["saude"], population=["rural"], ods=[3], uf="PA"),
}
CASES = [("artes caps", "arte_caps"), ("arte saúde mental", "arte_caps"), ("projeto idosos", "idosos"), ("educação rural", "rural"),
         ("mulheres violência", "mulheres"), ("PcD tecnologia", "pcd"), ("sude mental arte", "arte_caps")]


def run() -> dict:
    ranks = {}
    for q, key in CASES:
        res = fu.post("/v1/solutions/search", {"text": q, "limit": 50}).json["items"]
        ids = [i["id"] for i in res]
        ranks[q] = ids.index(S[key]) + 1 if S[key] in ids else None
    return ranks


base = run()
original = copy.deepcopy(SC.W["search_relevance"])
out = {"base_ranks": base, "perturbations": []}
for k in ("text_relevance", "ods_esg", "population", "territory", "budget", "maturity", "replicability", "evidence"):
    for f in (0.5, 1.5):
        SC.W["search_relevance"] = {**original, k: original[k] * f}
        r = run()
        out["perturbations"].append({"weight": k, "factor": f, "top3_kept": all(v is not None and v <= 3 for v in r.values()), "ranks": r})
SC.W["search_relevance"] = original
# todos os pesos de sinal em 1 (sem hierarquia) — ponto de comparação
SC.W["search_relevance"] = {**original, **{k: 10 for k in ("text_relevance", "ods_esg", "population", "territory", "budget", "maturity", "replicability", "evidence")}}
flat = run()
SC.W["search_relevance"] = original
out["flat_weights"] = {"ranks": flat, "top3_kept": all(v is not None and v <= 3 for v in flat.values())}
out["summary"] = {"perturbations": len(out["perturbations"]), "kept_top3": sum(1 for p in out["perturbations"] if p["top3_kept"]),
                  "base_all_top3": all(v is not None and v <= 3 for v in base.values()),
                  "note": "Corpus sintético de 8 soluções e 7 consultas: mostra robustez do desenho, não otimalidade. Pesos continuam HIPÓTESE inicial."}
Path(__file__).resolve().parents[1].joinpath("docs/evidence/weights_sensitivity_v0.9.0.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(out["summary"], indent=2, ensure_ascii=False)); print("base", base); print("flat", flat)
for p in out["perturbations"]:
    if not p["top3_kept"]:
        print("MUDA:", p["weight"], p["factor"], p["ranks"])
