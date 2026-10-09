# Notas da versão — v0.31.0 (Infraestrutura Railway + Supabase + Cloudflare R2: auditada e preparada, não publicada)

**Uma regra:** conectar um serviço não prova que ele funciona. Cada item desta rodada diz se foi **comprovado**, **não
comprovado** ou **bloqueado por acesso** — e nada foi publicado, migrado em produção, apagado ou cobrado.

**O que isso virou em software e em prova:**

1. **Identidade do código** — a "baseline 0.29.01" do pacote é, byte a byte, a tag v0.29.0 (`dd2f8c3`); o repositório está
   à frente. Nada da baseline foi copiado (regrediria o código).
2. **Supabase lido de verdade** — PostgreSQL 17.11; `impacto_app` sem superusuário e sem bypass de RLS; 71 migrações em dia;
   **15 contas de demonstração e 1 real no mesmo projeto** (decisão sua: separar staging e produção); o lote 0064–0070 foi
   aplicado em 09/10 fora do GitHub, com troca da senha de `impacto_app` — a confirmar com você.
3. **Backup restaurado de verdade** — dump do Supabase restaurado num PostgreSQL descartável, com os verificadores de
   integridade do CI: 341 tabelas, 2.577 linhas idênticas, RTO medido 15,1 s, nada exportado.
4. **Worker próprio** — as 21 tarefas periódicas (antivírus, retenção LGPD, prazos, canário, backup) ganham um serviço que
   não migra, espera o esquema e roda como `impacto_app`.
5. **Armazenamento** — região `auto` do R2 validada; arquivo em disco de contêiner sem volume sinalizado em `/readyz` e no log;
   adaptador S3 provado contra servidor S3 real no CI; verificador do bucket R2 pronto.
6. **Um caminho de publicação** — o Railway publica pelo Git; o `deploy.yml` (modelo com `echo`) saiu; `pos-deploy` verifica a
   instância de fora e confere que o commit no ar é o esperado (`/healthz` agora informa o commit).

**Números:** 940 operações · 227 telas · 70 migrações · 50 motores · 24 testes novos (+1 de protocolo S3 que roda no CI).

**O que continua dependendo de você:** URL e configuração do Railway; separar staging/produção; igualar a senha de
`impacto_app` no GitHub; buckets e tokens R2; SMTP; domínio na Cloudflare; aprovação para produção.
Lista em ordem: `docs/ops/CHECKLIST_PROPRIETARIO_v0310.md`.

---

# Notas da versão — v0.30.0 (Evidência de primeira classe e dossiê longitudinal)

**Uma regra:** o que a plataforma mostra a quem financia é exatamente o que está gravado — com origem, data e lacunas — e cada
evidência diz como foi coletada, quem pode vê-la, se pode ser contestada e o que o hash prova (integridade, não veracidade).

**O que isso virou em software:**

1. **Baseline antes de alterar** — inventário da base real em quatro estados, com o teste que prova cada linha; o que o pacote
   propunha contra decisões já tomadas (escrow, retenção automática, assinatura, selo pago) ficou registrado e fora.
2. **Evidência como objeto** — método de coleta, nível de acesso, base de consentimento, classe de retenção; substituir cria
   versão nova (a anterior fica legível como substituída); rejeitar exige motivo; a executora contesta com motivo e quem revisa
   decide com justificativa; histórico próprio que ninguém apaga; máquina de estados no banco.
3. **Dossiê longitudinal** — uma leitura só para quem financia ou acompanha: prontidão, marcos e obrigações, evidências por
   estado (validadas × declaradas × contestadas), séries reportado × validado com método e unidade, aportes e repasses,
   diligências, trilha — cada bloco com origem e atualidade, lacunas declaradas, "o que isto não é" no topo. A OSC vê o mesmo.
4. **Mudança metodológica registrada** — trocar o método de medição exige motivo, fica no histórico e a série marca a
   descontinuidade em vez de fingir comparabilidade.
5. **Economia do SaaS a partir do catálogo real** — 11 regras, 0 ativas, 5 recusadas; mapa pagador → valor → evento → preço-hipótese;
   sensibilidade do take rate 2–5 % como simulação; matriz de elegibilidade de cobrança para revisão jurídica/contábil.
6. **Matriz perfil × jornada × permissão × dado × ação** gerada das jornadas realmente executadas.

**Números:** 940 operações · 227 telas · 70 migrações · 50 motores · 20 testes novos.

**O que continua dependendo de pessoa ou terceiro:** parecer para ativar qualquer regra comercial; provedor de pagamento/fiscal;
conferência das fontes e revisão do glossário (v0.29.0); decisão sobre os controles bloqueados.

---

# Notas da versão — v0.29.0 (Base de conhecimento governada e ajuda contextual)

