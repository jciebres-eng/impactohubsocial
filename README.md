# Plataforma Impacto — v0.28.0

**Infraestrutura digital de conexão, estruturação, financiamento, execução, acompanhamento e comprovação de
impacto** para OSCs, empresas e fundações, profissionais e órgãos públicos. Um núcleo, várias experiências: cada
papel entra no mesmo ciclo de impacto — do contexto à evidência — sem produto separado, sem domínio duplicado e sem
permissão frouxa.

> **Estado:** **BASE TÉCNICA FECHADA** desde a v0.22.0 para a entrega ao Designer; a v0.23.0
> acrescentou rastreabilidade, integridade, governança de IA e o interruptor de emergência. Leia
> `TECHNICAL_FINALIZATION_STATUS.md` para o estado fase por fase, `NON_CUSTODIAL_ARCHITECTURE.md` para a regra de
> arquitetura que está acima das outras, e `RELEASE_READINESS.md` §5 para o que esta versão **NÃO** entrega.
> **Não publicado** em nenhuma loja ou domínio. Android/iOS: código pronto, **não construídos**. **Nenhuma
> cobrança real é possível:** nenhum provedor de pagamento, fiscal, de WhatsApp, de mapas ou de IA está ligado.

**Novo no v0.27.0 (não existem mais assinaturas — ADR-341):** o IMPACTO deixa de ser um SaaS por
mensalidade. Não há plano pago, trial, checkout, reajuste nem paywall: planos viraram **pacotes de
capacidades** concedidos por concessão, convênio, voucher ou contrato avulso/parcelado. A receita da
plataforma nasce da **camada econômica da operação financiada**: 5% do valor financiado = **3,5% taxa de
serviço** da plataforma + **1,5% participação de autoria** do proponente, só quando contratualmente
elegível, nunca automática. Os percentuais vêm do catálogo `economic_rules` (Pricing Version 2027.02) e
são congelados no acordo — nunca em código. O financiador faz **um aporte só, direcionado**: a matriz de
distribuição diz quem recebe, quanto e para qual **chave PIX informada no contrato**; a transferência é
registrada por quem paga e confirmada por quem recebe; a plataforma não custodia (ADR-284). Selos e
reconhecimentos nascem da **operação quitada** (entregas aceitas + repasses confirmados), nunca de pagar a
plataforma. Torre **MASTER** (`/controladoria/torre`): GMV × camada registrada/devida/paga, captura de
valor, "DADO FINANCEIRO NÃO CONECTADO" onde não há banco. Cartões do dia, trajetória pública cumulativa,
simulação de 24 meses derivada de hipóteses declaradas (`24_MONTH_FINANCIAL_MODEL.md`). Receita real desta
instalação: R$ 0,00 — a regra comercial continua desligada até parecer externo.

**v0.26.0 (a tese econômica virou produto):** o **contrato é regra de operação** — o acordo
assinado traz as cláusulas (taxa, quem paga, modo, prazo de aceite em dias úteis, contestação), ganha
versão imutável, deriva obrigações (entregar, aceitar, pagar) com prazo, exige aceite a quatro olhos e,
ao mudar, vira versão nova que invalida a aprovação anterior. A **matriz de distribuição** é calculada
na origem (R$ 100.000 com 3% → R$ 100.000 ao projeto + R$ 3.000 de taxa, ou 97.000/3.000 no modo
descontado), gravada com hash, e a taxa é **cobrança própria da plataforma ao financiador** — nunca
descontada de dinheiro em trânsito, nunca custodiada (ADR-284), e **só cobrável com a regra
`contract.platform_service_fee` ativa**, que nasce desligada com carta legal amarela. Duas **torres de
controle**: do financiador (`/torre`: meu capital → onde está → para quem → para quê → executado →
evidência → mudou → atrasos → riscos → o que preciso decidir) e do governo (`/torre-territorial`:
território → programas → editais → OSCs → projetos → recursos → indicadores declarados × validados →
atrasos → territórios descobertos, com k-anonimato). E o estado verificável **"Projeto IMPACTO
Ready"** na ficha do projeto: 15 critérios, cada um com a tabela e a contagem que o sustenta,
desconhecido ≠ zero, mesmo resultado para dono e financiador. 225 telas, 923 operações, 50 motores.
Relatório em `FINAL_EXECUTION_REPORT.md`; auditoria em `FINAL_EXECUTION_AUDIT.md`.

