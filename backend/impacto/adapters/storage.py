"""Armazenamento PRIVADO de arquivos.

* ``LocalStorage``: diretório fora da raiz web; leitura só via API autorizada com token temporário.
* ``S3Storage``: S3/MinIO/R2 com assinatura AWS SigV4 implementada aqui (sem boto3) e URLs pré-assinadas curtas.
  Validado contra o vetor oficial da documentação AWS (tests/test_unit_adapters.py).
As chaves de objeto são aleatórias (``<org>/<uuid>``) — nunca derivadas do nome enviado pelo usuário.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class LocalStorage:
    kind = "local"

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("chave de armazenamento inválida")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def presigned_get(self, key: str, filename: str, ttl: int) -> str | None:
        return None  # servido pela própria API com token assinado


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sigv4_presign(method: str, host: str, path: str, region: str, access_key: str, secret_key: str,
                  expires: int, now: datetime, extra_query: dict | None = None, service: str = "s3") -> str:
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    datestamp = now.strftime("%Y%m%d")
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    q = {"X-Amz-Algorithm": "AWS4-HMAC-SHA256", "X-Amz-Credential": f"{access_key}/{scope}", "X-Amz-Date": amz_date,
         "X-Amz-Expires": str(expires), "X-Amz-SignedHeaders": "host"}
    q.update(extra_query or {})
    canonical_qs = "&".join(f"{urllib.parse.quote(k, safe='-_.~')}={urllib.parse.quote(v, safe='-_.~')}" for k, v in sorted(q.items()))
    canonical_path = urllib.parse.quote(path, safe="/-_.~")
    canonical = "\n".join([method, canonical_path, canonical_qs, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _sign(("AWS4" + secret_key).encode(), datestamp)
    k = _sign(_sign(_sign(k, region), service), "aws4_request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    return f"{canonical_qs}&X-Amz-Signature={signature}"


class S3Storage:
    kind = "s3"

    def __init__(self, endpoint: str, region: str, bucket: str, access_key: str, secret_key: str):
        endpoint = endpoint or f"https://s3.{region}.amazonaws.com"
        self.base = endpoint.rstrip("/")
        self.host = urllib.parse.urlparse(self.base).netloc
        self.region, self.bucket, self.ak, self.sk = region, bucket, access_key, secret_key

    def _url(self, key: str, method: str, ttl: int = 300, extra: dict | None = None) -> str:
        path = f"/{self.bucket}/{key}"
        qs = sigv4_presign(method, self.host, path, self.region, self.ak, self.sk, ttl, datetime.now(timezone.utc), extra)
        return f"{self.base}{urllib.parse.quote(path, safe='/-_.~')}?{qs}"

    def put(self, key: str, data: bytes, content_type: str) -> None:
        req = urllib.request.Request(self._url(key, "PUT"), data=data, method="PUT",
                                     headers={"Content-Type": content_type})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - URL controlada pela configuração
            if r.status not in (200, 201):
                raise RuntimeError(f"S3 PUT falhou: {r.status}")

    def get(self, key: str) -> bytes:
        with urllib.request.urlopen(self._url(key, "GET"), timeout=30) as r:  # noqa: S310
            return r.read()

    def delete(self, key: str) -> None:
        req = urllib.request.Request(self._url(key, "DELETE"), method="DELETE")
        with urllib.request.urlopen(req, timeout=30):  # noqa: S310
            pass

    def presigned_get(self, key: str, filename: str, ttl: int) -> str:
        disp = f'attachment; filename="{filename.encode("ascii", "ignore").decode() or "arquivo"}"'
        return self._url(key, "GET", ttl, {"response-content-disposition": disp})