**Uma regra:** a plataforma só explica o que tem fonte registrada, conferida por outra pessoa e com direito de uso — e
diz em cada tela, no mesmo texto, o que um conceito é, como o IMPACTO o usa e o que ele NÃO garante.

**O que isso virou em software:**

1. **Base de conhecimento versionada e reconciliada** — a base v0.26.0 entrou no git sem retroceder a release; os 58
   controles foram classificados contra o código com os testes que os provam (6 implementados e testados, 27 parciais,
   13 bloqueados por terceiro, 12 não implementados). Nada foi declarado "em conformidade".
2. **Fontes com direitos de uso** — registro de fonte (lei, orientação, padrão voluntário, hipótese, decisão pendente)
   com jurisdição, vigência, licença, direitos por operação (guardar, indexar, citar trecho, resumir, traduzir, embutir,
   enviar a terceiro, treinar, redistribuir), verificação por pessoa diferente de quem registrou e data de revisão.
   As 11 fontes iniciais estão **não conferidas** — e a interface diz isso.
3. **Citação, retirada e fila editorial** — citação só em rascunho, trecho só com direito permitido e hash conferido
   pelo banco; retirada é terminal com motivo e some da busca, do assistente e do sitemap no mesmo instante; buscas
   sem resultado, "não ajudou", conteúdo vencido, fonte atrasada e relatos de erro viram itens de trabalho (só hash e
   tópicos, nunca o texto da pergunta).
4. **Assistente que cita e se abstém** — responde por extração a partir de UMA fonte publicada, oficial/educacional, não
   demo e não vencida; mostra o que excluiu e por quê; em empate, pergunta em vez de escolher; sem base, diz que não
   encontrou. Nunca se apresenta como "base oficial".
5. **Busca medida** — 35 consultas rotuladas, 8 métricas, baseline gravado como piso que reprova regressão. A única
   mudança (tesauro) foi feita porque a medição mostrou ganho. Embeddings não foram adicionados: sem ganho demonstrado.
6. **Ajuda contextual** — 33 conceitos definidos uma vez (`config/concepts.json`) e consumidos por tooltip (hover/foco),
   popover (clique/Enter/toque, Escape fecha) e página `/ajuda/glossario`; aplicado em 11 telas; acessível por mouse,
   teclado e toque; claro/escuro; movimento reduzido respeitado; sem biblioteca nova.

**Números:** 936 operações · 226 telas · 69 migrações · 50 motores · 33 conceitos · 11 fontes (0 conferidas) ·
58 controles reconciliados.

**O que continua dependendo de pessoa:** conferir as 11 fontes (reviewer), revisar as definições do glossário por área,
escrever conteúdo oficial com citações (a semente continua DEMO/educacional), e as 13 dependências externas da base.

---

# Notas da versão — v0.28.0 (IA sustentável: cota, crédito, patrocínio e similaridade)

**Uma regra:** ninguém paga para entrar no IMPACTO; paga-se pela operação de inteligência efetivamente executada —
e cada operação mostra o custo e quem paga ANTES de rodar. Falhou, não cobra. Mesmos dados, não cobra de novo.

**O que isso virou em software:**

1. **Catálogo versionado de operações** (A assistência leve, B contextual, C avançada, D originalidade e similaridade,
   E lote, F institucional) com faixa de risco, quem pode, de onde o dinheiro vem, créditos, limites e critério de
   conclusão. Preço novo = versão nova; execuções antigas guardam a sua.
2. **Camada de uso e custo** — prévia → autoriza → reserva → executa → liquida; débito só em sucesso; concorrência
   e idempotência no banco; o frontend nunca decide preço, saldo ou fonte.
3. **Gratuidade orçada** — cotas configuráveis (boas-vindas uma vez por organização e por pessoa; mensal leve);
   acabou, a tela diz o custo, as opções e preserva o trabalho.
4. **Créditos por PIX** — pedido com termos aceitos; em modo PILOTO (regra comercial inativa, sem provedor) não há
   pagamento e a administração pode aprovar como concessão; em modo REAL o crédito só nasce por webhook assinado
   (HMAC) ou conciliação manual com referência; cobrança simulada nunca credita.
5. **Patrocínio de uso** — financiador, governo ou empresa compromete créditos do próprio saldo para organizações
   elegíveis; esgotado, para; prestação de contas agregada, nunca conteúdo.
6. **Motor de originalidade, similaridade, complementaridade e integridade do financiamento** — local, oito
   dimensões separadas; similaridade textual ≠ escopo ≠ território ≠ duplicidade financeira ≠ plágio ≠ fraude;
   indícios com confiança e revisão humana; contestação; só projetos visíveis (rascunhos alheios como contagem
   k-anônima); nada bloqueia financiamento, reputação ou match.
