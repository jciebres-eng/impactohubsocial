"""Hash de senhas com scrypt (memory-hard, stdlib) + verificação de hashes legados PBKDF2 do v0.6.

Formato: ``scrypt$n=<N>,r=<r>,p=<p>$<salt_b64>$<hash_b64>``. Parâmetros seguem recomendação OWASP
(N=2^17, r=8, p=1 ≈ 128 MiB). Hashes com parâmetros antigos são re-hasheados no próximo login.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

# PASSWORD_SCRYPT_N permite custo menor SOMENTE em testes automatizados (mínimo 2^14).
N = max(2 ** 14, int(os.getenv("PASSWORD_SCRYPT_N", str(2 ** 17))))
R, P, DKLEN = 8, 1, 32
_MAXMEM = 256 * 1024 * 1024

# Lista curta de senhas triviais (o principal controle é comprimento mínimo + rate limit + MFA).
_COMMON = {"123456789012", "senha123456", "password1234", "qwertyuiop12", "1234567890", "administrador", "impacto123456",
           "0123456789", "abcdefghij", "senhasenha", "aaaaaaaaaa", "1111111111"}


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=DKLEN, maxmem=_MAXMEM)
    return f"scrypt$n={N},r={R},p={P}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        # trabalho equivalente para não vazar existência de conta por tempo de resposta
        hashlib.scrypt(b"dummy", salt=b"0" * 16, n=N, r=R, p=P, dklen=DKLEN, maxmem=_MAXMEM)
        return False
    try:
        if stored.startswith("scrypt$"):
            _, params, salt, dk = stored.split("$")
            kv = dict(x.split("=") for x in params.split(","))
            calc = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(kv["n"]), r=int(kv["r"]), p=int(kv["p"]),
                                  dklen=len(_unb64(dk)), maxmem=_MAXMEM)
            return hmac.compare_digest(calc, _unb64(dk))
        # Legado v0.6: urlsafe_b64(salt16 + pbkdf2_sha256(210000))
        raw = base64.urlsafe_b64decode(stored.encode())
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), raw[:16], 210000)
        return hmac.compare_digest(calc, raw[16:])
    except Exception:
        return False


def needs_rehash(stored: str | None) -> bool:
    return not stored or not stored.startswith(f"scrypt$n={N},r={R},p={P}$")


def password_problems(password: str, email: str | None = None, name: str | None = None) -> list[str]:
    problems = []
    if len(password) < 10:
        problems.append("A senha deve ter pelo menos 10 caracteres")
    if len(password) > 256:
        problems.append("A senha deve ter no máximo 256 caracteres")
    low = password.lower()
    if low in _COMMON or len(set(password)) < 4:
        problems.append("Senha muito comum ou repetitiva")
    if email and email.split("@")[0].lower() in low and len(email.split("@")[0]) >= 4:
        problems.append("A senha não pode conter seu e-mail")
    return problems
