#!/usr/bin/env python3
"""Varredura de segredo no repositório. Sai 0 se nada foi encontrado, 1 se algo foi.

POR QUE EXISTE, SE O CI JÁ RODA GITLEAKS

Porque gitleaks não existe em todo ambiente, e a regra permanente deste projeto — nenhuma senha,
chave de API, token, segredo ou certificado privado em entregável — não pode depender de uma
ferramenta estar instalada. Esta varredura roda com a biblioteca padrão, é chamada por
`test_v0230_security_gate.py` em cada suíte, e cobre o caso que mais importa aqui: o segredo que
entra no ZIP de entrega.

O QUE ELA PROCURA

Três coisas diferentes, porque segredo se parece com três coisas diferentes:

1. FORMATO CONHECIDO — chave da AWS, token do GitHub, chave do Stripe, bloco PEM privado, URL com
   senha embutida. Padrão específico, falso positivo raro.
2. ATRIBUIÇÃO SUSPEITA — `password = "..."`, `api_key: "..."` com valor que não é claramente
   exemplo. É onde vive o segredo colado sem pensar.
3. ENTROPIA ALTA em posição de valor — a cadeia que não parece palavra nenhuma.

O QUE ELA IGNORA, E POR QUÊ

Credencial de desenvolvimento declarada (`owner_dev_pw`, `app_dev_pw`), exemplo em documentação com
marca de exemplo, teste que precisa de senha fictícia, e o histórico em `history/`. Cada isenção tem
motivo escrito abaixo — uma isenção sem motivo é um buraco que ninguém lembra de ter aberto.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Formatos que não têm como ser outra coisa.
FORMATOS: tuple[tuple[str, str], ...] = (
    (r"AKIA[0-9A-Z]{16}", "chave de acesso da AWS"),
    (r"ASIA[0-9A-Z]{16}", "chave temporária da AWS"),
    (r"gh[pousr]_[A-Za-z0-9]{36,}", "token do GitHub"),
    (r"github_pat_[A-Za-z0-9_]{22,}", "token do GitHub (novo formato)"),
    (r"sk_live_[A-Za-z0-9]{20,}", "chave secreta de produção do Stripe"),
    (r"rk_live_[A-Za-z0-9]{20,}", "chave restrita de produção do Stripe"),
    (r"whsec_[A-Za-z0-9]{20,}", "segredo de webhook do Stripe"),
    (r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----", "bloco de chave privada"),
    (r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "JWT assinado"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "token do Slack"),
    (r"AIza[0-9A-Za-z_-]{35}", "chave de API do Google"),
    (r"SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", "chave do SendGrid"),
    # A senha do DSN não pode COMEÇAR com `$`: `postgresql://user:$OWNER_PASSWORD@host` é
    # referência a variável de ambiente, que é a forma CERTA de não versionar segredo. A negativa
    # entra no padrão, e não na lista de exemplos, para não afrouxar os outros formatos.
    (r"postgres(?:ql)?://[^:/\s]+:(?!owner_dev_pw|app_dev_pw|app_pw|postgres@|@|\$|%24)"
     r"[^@/\s]{8,}@", "DSN com senha"),
)

#: Atribuição de valor a nome que anuncia segredo.
ATRIBUICAO = re.compile(
    r"""(?i)\b(password|passwd|senha|secret|secret_key|api_key|apikey|access_token|
         auth_token|private_key|client_secret|token)\b\s*[:=]\s*["']([^"']{8,})["']""",
    re.X)

#: Valores que anunciam a si mesmos como não-segredo. Qualquer um destes dentro do valor o isenta.
MARCAS_DE_EXEMPLO = (
    "exemplo", "example", "changeme", "troque", "xxx", "placeholder", "redacted", "dummy",
    "fake", "test", "teste", "sample", "<", ">", "...", "sua-", "seu-", "your-", "coloque",
    "dev_pw", "dev_secret", "localhost", "127.0.0.1", "nao-use", "não-use", "SUBSTITUA",
)

#: Isenções de caminho, cada uma com motivo.
ISENTOS: dict[str, str] = {
    "history/": "versões anteriores arquivadas: auditadas na rodada em que foram criadas",
    ".git/": "banco de objetos do git, não é entregável",
    "node_modules/": "dependência de terceiro, não é código do projeto",
    "web/dist/": "saída de build, gerada a partir de web/src",
    "__pycache__/": "bytecode",
    ".ruff_cache/": "cache de ferramenta",
    "docs/evidence/": "registros de execução, auditados na rodada que os produziu",
}

#: Arquivos onde senha FICTÍCIA é o objeto do trabalho, com motivo.
ISENTOS_ARQUIVO: dict[str, str] = {
    "backend/tests/support.py": "define a senha fictícia compartilhada pelos testes (PASSWORD)",
    ".env.example": "arquivo de exemplo: é a sua função declarar os nomes das variáveis",
    "scripts/secrets_scan.py": "este arquivo: os próprios padrões de busca casariam consigo",
    "ENVIRONMENT_SETUP.md": "instruções de desenvolvimento com credencial local declarada",
    "DEPLOYMENT_CHECKLIST.md": "lista de verificação: nomeia variáveis, não traz valores",
}

#: Extensões binárias ou de dados que não carregam código.
PULAR_SUFIXO = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".woff",
                ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".webm", ".so", ".pyc", ".map"}

#: Piso de entropia de Shannon para uma cadeia ser suspeita por aleatoriedade.
ENTROPIA_MINIMA = 4.3
TAMANHO_MINIMO_ENTROPIA = 24

#: Marcas de que o "valor" é REFERÊNCIA a variável de ambiente, não o segredo. `${VAR}` num
#: docker-compose e `$VAR` num workflow são o jeito CERTO de não versionar segredo — acusá-los
#: ensina a ignorar a varredura.
REFERENCIA_DE_AMBIENTE = ("${", "$(", "process.env", "os.environ", "secrets.", "vars.")

#: Marcas de que o casamento pegou CÓDIGO, não literal: concatenação, chamada de função, template.
#: `token=' + (query.get(...))` é expressão, e a captura atravessou o fim da string.
MARCAS_DE_CODIGO = ("+", "(", "`", "{{")


def entropia(s: str) -> float:
    if not s:
        return 0.0
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in
                (s.count(c) for c in set(s)))


def _e_exemplo(valor: str) -> bool:
    baixo = valor.lower()
    if any(m.lower() in baixo for m in MARCAS_DE_EXEMPLO):
        return True
    if any(m in valor for m in REFERENCIA_DE_AMBIENTE) or valor.startswith("$"):
        return True
    return _e_alfabeto(valor)


def _e_alfabeto(valor: str) -> bool:
    """A cadeia é um ALFABETO declarado (Base32, Crockford, dígitos+letras), não um segredo?

    Um alfabeto tem entropia máxima por construção — é exatamente por isso que a heurística de
    entropia o acusa. O que o distingue: todo caractere aparece UMA vez. Um segredo aleatório de 30
    caracteres sorteados de 32 símbolos repete algum com probabilidade esmagadora (aniversário), e um
    que não repita nenhum é indistinguível de uma permutação do alfabeto. Cinco achados desta
    varredura eram alfabetos de geração de código: `ABCDEFGHJKLMNPQRSTUVWXYZ234567` (Base32 sem
    caracteres ambíguos), `0123456789ABCDEFGHJKLMNPQRSTVWXYZ` (Crockford) e o alfabeto minúsculo.
    """
    if len(valor) < TAMANHO_MINIMO_ENTROPIA:
        return False
    return len(set(valor)) == len(valor)


def _e_codigo(valor: str) -> bool:
    return any(m in valor for m in MARCAS_DE_CODIGO)


def _arquivos() -> list[Path]:
    """Arquivos RASTREADOS pelo git: é o que vai para o pacote."""
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        return [p for p in ROOT.rglob("*") if p.is_file()]
    return [ROOT / n for n in out.stdout.split("\0") if n]


def main() -> int:
    achados: list[str] = []
    formatos = [(re.compile(p), nome) for p, nome in FORMATOS]
    vistos = 0
    for caminho in _arquivos():
        rel = caminho.relative_to(ROOT).as_posix()
        if any(rel.startswith(i) or f"/{i}" in f"/{rel}" for i in ISENTOS):
            continue
        if rel in ISENTOS_ARQUIVO or caminho.suffix.lower() in PULAR_SUFIXO:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        vistos += 1
        # Em código de TESTE, credencial fictícia é o objeto do trabalho: um teste de integração
        # precisa de `secret="segredo-de-webhook-32bytes!"` para provar que a assinatura é conferida.
        # É a mesma razão pela qual `pyproject.toml` já ignora S105/S106/S107 em `tests/*`. As
        # heurísticas (atribuição e entropia) ficam de fora; os FORMATOS CONHECIDOS continuam
        # valendo, porque uma chave real da AWS colada num teste é vazamento igual.
        heuristicas = not rel.startswith(("backend/tests/", "web/tests/"))
        for i, linha in enumerate(texto.splitlines(), start=1):
            if len(linha) > 2000:
                continue
            for padrao, nome in formatos:
                m = padrao.search(linha)
                if m and not _e_exemplo(m.group(0)):
                    achados.append(f"{rel}:{i}  {nome}: {m.group(0)[:40]}…")
            if heuristicas:
                m = ATRIBUICAO.search(linha)
                if m and not _e_exemplo(m.group(2)) and not _e_codigo(m.group(2)):
                    achados.append(f"{rel}:{i}  atribuição a '{m.group(1)}': {m.group(2)[:30]}…")
                for cand in re.findall(r"""["']([A-Za-z0-9+/=_-]{24,})["']""", linha):
                    if (len(cand) >= TAMANHO_MINIMO_ENTROPIA and entropia(cand) >= ENTROPIA_MINIMA
                            and not _e_exemplo(cand) and not re.fullmatch(r"[a-f0-9]{32,}", cand)):
                        achados.append(f"{rel}:{i}  entropia {entropia(cand):.2f}: {cand[:30]}…")

    print(f"varredura de segredo: {vistos} arquivos de texto rastreados, "
          f"{len(ISENTOS)} prefixos isentos, {len(ISENTOS_ARQUIVO)} arquivos isentos")
    if achados:
        print(f"\n{len(achados)} achado(s):")
        for a in sorted(set(achados)):
            print(f"  {a}")
        return 1
    print("nenhum segredo encontrado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