7. **Painel financeiro da IA** — medido × NÃO MEDIDO, créditos vendidos/concedidos/consumidos, obrigações com
   clientes, margem parcial, alertas; e `AI_COST_MODEL.md` com piloto medido, três cenários e as doze perguntas.

**Números:** 923 operações, 225 telas, 50 motores (VERDE 37 · AMARELO 13 · VERMELHO 0), 68 migrações,
11 regras de monetização (0 ativas), 16 jornadas / 256 passos / 0 falha. Regressão completa:
`FINAL_EXECUTION_REPORT.md` §24. **Receita real de IA desta instalação: R$ 0,00 (modo piloto).**

**O que esta versão NÃO entrega**, com nome: venda real de créditos (parecer + provedor); BYOK; lote,
monitoramento e relatório institucional (planejados, 501); preço de produção; custo de provedor medido;
NFS-e; tag enviada ao GitHub (proxy). Detalhes em `FINAL_EXECUTION_REPORT.md` §25–26, `FINAL_EXECUTION_AUDIT.md`,
`AI_PROVIDERS_EVALUATION.md` e `EXTERNAL_INTEGRATIONS.md`.

**Para operar o piloto:** `docs/execution/PRODUCTION_CHECKLIST_v0280.md` (o que está feito, o que depende do
proprietário, o que só o piloto responde), `docs/execution/ROLLBACK_v0280.md` (código com banco mantido; restauração
só em último caso; migrações são forward-only) e `docs/execution/AI_COST_MONITORING_GUIDE.md` (onde olhar, alertas,
rotina diária/semanal/mensal, botões de emergência).

---

# Notas da versão — v0.27.0 (não existem mais assinaturas)

**Uma decisão:** o IMPACTO deixa de ser um SaaS por mensalidade (ADR-341). Não há plano pago, trial,
checkout, reajuste, paywall nem cobrança recorrente. O valor de estar na plataforma é alcançar
recursos, demonstrar e comprovar evidência; a receita da plataforma nasce da **operação financiada**,
não do acesso.

**O que isso virou em software:**

1. **Inventário antes de apagar** — cada ocorrência de assinatura/trial/preço/plano/checkout/paywall
   classificada KEEP / MIGRATE / DEPRECATE / DELETE (`docs/execution/SUBSCRIPTION_INVENTORY.md`);
   tudo o que caiu foi arquivado em `legacy_subscription_archive` antes do DROP.
2. **Pacotes de capacidades** — planos sem preço nem periodicidade, obtidos por concessão, convênio,
   voucher de concessão, licença da administração ou contrato avulso/parcelado (`/conta/acesso`).
3. **Camada econômica da operação** — 5% do valor financiado = 3,5% taxa de serviço da plataforma +
   1,5% participação de autoria do proponente, só quando contratualmente elegível, nunca automática.
   Percentuais do catálogo versionado (Pricing Version 2027.02), congelados no acordo, recusados se
   vierem do cliente.
4. **Um aporte só, direcionado** — a matriz de distribuição diz quem recebe, quanto e para qual
   chave PIX informada no contrato; transferência registrada por quem paga, confirmada por quem
   recebe; instrução ≠ custódia (ADR-343); livro econômico append-only com estorno obrigatório.
5. **Reconhecimento só na quitação** — entregas aceitas + repasses confirmados; trajetória pública
   cumulativa em contagens e datas, nunca valores; nada se ganha por pagar a plataforma.
6. **Torre MASTER** (`/controladoria/torre`) — GMV × camada registrada/devida/paga, participação,
   marketplace sem percentual, uso, contratos, a receber, banco "DADO FINANCEIRO NÃO CONECTADO",
   captura de valor "NÃO MEDIDO" sem denominador. GMV ≠ receita.
7. **Cartões do dia, selos e trajetória** na página inicial e no perfil público; simulação de 24
   meses derivada de hipóteses declaradas (`24_MONTH_FINANCIAL_MODEL.md`), conferida por teste.

**Números:** 895 operações, 221 telas, 48 motores (VERDE 35 · AMARELO 13 · VERMELHO 0), 67 migrações,
324 tabelas (323 com RLS, 675 políticas, 0 FORCE), 10 regras de monetização (0 ativas; 5 recusadas),
15 jornadas / 244 passos / 0 falha, 805 visitas de tela / 221 rotas / 0 falha. Regressão completa:
`FINAL_EXECUTION_REPORT.md` §24. **Receita real desta instalação: R$ 0,00.**

