#!/usr/bin/env python3
"""Gera a matriz de validação dos 42 motores a partir do REGISTRO, cruzada com a suíte de testes.

POR QUE DO REGISTRO

`engines/registry.py` já declara cada motor com módulo, função, natureza, versão, rotas, o que
produz e **o que ele nunca decide**. E já existe teste conferindo linha por linha contra o código:
a função existe, a versão bate com a constante do módulo, as rotas existem, e um motor declarado
determinístico não importa o gateway de IA.

O que esta matriz acrescenta é a ponte entre o registro e a EXECUÇÃO: para cada motor, quais
arquivos de teste o exercitam, se há caso de ausência de dado, se há caso adversarial, e se a saída
exige revisão humana.

COMO A COLUNA DE TESTE É PREENCHIDA

Por varredura: um arquivo de teste "exercita" o motor se cita o módulo dele, a função de entrada
ou uma das rotas declaradas. É uma aproximação, e é declarada como tal — mas é uma aproximação
VERIFICÁVEL, e um motor com zero arquivos é um motor sem teste, que é o que a matriz precisa achar.
"""

#: Destino. Aceita um caminho como argumento para que um teste possa gerar num diretório temporário e
#: comparar com o que está versionado, provando que a matriz não derivou do código — sem reescrever
#: arquivo do repositório durante a suíte.
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from impacto import api  # noqa: E402
from impacto.engines.registry import ENGINES  # noqa: E402
from impacto.http import ROUTES  # noqa: E402

TESTES = sorted((ROOT / "backend" / "tests").glob("test_*.py"))


def _alvos(e) -> list[str]:
    """Marcas que indicam que um arquivo de teste exercita este motor.

    A primeira versão procurava o caminho da rota LITERAL, com o parâmetro entre chaves — e nenhum
    teste escreve `/v1/projects/{project_id}/data-quality`, porque o teste substitui o parâmetro por
    um identificador de verdade. O resultado foi dois motores marcados como "sem teste" que tinham
    teste: `data_quality` e `solution_scoring`.

    Era defeito do INSTRUMENTO DE MEDIÇÃO, não do produto — e se a matriz tivesse sido publicada
    assim, duas lacunas falsas entrariam no relatório final. Por isso a rota agora entra pelo
    trecho literal depois do último parâmetro (`/data-quality`), que é o que o teste escreve.
    """
    ultimo = e.module.rsplit(".", 1)[-1]
    alvos = [e.module, f"{ultimo}.{e.entrypoint}", f"from {e.module}", f"import {ultimo}"]
    for rota in e.routes:
        if "{" not in rota:
            alvos.append(rota)
            continue
        sufixo = rota[rota.rfind("}") + 1:]
        if len(sufixo) > 4:          # `/x` casaria qualquer coisa
            alvos.append(sufixo)
        prefixo = rota[:rota.find("{")].rstrip("/")
        if prefixo.count("/") >= 3:  # `/v1/projects` é genérico demais
            alvos.append(prefixo)
    return alvos


def _quem_importa(modulo: str) -> list[str]:
    """Módulos de `impacto/` que importam este motor.

    Um motor sem rota própria (`solution_scoring` é o caso) só é alcançado ATRAVÉS de quem o chama.
    Procurar o nome dele nos testes devolve zero, e marcá-lo como "sem teste" por isso seria o
    instrumento de medição mentindo sobre o produto: `scoring.relevance()` é chamado por
    `services/solutions.py::search()`, que é chamado por `/v1/solutions/search`, que tem teste.

    Seguir um nível de importação é o mesmo recurso que `core/risk_levels.py` usa para achar o
    controle humano de uma rota, e para no primeiro nível pelo mesmo motivo: alcance a três saltos
    não é alcance que alguém consegue conferir.
    """
    ultimo = modulo.rsplit(".", 1)[-1]
    pacote = ROOT / "backend" / "impacto"
    chamadores = []
    for f in pacote.rglob("*.py"):
        texto = f.read_text(encoding="utf-8")
        if f"from {modulo} import" in texto or f"import {modulo}" in texto \
                or re.search(rf"from \.+\w*[\w.]* import .*\b{ultimo}\b", texto):
            rel = str(f.relative_to(pacote)).replace("/", ".")[:-3]
            chamadores.append(f"impacto.{rel}")
    return chamadores


def _rotas_de(modulo: str) -> list[str]:
    """Rotas servidas pelo módulo dado (pelo arquivo em que o handler foi definido)."""
    saida = []
    for r in ROUTES:
        mod = getattr(r.handler, "__module__", "")
        if mod == modulo:
            saida.append(r.path)
    return saida


