"""Gerador de QR Code (modo byte, nível de correção M) escrito aqui.

Por que próprio: os registros npm/PyPI estão bloqueados neste ambiente, então não há como instalar `segno`/`qrcode`.
Implementa ISO/IEC 18004 para versões 1–10: codificação em byte, Reed-Solomon sobre GF(256), intercalação de blocos,
padrões de posição/alinhamento/temporização, informação de formato e de versão (BCH) e escolha de máscara por penalidade.
A saída é SVG (sem dependência de renderização) e uma matriz booleana para inspeção/teste.

LIMITE DECLARADO: validado por testes estruturais e por **decodificação de volta** dos códigos de dados (ida e volta no
nosso próprio pipeline). Não foi lido por um leitor de QR comercial — ver TRUST_TESTING.md.
"""
from __future__ import annotations

# (total de códigos, códigos de correção por bloco, [(nº de blocos, códigos de dados por bloco), ...]) — nível M
_SPEC: dict[int, tuple[int, int, tuple[tuple[int, int], ...]]] = {
    1:  (26,  10, ((1, 16),)),
    2:  (44,  16, ((1, 28),)),
    3:  (70,  26, ((1, 44),)),
    4:  (100, 18, ((2, 32),)),
    5:  (134, 24, ((2, 43),)),
    6:  (172, 16, ((4, 27),)),
    7:  (196, 18, ((4, 31),)),
    8:  (242, 22, ((2, 38), (2, 39))),
    9:  (292, 22, ((3, 36), (2, 37))),
    10: (346, 26, ((4, 43), (1, 44))),
}
_ALIGN: dict[int, tuple[int, ...]] = {
    1: (), 2: (6, 18), 3: (6, 22), 4: (6, 26), 5: (6, 30),
    6: (6, 34), 7: (6, 22, 38), 8: (6, 24, 42), 9: (6, 26, 46), 10: (6, 28, 50),
}
_EC_BITS_M = 0b00
MAX_VERSION = 10

# ---------------------------------------------------------------------------------------------- GF(256)
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n: int) -> list[int]:
    g = [1]
    for i in range(n):
        g = [0] + g[:]
        for j in range(len(g) - 1):
            g[j] ^= _mul(g[j + 1], _EXP[i])
    return g


def _rs_ecc(data: list[int], n: int) -> list[int]:
    gen = _rs_generator(n)
    rem = [0] * n
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        for i in range(n):
            rem[i] ^= _mul(gen[i + 1], factor)
    return rem


# ---------------------------------------------------------------------------------------------- BCH
def _bch(value: int, poly: int, poly_bits: int, data_bits: int) -> int:
    v = value << (poly_bits - 1)
    while v.bit_length() >= poly_bits:
        v ^= poly << (v.bit_length() - poly_bits)
    return (value << (poly_bits - 1)) | v


def _format_bits(mask: int) -> int:
    return _bch((_EC_BITS_M << 3) | mask, 0x537, 11, 5) ^ 0x5412


def _version_bits(version: int) -> int:
    return _bch(version, 0x1F25, 13, 6)


# ---------------------------------------------------------------------------------------------- codificação
def _choose_version(length: int) -> int:
    for v in range(1, MAX_VERSION + 1):
        total, ecc_per_block, groups = _SPEC[v]
        data_codewords = sum(n * k for n, k in groups)
        count_bits = 8 if v < 10 else 16
        if 4 + count_bits + length * 8 <= data_codewords * 8:
            return v
    raise ValueError(f"conteúdo longo demais para QR versão {MAX_VERSION} (nível M): {length} bytes")