**Novo no v0.25.0 (validação operacional de baixo para cima):** as 218 telas do roteador abertas no
Chromium com os 6 perfis de demonstração e registros reais (`docs/execution/ROUTE_RUNTIME_MATRIX.csv`),
13 jornadas pela API real sem nenhuma escrita direta no banco, telas de menu em largura de telefone, e
uma **pilha do zero** com Docker (`infra/compose/demo/`) — banco vazio com o desenho do Supabase,
migrações, seed, aplicação como `impacto_app` — que o CI sobe a cada push e contra a qual roda as
jornadas, as 218 telas, o axe-core (WCAG A/AA, agora trava) e um reinício conferindo persistência.
Essas provas acharam e levaram à correção de um 500, uma tela que quebrava, a confirmação de
identidade que não existia na interface, chamadas recusadas escondidas e um inventário de telas que
contava errado. Ainda não há endereço público: depende de conta de hospedagem (D-PUB1). Matriz por
perfil em `docs/execution/COVERAGE_MATRIX.md`; relatório em `RELEASE_REPORT_v0.25.0.md`.

**Novo no v0.24.2 (Supabase aplicado):** o fluxo `supabase` do GitHub rodou contra o banco real
(PostgreSQL 17.11): migração pendente aplicada, `impacto_app` rotacionado, e a imagem Docker subiu
contra o banco em `staging` com `readyz` 200 (run 37727468920). Nenhuma instância pública do IMPACTO
está no ar — a imagem roda numa máquina descartável e é removida. A instância do terceiro, que usava
a senha antiga, parou de conectar. Detalhe em `docs/PUBLICACAO.md` §1-B.

**Novo no v0.24.1 (o CI passou a existir de verdade; Supabase pronto para verificar):** até aqui a suíte
NUNCA tinha rodado no GitHub — a action do gitleaks exigia licença e derrubava o primeiro passo de todo
push. Corrigido, a primeira execução real expôs 105 erros que este ambiente escondia (testes trocando a
senha de papéis da instância; aqui a autenticação local aceitava qualquer senha) e uma corrida no
auxiliar de TOTP; os dois foram corrigidos e reproduzidos aqui com autenticação por senha. A imagem
Docker constrói no CI, e `npm ci` + typecheck oficial passaram (D-SUP1 fechado). A primeira
auditoria de dependências que de fato rodou achou vulnerabilidades reais — **PyJWT 2.14.0 (2) e
pypdf 5.9.0 (49), este lendo PDF enviado por usuário** — e as duas foram atualizadas (2.15.0 e 6.19.0);
CI inteiro verde na execução `37720482955`. Para o Supabase:
`.github/workflows/supabase.yml` (manual; `verificar` é somente leitura, `aplicar` exige confirmação), a
troca de usuário que entende o pooler (`impacto_app.<ref>`), e o layout do Supabase (pgcrypto em
`extensions`) reproduzido em teste, com contraprova. Leia `docs/PUBLICACAO.md` §1-A e §1-B.

**Novo no v0.24.0 (identidade oficial, demonstração provada, banco gerenciado):** a interface veste
a identidade oficial (`web/brand/`, fonte única `tokens.json`; os nomes antigos do CSS viraram aliases
dos tokens, então toda regra de componente mudou de uma vez nos três temas); o lockup transparente
oficial, 48 ícones de traço, favicons, PWA e recursos Android/iOS entraram pelo pacote recebido, com os
limites que ele mesmo declara (licença não comprovada, logo em raster, fontes não embarcadas). A
**demonstração completa é provada por teste** no Chromium: 14 contas, 295 telas de menu, zero 5xx, com
as 10 contas internas passando pela verificação em duas etapas de verdade — o seed cadastra o TOTP
delas, porque administração exige MFA e isso não foi relaxado. O entrypoint do contêiner roda contra
PostgreSQL gerenciado (migrações como administrador, aplicação como `impacto_app`), e foi executado de
verdade contra um banco limpo. E uma correção de registro: o "defeito" anunciado na v0.23.1
(`/entrar` chamando rota inexistente) **não existia** — a rota é crua em `app.py` e o cruzamento não
a lia. Leia `CHANGELOG.md`, `docs/DEMO.md` e `docs/execution/TRIAGEM_PACOTE_UI_DEMO.md`.

**Novo no v0.23.0 (rastreabilidade, proveniência, governança de IA e interruptor de emergência):**
a rodada começou **auditando o que já existia** (`AI_AUDIT.md`, `PLATFORM_AUDIT_v0230.md`), e as duas
conclusões decidiram o escopo: a base é mais madura do que os prompts supõem, e a pilha de referência
deles (Supabase + Vercel + Next.js) não é a desta plataforma — então a infraestrutura **não foi
trocada** e os requisitos de segurança dela foram aplicados à pilha real.

As lacunas reais eram específicas. As quatro mais graves:

1. **O refresh token não vencia.** Trinta dias eram recontados a cada rotação, inclusive na mesma
   família — um token roubado e renovado dentro da janela sobrevivia indefinidamente. A família
   passou a ter idade máxima própria, que não se renova.
2. **O código TOTP servia duas vezes.** `verify()` devolvia o contador aceito e o docstring dela
   dizia "para impedir reuso" desde sempre; nenhum chamador usava o valor.
