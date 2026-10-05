"""Criptografia de campos sensíveis (segredos MFA) com Fernet (AES-128-CBC + HMAC-SHA256, lib `cryptography`).

FIELD_ENCRYPTION_KEY: chave Fernet (urlsafe base64 de 32 bytes). Em development, deriva-se uma chave do SECRET_KEY
para conveniência — em staging/production a chave dedicada é obrigatória (config.validate).
Rotação: aceite múltiplas chaves separadas por vírgula (a primeira cifra; todas decifram).
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class FieldCipher:
    def __init__(self, keys: str, fallback_secret: str = ""):
        ks = [k.strip() for k in (keys or "").split(",") if k.strip()]
        if not ks:
            if not fallback_secret:
                raise ValueError("FIELD_ENCRYPTION_KEY ausente")
            ks = [base64.urlsafe_b64encode(hashlib.sha256(("field:" + fallback_secret).encode()).digest()).decode()]
        self._f = MultiFernet([Fernet(k.encode()) for k in ks])

    def encrypt(self, plaintext: str) -> str:
        return self._f.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._f.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Falha ao decifrar campo protegido") from exc


def generate_key() -> str:
    return Fernet.generate_key().decode()
