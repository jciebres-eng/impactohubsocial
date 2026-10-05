# Registro de decisões (ADR)

ADR 001–015 do v0.6.0 permanecem válidos e estão preservados em `history/v0.6.0/DECISIONS.md` (001 núcleo SaaS B2B; 003 sem custódia de aportes;
007/008 nada vendável que altere ranking/match; 010 vouchers com hash; 011 fiscal como "mecanismo a validar"; 012 ledger sem blockchain; 014 IA nunca decide).
A ADR **015** (escolha de cloud, gateway, IdP, nome/marca) **continua ABERTA** — depende do proprietário.

| # | Decisão | Motivo | Consequência | Status |
|---|---|---|---|---|
| 016 | **Driver PostgreSQL próprio** via `ctypes` sobre libpq (`db/pq.py`), só `PQexecParams`, exceções tipadas | psycopg/asyncpg indisponíveis no ambiente (registros bloqueados); libpq é a biblioteca oficial | Interface `Connection` isolada: trocar por psycopg 3 sem alterar serviços; é código a manter | Aceita — reavaliar com rede |
| 017 | **Python + Starlette/uvicorn/pydantic** em vez de NestJS (ADR-005 admitia "ou equivalente") | único ecossistema completo disponível; stack madura e pinada | monólito modular; OpenAPI gerado do código | Aceita |
| 018 | `premium_osc` **ligado** por padrão (muda ADR-009) | 2ª mensagem do proprietário: buscas, rastreio e alertas pagos para OSC | plano "OSC Captação" com preço `null` até o proprietário definir; cobrança real só com gateway homologado | Aceita |
| 019 | **Reescrever a camada executável** sobre PostgreSQL (descartar SQLite/auth de demonstração do v0.6.0) | documentação ≠ código; demo não é produção | v0.6.0 preservado em `history/v0.6.0/` | Aceita |
| 020 | **Catálogo unificado `calls`** (edital, fundo, chamamento, grant; privado/federal/estadual/municipal/internacional) com origem `platform/government/curated/imported` | uma mesma busca/match/candidatura para qualquer fonte | editais externos exigem URL oficial e verificação; `last_verified_at` | Aceita |
| 021 | Assinatura profissional = **registro de conferência** (hash do conteúdo + credencial verificada), **não ICP-Brasil** | evitar alegar validade jurídica não validada | se o edital exigir assinatura qualificada, integrar provedor ICP depois | Aceita — **[VALIDAR JURÍDICO]** |
| 022 | Aportes são **registrados e conferidos** (financiador informa desembolso; OSC confirma recebimento); plataforma **não custodia nem processa** | reafirma ADR-003; evita enquadramento como instituição de pagamento/oferta de valor mobiliário | sem "cotas"/split; modelo de contribuição formal fica para quando houver parecer | Aceita |
| 023 | **Capacitor** para Android/iOS (mesmo build web) | uma base de código no piloto | recursos nativos (push, mapas) exigem plugins/trabalho futuro | Aceita — reavaliar se exigir nativo pesado |
| 024 | Segurança aplicada **no banco** (RLS + triggers + cadeias) e na API (RouteSpec) | defesa em profundidade; prova por SQL direto nos testes | papel `impacto_app` obrigatório; boot recusa papel inseguro | Aceita |
| 025 | Regras fiscais reais **não são embarcadas**; só candidatas em rascunho | não inventar legislação | até aprovação por 2 revisores, o motor não retorna regras | Aceita |
| 026 | Sem confiança suficiente → **sem nota** no match (`score = null`, limiar 50) | não fabricar precisão | UI mostra "revisão humana" e dados faltantes | Aceita |
| 027 | Segredos e modos inseguros **recusados no boot** em staging/production | falha rápida evita produção insegura | `config.validate` | Aceita |