3. **O evento de segurança mais grave não alertava ninguém da operação.** Reuso de refresh token era
   registrado, auditado e notificado ao titular — e esperava que alguém abrisse uma tela.
4. **A verificação de órfão era uma string literal** afirmando que nenhuma verificação era aplicável,
   num banco com 25 colunas de referência polimórfica sem chave estrangeira.

E a regra de proveniência passou a valer no banco: **medição autodeclarada é permitida; autodeclarada
apresentada como validada, não.** `GET /v1/indicator-values/{id}/provenance` devolve a cadeia inteira
— projeto, indicador, linha de base e fonte, documento com sha256, evidência, revisão, validação,
Impact Ledger com hash, auditoria — **e `gaps`**, que nomeia cada elo ausente com o efeito dele sobre
o que o número prova. Cadeia que esconde o elo que falta transforma ausência de prova em aparência de
prova. Leia `PROVENANCE_ENGINE.md`, `AUDIT_ENGINE.md` e `AI_FINAL_AUDIT.md`.

**Novo no v0.22.0 (login inteligente, controladoria e o fim do booleano único de administrador):** a regra que
governou a rodada veio antes do escopo — *"não implemente uma fintech dentro do IMPACTO só porque isso parece
aumentar a monetização; primeiro prove que a mesma receita e garantia operacional podem ser obtidas com uma
arquitetura muito mais simples"*. A auditoria dessa exigência encontrou algo melhor do que uma lista de remoções:
**a regra já era verdadeira no código**. `split`, `payout`, `recipient`, `repasse`, `escrow`, `wallet` e saldo de
terceiro têm **zero ocorrências** em 325 módulos Python, 45 arquivos de frontend e 298 tabelas — e a v0.20.0 havia
*removido* o gerador de PIX justamente porque, sem provedor, chamá-lo exigiria valor inventado. O trabalho passou a
ser **provar, documentar e travar** isso (`NON_CUSTODIAL_ARCHITECTURE.md`, ADR-284) e recusar, item por item, os
pedidos de custódia.

E corrigiu o defeito simétrico do lado de dentro:

* **Havia UM booleano para toda a equipe interna.** Quem tivesse `is_platform_admin` alcançava receita apurada,
  custo de IA, fatura e tabela de preços **sem nenhum papel financeiro no caminho**. Os três papéis nomeados que
  existiam eram todos de conteúdo. Agora são **14 papéis** e **43 permissões**, com a permissão funcionando como
  **chave na porta** da API, não como rótulo.
* **Quatro olhos declarados e não implementados.** `core/risk_levels.py` dizia quais operações exigiam dupla
  aprovação sem implementar nenhuma — o próprio docstring dele chamava isso de "a forma mais cara de mentir nesta
  plataforma". Agora a alçada é **dado no banco**, com 8 faixas e dois gatilhos: quem pede não aprova, e faixa de
  duas assinaturas recusa a mesma permissão duas vezes.
* **224 das 848 rotas não tinham tela nenhuma** — a saúde do sistema, a receita apurada, as tarefas agendadas e o
  Integration Hub inteiro. **16 telas internas** foram construídas, e um teste passou a reprovar a suíte quando um
  domínio de permissão tem rota e não tem tela. Foi esse teste que encontrou o FULL FREE 2026: rota, serviço, banco
  e teste desde a v0.21.0, e nenhuma tela por onde conceder ou auditar cortesia.
* **Duas tabelas registravam a execução das tarefas** com respostas divergentes — e a que cobria 22 tarefas era a
  que não sabia duração nem erro. Unificadas; a antiga **removida** do esquema.
* **Indicador sem base responde `available: false` com o motivo, nunca zero.** Churn, LTV, CAC e custo de IA estão
  nesse estado, declaradamente — zero parece medição.

Mais: `/portal` resolvendo a cadeia *quem entra → organização → perfil → função → plano → recursos → situação
financeira → painel* no servidor; contabilidade por competência com partida dobrada real; instrução de pagamento
como **documento** que congela na emissão e exige evidência; Health Center; Central de Alertas derivada do estado.

E uma **auditoria final independente**, feita por quem não produziu o trabalho: com a suíte já
verde, ela encontrou 11 defeitos reais e 12 testes fracos — entre eles a decisão de aprovação que
nunca chegava à despesa aprovada (o painel mostrava "A pagar R$ 0,00" ao lado da despesa total), o
menu que ainda oferecia o que a porta recusa em quatro papéis, e um teste **tautológico** que a
própria documentação citava como prova do contrário. Tudo corrigido; cada achado virou teste.

**1.806 testes, 873 operações, 50 migrações, 42 motores.** Documentos desta rodada:
`NON_CUSTODIAL_ARCHITECTURE.md`, `AUTHORIZATION.md`, `FINANCIAL_ENGINE.md`, `INTERNAL_OPERATIONS.md` e
`TECHNICAL_FINALIZATION_STATUS.md`.