def _bitstream(payload: bytes, version: int) -> list[int]:
    total, ecc_per_block, groups = _SPEC[version]
    data_codewords = sum(n * k for n, k in groups)
    count_bits = 8 if version < 10 else 16
    bits: list[int] = []
    for value, width in ((0b0100, 4), (len(payload), count_bits)):
        bits += [(value >> (width - 1 - i)) & 1 for i in range(width)]
    for byte in payload:
        bits += [(byte >> (7 - i)) & 1 for i in range(8)]
    capacity = data_codewords * 8
    bits += [0] * min(4, capacity - len(bits))                 # terminador
    bits += [0] * (-len(bits) % 8)                             # alinha em byte
    words = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    pads = (0xEC, 0x11)
    while len(words) < data_codewords:
        words.append(pads[(len(words) - len(bits) // 8) % 2])
    return words


def _codewords(payload: bytes, version: int) -> list[int]:
    """Códigos finais, já com correção de erro e intercalados."""
    total, ecc_per_block, groups = _SPEC[version]
    words = _bitstream(payload, version)
    blocks: list[list[int]] = []
    pos = 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[pos:pos + size])
            pos += size
    eccs = [_rs_ecc(b, ecc_per_block) for b in blocks]
    out: list[int] = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ecc_per_block):
        for e in eccs:
            out.append(e[i])
    return out


# ---------------------------------------------------------------------------------------------- matriz
def _reserved(version: int) -> list[list[bool]]:
    size = 17 + 4 * version
    res = [[False] * size for _ in range(size)]

    def block(r0: int, c0: int, h: int, w: int) -> None:
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                if 0 <= r < size and 0 <= c < size:
                    res[r][c] = True

    for r0, c0 in ((0, 0), (0, size - 8), (size - 8, 0)):
        block(r0, c0, 9 if r0 == 0 else 8, 9 if c0 == 0 else 8)
    for i in range(size):
        res[6][i] = True
        res[i][6] = True
    centers = _ALIGN[version]
    for r in centers:
        for c in centers:
            if (r, c) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            block(r - 2, c - 2, 5, 5)
    if version >= 7:
        block(size - 11, 0, 3, 6)
        block(0, size - 11, 6, 3)
    return res


def _skeleton(version: int) -> list[list[int]]:
    """-1 = livre para dados; 0/1 = módulo fixo."""
    size = 17 + 4 * version
    m = [[-1] * size for _ in range(size)]

    def finder(r0: int, c0: int) -> None:
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if not (0 <= rr < size and 0 <= cc < size):
                    continue
                if r in (-1, 7) or c in (-1, 7):
                    m[rr][cc] = 0
                else:
                    ring = max(abs(r - 3), abs(c - 3))
                    m[rr][cc] = 1 if ring != 2 else 0

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)
    for i in range(size):
        if m[6][i] == -1:
            m[6][i] = 1 - (i % 2)
        if m[i][6] == -1:
            m[i][6] = 1 - (i % 2)
    centers = _ALIGN[version]
    for r in centers:
        for c in centers:
            if (r, c) in ((6, 6), (6, size - 7), (size - 7, 6)):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    m[r + dr][c + dc] = 1 if max(abs(dr), abs(dc)) != 1 else 0
    m[size - 8][8] = 1                                          # módulo escuro
    if version >= 7:
        bits = _version_bits(version)
        for i in range(18):
            bit = (bits >> i) & 1
            m[size - 11 + i % 3][i // 3] = bit
            m[i // 3][size - 11 + i % 3] = bit
    return m


_FORMAT_POS_A = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
                 (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]


def _place_format(m: list[list[int]], mask: int) -> None:
    size = len(m)
    bits = _format_bits(mask)
    for i, (r, c) in enumerate(_FORMAT_POS_A):            # i = 0 é o bit mais significativo (bit 14)
        m[r][c] = (bits >> (14 - i)) & 1
    for i in range(15):
        bit = (bits >> i) & 1
        if i < 8:
            m[size - 1 - i][8] = bit
        else:
            m[8][size - 15 + i] = bit


def _mask_fn(mask: int, r: int, c: int) -> bool:
    if mask == 0:
        return (r + c) % 2 == 0
    if mask == 1:
        return r % 2 == 0
    if mask == 2:
        return c % 3 == 0
    if mask == 3:
        return (r + c) % 3 == 0
    if mask == 4:
        return (r // 2 + c // 3) % 2 == 0
    if mask == 5:
        return (r * c) % 2 + (r * c) % 3 == 0
    if mask == 6:
        return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    return ((r + c) % 2 + (r * c) % 3) % 2 == 0


def _data_positions(version: int) -> list[tuple[int, int]]:
    size = 17 + 4 * version
    res = _reserved(version)
    out: list[tuple[int, int]] = []
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not res[r][c]:
                    out.append((r, c))
        col -= 2
        upward = not upward
    return out


def _penalty(m: list[list[int]]) -> int:
    size = len(m)
    score = 0
    for line in list(m) + [list(col) for col in zip(*m, strict=True)]:
        run, prev = 1, line[0]
        for v in line[1:]:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, v
        if run >= 5:
            score += 3 + (run - 5)
        text = "".join(str(v) for v in line)
        score += 40 * (text.count("1011101000") + text.count("0001011101"))
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(sum(row) for row in m)
    score += 10 * (abs(dark * 100 // (size * size) - 50) // 5)
    return score


def matrix(text: str) -> list[list[int]]:
    """Matriz final de módulos (1 = escuro), máscara já escolhida pela menor penalidade."""
    payload = text.encode("utf-8")
    version = _choose_version(len(payload))
    words = _codewords(payload, version)
    bits = [(w >> (7 - i)) & 1 for w in words for i in range(8)]
    positions = _data_positions(version)
    best: tuple[int, list[list[int]]] | None = None
    for mask in range(8):
        m = _skeleton(version)
        for (r, c), bit in zip(positions, bits, strict=False):
            m[r][c] = bit ^ (1 if _mask_fn(mask, r, c) else 0)
        for r, c in positions[len(bits):]:
            m[r][c] = 0 ^ (1 if _mask_fn(mask, r, c) else 0)
        _place_format(m, mask)
        p = _penalty(m)
        if best is None or p < best[0]:
            best = (p, m)
    assert best is not None
    return best[1]


def svg(text: str, *, module: int = 4, quiet: int = 4, dark: str = "#101828", light: str = "#ffffff") -> str:
    """QR em SVG. `module` é o lado de cada módulo em px; `quiet` é a margem obrigatória em módulos."""
    m = matrix(text)
    size = len(m)
    side = (size + quiet * 2) * module
    rects = []
    for r in range(size):
        c = 0
        while c < size:
            if m[r][c]:
                start = c
                while c < size and m[r][c]:
                    c += 1
                rects.append(f'<rect x="{(start + quiet) * module}" y="{(r + quiet) * module}"'
                             f' width="{(c - start) * module}" height="{module}"/>')
            else:
                c += 1
    body = "".join(rects)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{side}" viewBox="0 0 {side} {side}"'
            f' shape-rendering="crispEdges" role="img" aria-label="QR Code de verificação">'
            f'<rect width="{side}" height="{side}" fill="{light}"/><g fill="{dark}">{body}</g></svg>')