**O que esta versão NÃO entrega**, com nome: cobrança real da taxa (regra desligada até parecer
jurídico/contábil); chave PIX real da plataforma (`PLATFORM_PIX_KEY` vazia → "NÃO CONFIGURADA");
banco/provedor de pagamento (conciliação manual); nota fiscal; preço de contrato (negociado); tag
enviada ao GitHub (proxy). Detalhes em `FINAL_EXECUTION_REPORT.md` §25–26, `FINAL_EXECUTION_AUDIT.md`
e `EXTERNAL_INTEGRATIONS.md`.

---

# Notas da versão — v0.26.0 (a tese econômica virou produto)

**Uma tese:** o IMPACTO é infraestrutura de confiança, inteligência e execução do ecossistema de
impacto; a monetização é consequência do valor gerado, não cobrança por acesso. Utilidade real, não
dependência artificial.

**O que isso virou em software:**

1. **Contrato como regra de operação** — cláusulas no acordo assinado (taxa, quem paga, modo, prazo
   de aceite em dias úteis, contestação), congeladas após o rascunho; versão imutável; obrigações
   derivadas (entregar, aceitar, pagar) com prazo; aceite a quatro olhos no banco; mudar o contrato
   cria versão nova e invalida a aprovação anterior.
2. **Matriz de distribuição sem custódia** — calculada na origem e gravada com hash: R$ 100.000 com
   3% → R$ 100.000 ao projeto + R$ 3.000 de taxa (ou 97.000/3.000 no modo descontado). A taxa é
   cobrança própria da plataforma ao financiador, nunca descontada de dinheiro em trânsito, e só
   cobrável com a regra `contract.platform_service_fee` ativa — que nasce desligada, sem percentual
   fixo (o percentual é do contrato) e com carta legal amarela. GMV ≠ receita.
3. **Torre de controle do financiador** (`/torre`) — meu capital → onde está → para quem → para quê
   → executado → evidência → o que mudou → atrasos → riscos → o que preciso decidir (com o link da
   tela onde se decide).
4. **Torre territorial do governo** (`/torre-territorial`) — território → programas → editais → OSCs
   → projetos → recursos → indicadores declarados × validados → atrasos → territórios descobertos;
   só projetos publicados, k-anonimato ≥ 3.
5. **"Projeto IMPACTO Ready"** — estado verificável, não selo: 15 critérios com a tabela e a
   contagem que sustentam cada um, desconhecido ≠ zero, hash reproduzível, mesmo resultado para dono
   e financiador.

**Números:** 894 operações, 220 telas, 45 motores, 65 migrações, 325 tabelas (324 com RLS, 677
políticas), 10 regras de monetização (0 ativas), 14 jornadas / 195 passos / 0 falha, 796 visitas de
tela / 0 falha. Regressão completa: ver `FINAL_EXECUTION_REPORT.md` §24.

**O que esta versão NÃO entrega**, com nome: cobrança real da taxa (parecer pendente); nota fiscal;
varredura que grave obrigação vencida no razão; snapshot histórico do Ready; Ready como entrada do
match; nível de identidade por organização; tag enviada ao GitHub (proxy). Detalhes em
`FINAL_EXECUTION_REPORT.md` §25–26 e `FINAL_EXECUTION_AUDIT.md`.

---

# Notas da versão — v0.18.0 (impacto contextualizado)

**Uma tese:** impacto não é quantidade; impacto é resultado contextualizado. "50 pessoas numa comunidade indígena
remota" não é automaticamente menos impacto que "5.000 pessoas num centro urbano".

**O que isso custou, de propósito:** sem denominador declarado com fonte, data e método, **não existe número
normalizado** — a resposta é "indisponível" com o motivo, nunca uma estimativa. A avaliação de equidade **não produz
nota**, e a comparação entre dois projetos devolve `comparable: false` com os motivos, **nunca um veredito**.

**Oito entregas:**

1. **Equidade e contexto** — sete métodos de normalização, denominador versionado com fonte obrigatória, barreiras
   com escada de prova (declarada → documentada → com evidência).
2. **Território** — catálogo com `from_official_load` separando carga oficial de conhecimento da plataforma; perfil
   territorial que mostra o **não medido** com o mesmo peso do medido; dois importadores que exigem fonte.
3. **Referenciais** — 19 registrados (ODS, ESG, GRI, ISSB, TCFD, TNFD, IRIS+, SROI, MCDA, LCA e outros), escada de
   relação de seis degraus que **para em `audited`**; `certified` é recusado por gatilho.
4. **Materialidade** — três lentes, limiar declarado, `is_material` **derivada**.
5. **Integridade de alegação** — 11 regras determinísticas com léxico público; situação **derivada** (não existe
   coluna de situação); revisão humana por **convite nomeado** de outra organização.
6. **Reputação** — seis dimensões, **sem nota única**; organização nova começa **sem medida**; órgão público recebe
   perfil de governança; pessoa física não tem perfil público; contestação aparece no perfil.
