"""Validadores de domínio brasileiros e utilitários de entrada."""
from __future__ import annotations

import re
import unicodedata

_CNPJ_W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_CNPJ_W2 = [6] + _CNPJ_W1


def only_digits(v: str | None) -> str:
    return re.sub(r"\D", "", v or "")


def cnpj_valid(v: str | None) -> bool:
    d = only_digits(v)
    if len(d) != 14 or d == d[0] * 14:
        return False
    nums = [int(x) for x in d]
    s1 = sum(a * b for a, b in zip(nums[:12], _CNPJ_W1)) % 11
    dv1 = 0 if s1 < 2 else 11 - s1
    s2 = sum(a * b for a, b in zip(nums[:13], _CNPJ_W2)) % 11
    dv2 = 0 if s2 < 2 else 11 - s2
    return nums[12] == dv1 and nums[13] == dv2


def cnpj_format(v: str) -> str:
    d = only_digits(v)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else v


def cnpj_with_check_digits(base12: str) -> str:
    nums = [int(x) for x in base12]
    s1 = sum(a * b for a, b in zip(nums, _CNPJ_W1)) % 11
    nums.append(0 if s1 < 2 else 11 - s1)
    s2 = sum(a * b for a, b in zip(nums, _CNPJ_W2)) % 11
    nums.append(0 if s2 < 2 else 11 - s2)
    return "".join(map(str, nums))


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]")


def safe_filename(name: str) -> str:
    name = unicodedata.normalize("NFKD", name or "arquivo").encode("ascii", "ignore").decode()
    name = name.replace("\\", "/").split("/")[-1]
    name = SAFE_FILENAME.sub("_", name).strip(" .") or "arquivo"
    return name[:120]
