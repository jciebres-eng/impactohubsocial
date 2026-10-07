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
| 028 | **Financiador PF = `organizations.kind='individual'`**, nome mascarado por padrão | privacidade do apoiador; reutiliza aportes/candidaturas | `org_display()` em toda saída; opt-in `public_name`; sem CNPJ/KYB (compliance PF a definir) | Aceita — **[VALIDAR JURÍDICO]** |
| 029 | **ODS/indicadores: catálogo próprio, metas oficiais importadas** (não embutidas) | não inventar texto oficial | `ods_targets` vazio até importação; alinhamento "declarado" × "com evidência" | Aceita |
| 030 | **Impact Graph tipado**; causalidade só validada externamente | correlação ≠ causa | CHECKs no banco; UI explica a força da afirmação | Aceita |
| 031 | **Pagamentos = registro com máquina de estados**, sem custódia; modelos de contribuição exigem aprovação jurídica | reafirma ADR-022 | triggers de transição/imutabilidade; `payment_events` append-only; cotas só após parecer | Aceita — **[VALIDAR JURÍDICO]** |
| 032 | **Risco = sinais para revisão humana**, nunca bloqueio automático | evitar acusação/injustiça algorítmica | linguagem neutra; bloqueio exige decisor humano (CHECK) | Aceita |
| 033 | **Sem mapa-base externo**: SVG próprio + precisão de localização configurável | sem dependência/CSP nova; LGPD | tiles reais exigem decisão de provedor | Aceita |
| 034 | **Tracing W3C próprio** sem exportador OpenTelemetry; erros agregados em tabela | sem coletor disponível | trocar por OTel SDK quando houver coletor | Aceita |
| 035 | **Match profissional separado** (professional-match@1.0.0) | categorias regulamentadas exigem credencial verificada | invariância ao plano testada | Aceita |
| 036 | **Biblioteca de Soluções** como módulo próprio integrado a organizações/projetos/ODS (não um "projeto" disfarçado) | ideia ≠ projeto ≠ case; ciclo de vida e confiança próprios | 20 tabelas; `kind` + `stage` + `trust_level` separados | Aceita |
| 037 | **Sem vetores/embeddings**: busca híbrida por tesauro + FTS `pt_unaccent` + trigramas | pgvector indisponível; explicabilidade; sem custo/dep. externa | sinônimos fora do tesauro não entendidos; pipeline com passo vetorial reservado | Aceita — reavaliar com dados reais |
| 038 | **Relevância explicável com pesos em arquivo** e status "HIPÓTESE" | não fingir calibração; ajuste sem recompilar | sensibilidade provada só em corpus sintético | Aceita — calibrar com uso real |
| 039 | **Nível de confiança só pela administração**, com evidência aceita; autodeclarado nunca vira "comprovado" | não inventar prova | triggers + testes; edição substantiva reabre revisão | Aceita |
| 040 | **Intenção de financiamento**: etapas avançadas só por pedido real + confirmação do autor (`SECURITY DEFINER`); identidade privada por padrão; visualização ≠ intenção | anti-manipulação e privacidade | RLS `sintent_read`; funil agregado por organizações distintas | Aceita |
| 041 | **Copiloto/"Desenvolver ideia" sem IA obrigatória**: respostas ancoradas e rascunho por regras com `[COMPLETAR]`; publicar exige revisão humana (CHECK) | IA não é fonte de fato (ADR-014) | `ai_used:false`; slot de LLM documentado, não implementado | Aceita |
| 042 | **Plano/assinatura não influencia busca, match nem recomendação** (teste AST + igualdade de score) | ADR-007/008 | monetização só em capacidade (limites/alertas), nunca em ranking | Aceita |
| 043 | **Log de busca guarda hash + intenção estruturada, nunca texto**; personalização por opt-in, apagável | LGPD/minimização | sem "buscas populares" textuais | Aceita |
| 044 | **Roteamento por especificidade** em `app.py` (literal antes de `{param}`) | evitar captura de `/solutions/search` por `/{solution_id}` | independe da ordem de import | Aceita |
| 045 | **Cinco camadas separadas** (natureza jurídica, qualificações, perfil, situação, elegibilidade calculada) | evitar "selo" único que mistura declaração e prova | elegibilidade é por oportunidade e nunca editável à mão | Aceita |
| 046 | **Declarado ≠ verificado**: só a administração verifica (autoridade, número, comprovante, vigência, justificativa) com histórico de eventos | anti-fraude, honestidade | certificação declarada não satisfaz requisito do match | Aceita |
| 047 | **Regras de elegibilidade são dados**, com conjunto fechado de tipos de requisito, fonte, data de consulta e quatro olhos | nada de regra legal fixa no código | sem regra publicada ⇒ PENDENTE; regras jurídicas ⇒ validação profissional | Aceita |
| 048 | **Ausência de informação nunca vira "elegível"**; "Não foi possível confirmar." | PROVE, não invente | cinco estados incluindo REQUER VALIDAÇÃO PROFISSIONAL | Aceita |
| 049 | **Situação institucional é decisão humana justificada**; o sistema só sugere | responsabilidade | `suggest_status` não grava | Aceita |
| 050 | **Catálogos/regras iniciais como rascunho/candidatas com validação jurídica pendente** | não inventar compliance | importar ≠ publicar | Aceita |
| 051 | **Publicação de solução exige titularidade e autorização declaradas; a plataforma não as verifica** | IP/LGPD | aviso explícito na resposta | Aceita |
| 052 | **Estimativa fiscal e elegibilidade institucional são camadas separadas na resposta** | misturar sugeriria direito a benefício | bloco `institutional_eligibility` com aviso próprio | Aceita |
| 053 | **Instrumentos (contrato de gestão/termos) nascem declarados; verificar exige número + comprovante validado ou URL oficial + nota**; org só pode editar/remover enquanto não verificado (gatilho `agreement_guard`) | declarado ≠ verificado (ADR-046) | provado também via SQL direto | Aceita |
| 054 | **Trilha de formalização: etapas automáticas derivam de dados; manuais são só declaradas** e não afirmam verificação | honestidade; trilha é hipótese | `config/formalization_path.json` com aviso | Aceita |
| 055 | **Rede da solução mostra só relações cadastradas e demanda agregada**, sem identidades; lista acessível em vez de grafo visual | privacidade/anti-manipulação | sem causalidade inferida | Aceita |
| 056 | **Termos que colidem com conceitos existentes foram retirados dos conceitos novos do tesauro** | evitar reclassificar buscas atuais | alguns termos novos resolvem para o conceito amplo | Aceita |