7. **Selos** — critério avaliado **em SQL**; a aplicação não tem INSERT na concessão; definição versionada e
   imutável; revogação como fato novo; **zero definições embarcadas**.
8. **Formulários inteligentes e responsabilidade** — sugestão com procedência que **nunca sobrescreve** em silêncio;
   responsável × papel × escopo × período × decisão × **versão**, separado da assinatura.

**Números:** 1.223 testes (0 falhas, 26 pulados), 815 operações, 285 tabelas, 32 migrações, 70 rotas novas.

**O que esta versão NÃO entrega**, com nome: as 169 metas oficiais dos ODS e os dados do IBGE (a rede do ambiente
alcança só registros de pacote; estrutura e importadores prontos); mapeamento para GRI/ISSB/IRIS+ (decisão de
produto **e** jurídica); nenhuma definição de selo publicada; nenhuma arte de selo; decaimento por idade nas
dimensões de reputação; detecção de conluio.

**Próxima fase:** design, agora com o modelo de impacto decidido.

---

# Release notes — v0.17.0

## v0.17.0 — Camada econômica, legal e de pagamento

**Resumo:** a plataforma passou a saber **quem paga, por quê, e o que ela ainda não pode cobrar**. A rodada inverte a
ordem do roteiro a pedido do proprietário — monetização, pagamento e auditoria legal **antes** do design — e
implementa uma tese só: **o proponente não pode ser o pagador principal.**

### Para quem usa

- **Entrada gratuita, de forma permanente.** Cadastro, perfil, criação de projeto, descoberta de oportunidades,
  participação na rede e acompanhamento básico são gratuitos e seguem gratuitos. O plano chama-se "OSC — gratuito"
  porque é isso que ele é. Atingir um limite técnico não tira o acesso ao que já foi criado.
- **Programa**, para quem financia: a carteira, as chamadas, os indicadores e as necessidades de território num
  lugar só — com **gasto** e **comprovado** em colunas separadas, a força declarada de cada elo da cadeia de
  resultado, e a lacuna territorial com a qualidade da evidência que a sustenta.
- **Onze documentos legais** publicados como minuta, cada um dizendo em letras o que a plataforma **não** faz.
- **O que a plataforma entregou** passou a ser um registro próprio, separado do que ela cobrou.

### O que você vai ver escrito, e é verdade

- **`PRODUCTION PAYMENT NOT CONFIGURED`** em toda a área de pagamento. Não há provedor contratado, então **nenhuma
  cobrança real foi processada** — e cada cobrança de teste aparece marcada como simulada, em cada linha, não só no
  resumo.
- **Nenhuma receita ativa.** Nove regras cadastradas, nenhuma liberada: cinco esperam parecer jurídico e quatro
  foram recusadas.
- **Nenhum aceite de termos é registrável.** As minutas não passaram por advogado(a), e o banco recusa registrar
  aceite de rascunho — porque "o usuário aceitou os termos" dito sobre um rascunho é afirmação falsa com aparência
  de prova.
- **Nenhuma estimativa de "horas economizadas".** Sem linha de base declarada com fonte, data e método, o produto
  mostra as contagens que mediu e deixa a estimativa em branco.

### Para quem decide

O que falta para faturar **não é software**: parecer jurídico, provedor de pagamento contratado e contador para
nota fiscal. A lista completa, com o que cada item destrava, está em `MONETIZATION_LEGAL_MATRIX.md` §5 e em
`RELEASE_READINESS.md` §5.

**961 testes, 749 operações, 253 tabelas, 24 migrações.** Um limite declarado: o feed do financiador ficou mais
lento (1,87–2,04 s, folga de 1,2× até o orçamento) e a correção já está nomeada.

## v0.16.0 — IMPACT NETWORK CORE

**Resumo:** a plataforma deixou de ser um lugar com projetos e passou a ser **infraestrutura de impacto** — onde
quem precisa, quem financia, quem executa e quem fiscaliza participam do **mesmo ciclo**, cada um com o seu ambiente
de trabalho, sem quatro aplicações separadas.

**Para a organização que executa:** uma Área de trabalho que diz **o que fazer agora** — não um painel de números.
Anuncia o projeto no marketplace, recebe propostas, aceita e a relação nasce formalizada. No fim do período, presta
contas no mesmo lugar: escreve o relatório, e os **números vêm do que foi lançado** (indicadores, marcos,
evidências) — não há campo para digitar "atendemos 400 pessoas".

**Para quem financia:** descobre projetos, lê a **prontidão** em seis dimensões *com a explicação do que falta*,
acompanha em lista privada, conversa **sempre com contexto**, propõe, e depois recebe a prestação de contas e aceita
ou pede ajuste. E a plataforma nunca diz "investido" quando só houve intenção — intenção, compromisso e transação
são três coisas distintas, com nomes distintos.

