"""TOTP (RFC 6238, HMAC-SHA1, 6 dígitos, passo 30s) — compatível com Google Authenticator, Authy, 1Password."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.upper().replace(" ", "")
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(key: bytes, counter: int, digits: int = 6, digest=hashlib.sha1) -> str:
    mac = hmac.new(key, struct.pack(">Q", counter), digest).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    return hotp(_key(secret), int((at if at is not None else time.time()) // step), digits)


def verify(secret: str, code: str, at: float | None = None, window: int = 1, step: int = 30) -> int | None:
    """Retorna o contador aceito (para impedir reuso) ou None."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return None
    now = int((at if at is not None else time.time()) // step)
    key = _key(secret)
    for delta in range(-window, window + 1):
        if hmac.compare_digest(hotp(key, now + delta), code):
            return now + delta
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "Impacto") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def recovery_codes(n: int = 8) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)) for _ in range(n)]


def verify_once(conn, user_id: str, secret: str, code: str, *, window: int = 1) -> bool:
    """Confere o código TOTP e o QUEIMA: o mesmo código não serve duas vezes.

    O defeito que isto corrige foi encontrado por auditoria: `verify()` devolve o contador aceito e
    o docstring dela diz, desde sempre, "para impedir reuso" — e **nenhum dos quatro chamadores
    guardava esse contador**. Com janela de ±1 passo, o mesmo código de seis dígitos valia cerca de
    90 segundos e podia ser usado mais de uma vez. Quem lê o código por cima do ombro, ou o captura
    numa página falsa, o reapresenta.

    A trava é dupla de propósito: aqui o contador é comparado e gravado, e no banco o gatilho
    `totp_counter_moves_forward()` recusa qualquer regressão — então uma via de verificação futura
    que esquecesse de gravar não conseguiria, nem por engano, aceitar um código já usado.

    O `UPDATE ... WHERE mfa_last_counter IS NULL OR mfa_last_counter < $2` é o que torna a operação
    atômica: duas requisições simultâneas com o mesmo código disputam a linha, uma grava e a outra
    recebe zero linhas afetadas.
    """
    contador = verify(secret, code, window=window)
    if contador is None:
        return False
    afetadas = conn.run(
        "UPDATE users SET mfa_last_counter = $2 WHERE id = $1"
        "   AND (mfa_last_counter IS NULL OR mfa_last_counter < $2)", user_id, contador)
    return bool(afetadas)
