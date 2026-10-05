#!/usr/bin/env python3
"""Teste de carga SIMPLES (somente biblioteca padrão) contra uma instância já em execução.

Mede latência (p50/p95/p99) e taxa de erro de rotas de leitura autenticadas sob N threads. NÃO é um teste de capacidade de produção:
roda na mesma máquina do servidor/banco, com dados mínimos. Serve para detectar regressões grosseiras e registrar números reais.

Uso: python3 scripts/loadtest.py --base http://127.0.0.1:8099 --threads 8 --seconds 15 --out docs/evidence/loadtest_v0.8.0.json
Requer RATE_LIMIT_MULTIPLIER alto no servidor (o limitador de taxa é mantido ligado e distorce o teste se ficar no padrão).
"""
import argparse, http.cookiejar, json, statistics, threading, time, urllib.request, uuid

PW = "Senha-Teste-Forte-2026"


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


def setup(base):
    call = client(base)
    email = f"load-{uuid.uuid4().hex[:8]}@teste.org"
    code, _ = call("POST", "/v1/auth/register", {"email": email, "password": PW, "full_name": "Carga Teste", "accept_terms": True,
                                                   "organization": {"kind": "individual", "legal_name": "Carga Teste"}})
    assert code in (200, 201, 202), f"cadastro falhou: {code}"
    code, _ = call("POST", "/v1/auth/login", {"email": email, "password": PW})
    assert code == 200, f"login falhou: {code}"
    return call


ROUTES = ["/v1/dashboard", "/v1/feed/projects", "/v1/ods", "/v1/indicators/catalog", "/v1/report-center", "/v1/map/projects", "/v1/portfolio", "/v1/me"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8099"); ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--seconds", type=int, default=15); ap.add_argument("--out")
    a = ap.parse_args()
    lat: dict[str, list[float]] = {r: [] for r in ROUTES}
    errs: dict[str, int] = {r: 0 for r in ROUTES}
    lock = threading.Lock(); stop = time.time() + a.seconds
    def worker(i):
        call = setup(a.base)
        k = i
        while time.time() < stop:
            r = ROUTES[k % len(ROUTES)]; k += 1
            code, ms = call("GET", r)
            with lock:
                lat[r].append(ms)
                if code >= 400:
                    errs[r] += 1
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(a.threads)]
    t0 = time.time(); [t.start() for t in ts]; [t.join() for t in ts]; dur = time.time() - t0
    def pct(v, p): s = sorted(v); return round(s[min(len(s) - 1, int(len(s) * p))], 1) if s else None
    rows = {r: {"requests": len(v), "errors": errs[r], "p50_ms": pct(v, .5), "p95_ms": pct(v, .95), "p99_ms": pct(v, .99), "mean_ms": round(statistics.mean(v), 1) if v else None} for r, v in lat.items()}
    total = sum(len(v) for v in lat.values())
    out = {"threads": a.threads, "seconds": round(dur, 1), "total_requests": total, "rps": round(total / dur, 1), "total_errors": sum(errs.values()), "routes": rows,
           "caveats": "mesma máquina para cliente, API e PostgreSQL; dados mínimos; sem rede real; não representa capacidade de produção"}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if a.out:
        open(a.out, "w").write(json.dumps(out, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