**Novo no v0.21.0 (monetização):** a infraestrutura comercial **existia inteira e estava vazia** — versionamento de
preço com gatilho de imutabilidade, aviso de 30 dias e aceite congelado, com **zero linhas** em
`plan_price_versions` e 7 planos pagos com preço nulo. Esta rodada publicou o catálogo 2027.01 (8 versões vigentes,
2 pisos de proposta, 5 planos gratuitos, **nenhum valor em código**), criou a **gratuidade temporal por conta**
(`free_periods`, com origem, motivo e autor) e separou **ACESSO GRATUITO** de **AUTORIZAÇÃO DE COBRANÇA** em dois
atos com dois registros, com gatilho de banco recusando cobrança real sem autorização vigente. Comece por
`PRICING_BIBLE.md`, `PRICING_RECONCILIATION.md` e `COMMERCIAL_TERMS.md`.

**Novo no v0.20.0 (fechamento da engenharia antes do Designer):** rodada de **auditoria**, não de funcionalidade,
dividida em onze etapas. Cada etapa procurou a diferença entre o que a plataforma **afirmava** e o que ela
**fazia** — e o que encontrou foi, em quase todos os casos, um mecanismo escrito, testado e **inalcançável**:

* **Quinze tipos de aviso não pertenciam a interruptor nenhum.** A pessoa desligava todas as preferências que a
  tela oferecia e continuava recebendo aviso de conformidade, candidatura, pagamento, evidência e situação
  institucional, porque 29 chamadas usavam prefixos que não casavam com nenhum grupo. Interruptor que não desliga
  é pior que interruptor nenhum, porque quem o usa acredita ter escolhido.
* **Três funções existiam e nunca eram chamadas.** Proposta com prazo vencido ficava em "enviada" para sempre, e o
  evento que avisaria as duas partes nunca acontecia. Selo cujo critério caiu continuava sendo exibido — o próprio
  docstring da função que o revogaria diz que isso é pior que não ter selo.
* **Dezoito eventos de domínio declarados e nunca emitidos**, incluindo "documento anexado" — literalmente o caso
  que originou o módulo de notificação.
* **Doze motores existiam fora do inventário**, entre eles a camada de impacto inteira: afirmações, equidade,
  reputação e selos. Registro incompleto dá a impressão de inventário.
* **O importador de metas dos ODS que um documento dizia ter entregue não existia.** Foi escrito, e o documento
  corrigido sem apagar o erro.
* **`.docx` era aceito no envio e subia sem texto nenhum extraído**: os leitores existiam e nenhum estava ligado.
* **Uma bandeira de administração não ligava nada.** Ligar ou desligar não mudava o produto.

E implementou o que o escopo da rodada pedia: denúncia separada em **quatro níveis** (denúncia → suspeita →
infração apurada → consequência), com gatilho no banco impedindo que medida seja aplicada sem apuração concluída;
**procedência** completa de dado público, em que "prazo não declarado" nunca mais vira "atual"; **qualidade de
dado** que jamais se converte em desempenho do projeto; **nível de risco** das 837 operações com o controle humano
que cada uma exige; **benchmark de preço** por pesquisa nas páginas dos próprios fornecedores; e as **seis telas**
que faltavam.

**1.557 testes, 837 operações, 293 tabelas, 41 migrações, 42 motores.** Entregas de documento desta rodada:
`FINAL_TECHNICAL_RELEASE_REPORT.md`, `FINAL_RELEASE_MANIFEST.json`, `ENGINE_COVERAGE.md`, `PRICE_BENCHMARK.md` e
`DESIGN_HANDOFF_FINAL.md` reescrito.

**Novo no v0.18.1 (endurecimento técnico final):** rodada de **prova**, não de funcionalidade. Integrou quatro
reforços de núcleo recebidos num pacote externo (sinal contextual no match, oito prontidões no diagnóstico,
proveniência por campo em documento, série longitudinal) e rodou-os contra PostgreSQL real — o que o ambiente de
origem não pôde fazer. Encontrou e corrigiu sete defeitos, quatro deles graves: o **sinal contextual estava morto
para todo financiador** (a RLS, corretamente, não entrega a narrativa de equidade a terceiro — agora há função
agregada que devolve **só números**), a **"referência neutra" de 0,5 premiava quem não declarava contexto**,
**prazo sem fuso horário devolvia 500** (agora 422 com exemplo, sem adivinhar fuso) e **"erradicamos" passava como
alegação sustentada** (nasceu a 12ª regra: totalidade se confere por divisão, medido sobre elegível). Acrescentou
75 testes de prova: concorrência real, caminho de atualização com dado dentro, jornada completa de 18 passos,
smoke de publicação com 20 verificações, acessibilidade no navegador com contraste calculado nos dois temas, e
carga nas rotas novas. Declarou como **bloqueado pelo ambiente** — não como aprovado — o que não pôde ser
executado: `npm audit`, `pip-audit`, `axe-core`, leitor de tela e Docker.

