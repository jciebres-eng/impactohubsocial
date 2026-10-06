#!/usr/bin/env python3
"""Smoke test de publicação: 20 verificações contra uma instância JÁ EM EXECUÇÃO.

Para que serve: responder, em menos de um minuto e sem adivinhação, se a instância que acabou de
subir está servindo o produto — e não apenas "respondendo 200 em /healthz". Cada verificação diz o
que provou, e as que dependem de serviço externo dizem isso em vez de passar calado.

Uso:
    python3 scripts/smoke_test.py --base https://app.exemplo.org \
        --email conta@exemplo.org --password '...' --out docs/evidence/smoke_v0.18.1.json

Sem `--email/--password` as verificações autenticadas são marcadas SKIPPED (não PASSED): smoke que
pula login e diz "ok" é o pior resultado possível.

Saída: JSON com uma linha por verificação e o veredito final GO / NO-GO. Código de saída 1 quando
alguma verificação obrigatória falha — serve para portão de pipeline.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import ssl
import sys
import time
import urllib.error
import urllib.request

TIMEOUT = 20


class Http:
    def __init__(self, base: str, *, insecure: bool = False) -> None:
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl._create_unverified_context() if insecure else None
        handlers = [urllib.request.HTTPCookieProcessor(self.jar)]
        if ctx is not None:
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        self.op = urllib.request.build_opener(*handlers)
        self.token: str | None = None

    def call(self, method: str, path: str, body=None, *, headers: dict | None = None) -> tuple:
        data = json.dumps(body).encode() if body is not None else None
        h = {"Accept": "application/json", "User-Agent": "impacto-smoke/1.0"}
        if data:
            h["Content-Type"] = "application/json"
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        for c in self.jar:
            if c.name.endswith("impacto_csrf"):
                h["X-CSRF-Token"] = c.value
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        t0 = time.perf_counter()
        try:
            with self.op.open(req, timeout=TIMEOUT) as r:
                raw = r.read()
                return r.status, _json(raw), (time.perf_counter() - t0) * 1000, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, _json(raw), (time.perf_counter() - t0) * 1000, dict(e.headers)
        except Exception as exc:  # noqa: BLE001
            return 0, {"error": f"{type(exc).__name__}: {exc}"}, (time.perf_counter() - t0) * 1000, {}


def _json(raw: bytes):
    try:
        return json.loads(raw or b"{}")
    except Exception:  # noqa: BLE001
        return {"raw": raw[:400].decode("utf-8", "replace")}


class Smoke:
    def __init__(self, http: Http, *, email: str | None, password: str | None) -> None:
        self.h = http
        self.email, self.password = email, password
        self.results: list[dict] = []

    def check(self, key: str, what: str, *, required: bool = True):
        def deco(fn):
            t0 = time.perf_counter()
            try:
                detail = fn()
                status = "PASSED"
            except Skip as s:
                detail, status = str(s), "SKIPPED"
            except AssertionError as a:
                detail, status = str(a), "FAILED"
            except Exception as exc:  # noqa: BLE001
                detail, status = f"{type(exc).__name__}: {exc}", "FAILED"
            self.results.append({"key": key, "what": what, "status": status, "detail": detail,
                                 "required": required, "ms": round((time.perf_counter() - t0) * 1000, 1)})
            print(f"  [{status:7s}] {key:26s} {detail}"[:160])
            return fn
        return deco


class Skip(Exception):
    pass


def run(base: str, email: str | None, password: str | None, *, insecure: bool) -> dict:
    h = Http(base, insecure=insecure)
    s = Smoke(h, email=email, password=password)
    print(f"smoke em {base}")

    @s.check("health", "/healthz responde e declara versão e ambiente")
    def _():
        st, body, ms, _hd = h.call("GET", "/healthz")
        assert st == 200, f"status {st}"
        assert body.get("status") == "ok", body
        assert body.get("version"), "sem versão na resposta"
        return f"versão {body['version']} · ambiente {body.get('env')} · {ms:.0f} ms"

    @s.check("ready", "/readyz confere banco e migrations pendentes")
    def _():
        st, body, ms, _hd = h.call("GET", "/readyz")
        assert st == 200, f"status {st} · {body}"
        assert body.get("database") == "ok", body
        assert not body.get("pending_migrations"), body
        return (f"banco ok · storage {body.get('storage')} · antivírus {body.get('antivirus')}"
                f" · ia {body.get('ai')} · cobrança {body.get('billing')} · {ms:.0f} ms")

    @s.check("ready_declares_providers", "o estado declara QUAL provedor está ligado")
    def _():
        _st, body, _ms, _hd = h.call("GET", "/readyz")
        faltando = [k for k in ("storage", "antivirus", "ai", "billing", "mail") if not body.get(k)]
        assert not faltando, f"provedor não declarado: {faltando}"
        simulados = [k for k in ("antivirus", "ai", "billing")
                     if str(body.get(k)).lower() in ("noop", "local", "sandbox", "console", "none")]
        return ("todos declarados" + (f" · ATENÇÃO, em modo não produtivo: {simulados}" if simulados else ""))

    @s.check("meta_config", "/v1/meta/config devolve versão de termos e privacidade")
    def _():
        st, body, _ms, _hd = h.call("GET", "/v1/meta/config")
        assert st == 200, f"status {st}"
        assert body.get("terms_version") and body.get("privacy_version"), body
        return f"termos {body['terms_version']} · privacidade {body['privacy_version']}"

    @s.check("openapi", "/v1/openapi.json descreve as operações")
    def _():
        st, body, _ms, _hd = h.call("GET", "/v1/openapi.json")
        assert st == 200, f"status {st}"
        n = sum(len(v) for v in (body.get("paths") or {}).values())
        assert n > 100, f"apenas {n} operações"
        return f"{n} operações em {len(body.get('paths') or {})} caminhos"

    @s.check("security_headers", "cabeçalhos de segurança presentes")
    def _():
        _st, _b, _ms, hd = h.call("GET", "/healthz")
        presentes = {k.lower() for k in hd}
        faltando = [k for k in ("X-Content-Type-Options", "Referrer-Policy")
                    if k.lower() not in presentes]
        assert not faltando, f"faltando: {faltando}"
        return "X-Content-Type-Options e Referrer-Policy presentes"

    @s.check("https_or_local", "TLS em produção (ou alvo local declarado)")
    def _():
        if base.startswith("https://"):
            return "alvo em https"
        if base.startswith(("http://127.0.0.1", "http://localhost")):
            raise Skip("alvo local: TLS não se aplica")
        raise AssertionError("alvo remoto em http: publicar sem TLS não é aceitável")

    @s.check("unauth_is_denied", "rota privada recusa sem sessão")
    def _():
        st, _b, _ms, _hd = h.call("GET", "/v1/projects")
        assert st in (401, 403), f"rota privada respondeu {st} sem sessão"
        return f"status {st} sem sessão"

    @s.check("rate_limit_present", "limitador de taxa responde no login")
    def _():
        vistos = set()
        for _ in range(12):
            st, _b, _ms, _hd = h.call("POST", "/v1/auth/login",
                                      {"email": "nao-existe@exemplo.org", "password": "x"})
            vistos.add(st)
            if st == 429:
                break
        if 429 in vistos:
            return "429 após tentativas repetidas"
        raise Skip(f"não houve 429 em 12 tentativas (status vistos: {sorted(vistos)});"
                   " confira RATE_LIMIT_MULTIPLIER do ambiente")

    @s.check("login", "login com a conta de smoke")
    def _():
        if not (email and password):
            raise Skip("sem --email/--password: verificações autenticadas não foram executadas")
        st, body, ms, _hd = h.call("POST", "/v1/auth/login", {"email": email, "password": password})
        assert st == 200, f"status {st} · {body}"
        tok = body.get("access_token") or body.get("token")
        if tok:
            h.token = tok
        return f"sessão estabelecida em {ms:.0f} ms"

    @s.check("session", "/v1/me devolve a sessão e a organização ativa")
    def _():
        if not h.token and not any(c.name.startswith("impacto") for c in h.jar):
            raise Skip("sem sessão")
        st, body, _ms, _hd = h.call("GET", "/v1/me")
        assert st == 200, f"status {st} · {body}"
        assert body.get("user"), body
        org = (body.get("active_org") or {}).get("id")
        return f"usuária {body['user'].get('email')} · organização {'ativa' if org else 'ausente'}"

    @s.check("db_read", "leitura de banco pela rota de projetos")
    def _():
        if not h.token and not any(c.name.startswith("impacto") for c in h.jar):
            raise Skip("sem sessão")
        st, body, ms, _hd = h.call("GET", "/v1/projects?limit=1")
        assert st == 200, f"status {st} · {body}"
        return f"{len(body.get('items') or [])} projeto(s) · {ms:.0f} ms"

    @s.check("lookup", "busca incremental responde com procedência", required=False)
    def _():
        if not h.token and not any(c.name.startswith("impacto") for c in h.jar):
            raise Skip("sem sessão")
        st, body, ms, _hd = h.call("GET", "/v1/lookups/territories?q=ma&limit=3")
        assert st == 200, f"status {st} · {body}"
        itens = body.get("items") or []
        assert itens, "nenhuma sugestão: catálogo territorial vazio"
        assert all(i.get("origin") for i in itens), "sugestão sem origem declarada"
        return f"{len(itens)} sugestão(ões), todas com origem · {ms:.0f} ms"

    @s.check("claim_rules", "catálogo de regras de alegação carregado", required=False)
    def _():
        if not h.token and not any(c.name.startswith("impacto") for c in h.jar):
            raise Skip("sem sessão")
        st, body, _ms, _hd = h.call("GET", "/v1/claims/rules")
        assert st == 200, f"status {st}"
        assert len(body.get("items") or []) >= 11, body
        return f"{len(body['items'])} regras determinísticas"

    @s.check("reputation_dimensions", "dimensões de reputação carregadas", required=False)
    def _():
        if not h.token and not any(c.name.startswith("impacto") for c in h.jar):
            raise Skip("sem sessão")
        st, body, _ms, _hd = h.call("GET", "/v1/reputation/dimensions")
        assert st == 200, f"status {st}"
        assert len(body.get("items") or []) >= 6, body
        assert "ranking" in (body.get("no_single_score") or ""), "a resposta perdeu o aviso de não-ranking"
        return f"{len(body['items'])} dimensões · sem nota única"

    @s.check("legal_pending", "estado dos documentos legais é legível", required=False)
    def _():
        if not h.token and not any(c.name.startswith("impacto") for c in h.jar):
            raise Skip("sem sessão")
        st, body, _ms, _hd = h.call("GET", "/v1/legal/pending")
        if st == 404:
            raise Skip("rota de pendências legais não exposta nesta instância")
        assert st == 200, f"status {st}"
        return f"{len(body.get('items') or [])} documento(s) pendente(s) de aceite"

    @s.check("storage_upload", "envio de arquivo chega ao armazenamento", required=False)
    def _():
        raise Skip("envio exige multipart e documento de projeto: executar na suíte E2E")

    @s.check("metrics", "endpoint de métricas protegido ou ausente")
    def _():
        st, _b, _ms, _hd = h.call("GET", "/metrics")
        if st == 200:
            return "métricas abertas: aceitável só em rede interna"
        if st in (401, 404):
            return f"protegido (status {st})"
        raise AssertionError(f"status inesperado {st}")

    @s.check("404_shape", "erro 404 devolve corpo estruturado")
    def _():
        st, body, _ms, _hd = h.call("GET", "/v1/rota-que-nao-existe")
        assert st == 404, f"status {st}"
        assert body.get("code") or body.get("type"), f"404 sem corpo estruturado: {body}"
        return "corpo com código de erro"

    @s.check("no_server_banner", "resposta não expõe pilha de servidor")
    def _():
        _st, _b, _ms, hd = h.call("GET", "/healthz")
        banner = hd.get("Server") or hd.get("server") or ""
        assert "uvicorn" not in banner.lower(), f"cabeçalho Server expõe a pilha: {banner}"
        return f"cabeçalho Server: {banner or 'ausente'}"

    obrig = [r for r in s.results if r["required"]]
    falhas = [r for r in s.results if r["status"] == "FAILED"]
    falhas_obrig = [r for r in obrig if r["status"] == "FAILED"]
    pulados = [r for r in s.results if r["status"] == "SKIPPED"]
    veredito = "NO-GO" if falhas_obrig else ("GO WITH CONDITIONS" if (falhas or pulados) else "GO")
    out = {"base": base, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "checks": s.results,
           "summary": {"total": len(s.results), "passed": len([r for r in s.results if r["status"] == "PASSED"]),
                       "failed": len(falhas), "skipped": len(pulados),
                       "required_failed": len(falhas_obrig)},
           "verdict": veredito}
    print(f"\n{veredito} · {out['summary']}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--insecure", action="store_true", help="aceita certificado inválido (só homologação)")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = run(a.base, a.email, a.password, insecure=a.insecure)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"relatório em {a.out}")
    return 1 if out["summary"]["required_failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