**Para o profissional:** página pública própria em **`impacto.app/@seunome`**, com registro profissional conferido e
experiência que só aparece **depois** de a organização citada confirmar. Recebe propostas de serviço e mentoria.

**Para o governo:** registra necessidades do território, publica edital, propõe convênio, acompanha execução e
analisa relatório. O indicador do território se move com o resultado.

**Para toda a equipe:** cada evolução, mudança de etapa ou documento anexado **avisa quem está envolvido** — não só
quem é dono. Catorze grupos de aviso, com preferência por grupo e por canal, e um aviso por fato (nunca dois).

**Também entrou:**

- **Rede visível e controlada:** 22 tipos de relação, cada uma com cinco níveis possíveis de visibilidade — e
  bloquear, favoritar e acompanhar são **sempre privados**. A existência de uma relação nunca implica que ela seja
  pública.
- **Marketplace** onde só o que está publicado aparece, com um único lugar no código que decide isso.
- **Escada de moderação** de dez degraus com regra, motivo, prazo e **direito de contestar** — julgado por quem não
  aplicou. Nada automático, e banimento nunca como primeira resposta.
- **Preço com regra escrita:** 14 dias de teste com o produto completo, **US$ 1,99/mês nos 3 primeiros meses
  pagos**, depois US$ 19,99/mês ou US$ 179,88/ano (equivalente a US$ 14,99/mês), com o total sempre visível e
  imposto declarado no checkout. Aumento de preço exige **30 dias de aviso**; o preço nunca muda em silêncio.
- **Vocabulário comum** (taxonomias versionadas no banco, não listas soltas em cada tela).

**O que esta versão NÃO entrega:** cobrança real (não há conta, chave nem preço no provedor — a plataforma **recusa
cobrar** em vez de inventar), camada de design, aplicativo em loja, notificação no aparelho e validação de segurança
por terceiro. O pacote de Design System "Convergência" **não foi recebido**, e as seções que dependiam dele não
foram executadas. Tudo nomeado em `RELEASE_READINESS.md` §5.

**Números:** 788 testes (0 falhas) · 704 operações de API · 231 tabelas · 17 migrações · 27 telas novas.

**Leia:** `IMPACT_NETWORK_ARCHITECTURE.md`, `DESIGN_HANDOFF_FINAL.md`, `FINAL_IMPACT_NETWORK_HARDENING_REPORT.md`.

---

## v0.15.0 — Núcleo do produto

**Resumo:** as seis peças (ideia, diagnóstico, projeto, documento, match, acompanhamento) passaram a ser **um
sistema**, compartilhando o mesmo vocabulário de evidência — com fonte, data e frescura —, as mesmas versões de
motor e a mesma trilha encadeada por hash. A ideia não é apagada ao virar projeto; a máquina de 17 situações é dado
no banco; o diagnóstico separa FATO, INFERÊNCIA, RECOMENDAÇÃO e **DESCONHECIDO**; a montagem de documento recusa
gerar incompleto dizendo o que falta e exige quatro olhos para aprovar. 673 testes, 625 operações, 205 tabelas.
Documentos: `CORE_PRODUCT_ARCHITECTURE.md`, `FINAL_PRE_DESIGN_HARDENING_REPORT.md`.

---

## v0.14.0 — Confiança, identidade e assinatura digital
**Resumo:** documento assinado na plataforma passou a ser **conferível por qualquer pessoa autorizada**, sem conta: pelo
código impresso ou pelo QR Code, em `/verificar`. A página responde se o documento é genuíno, **qual versão foi
assinada**, se a integridade permanece intacta, quem assinou e se foi revogado.
- **Para quem recebe o documento:** confere em segundos, sem login, e vê se existe versão mais nova.
- **Para quem assina:** assinatura em duas camadas (senha + código de uso único por e-mail) amarrada à versão exata do
  conteúdo — se o documento muda, o código deixa de valer.
- **Para a organização:** cadeia de custódia de cada documento, revogação com motivo visível, acordos assinados por todas
  as partes com acompanhamento das entregas, identidade e credencial profissional conferidas por pessoas da equipe.
- **Também entrou:** taxonomia ODS/ESG/determinantes sociais, idioma e tema por usuária, financiamento em cotas com
  campanha pública ("faltam N cotas"), tabela de honorários que só publica com fonte e data, georreferência com
  consentimento, diagnóstico guiado em 8 etapas e exportação em docx, xlsx, odt, ods, xml e PDF com QR.
