# LIMPEZA v0.30.0 — o que saiu, o que ficou e por quê

Regra (a mesma das rodadas anteriores): remover só o que não serve mais E cuja remoção é provada segura pela suíte (nenhum teste
enfraquecido — ADR-340); tudo o mais fica, com o motivo escrito. Classificação: **REMOVIDO**, **MOVIDO**, **UNIFICADO**, **MANTIDO**.

| Item | Classificação | Motivo / prova |
| --- | --- | --- |
| `evidences.status ∈ {submitted, accepted, rejected, needs_info}` (quatro estados) | **UNIFICADO** (ampliado no lugar) | a mesma coluna ganhou `contested`, `under_review`, `superseded` com máquina de estados no banco; nenhuma rota ou tela antiga quebrou (`test_api_workflow`, `test_v080`, jornadas) |
| Edição de evidência por UPDATE | **REMOVIDO** (gatilho recusa) | "corrigir" é enviar nova versão (`supersedes_id`); a anterior fica legível. Nenhum código editava evidência — a proibição não quebrou nada |
| Apagar evidência (mesmo como dono do banco) | **REMOVIDO** por consequência (FK RESTRICT do histórico) | `test_v0190_lgpd_deletion` atualizado: prova que a recusa agora vem da evidência; a conclusão ("a plataforma não remove organização") é a mesma |
| `project_indicators.method` editável sem rastro | **REMOVIDO** (gatilho exige motivo) | `indicator_method_changes` append-only; `test_v0300_dossier` |
| Modelo de 24 meses com um único percentual | **MANTIDO** + seção de sensibilidade | o catálogo (3,5 %) não mudou; a sensibilidade é hipótese declarada; `test_v0270_financial_model` continua provando documento = gerador |
| Propostas do pacote: escrow/BaaS, retenção automática, assinatura B2B/B2G, selo pago | **NÃO ENTRARAM** | conflitam com ADR-284/337/341/selos; registrados em `BASELINE_v0300.md` §0 e ADR-363 |
| `IMPACTO_v0.29.0_TRACEABILITY.json` na raiz | **MOVIDO** → `history/manifests/` (no fechamento) | mesmo tratamento das versões anteriores |
| Código morto / flags sem leitor / funções sem chamador | **nenhum encontrado** | `test_v0200_cleanup` verde; `services/dossier.py` tem chamador (rota); toda rota nova tem teste |
| `backend/.tmp_entry_storage*` | **REMOVIDO** do disco antes do pacote (não versionado) | lixo de execução de teste |
| Tipos do DefinitelyTyped usados para o typecheck local | **NÃO versionados** | ficam no scratchpad; `node_modules` continua igual ao lockfile (portão `test_every_installed_package_matches_the_locked_version`) |

O que NÃO foi feito: apagar tabelas/colunas aposentadas (migrações forward-only); mover documentos SUPERADO; os itens P2 do baseline
(conflito de interesse por serviço; versão das regras de elegibilidade no resultado do match).
