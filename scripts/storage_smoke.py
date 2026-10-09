#!/usr/bin/env python3
"""Verificação REAL do adaptador S3 do IMPACTO contra um armazenamento S3-compatível (v0.31.0).

Usa a MESMA classe que a aplicação usa (`impacto.adapters.storage.S3Storage`) — não um SDK — e
confere o que o produto depende, contra um servidor que valida assinatura:

  1. PUT de um objeto (URL assinada, path-style)          5. URL pré-assinada EXPIRADA é recusada
  2. GET devolve exatamente os mesmos bytes (SHA-256)     6. URL com assinatura adulterada é recusada
  3. URL pré-assinada baixa sem credencial                7. credencial errada é recusada
  4. o nome do arquivo vai no Content-Disposition         8. DELETE remove (GET seguinte falha)
     (informativo: o R2 não documenta esse parâmetro)

Nunca imprime chave, segredo nem URL assinada (a URL é um portador: quem a tem, baixa). Os objetos de
teste ficam sob o prefixo `_smoke/` e são apagados ao fim, inclusive em falha.

Uso (lê S3_ENDPOINT, S3_REGION, S3_BUCKET, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY):
    python3 scripts/storage_smoke.py [--create-bucket] [--json saida.json]
`--create-bucket` só para servidor de teste descartável (MinIO do CI). Código de saída 1 se falhar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from impacto.adapters.storage import S3Storage, sigv4_presign  # noqa: E402


def _status(url: str, method: str = "GET") -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - endpoint de teste configurado
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def create_bucket(st: S3Storage) -> None:
    """Só para servidor descartável: PUT /<bucket> assinado (path-style)."""
    path = f"/{st.bucket}"
    qs = sigv4_presign("PUT", st.host, path, st.region, st.ak, st.sk, 300, datetime.now(UTC))
    code, body, _ = _status(f"{st.base}{path}?{qs}", "PUT")
    if code not in (200, 409):   # 409 = já existe
        raise RuntimeError(f"criar bucket falhou: HTTP {code} {body[:200]!r}")


def run(st: S3Storage) -> list[dict]:
    res: list[dict] = []

    def ok(check: str, passed: bool, detail: str = "", required: bool = True) -> None:
        res.append({"check": check, "passed": bool(passed), "required": required, "detail": detail})

    key = f"_smoke/{secrets.token_hex(12)}.pdf"
    data = b"%PDF-1.4\n% impacto storage smoke " + secrets.token_bytes(64)
    try:
        st.put(key, data, "application/pdf")
        ok("put", True)
        got = st.get(key)
        ok("get_same_bytes", hashlib.sha256(got).hexdigest() == hashlib.sha256(data).hexdigest(), f"{len(got)} bytes")

        url = st.presigned_get(key, "relatório final.pdf", 60)
        code, body, headers = _status(url)
        ok("presigned_get_without_credentials", code == 200 and body == data, f"HTTP {code}")
        disp = next((v for k, v in headers.items() if k.lower() == "content-disposition"), "")
        ok("presigned_sets_filename", "relat" in disp and "attachment" in disp,
           "Content-Disposition presente" if disp else "Content-Disposition AUSENTE — o navegador usará o nome da chave",
           required=False)

        short = st.presigned_get(key, "x.pdf", 1)
        time.sleep(2.5)
        code, _, _ = _status(short)
        ok("expired_presigned_refused", code in (400, 401, 403), f"HTTP {code}")

        tampered = url[:-4] + ("0000" if not url.endswith("0000") else "1111")
        code, _, _ = _status(tampered)
        ok("tampered_signature_refused", code in (400, 401, 403), f"HTTP {code}")

        wrong = S3Storage(st.base, st.region, st.bucket, st.ak, st.sk[::-1] + "x")
        try:
            wrong.get(key)
            ok("wrong_secret_refused", False, "GET com segredo errado foi ACEITO")
        except urllib.error.HTTPError as e:
            ok("wrong_secret_refused", e.code in (400, 401, 403), f"HTTP {e.code}")
    except Exception as exc:  # noqa: BLE001 - registra e segue para a limpeza
        ok("unexpected_error", False, f"{type(exc).__name__}: {str(exc)[:200]}")
    finally:
        try:
            st.delete(key)
            try:
                st.get(key)
                ok("delete_removes", False, "objeto ainda legível após DELETE")
            except urllib.error.HTTPError as e:
                ok("delete_removes", e.code == 404, f"HTTP {e.code} após DELETE")
        except Exception as exc:  # noqa: BLE001
            ok("delete_removes", False, f"{type(exc).__name__}: {str(exc)[:200]}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create-bucket", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    env = {k: os.getenv(k, "") for k in ("S3_ENDPOINT", "S3_REGION", "S3_BUCKET", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY")}
    falta = [k for k, v in env.items() if not v and k != "S3_REGION"]
    if falta:
        print(f"faltam variáveis: {', '.join(falta)}", file=sys.stderr)
        return 2
    st = S3Storage(env["S3_ENDPOINT"], env["S3_REGION"] or "auto", env["S3_BUCKET"], env["S3_ACCESS_KEY_ID"], env["S3_SECRET_ACCESS_KEY"])
    print(f"armazenamento: host {st.host} · região {st.region} · bucket {st.bucket}")
    if a.create_bucket:
        create_bucket(st)
    res = run(st)
    for r in res:
        marca = "PASS" if r["passed"] else ("FAIL" if r["required"] else "AVISO")
        print(f"  {marca:5} {r['check']}: {r['detail']}")
    falhou = [r["check"] for r in res if r["required"] and not r["passed"]]
    print("VEREDITO:", "PASS" if not falhou else f"FAIL ({', '.join(falhou)})")
    if a.json:
        Path(a.json).write_text(json.dumps({"host": st.host, "results": res, "passed": not falhou}, ensure_ascii=False, indent=2))
    return 0 if not falhou else 1


if __name__ == "__main__":
    raise SystemExit(main())
