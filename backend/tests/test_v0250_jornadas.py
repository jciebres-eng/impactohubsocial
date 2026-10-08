"""v0.25.0 — as jornadas da demonstração, de ponta a ponta, pela API real e com as contas de demonstração.

Cada passo chama a mesma operação que a tela chama. O teste falha listando cada passo que não deu o
resultado esperado — e grava o relatório em `docs/evidence/jornadas_v0250/relatorio.json`.
Ver `tests/demo_journeys.py`: o roteiro é 100% HTTP, sem nenhuma escrita direta no banco.
"""
from __future__ import annotations

import json
import os
import unittest
from collections import Counter

from tests.support import PASSWORD, ROOT, server

EVID = ROOT / "docs" / "evidence" / "jornadas_v0250"


class TheDemoJourneysCloseEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        os.environ["DEMO_PASSWORD"] = PASSWORD
        from impacto import seed_dev
        r = seed_dev.seed(cls.state)
        assert r["status"] in ("seeded", "already_seeded"), r
        from tests import demo_journeys
        cls.res = demo_journeys.run(cls.base, cls.state)
        EVID.mkdir(parents=True, exist_ok=True)
        por_jornada = Counter(p["jornada"] for p in cls.res["passos"])
        (EVID / "relatorio.json").write_text(json.dumps({
            "passos": len(cls.res["passos"]), "falhas": len(cls.res["falhas"]),
            "por_jornada": dict(por_jornada), "atalhos_declarados": cls.res["atalhos"],
            "detalhe": [{k: p[k] for k in ("jornada", "passo", "metodo", "rota", "status", "ok", "erro")}
                        for p in cls.res["passos"]],
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def test_every_step_of_every_journey_succeeds(self):
        self.assertEqual(self.res["falhas"], [], "\n" + "\n".join(
            f"[{p['jornada']}] {p['passo']}: {p['metodo']} {p['rota']} → {p['status']} {p['erro']}"
            for p in self.res["falhas"]))

    def test_the_journeys_are_long_enough_to_be_journeys(self):
        """Um passo não é uma jornada. Cada jornada tem de atravessar várias operações."""
        por = Counter(p["jornada"] for p in self.res["passos"])
        self.assertGreaterEqual(len(por), 12, por)
        curtas = {j: n for j, n in por.items() if n < 4}
        self.assertEqual(curtas, {}, "jornada com menos de 4 passos")

    def test_nothing_was_written_straight_into_the_database(self):
        """Nenhum atalho: até o plano das contas de demonstração vem da administração, pela API."""
        self.assertEqual(self.res["atalhos"], [])
        import inspect
        from tests import demo_journeys
        fonte = inspect.getsource(demo_journeys.Jornadas)
        for proibido in ("db_system", "owner_conn", "INSERT INTO", "UPDATE "):
            self.assertNotIn(proibido, fonte, f"o roteiro das jornadas usa {proibido}")