**1.298 testes, 815 operações, 285 tabelas, 34 migrações** *(números da v0.18.1; ver acima os atuais)*. Entregas de documento desta rodada:
`TECHNICAL_BASELINE_LOCK.md`, `REQUIREMENTS_MATRIX.md`, `TECHNICAL_DEBT_REGISTER.md`,
`PRODUCTION_RELEASE_RUNBOOK.md`, `ACCESSIBILITY_REPORT.md` e `DESIGN_HANDOFF_FINAL.md` reescrito.

**Novo no v0.18.0 (interoperabilidade de referenciais de impacto, equidade e confiança):** a rodada implementa uma
tese só — **impacto não é quantidade; impacto é resultado contextualizado.** "50 pessoas numa comunidade indígena
remota" não é automaticamente menos impacto que "5.000 pessoas num centro urbano", e a consequência é
desconfortável de propósito: **sem denominador declarado com fonte, data e método, não existe número normalizado**
(sete métodos, cada um dizendo qual denominador exige), a avaliação de equidade **não produz nota**, e a comparação
entre projetos devolve `comparable: false` com os motivos — **nunca um veredito**. Entram: **território como
catálogo** separando `from_official_load` do conhecimento da plataforma (as 27 UFs semeadas dizem "conferir na carga
oficial"); **registro de 19 referenciais** (ODS, ESG, GRI, ISSB, TCFD, TNFD, IRIS+, SROI, MCDA, LCA e outros) com
escada de relação de **seis degraus que para em `audited`** — `certified` é recusado por gatilho, porque a
plataforma não é organismo certificador; **materialidade** com `is_material` **derivada** da lente e do limiar;
**integridade de alegação** com 11 regras determinísticas e situação **derivada** (não existe coluna de situação em
`claims`), revisão humana **por convite nomeado** de outra organização, e a marca que a revisão qualifica sem
apagar; **reputação explicável em seis dimensões e SEM nota única** (divergência declarada dos prompts: nota única
vira ranking, e ranking vira critério de acesso), em que organização nova **começa sem medida, não com nota baixa**,
órgão público recebe perfil de governança sem nota e pessoa física não tem perfil público, com contestação que
aparece no próprio perfil e correção que gera ponto novo; **motor de selos** cujo critério é avaliado **em SQL** —
a aplicação não tem INSERT em `seal_awards`, então nenhuma rota concede selo sem critério — com definição
versionada e imutável, revogação como fato novo e **zero definições embarcadas**; **busca incremental com
procedência em cada sugestão** e componente que **nunca sobrescreve** o que a pessoa escreveu em silêncio; e
**responsabilidade** como responsável × papel × escopo × período × decisão × **versão**, separada da assinatura,
com quatro-olhos declarado em dado.

**(v0.18.0: 1.223 testes, 815 operações, 285 tabelas, 31 migrações.)** O que esta versão **não** entrega continua escrito com
nome: as 169 metas oficiais dos ODS e os dados do IBGE **não foram carregados** (a rede do ambiente alcança só
registros de pacote — a estrutura e os importadores estão prontos); mapeamento para GRI/ISSB/IRIS+ depende de
decisão de produto **e** jurídica; nenhum selo publicado; nenhuma arte de selo. Comece por
`IMPACT_FRAMEWORK_AUDIT.md`, `CLAIM_INTEGRITY.md`, `REPUTATION_ARCHITECTURE.md`, `SEAL_ENGINE.md`,
`SMART_FORMS.md`, `RESPONSIBILITY_ENGINE.md` e `FINAL_IMPACT_FRAMEWORK_REPORT.md`.

**Novo no v0.17.0 (camada econômica, legal e de pagamento):** a rodada inverte a ordem do roteiro a pedido do
proprietário — **monetização, pagamento e auditoria legal vêm antes do design** — e implementa uma tese só: **o
proponente não pode ser o pagador principal.** Cadastro, perfil, projeto, descoberta, rede e acompanhamento básico
são **gratuitos e permanecem gratuitos** (ADR-173, que muda a regra comercial da v0.16.0). Entram: **Programa** como
entidade de primeira classe, com objetivo obrigatório e três funções que separam o declarado do medido
(`program_financials` distingue **gasto** de **comprovado**; `result_chain` carrega a força declarada de cada elo
sem promover hipótese a evidência; `territorial_gap` leva a qualidade da evidência por território); **Value Ledger**
separado da cobrança, com a aplicação **sem INSERT** na tabela e nenhuma linha de base nascendo com número;
**monetização com portão legal no banco** — nove regras, **zero verdes, nenhuma ativa**, e `green_needs_evidence`
recusando verde sem fonte porque ausência de proibição não é permissão; **arquitetura de pagamento** com cartão,
recorrente, **parcelamento modelado à parte da assinatura**, PIX e boleto, toda marcada `PRODUCTION PAYMENT NOT
CONFIGURED` porque é o estado verdadeiro, com `is_simulated` derivada do provedor e irreescrevível; **onze documentos
legais versionados** com aceite que guarda o **sha256 do texto aceito** — e o banco **recusando registrar aceite de
minuta não revisada por advogado(a)**, o que trava o produto de propósito; e o **registro de motores (28 na v0.17.0; 42 na v0.20.0)
operacionais** com cinco testes que provam que IA aqui é motor, não chatbot.

**(v0.17.0: 961 testes, 749 operações, 253 tabelas, 24 migrações.)** O que aquela versão **não** entregou está escrito com nome:
nenhuma receita ativa, nenhum aceite registrável, nenhum provedor de pagamento, nenhuma nota fiscal, nenhum SLA.
Comece por `ECONOMICS.md`, `MONETIZATION_LEGAL_MATRIX.md` e `FINAL_ECONOMIC_HARDENING_REPORT.md`.

**Novo no v0.16.0 (IMPACT NETWORK CORE):** a plataforma deixou de ser "um lugar com projetos" e passou a ser
**infraestrutura de conexão, estruturação, financiamento, execução, acompanhamento e comprovação de impacto** — com
**um núcleo** e experiências por papel, não quatro aplicações. A cadeia inteira existe como dado: Pessoa/Organização
→ Contexto → Necessidade → Rede → Match → Proposta → Relação → Projeto → Execução → Evidência → Resultado → Novo
Match. **Grafo de impacto** relacional (uma tabela de aresta, 22 tipos, 5 níveis de visibilidade, travessia de
profundidade 2 em 15 ms — a razão medida de **não** adotar banco de grafos); **motor de propostas** (9 tipos, 10
situações, grafo de transições no banco) onde *proposta ≠ contrato ≠ investimento ≠ pagamento*; **marketplace** com
um único lugar que decide o que é público; **conversa com contexto obrigatório**; **notificação para toda a equipe
envolvida** em cada evolução (14 grupos, idempotente, um aviso por fato); **prontidão** em 6 dimensões sempre com
explicação; **recomendação ≠ match**; **workspace por persona** (10 personas, 24 seções, 15 capacidades) que devolve
próximas ações, não números; **perfil público `impacto.app/@identificador`** que lê só uma projeção curada;
**relatório de impacto** cujos números são **colhidos pelo banco**, não digitados; **escada de moderação** de 10
degraus com proporcionalidade e contestação; **cobrança versionada** com aviso de 30 dias e imposto no checkout.
788 testes, 704 operações, 231 tabelas e 17 migrações à época. O pacote de Design System "Convergência" **não foi
recebido** — as seções que dependiam dele não foram executadas, e isso está escrito em
`DESIGN_HANDOFF_FINAL.md` §1. Comece por `IMPACT_NETWORK_ARCHITECTURE.md`, `DESIGN_HANDOFF_FINAL.md` e
`FINAL_IMPACT_NETWORK_HARDENING_REPORT.md`.

**Novo no v0.15.0 (Núcleo do produto):** as seis peças passaram a ser **um sistema**, não seis telas — ideia → diagnóstico → projeto → documento → match → acompanhamento compartilhando o mesmo vocabulário de evidência (com fonte, data e frescura), as mesmas versões de motor e a mesma trilha encadeada por hash. A **ideia não é apagada** ao virar projeto; a **máquina de 17 situações é dado no banco**, com gatilho que recusa transição inválida até em SQL direto; a **linha de tempo** é a trilha que já existia, verificável; **retratos comparáveis** respondem "o que mudou entre março e setembro"; o **diagnóstico** separa FATO, INFERÊNCIA, RECOMENDAÇÃO e **DESCONHECIDO**, com versões imutáveis e `o que mudou` calculado pelo servidor; a **montagem de documento** recusa gerar incompleto, dizendo o que falta, e exige **quatro olhos** para aprovar; o **match** carrega quatro versões e aceita retorno humano **sem treinar nada automaticamente**. 673 testes, 625 operações, 205 tabelas. **Não há assinatura qualificada (ICP-Brasil/Gov.br), KMS/HSM, integração contra sistema real nem teste de intrusão independente** — tudo isso está listado com nome e motivo. Comece por `CORE_PRODUCT_ARCHITECTURE.md`, `FINAL_PRE_DESIGN_HARDENING_REPORT.md` e `DESIGN_HANDOFF.md` §13.

**Novo no v0.14.0 (Confiança, identidade e assinatura digital):** **qualquer pessoa autorizada pode verificar um documento da plataforma sem ter conta** — pelo código impresso ou pelo QR, em `/verificar`: diz se é genuíno, **qual versão foi assinada**, se a integridade continua intacta, quem assinou e se foi revogado. Mais: assinatura eletrônica avançada em **duas camadas** (senha + código de uso único amarrado ao hash do conteúdo), cadeia de custódia encadeada por objeto, identidade por níveis com conferência humana, credencial profissional com catálogo de 20 conselhos, acordos multiassinatura com acompanhamento, carimbo de tempo interno, taxonomia ODS/ESG/determinantes sociais, idioma e tema por usuária, financiamento em cotas com campanha pública, honorários exigindo fonte, georreferência com consentimento, diagnóstico guiado em 8 etapas e exportação em docx/xlsx/odt/ods/xml/pdf. 564 testes. **Não há assinatura qualificada (ICP-Brasil/gov.br), biometria, SMS nem carimbo de ACT** — essas dependem de contratação externa e a plataforma **recusa explicitamente** em vez de simular. Comece por `PUBLIC_VERIFICATION.md`, `DIGITAL_SIGNATURE.md` e `FINAL_TRUST_HARDENING_REPORT.md`.

**Novo no v0.13.0 (Integration Hub):** camada de integração desacoplada — conexões por ambiente, credenciais cifradas que a API nunca devolve, mapeamento de campos, correspondência de ID externo com conflito explícito, jobs idempotentes com repetição e disjuntor, webhooks de entrada e saída assinados, importação CSV/XLSX com aprovação humana, exportação e painel de operação. 13 tabelas, 36 rotas, 9 provedores declarados com **maturidade honesta**, 468 testes. **Nenhuma integração foi executada contra sistema externo real** e **não há nenhuma tela** — comece por `INTEGRATION_HUB.md`, `FINAL_INTEGRATION_HARDENING_REPORT.md` e `DESIGN_HANDOFF.md` §11.

**Novo no v0.12.1 (baseline técnica):** endurecimento final antes da camada de design — varredura de autorização nas 475 operações, testes de concorrência, correção de vazamento de esquema em erros, do desconto de voucher que não aparecia, da perda de boletim em falha de SMTP e do contraste reprovado (WCAG AA). 392 testes. Comece por `FINAL_TECHNICAL_BASELINE.md` e `DESIGN_HANDOFF.md`.

**Novo no v0.12.0:** Central de Conhecimento — `/ajuda` (busca, guias, biblioteca, FAQ, assistente ancorado), Academia, eventos, suporte com SLA, parcerias, demonstração, solicitação de teste, boletim e CMS em `/admin/central`. Começa em `KNOWLEDGE_HUB.md`. **Sem conteúdo oficial real ainda (só exemplos rotulados).**

**Novo no v0.11.0:** monetização SaaS — trial de 14 dias FULL sem cartão, níveis FREE/PLUS/PREMIUM/GOV, cobrança mensal/anual (Stripe, só simulado em testes), vouchers, licenças e convênios. Comece por `docs/billing.md`. **Preços não definidos; Stripe não homologado.**

**Novo no v0.10.1:** fecha pendências da camada institucional — perfis OS/OSCIP, instrumentos, trilha de formalização e mentoria, cruzamento fiscal × elegibilidade, rede da solução, tesauro de 67 conceitos. Veja `CHANGELOG.md` e `FINAL_RELEASE_AUDIT.md` §3-C.

**Novo no v0.10.0:** camada institucional do terceiro setor — natureza jurídica × qualificações × situação × elegibilidade por oportunidade, com explicação e fonte. Comece por `THIRD_SECTOR_MODEL.md`, `INSTITUTIONAL_ELIGIBILITY_ENGINE.md` e `FINAL_RELEASE_AUDIT.md` §3-B.

**Novo no v0.9.0:** Biblioteca de Soluções de Impacto — busca por intenção, relevância/match explicáveis, replicação, intenção de financiamento com privacidade. Comece por `SOLUTION_LIBRARY.md`.

## Comece aqui
| Biblioteca de Soluções | `SOLUTION_LIBRARY.md`, `SOLUTION_SEARCH.md`, `SOLUTION_MATCH_ENGINE.md`, `REPLICATION_ENGINE.md`, `INTENT_ENGINE.md`, `AI_SEARCH_ARCHITECTURE.md`, `SOLUTION_DATA_MODEL.md`, `API_DOCUMENTATION.md`, `TEST_REPORT.md` |
| Quero… | Leia |
|---|---|
| rodar localmente | `ENVIRONMENT_SETUP.md` |
| saber o que funciona e o que falta | `FINAL_RELEASE_AUDIT.md`, `PRODUCTION_READINESS.md` |
| publicar (Web, Google Play, App Store) | `DEPLOYMENT_CHECKLIST.md`, `docs/DEPLOYMENT.md`, `docs/MOBILE.md` |
| continuar o desenvolvimento | `CLAUDE_HANDOFF_FINAL.md`, `DECISIONS.md` |
| entender o núcleo do produto | `CORE_PRODUCT_ARCHITECTURE.md`, `MATCH_ENGINE_FINAL.md`, `DIAGNOSTIC_ENGINE.md`, `PROJECT_LIFECYCLE.md`, `DOCUMENT_ASSEMBLY.md`, `LONGITUDINAL_TRACKING.md` |
| fazer o design | **`DESIGN_HANDOFF_FINAL.md`** (v0.16.0), `INFORMATION_ARCHITECTURE.md`, `NAVIGATION_MODEL.md`; histórico em `DESIGN_HANDOFF.md` §13 |
| entender a rede de impacto | `IMPACT_NETWORK_ARCHITECTURE.md`, `IMPACT_GRAPH.md`, `RELATIONSHIP_MODEL.md`, `PROPOSAL_ENGINE.md`, `IMPACT_MARKETPLACE.md`, `IMPACT_REPORTING.md` |
| entender as personas e o workspace | `ROLE_BASED_EXPERIENCE.md`, `WORKSPACE_ARCHITECTURE.md` |
| saber quem vê o quê | **`PRIVACY_VISIBILITY_MATRIX.md`** |
| saber quem pode o quê (equipe interna) | **`AUTHORIZATION.md`**, `INTERNAL_OPERATIONS.md` |
| entender o motor financeiro e por que ele não custodia | **`NON_CUSTODIAL_ARCHITECTURE.md`**, `FINANCIAL_ENGINE.md` |
| saber o estado de cada fase do fechamento técnico | **`TECHNICAL_FINALIZATION_STATUS.md`** |
| entender moderação e cobrança | `MODERATION_LADDER.md`, `BILLING_V2.md` |
| publicar no celular | `MOBILE_READINESS_FINAL.md`, `STORE_READINESS.md` |
| saber o que depende de terceiro | `EXTERNAL_DEPENDENCIES.md`, `HOMOLOGATION_MATRIX.md`, `SIGNATURE_VALIDATION_MATRIX.md` |
| auditar segurança, banco e desempenho | `SECURITY_FINAL_CHECKLIST.md`, `DATABASE_INTEGRITY_REPORT.md`, `PERFORMANCE_REPORT.md` |
| rotacionar chave de cifragem | `KEY_ROTATION.md` |
| saber o que é guardado e por quanto tempo | `DATA_RETENTION_MATRIX.md` |
| segurança / LGPD | `SECURITY_AUDIT.md`, `docs/SECURITY.md`, `LGPD_AUDIT.md`, `docs/LGPD.md`, `docs/legal/` |
| licenças e PI | `THIRD_PARTY_DEPENDENCIES.md`, `IP_REGISTER.md` |
| integridade do pacote | `RELEASE_MANIFEST.sha256` (`python3 scripts/make_release.py --verify .`) |

## Estrutura
```
backend/     API (Starlette), serviços, engines (match, fiscal, IA), adapters, jobs, migrações SQL, testes
web/         SPA/PWA React+TypeScript (src/), build esbuild (dist/ já construído), Capacitor (Android/iOS)
mobile/      scripts, ícones/splash e modelos de deep link
config/      planos, taxonomia, pesos do match, regras fiscais candidatas (rascunho)
infra/       bootstrap do banco, compose, nginx, alertas
scripts/     backup/restore, reset do banco de dev, gerador de API docs, make_release
docs/        arquitetura, banco, API (gerada), segurança, LGPD, match, fiscal, IA, compliance, pagamentos, operação, mobile, testes, admin, negócio, a11y, ESG/ODS, legal/, evidence/
history/     v0.6.0, v0.7.0 e v0.8.0 preservados (sem sobrescrever)
```
Mapa dos documentos pedidos: `AI_ARCHITECTURE` = `docs/AI.md` · `MATCH_ENGINE`, `DATABASE`, `API` (gerada de 306 operações), `SECURITY`, `LGPD`, `DEPLOYMENT`, `TESTING`, `ADMIN`, `BUSINESS_MODEL` em `docs/`.

## Princípios (verificáveis no código)
- **Isolamento no banco** (RLS) — não só na API. · **Match independe de plano/voucher** (teste AST). · **Sem nota sem dados suficientes.**
- **IA só rascunha**; revisão e assinatura por profissional verificado. · **Fiscal só com regra aprovada por dois revisores.**
- **Aportes não passam pela plataforma** (registrados e conferidos). · **Sem pagamento falso**; **sem segredos** no repositório.

## Início rápido (dev)
```bash
make db && make web && IMPACTO_SEED_DEMO=true make dev     # http://localhost:8080 — dados FICTÍCIOS
make test                                                   # suíte completa (Postgres + navegador)
```
Licença do código: **a definir pelo proprietário** (ver `IP_REGISTER.md`). Dependências: `THIRD_PARTY_DEPENDENCIES.md`.