- **O que NÃO é:** **não há assinatura qualificada (ICP-Brasil ou gov.br)**, nem biometria, nem prova de vida, nem SMS,
  nem carimbo de Autoridade de Carimbo de Tempo. Tudo isso depende de contratação externa e a plataforma **recusa com
  mensagem explicando**, em vez de fingir. "Credencial verificada" significa **documento conferido pela equipe** — a
  plataforma não consulta conselho profissional on-line. Os emblemas oficiais da ONU **não acompanham** a plataforma.
- **Atenção a integrações:** `POST /v1/signatures` passou a exigir o campo `code`. Quem assinava com senha apenas precisa
  pedir o código antes (`POST /v1/signatures/challenge`).
- Leia `PUBLIC_VERIFICATION.md` e `FINAL_TRUST_HARDENING_REPORT.md`.

## v0.13.0 — Integration Hub (fundação)
**Resumo:** a plataforma passou a conversar com sistemas externos por uma camada própria, desacoplada: conexões por ambiente, credenciais cifradas que a API nunca devolve, mapeamento de campos, correspondência de ID externo com conflito explícito, jobs idempotentes com repetição e disjuntor, webhooks de entrada e saída assinados, importação CSV/XLSX com aprovação humana, exportação e um painel que responde “qual integração está quebrada agora”.
- **Para quem contrata:** dá para conectar um ERP (Senior, TOTVS) ou qualquer API REST sem mexer no núcleo do produto, e trocar de fornecedor sem reescrever o sistema.
- **Para a equipe:** 36 rotas novas, 13 tabelas, 9 provedores no catálogo com **maturidade honesta**, 76 testes novos (468 no total).
- **O que NÃO é:** **nenhuma integração foi executada contra um sistema externo real** — tudo foi provado contra dublê. Nenhum provedor está homologado. Integração com governo exige credenciamento e o adapter **recusa agir** enquanto isso. SFTP não foi implementado. E **não existe nenhuma tela** — a interface é a próxima etapa.
- Leia `INTEGRATION_HUB.md` e `FINAL_INTEGRATION_HARDENING_REPORT.md`.

## v0.12.0 — Central de Conhecimento
**Resumo:** hub de ajuda (guias, busca, ajuda contextual, biblioteca, FAQ, assistente ancorado), Academia com quiz e certificado não oficial, eventos, suporte com SLA, parcerias, demonstração, solicitação de teste, boletim e CMS editorial com quatro olhos. **Não há conteúdo oficial real publicado** — só exemplos rotulados.
- **Quem usa:** qualquer pessoa pode buscar, ler guias públicos, ver eventos/cursos, pedir demonstração, propor parceria e assinar o boletim (com confirmação por e-mail). Quem entrou salva checklists, faz cursos, abre chamados e se inscreve em eventos.
- **Equipe:** `/admin/central` (editor escreve; revisor aprova e publica — outra pessoa). Suporte atende pela fila com SLA.
- **Avisos por e-mail** agora saem para cobrança, suporte e eventos (respeitando `/ajuda/preferencias`).
- **O que NÃO é:** o assistente não usa IA generativa; certificados não são oficiais; SLA inicial é hipótese; preços e Stripe real continuam pendentes. Veja `KNOWLEDGE_HUB.md` §4.1.
- Atualização: aplicar a migração `0009`; configurar o worker para o job `hub_ops`; opcionalmente `kb-import` para criar rascunhos.

---


**Resumo v0.11.0:** monetização completa sobre o billing existente — níveis FREE/PLUS/PREMIUM/GOV, trial de 14 dias FULL sem cartão, cobrança mensal/anual por Stripe (webhooks seguros), vouchers, licenças e convênios, tudo com preço/desconto/direitos decididos no servidor. **Preços ainda não definidos e Stripe ainda não homologado** (`docs/billing.md`).
## Para qualquer organização
- Ao se cadastrar você recebe **14 dias de acesso FULL, sem cartão**. Você pode cancelar a qualquer momento: o acesso FULL continua até o fim do teste, **nenhuma cobrança é feita**, e depois a conta passa ao plano gratuito — seus dados e histórico financeiro permanecem.
- Página **Plano e cobrança** (`/conta/plano`): mensal/anual com a economia real, valor final calculado pelo servidor, voucher, código de convênio, cancelar/manter assinatura, faturas e portal de pagamento.
- Falha de pagamento: aviso claro, sem corte imediato e sem perda de dados.
## Para a administração
- Vouchers de desconto (%/valor/100%/permanente), convênios (código + vagas + plano/desconto, ativação por 2º admin), licenças com origem e revogação, trial concedido com motivo, preço do plano — tudo auditado.
## Limites desta versão
Sem preços definidos, a contratação online é recusada. Stripe só foi simulado em testes. Avisos apenas dentro da plataforma.


**Resumo:** fecha as pendências da camada institucional do v0.10.0 que podiam ser resolvidas sem infraestrutura externa. Nada aqui é parecer jurídico nem certificação governamental.