def _arquivos_que_exercitam(e) -> tuple[list[str], str]:
    """Devolve (arquivos, como). `como` distingue alcance direto de alcance por quem chama."""
    alvos = _alvos(e)
    achados = [f.name for f in TESTES
               if any(a in f.read_text(encoding="utf-8") for a in alvos)]
    if achados:
        return achados, "direto"
    # Sem alcance direto: segue um nível de importação e tenta pelas rotas de quem chama.
    for chamador in _quem_importa(e.module):
        for rota in _rotas_de(chamador):
            alvo = rota[rota.rfind("}") + 1:] if "{" in rota else rota
            if len(alvo) < 5:
                alvo = rota[:rota.find("{")].rstrip("/") if "{" in rota else rota
            achados += [f.name for f in TESTES if alvo in f.read_text(encoding="utf-8")]
    achados = sorted(set(achados))
    return achados, ("por_quem_chama" if achados else "nenhum")


def _tem_caso(arquivos: list[str], padroes: tuple[str, ...]) -> bool:
    for nome in arquivos:
        texto = (ROOT / "backend" / "tests" / nome).read_text(encoding="utf-8")
        if any(re.search(p, texto, re.I) for p in padroes):
            return True
    return False


def main() -> int:
    api.load_all()
    caminhos = {r.path for r in ROUTES}
    destino = (Path(sys.argv[1]) if len(sys.argv) > 1
               else ROOT / "docs" / "execution" / "ENGINE_VALIDATION_MATRIX.csv")
    destino.parent.mkdir(parents=True, exist_ok=True)

    campos = ["engine_key", "engine_name", "type", "group", "version", "routes", "routes_exist",
              "min_input", "expected_output", "never_decides", "missing_data_behavior",
              "human_review", "fallback", "security_test", "regression_test", "test_files",
              "reached_via", "evidence", "status"]
    linhas = []
    for e in sorted(ENGINES, key=lambda x: (x.group, x.key)):
        arquivos, alcance = _arquivos_que_exercitam(e)
        rotas_ok = all(r in caminhos for r in e.routes) if e.routes else True
        ausencia = _tem_caso(arquivos, (r"vaz[ia]", r"sem dado", r"ausente", r"unavailable",
                                        r"not_declared", r"missing", r"nenhum"))
        adversarial = _tem_caso(arquivos, (r"cross.?tenant", r"outra organiza", r"forj",
                                           r"assertRaises", r"403", r"404", r"IDOR", r"escalada"))
        regressao = bool(arquivos)
        linhas.append({
            "engine_key": e.key, "engine_name": e.name, "type": e.kind, "group": e.group,
            "version": e.version, "routes": " ".join(e.routes),
            "routes_exist": "yes" if rotas_ok else "NO",
            "min_input": "organização ativa + dado do domínio do motor",
            "expected_output": e.produces[:160],
            "never_decides": e.never[:160],
            "missing_data_behavior": "coberto" if ausencia else "nao_coberto",
            # Revisão humana: obrigatória em todo motor assistido por modelo (política de faixa);
            # nos determinísticos a saída é cálculo auditável e não exige revisão por desenho.
            "human_review": "obrigatoria" if e.kind == "llm_assisted" else "nao_aplicavel",
            "fallback": "motor local" if e.kind == "llm_assisted" else "nao_aplicavel",
            "security_test": "coberto" if adversarial else "nao_coberto",
            "regression_test": "na_suite" if regressao else "AUSENTE",
            "test_files": " ".join(arquivos[:6]) + (" …" if len(arquivos) > 6 else ""),
            "reached_via": alcance,
            "evidence": "docs/execution/TEST_EVIDENCE.md",
            "status": "PASS" if (arquivos and rotas_ok) else "FAILED",
        })

    with destino.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)

    print(f"{destino.name}: {len(linhas)} motores")
    print(f"  {'determinísticos':28s} {sum(1 for x in linhas if x['type'] == 'deterministic'):3d}")
    print(f"  {'recuperação ancorada':28s} {sum(1 for x in linhas if x['type'] == 'grounded_retrieval'):3d}")
    print(f"  {'assistidos por modelo':28s} {sum(1 for x in linhas if x['type'] == 'llm_assisted'):3d}")
    print(f"  {'com arquivo de teste':28s} {sum(1 for x in linhas if x['regression_test'] == 'na_suite'):3d}")
    print(f"  {'com caso de ausência':28s} {sum(1 for x in linhas if x['missing_data_behavior'] == 'coberto'):3d}")
    print(f"  {'com caso adversarial':28s} {sum(1 for x in linhas if x['security_test'] == 'coberto'):3d}")
    print(f"  {'rotas conferidas':28s} {sum(1 for x in linhas if x['routes_exist'] == 'yes'):3d}")
    print(f"  {'alcance direto':28s} {sum(1 for x in linhas if x['reached_via'] == 'direto'):3d}")
    print(f"  {'alcance por quem chama':28s} {sum(1 for x in linhas if x['reached_via'] == 'por_quem_chama'):3d}")
    falhos = [x["engine_key"] for x in linhas if x["status"] != "PASS"]
    print(f"  {'FALHOS':28s} {len(falhos):3d} {falhos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
