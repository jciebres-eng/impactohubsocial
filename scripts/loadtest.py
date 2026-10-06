#!/usr/bin/env python3
"""Teste de carga SIMPLES (somente biblioteca padrão) contra uma instância já em execução.

Mede latência (p50/p95/p99) e taxa de erro de rotas de leitura autenticadas sob N threads. NÃO é um teste de capacidade de produção:
roda na mesma máquina do servidor/banco, com dados mínimos. Serve para detectar regressões grosseiras e registrar números reais.

Uso: python3 scripts/loadtest.py --base http://127.0.0.1:8099 --threads 8 --seconds 15 --out docs/evidence/loadtest_v0.8.0.json
Requer RATE_LIMIT_MULTIPLIER alto no servidor (o limitador de taxa é mantido ligado e distorce o teste se ficar no padrão).
"""
import argparse, http.cookiejar, json, statistics, threading, time, urllib.request, uuid

PW = "Senha-Teste-Forte-2026"
_SEQ = [700000]


def cnpj():
    """CNPJ sintético com dígitos verificadores válidos (o cadastro de OSC exige CNPJ válido)."""
    _SEQ[0] += 1
    base = f"{_SEQ[0]:012d}"[-12:]
    for pesos in ((5,4,3,2,9,8,7,6,5,4,3,2), (6,5,4,3,2,9,8,7,6,5,4,3,2)):
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        base += "0" if resto < 2 else str(11 - resto)
    return base


def client(base):
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def call(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        for c in jar:
            if c.name.endswith("impacto_csrf"):
                h["X-CSRF-Token"] = c.value
        req = urllib.request.Request(base + path, data=data, method=method, headers=h)
        t = time.perf_counter()
        try:
            with op.open(req, timeout=30) as r:
                r.read(); code = r.status
        except urllib.error.HTTPError as e:
            e.read(); code = e.code
        return code, (time.perf_counter() - t) * 1000
    return call


def setup(base, kind="osc"):
    call = client(base)
    email = f"load-{uuid.uuid4().hex[:8]}@teste.org"
    # OSC em vez de pessoa física: as rotas da camada de impacto exigem organização com projeto,
    # e medir carga em rota que devolve 403 mede o limitador, não o produto.
    code, _ = call("POST", "/v1/auth/register", {"email": email, "password": PW, "full_name": "Carga Teste", "accept_terms": True,
                                                   "organization": {"kind": kind, "legal_name": f"Org Carga {uuid.uuid4().hex[:6]}", "cnpj": cnpj(), "uf": "MT"}})
    assert code in (200, 201, 202), f"cadastro falhou: {code}"
    code, _ = call("POST", "/v1/auth/login", {"email": email, "password": PW})
    assert code == 200, f"login falhou: {code}"
    return call


# v0.18.1: as rotas da camada de impacto entraram na carga porque são as que fazem
# `CROSS JOIN LATERAL` sobre função (claim_status, seal_status, dispute_status) e as que o
# autocomplete chama a cada tecla — exatamente o que degrada primeiro sob concorrência.
# Cada rota com o TIPO de organização que pode chamá-la. Medir carga numa rota que devolve 403
# mede o controle de acesso, não o produto — foi o que aconteceu na primeira execução desta rodada,
# quando `/v1/portfolio` e `/v1/feed/projects` (exclusivas de financiador) entraram com conta de OSC
# e produziram 330 "erros" que não eram defeito nenhum.
ROUTES = [
    ("/v1/dashboard", "osc"), ("/v1/me", "osc"), ("/v1/ods", "osc"),
    ("/v1/indicators/catalog", "osc"), ("/v1/report-center", "osc"), ("/v1/map/projects", "osc"),
    ("/v1/claims?limit=20", "osc"), ("/v1/claims/rules", "osc"), ("/v1/reputation/me", "osc"),
    ("/v1/reputation/dimensions", "osc"), ("/v1/seals/awards", "osc"),
    ("/v1/seals/definitions", "osc"), ("/v1/lookups/territories?q=ma", "osc"),
    ("/v1/lookups/indicators?q=pes", "osc"), ("/v1/responsibility/mine", "osc"),
    ("/v1/responsibility/roles", "osc"), ("/v1/frameworks", "osc"),
    ("/v1/equity/catalog", "osc"), ("/v1/territories/search?q=mato", "osc"),
    ("/v1/feed/projects", "company"), ("/v1/portfolio", "company"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8099"); ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--seconds", type=int, default=15); ap.add_argument("--out")
    a = ap.parse_args()
    lat: dict[str, list[float]] = {r: [] for r, _k in ROUTES}
    errs: dict[str, int] = {r: 0 for r, _k in ROUTES}
    codes: dict[str, set] = {r: set() for r, _k in ROUTES}
    lock = threading.Lock(); stop = time.time() + a.seconds
    def worker(i):
        chamadas = {"osc": setup(a.base, "osc"), "company": setup(a.base, "company")}
        k = i
        while time.time() < stop:
            r, kind = ROUTES[k % len(ROUTES)]; k += 1
            code, ms = chamadas[kind]("GET", r)
            with lock:
                lat[r].append(ms)
                codes[r].add(code)
                if code >= 400:
                    errs[r] += 1
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(a.threads)]
    t0 = time.time(); [t.start() for t in ts]; [t.join() for t in ts]; dur = time.time() - t0
    def pct(v, p): s = sorted(v); return round(s[min(len(s) - 1, int(len(s) * p))], 1) if s else None
    rows = {r: {"requests": len(v), "errors": errs[r], "status_codes": sorted(codes[r]),
                "p50_ms": pct(v, .5), "p95_ms": pct(v, .95), "p99_ms": pct(v, .99),
                "mean_ms": round(statistics.mean(v), 1) if v else None} for r, v in lat.items()}
    total = sum(len(v) for v in lat.values())
    out = {"threads": a.threads, "seconds": round(dur, 1), "total_requests": total, "rps": round(total / dur, 1), "total_errors": sum(errs.values()), "routes": rows,
           "caveats": "mesma máquina para cliente, API e PostgreSQL; dados mínimos; sem rede real; não representa capacidade de produção"}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if a.out:
        open(a.out, "w").write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
