#!/usr/bin/env python3
"""Cifra AUTENTICADA do backup do banco (v0.35.0, auditoria BCP-01).

Antes: `openssl enc -aes-256-cbc -pbkdf2` — confidencial, mas SEM autenticação: um arquivo alterado no bucket
decifrava em lixo (ou, pior, em um dump plausível) sem erro. O SHA-256 ficava no MESMO bucket, então quem
alterasse o backup alterava o hash junto.

Agora (formato `IMPACTO-BACKUP-AEAD-1`, extensão `.dump.aead`):
  * chave derivada da MESMA frase de sempre (`BACKUP_PASSPHRASE`) com scrypt (n=2^17, r=8, p=1) e sal aleatório;
  * AES-256-GCM em blocos de 4 MiB (o dump não precisa caber na memória); o nonce de cada bloco é
    prefixo aleatório + contador + marca de "último bloco" (desenho STREAM) e o cabeçalho inteiro entra como
    dado autenticado de cada bloco. Resultado: qualquer bit alterado, bloco trocado de ordem, bloco removido
    do fim (truncamento) ou cabeçalho mexido faz a decifração FALHAR — nunca devolver dado errado;
  * o SHA-256 do arquivo cifrado vai também para o resumo da execução no GitHub (fora do bucket).

Uso (a frase vem SEMPRE do ambiente, nunca da linha de comando):
    BACKUP_PASSPHRASE=... python3 scripts/backup_crypt.py encrypt impacto.dump impacto.dump.aead
    BACKUP_PASSPHRASE=... python3 scripts/backup_crypt.py decrypt impacto.dump.aead impacto.dump

Arquivos antigos (`.dump.enc`, openssl) continuam sendo decifrados pelo comando openssl documentado no
workflow `backup-supabase` enquanto existirem (retenção de 30 dias).
"""
from __future__ import annotations

import os
import struct
import sys

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"IMPACTO-BACKUP-AEAD-1\n"
CHUNK = 4 * 1024 * 1024
TAG = 16
LOG2N, R, P = 17, 8, 1
MIN_PASSPHRASE = 32


class BackupCryptError(Exception):
    pass


def _key(passphrase: str, salt: bytes, log2n: int, r: int, p: int) -> bytes:
    if len(passphrase) < MIN_PASSPHRASE:
        raise BackupCryptError(f"BACKUP_PASSPHRASE precisa de pelo menos {MIN_PASSPHRASE} caracteres")
    return Scrypt(salt=salt, length=32, n=2 ** log2n, r=r, p=p).derive(passphrase.encode("utf-8"))


def _nonce(prefix: bytes, counter: int, last: bool) -> bytes:
    if counter >= 2 ** 32:
        raise BackupCryptError("arquivo grande demais para um único cabeçalho")
    return prefix + struct.pack(">I", counter) + (b"\x01" if last else b"\x00")


def encrypt(src, dst, passphrase: str) -> None:
    salt, prefix = os.urandom(16), os.urandom(7)
    header = MAGIC + salt + bytes([LOG2N, R, P]) + prefix
    aes = AESGCM(_key(passphrase, salt, LOG2N, R, P))
    dst.write(header)
    counter = 0
    current = src.read(CHUNK)
    while True:
        nxt = src.read(CHUNK)
        last = not nxt
        ct = aes.encrypt(_nonce(prefix, counter, last), current, header)
        dst.write(struct.pack(">I", len(ct)) + ct)
        if last:
            return
        counter, current = counter + 1, nxt


def decrypt(src, dst, passphrase: str) -> None:
    head = src.read(len(MAGIC) + 16 + 3 + 7)
    if not head.startswith(MAGIC) or len(head) != len(MAGIC) + 26:
        raise BackupCryptError("não é um backup no formato IMPACTO-BACKUP-AEAD-1")
    salt = head[len(MAGIC):len(MAGIC) + 16]
    log2n, r, p = head[len(MAGIC) + 16:len(MAGIC) + 19]
    prefix = head[len(MAGIC) + 19:]
    if not (14 <= log2n <= 22 and 1 <= r <= 32 and 1 <= p <= 16):
        raise BackupCryptError("parâmetros de derivação fora do esperado")
    aes = AESGCM(_key(passphrase, salt, log2n, r, p))

    def _read_block():
        raw = src.read(4)
        if not raw:
            return None
        if len(raw) != 4:
            raise BackupCryptError("arquivo truncado no meio de um bloco")
        size = struct.unpack(">I", raw)[0]
        if size < TAG or size > CHUNK + TAG:
            raise BackupCryptError("tamanho de bloco inválido")
        data = src.read(size)
        if len(data) != size:
            raise BackupCryptError("arquivo truncado no meio de um bloco")
        return data

    counter = 0
    block = _read_block()
    if block is None:
        raise BackupCryptError("arquivo sem nenhum bloco")
    while block is not None:
        nxt = _read_block()
        try:
            plain = aes.decrypt(_nonce(prefix, counter, nxt is None), block, head)
        except InvalidTag as exc:
            raise BackupCryptError("autenticação falhou: frase errada, arquivo alterado ou truncado") from exc
        dst.write(plain)
        counter, block = counter + 1, nxt


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in ("encrypt", "decrypt"):
        print(__doc__, file=sys.stderr)
        return 2
    passphrase = os.environ.get("BACKUP_PASSPHRASE", "")
    tmp = argv[3] + ".parcial"
    try:
        with open(argv[2], "rb") as src, open(tmp, "wb") as dst:
            (encrypt if argv[1] == "encrypt" else decrypt)(src, dst, passphrase)
        os.replace(tmp, argv[3])
    except BackupCryptError as exc:
        if os.path.exists(tmp):
            os.remove(tmp)   # nada parcial fica para trás: decifração que falhou não deixa dump pela metade
        print(f"backup_crypt: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