## Para OSCs, OS, OSCIP e coletivos
- Abas novas em **Instituição**: *OS / OSCIP* (qualificações, autoridade, áreas, alertas de validade, próximos passos), *Instrumentos* (contratos de gestão e termos — **declarados** até a administração verificar) e *Formalização e mentoria* (trilha de 11 etapas e pedido de mentoria humana).
- Qualificações aceitam **áreas de atuação**.
## Para financiadores
- Estimativa fiscal de um projeto mostra, **em separado**, se a OSC proponente está elegível institucionalmente.
- Nas soluções, **“Ver rede de relações”**: autoria, território, ODS, temas, soluções relacionadas e demanda agregada (sem identificar organizações).
## Para a administração
- Filas de **instrumentos** e de **mentoria** no painel institucional (testadas no navegador com MFA real).
## Limites honestos
- Trilha, catálogos e regras seguem como hipótese sem revisão jurídica; IA sobre documentos **não existe**; Android/iOS não construídos; sem linter além de `tsc`/`compileall`.

---
# Release notes — v0.10.0 (anterior)

**Resumo:** adiciona a **camada institucional do terceiro setor**: a plataforma passa a distinguir o que a organização *é* (natureza jurídica), o que *declara* e o que *comprovou* (qualificações e documentos), em que **situação** está e se **pode concorrer a uma oportunidade específica** — sempre com explicação, fonte e o que falta, e sem prometer recurso nem benefício fiscal.

## Para OSCs e coletivos
- Página **Instituição**: natureza jurídica, qualificações (declaradas × verificadas), documentos (AUSENTE · PENDENTE DE VALIDAÇÃO · VALIDADO · EXPIRADO · REJEITADO), maturidade 0–6 e "o que falta".
- Coletivos sem CNPJ podem se cadastrar e participar do que não exige CNPJ.
- Verificar elegibilidade para um edital: 5 estados, com requisito a requisito.
## Para financiadores, empresas e governo
- Critérios institucionais em editais e perfil do financiador; match mostra **bloqueios explicados**.
- Biblioteca de soluções com filtros por natureza jurídica, qualificação verificada, modalidade e prontidão para financiamento.
## Para a administração
- Fila de qualificações e documentos; regras e catálogos com rascunho → revisão → aprovação (por outra pessoa) → publicação.
## O que mudou de comportamento
- Certificação exigida por edital só é aceita se **verificada** pela administração.
## Limites honestos
- Catálogos e regras iniciais são classificação da plataforma, **sem revisão jurídica**; sem integração com bases governamentais; badges não são certificação governamental.

---
# Release notes — v0.9.0 (anterior)

**Resumo:** além do fluxo OSC → edital/fundo → candidatura → execução → prestação de contas (v0.7.0) e dos módulos de impacto, compras, pagamentos registrados, risco, rede, mapa e relatórios (v0.8.0, incluído), esta versão traz a **Biblioteca de Soluções de Impacto**: um banco inteligente de ideias, projetos, metodologias, tecnologias sociais e projetos acadêmicos.

## Biblioteca de Soluções
- **Buscar por intenção**: "artes caps", "projeto idosos", "tenho R$ 250 mil para saúde mental no MT" — o sistema mostra o que entendeu e **por que** cada resultado apareceu.
- **Entender a confiança**: cada solução mostra quem declarou, o que tem evidência, o que foi validado e o que foi apenas autodeclarado. Ideia nunca vira case; "comprovado" só com revisão da administração.
- **Agir**: comparar 2–4 soluções, combinar, "quero algo como este", adaptar para meu território, desenvolver uma ideia (rascunho que exige revisão humana), pedir informações/contato/replicação, declarar interesse de financiamento (identidade privada por padrão), replicar e ter a replicação confirmada pelo autor.
- **Financiadores**: tese de investimento, match explicável e recomendações (personalização só com consentimento).
- **Administração**: fila de verificação, revisão de evidências, validação de resultados, remoção e contestações de autoria.

## Números reais
API 306 operações · 105 tabelas · 207 políticas RLS · 182 testes · busca p95 ≈ 474 ms com 5.000 soluções sintéticas (local).

## Limites (leia)
Sem embeddings (tesauro + FTS + trigramas) · IA opcional e **não usada** na busca/copiloto · pesos de relevância são hipóteses · todos os dados são DEMO · nada foi publicado (web/lojas) · textos legais são minutas [VALIDAR JURÍDICO] · fiscal sem regras aprovadas · pagamentos são registro, sem custódia.

## Atualização
Instale do zero (`ENVIRONMENT_SETUP.md`); migrações 0001–0005 aplicam em sequência. Não há dados legados a migrar. Histórico de versões em `history/`.
