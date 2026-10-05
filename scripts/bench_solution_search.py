#!/usr/bin/env python3
"""Mede a busca da Biblioteca de Soluções num banco de teste com N soluções sintéticas (todas marcadas is_demo).
Uso: cd backend && TEST_ADMIN_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres PYTHONPATH=. python3 ../scripts/bench_solution_search.py [N]
Escreve docs/evidence/search_perf_v0.9.0.json. Números = ESTE ambiente (1 processo, PostgreSQL local), não projeção de produção."""
import json
import statistics
import sys
import time
from pathlib import Path

from tests.support import db_system, new_account, server

N = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
server()
org = new_account("osc")
fu = new_account("company")
THEMES = ["saude", "educacao", "cultura", "pessoa_idosa", "igualdade_genero", "meio_ambiente", "esporte", "inclusao_digital"]
POPS = ["saude_mental", "idosos", "criancas", "jovens", "mulheres", "pcd", "rural"]
UFS = ["MT", "SP", "PA", "BA", "RS", "MG", "AM", "PE"]
WORDS = ["oficinas", "grupos", "formação", "acolhimento", "arte", "música", "esporte", "tecnologia", "horta", "leitura", "cuidado", "renda", "território", "rede"]
with db_system() as d:
    d.run("""INSERT INTO solutions(org_id, created_by, kind, stage, title, summary, problem, approach, themes, population, ods, uf, budget_cents, visibility, is_demo)
             SELECT $1::uuid, $2::uuid, 'project', (ARRAY['proposal','running','completed'])[1 + i % 3],
                    '[DEMO] ' || ($3::text[])[1 + i % 14] || ' ' || ($3::text[])[1 + (i / 3) % 14] || ' ' || i,
                    'Solução sintética ' || i || ' de ' || ($3::text[])[1 + (i / 5) % 14] || ' para teste de desempenho da busca.',
                    'Problema sintético.', 'Abordagem sintética com ' || ($3::text[])[1 + (i / 7) % 14],
                    ARRAY[($4::text[])[1 + i % 8]], ARRAY[($5::text[])[1 + i % 7]], ARRAY[(1 + i % 17)::smallint], ($6::text[])[1 + i % 8],
                    (100000 + (i * 7919) % 9000000)::bigint, 'published', true
             FROM generate_series(1, $7::int) AS i""", org.org_id, org.user["id"], WORDS, THEMES, POPS, UFS, N)
    total = d.scalar("SELECT count(*) FROM solutions WHERE visibility = 'published'")
    d.run("ANALYZE solutions")
QUERIES = ["artes caps", "arte saúde mental", "projeto idosos", "educação rural", "mulheres violência", "PcD tecnologia", "tenho R$ 250 mil para esporte em MT", "horta", "sude mental"]
lat = []
for r in range(6):
    for q in QUERIES:
        t = time.perf_counter()
        res = fu.post("/v1/solutions/search", {"text": q, "limit": 12})
        lat.append((time.perf_counter() - t) * 1000)
        assert res.status == 200, res
lat.sort()
out = {"published_solutions": total, "queries": len(lat), "p50_ms": round(statistics.median(lat), 1), "p95_ms": round(lat[int(len(lat) * 0.95) - 1], 1), "max_ms": round(lat[-1], 1),
       "candidate_cap": 200, "note": "1 processo, PostgreSQL local, sem cache; inclui HTTP local, autenticação, RLS, FTS+trigramas, pontuação em Python e registro do log de busca."}
Path(__file__).resolve().parents[1].joinpath("docs/evidence/search_perf_v0.9.0.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(out, indent=2, ensure_ascii=False))
