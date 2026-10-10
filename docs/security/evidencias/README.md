# Evidências da fase 2 (correções) — v0.35.0

Cada arquivo `loteX_antes_<commit>.txt` é a saída dos testes NOVOS daquele lote rodados no código ANTERIOR ao lote
(cópia descartável do commit indicado, via `git worktree`), para provar que o teste pega a falha. Depois da correção,
os mesmos testes passam na suíte (`backend/tests/test_v0350_security.py`, 84 testes, 32 classes).

| Lote | Rodado em | Resultado no código anterior | Observação |
|---|---|---|---|
| A | `16d837b` (v0.34.0) | 5 de 7 falham | os 2 que já passavam guardam o que tem de continuar (documentos institucionais, do projeto e compartilhados seguem disponíveis na diligência; a dona da OSC continua vendo tudo) |
| B | `2b44b58` (lote A) | as 4 classes falham já na preparação (a rota de confirmação por segunda pessoa não existia) | por isso a **sonda** `sondas/probe_loteB_old.py` (saída em `probe_loteB_saida_2b44b58.txt`) mostra as falhas com os helpers DAQUELE commit: recusa posterior não revogava o "verificado" e a doação seguia entrando; a rota antiga conciliava doação confirmada sem evento assinado; o doador transformava recurso público em privado |
| C | `82ed19e` (lote B) | 13 de 13 falham | — |
| D | `4f8bcf6` (lote C) | 10 de 10 falham | a sonda `sondas/probe_pay01_squat_old.py` (saída em `probe_pay01_saida_4f8bcf6.txt`) prova no formato antigo: evento repetido sem limite de tempo e **ocupação do `event_id`** por evento sem assinatura (doação ficava sem confirmar) |
| E | `a8ba87e` (lote D) | 5 de 6 falham | o teste de concessões globais já passava (fica como guarda) |
| F | `b587bf3` (lote E) | 6 de 7 falham | "PDF comum continua entrando" já passava (guarda contra falso positivo) |
| G | `54e06dd` (lote F) | 8 de 8 falham | — |
| H | `2e41dd9` (lote G) | 10 de 10 falham | — |
| I | `3eecfea` (lote H) | 10 de 10 falham | — |

`sondas/probe_file07.py` é a sonda da fase 1 (somente leitura) que provou o acesso do financiador aos documentos privados
da OSC (FILE-07). As sondas usam só dados sintéticos num banco descartável; nada aqui tocou a produção.
