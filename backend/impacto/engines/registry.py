"""Registro dos motores operacionais da Plataforma.

POR QUE ESTE ARQUIVO EXISTE

Os documentos desta rodada pedem IA como **motor operacional, não chatbot**. Isso é fácil de afirmar
num documento e impossível de conferir depois. Então a afirmação virou dado: cada motor é declarado
aqui com módulo, função, natureza, versão, rotas, o que produz e **o que ele nunca decide** — e há
teste que confere linha por linha contra o código:

* a função declarada tem de existir e ser chamável;
* a versão declarada tem de bater com a constante do módulo;
* as rotas declaradas têm de existir no roteador;
* um motor declarado determinístico **não pode** importar o gateway de IA;
* e o conjunto de pontos do código que chamam o modelo tem de ser EXATAMENTE o conjunto declarado
  como `llm_assisted`. É essa última regra que impede um chatbot novo entrar de carona sem que
  ninguém perceba.

O ESTADO REAL, HOJE

São três os pontos do produto que chamam modelo de linguagem, todos em `api/ai_routes.py`, todos
sobre uma base determinística que continua valendo se o modelo falhar, e todos devolvendo rascunho
para revisão humana. Os dois "assistentes" (`/v1/help/assistant` e `/v1/solutions/assistant`) **não**
chamam modelo: respondem por extração do conteúdo cadastrado e devolvem `ai_used: False`.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

#: Natureza de um motor. A distinção importa porque muda o que se pode prometer:
#: - `deterministic`: mesma entrada, mesma saída, auditável linha a linha;
#: - `grounded_retrieval`: responde por extração do conteúdo cadastrado, sem gerar texto;
#: - `llm_assisted`: um modelo reescreve ou complementa, SOBRE base determinística, como rascunho.
KINDS = ("deterministic", "grounded_retrieval", "llm_assisted")


@dataclass(frozen=True)
class Engine:
    key: str
    name: str
    module: str
    entrypoint: str
    kind: str
    produces: str
    never: str
    group: str
    version: str | None = None
    version_attr: str = "ENGINE_VERSION"
    routes: tuple[str, ...] = ()
    notes: str = ""
    config: tuple[str, ...] = field(default=())
    #: Rotas deste motor que são PÚBLICAS de propósito. Declarar aqui é assumir a exposição; a
    #: revisão de segurança global continua sendo a do teste de arquitetura.
    public_routes: tuple[str, ...] = ()


ENGINES: tuple[Engine, ...] = (
    # ------------------------------------------------------------------ prontidão
    Engine(
        key="readiness", name="Prontidão da organização e do projeto",
        module="impacto.network.readiness", entrypoint="evaluate", kind="deterministic",
        version="readiness@1.0.0", group="prontidão",
        routes=("/v1/readiness/purposes", "/v1/readiness/snapshots", "/v1/readiness/history"),
        produces="Seis notas de 'pronto para quê' (documentação, projeto, captação, governança, "
                 "execução, evidência), faixa, critérios conferidos e impedimentos.",
        never="Não diz que a organização vai ser aprovada, e não inventa critério ausente: o que "
              "falta aparece como impedimento, não como nota baixa sem explicação.",
        notes="`snapshot()` grava em tabela append-only e alimenta o Value Ledger."),
    Engine(
        key="funding_readiness", name="Prontidão de captação de uma solução",
        module="impacto.engines.institutional.readiness", entrypoint="compute",
        kind="deterministic", version=None, group="prontidão",
        routes=("/v1/solutions/{solution_id}", "/v1/solutions/search"),
        produces="Prontidão de captação da solução, com nota só quando a confiança passa de 0,6.",
        never="Abaixo da confiança mínima devolve nota nula em vez de número frágil."),

    # ------------------------------------------------------------------ compatibilidade
    Engine(
        key="match", name="Compatibilidade OSC ↔ oportunidade",
        module="impacto.engines.match.engine", entrypoint="evaluate", kind="deterministic",
        version="match-engine@1.2.0", group="compatibilidade",
        routes=("/v1/calls", "/v1/calls/recommended", "/v1/feed/projects", "/v1/feed/compare"),
        config=("config/match_weights.json", "config/taxonomy.json"),
        produces="Elegibilidade (elegível / requer revisão / bloqueada) SEPARADA de nota e de "
                 "confiança, com por-que-combina, por-que-não, riscos e dados ausentes.",
        never="Plano, voucher e pagamento não entram no cálculo (ADR-008), e o pacote não importa "
              "o módulo de cobrança — há teste de arquitetura conferindo."),
    Engine(
        key="professional_match", name="Compatibilidade profissional ↔ necessidade",
        module="impacto.engines.match.professional", entrypoint="evaluate", kind="deterministic",
        version="professional-match@1.0.0", group="compatibilidade",
        routes=("/v1/professional/opportunities", "/v1/needs/{need_id}/professionals"),
        produces="Compatibilidade entre profissional e necessidade do projeto.",
        never="Em categoria regulada, sem registro no conselho não há compatibilidade."),
    Engine(
        key="solution_match", name="Aderência da solução à tese do financiador",
        module="impacto.engines.match.solution", entrypoint="evaluate", kind="deterministic",
        version="solution-match@1.0.0", group="compatibilidade",
        routes=("/v1/solutions/{solution_id}/match", "/v1/solutions/recommendations"),
        produces="Aderência entre solução cadastrada e tese declarada do financiador.",
        never="Não promete aporte nem decide financiamento: devolve ADERÊNCIA à tese declarada "
              "pelo financiador, que é uma leitura, não um compromisso de ninguém."),
    Engine(
        key="recommendation", name="Próxima ação recomendada",
        module="impacto.network.recommendation", entrypoint="compute", kind="deterministic",
        version="recommendation@1.0.0", group="compatibilidade",
        routes=("/v1/recommendations", "/v1/recommendations/refresh"),
        produces="A próxima ação a tomar, cada uma com razão e evidência rastreável (qual match, "
                 "qual versão de diagnóstico).",
        never="Recomendação não é match: não vira nota de compatibilidade."),

    # ------------------------------------------------------------------ conformidade
    Engine(
        key="diagnostic", name="Diagnóstico de lacunas",
        module="impacto.core.diagnostic", entrypoint="analyse", kind="deterministic",
        version="diagnostic-engine@1.0.0", group="conformidade",
        routes=("/v1/readiness", "/v1/diagnoses/{diagnosis_id}/analysis", "/v1/diagnostic-engine"),
        produces="Diagnóstico que separa FATO (evidência com fonte e data), INFERÊNCIA (lacuna "
                 "apontada por regra) e RECOMENDAÇÃO (ação), com completude por dimensão.",
        never="Sem dado, responde 'desconhecido'. Nunca palpite apresentado como fato."),
    Engine(
        key="lifecycle", name="Ciclo de vida do projeto",
        module="impacto.core.lifecycle", entrypoint="transition", kind="deterministic",
        version=None, group="conformidade",
        routes=("/v1/projects/{project_id}/lifecycle", "/v1/projects/{project_id}/transitions",
                "/v1/projects/{project_id}/timeline"),
        produces="Situação atual, transições permitidas e histórico imutável encadeado por hash.",
        never="Transição fora do grafo é recusada pelo BANCO, não pela interface — a máquina de "
              "estados é dado em `project_status_graph`."),
    Engine(
        key="eligibility", name="Elegibilidade institucional",
        module="impacto.engines.institutional.eligibility", entrypoint="evaluate",
        kind="deterministic", version="institutional-eligibility@1.0.0", group="conformidade",
        routes=("/v1/institutional/eligibility",),
        produces="Estado de elegibilidade, o que falta por requisito e as regras e fontes usadas "
                 "(código, versão, citação, URL e data de consulta).",
        never="Ausência de regra produz PENDENTE, nunca 'elegível'. Conjunto fechado de nove tipos "
              "de requisito: tipo novo exige código novo, não configuração solta."),

    # ------------------------------------------------------------------ documento
    Engine(
        key="document_classification", name="Classificação de documento",
        module="impacto.engines.ai.local", entrypoint="classify_document", kind="deterministic",
        version=None, group="documento",
        routes=("/v1/documents", "/v1/ai/classify-document/{document_id}"),
        produces="Tipo sugerido do documento, confiança, alternativas, validade extraída e CNPJs "
                 "encontrados.",
        never="Apesar de morar no pacote de IA, **não chama modelo**: é casamento de palavra-chave e "
              "regex, local, e devolve `human_review_required`. A sugestão nunca classifica sozinha."),
    Engine(
        key="document_assembly", name="Montagem de documento a partir de modelo",
        module="impacto.core.assembly", entrypoint="generate", kind="deterministic",
        version="document-assembly@1.0.0", group="documento",
        routes=("/v1/document-assemblies", "/v1/document-assemblies/{assembly_id}/generate",
                "/v1/document-assemblies/{assembly_id}/review"),
        produces="Documento final (PDF, DOCX ou ODT) montado com dados do banco — ou a recusa "
                 "explícita com a lista do que falta.",
        never="Não gera documento com campo obrigatório vazio: recusa com 409 e diz o que falta. "
              "Aprovação em quatro olhos garantida por CHECK no banco."),

    # ------------------------------------------------------------------ evidência e relatório
    Engine(
        key="evidence", name="Evidência, frescor e confiança",
        module="impacto.core.evidence", entrypoint="decay_confidence", kind="deterministic",
        version=None, group="evidência",
        produces="Frescor de cada evidência e a confiança resultante, que decai com a idade do dado.",
        never="Não transforma ausência de evidência em evidência fraca: ausência é ausência."),
    Engine(
        key="impact_report", name="Relatório de impacto por período",
        module="impacto.network.impact_report", entrypoint="gather", kind="deterministic",
        version=None, group="evidência",
        routes=("/v1/impact-updates/gather", "/v1/impact-updates",
                "/v1/impact-updates/{update_id}/transition"),
        produces="Relatório cujos números são COLHIDOS pelo banco (`app_impact_metrics()`), com "
                 "campo de limitações e revisão por quem apoiou.",
        never="O motor não consegue escrever os números: `metrics`, `milestones` e `evidence_count` "
              "estão em `guard_columns`. E quem criou não pode revisar."),
    Engine(
        key="report_center", name="Central de relatórios",
        module="impacto.services.reports", entrypoint="build", kind="deterministic",
        version=None, group="evidência",
        routes=("/v1/report-center", "/v1/report-center/{rtype}"),
        produces="Relatório executivo, técnico, financeiro, de evidência, ODS, ESG, auditoria ou "
                 "conselho, com linguagem controlada ('reportado' × 'validado').",
        never="Não é rating ESG nem prova de causalidade, e o texto não chama correlação de impacto."),

    # ------------------------------------------------------------------ fiscal
    Engine(
        key="fiscal", name="Estimativa fiscal",
        module="impacto.engines.fiscal.engine", entrypoint="evaluate", kind="deterministic",
        version="fiscal-engine@1.0.0", group="fiscal",
        routes=("/v1/fiscal/estimates", "/v1/fiscal/rules"),
        produces="Por mecanismo: REGRA (com fonte oficial e vigência), ELEGIBILIDADE PROVÁVEL, "
                 "ESTIMATIVA (teto) e a exigência de VALIDAÇÃO PROFISSIONAL.",
        never="Avalia só regra aprovada por dois revisores distintos e vigente na data. Nunca diz "
              "'economia garantida', e não entra no cálculo de compatibilidade (ADR-011)."),

    # ------------------------------------------------------------------ busca
    Engine(
        key="help_search", name="Busca na Central de Conhecimento",
        module="impacto.engines.knowledge.search", entrypoint="score", kind="deterministic",
        version="help-search@1.0.0", group="busca",
        routes=("/v1/help/search", "/v1/help/context"),
        config=("config/help_synonyms.json",),
        public_routes=("/v1/help/search", "/v1/help/context",),
        produces="Resultados ordenados por texto completo, título, tópico, contexto e público.",
        never="Não há embeddings nem modelo: a camada semântica é vocabulário de sinônimos."),
    Engine(
        key="help_assistant", name="Assistente da Central de Conhecimento",
        module="impacto.services.knowledge", entrypoint="assistant", kind="grounded_retrieval",
        version=None, group="busca", routes=("/v1/help/assistant",),
        public_routes=("/v1/help/assistant",),
        produces="Resposta extraída de artigo ou FAQ cadastrado, com fonte, versão e confiança — ou "
                 "a recusa honesta de que não há informação suficiente na base.",
        never="**Não é chatbot.** Nenhum modelo gera texto: a resposta é concatenação de campos do "
              "banco, devolvida com `grounded: true` e `ai_used: false`. Abaixo da confiança mínima "
              "devolve resposta nula e oferece abrir chamado."),
    Engine(
        key="solution_assistant", name="Copiloto de soluções",
        module="impacto.services.solutions", entrypoint="search", kind="grounded_retrieval",
        version=None, group="busca",
        routes=("/v1/solutions/assistant", "/v1/solutions/search"),
        produces="Soluções realmente cadastradas que atendem à intenção interpretada.",
        never="Também não gera texto: devolve `ai_used: false` e a lista do que existe no acervo."),

    # ------------------------------------------------------------------ soluções
    Engine(
        key="solution_scoring", name="Pontuação de solução",
        module="impacto.engines.solutions.scoring", entrypoint="relevance", kind="deterministic",
        version=None, group="soluções", config=("config/solution_weights.json",),
        produces="Maturidade, evidência, replicabilidade e relevância, cada uma com versão própria.",
        never="Falta de dado devolve nulo, não número inventado."),
    Engine(
        key="intent_parser", name="Interpretação de intenção de busca",
        module="impacto.engines.solutions.intent", entrypoint="parse", kind="deterministic",
        version="intent-parser@1.0.0", version_attr="PARSER_VERSION", group="soluções",
        routes=("/v1/solutions/intent/parse",),
        produces="Território, orçamento, prazo e tema extraídos da frase de busca.",
        never="Não chama modelo: é gramática e tesauro."),
    Engine(
        key="solution_combine", name="Combinação de soluções",
        module="impacto.engines.solutions.combine", entrypoint="combine", kind="deterministic",
        version="combine@1.0.0", group="soluções",
        routes=("/v1/solutions/combine", "/v1/solutions/combinations"),
        produces="Combinação coerente de soluções complementares.",
        never="Não combina o que não é complementar só para preencher a resposta."),
    Engine(
        key="solution_adaptation", name="Adaptação de solução a outro território",
        module="impacto.engines.solutions.adaptation", entrypoint="adapt", kind="deterministic",
        version="adaptation@1.0.0", group="soluções",
        routes=("/v1/solutions/{solution_id}/adapt",),
        produces="O que muda para levar a solução a outro contexto.",
        never="Se o autor não autorizou adaptação, devolve bloqueado; sem base, 'dado insuficiente'."),

    # ------------------------------------------------------------------ econômico (v0.17.0)
    Engine(
        key="result_chain", name="Cadeia de resultado",
        module="impacto.economics.programs", entrypoint="result_chain", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/projects/{project_id}/result-chain",),
        produces="A cadeia insumo → atividade → produto → resultado com a FORÇA DECLARADA de cada "
                 "elo, separando elo forte de elo fraco.",
        never="Não promove hipótese a evidência: devolve nota dizendo que elo declarado não é "
              "resultado comprovado."),
    Engine(
        key="territorial_gap", name="Lacuna territorial da carteira",
        module="impacto.economics.programs", entrypoint="territorial_gap", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/territorial-gap",),
        produces="Onde a carteira não chega, com a qualidade da evidência que sustenta cada lacuna.",
        never="Lacuna apontada por necessidade sem fonte vem marcada como tal."),
    Engine(
        key="value_ledger", name="Registro de valor entregue",
        module="impacto.economics.value_ledger", entrypoint="summary", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/value/summary", "/v1/value/events"),
        produces="O valor que a Plataforma entregou, por tipo de evento, separado da cobrança.",
        never="Não estima tempo economizado sem linha de base declarada com fonte, data e método: "
              "a tabela de linhas de base **nasce vazia** e o evento fica 'sem linha de base'."),

    # ------------------------------------------------------------------ contrato e torres (v0.26.0)
    Engine(
        key="contract_rules", name="Contrato como regra de operação",
        module="impacto.trust.contract_rules", entrypoint="compute_allocation", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/signed-agreements/{agreement_id}/allocation", "/v1/signed-agreements/{agreement_id}/new-version",
                "/v1/agreements/pending"),
        produces="Do acordo assinado: versão imutável, obrigações derivadas (entregar, aceitar, pagar) com prazo "
                 "pela política de aceite, e a matriz de distribuição (bruto, projeto, taxa da plataforma, terceiros) "
                 "com hash — a taxa calculada na origem e paga por quem o contrato indica, em cobrança própria.",
        never="Não custodia nem movimenta dinheiro (ADR-284): calcula, instrui e concilia. Não desconta taxa de "
              "dinheiro em trânsito. Não cobra a taxa com a regra comercial desligada (sem carta legal verde): "
              "registra 'não cobrável' e o motivo. Nenhuma parte aceita a própria entrega."),
    Engine(
        key="control_tower", name="Torres de controle (financiador e governo)",
        module="impacto.network.control_tower", entrypoint="funder", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/control-tower/funder", "/v1/control-tower/government"),
        produces="Financiador: meu capital → onde está → para quem → finalidade → executado → evidência → mudou → "
                 "atrasos → riscos → decisões, a partir dos registros existentes. Governo: território → programas → "
                 "editais → OSCs → projetos → recursos → indicadores declarados × validados → atrasos → lacunas.",
        never="Não decide nada: aponta para a tela do registro. Não mostra saldo (não existe). Governo só vê "
              "projetos publicados e nunca linha a linha abaixo de 3 projetos (k-anonimato); risco de projeto "
              "sai como contagem, o registro é da OSC."),
    # ------------------------------------------------------------------ camada econômica (v0.27.0, ADR-341)
    Engine(
        key="economic_layer", name="Camada econômica da operação (matriz, repasses, participação, quitação)",
        module="impacto.trust.economy", entrypoint="instruct_payouts", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/signed-agreements/{agreement_id}/payouts", "/v1/payouts/{payout_id}/transfers",
                "/v1/payout-transfers/{transfer_id}/confirm", "/v1/payout-transfers/{transfer_id}/reject",
                "/v1/payouts/{payout_id}/reconcile", "/v1/projects/{project_id}/participations",
                "/v1/participations", "/v1/participations/{participation_id}/accept", "/v1/economic-rules",
                "/v1/signed-agreements/{agreement_id}/value"),
        produces="Do acordo de financiamento vigente: uma instrução de repasse por linha da matriz (projeto, plataforma 3,5%, "
                 "proponente 1,5%) com a chave PIX informada no contrato; registro da transferência por quem paga, confirmação "
                 "por quem recebe, conciliação com nota; participação de autoria com estados e aceite pelo proponente; "
                 "operação quitada quando toda entrega está aceita e todo repasse devido confirmado; livro econômico "
                 "append-only (quem → pagou → quem → quanto → por quê → regra → versão).",
        never="Não custodia nem move dinheiro: o aporte é único e direcionado pelo financiador (ADR-284). Nada vira pago por "
              "existir registro — só quem recebe confirma. Percentual nunca em código: catálogo versionado congelado no acordo. "
              "Participação nunca automática. Reconhecimento nunca por pagar a plataforma."),
    Engine(
        key="master_tower", name="Torre MASTER / financeira do proprietário",
        module="impacto.economics.master_tower", entrypoint="master", kind="deterministic",
        version=None, group="econômico",
        routes=("/v1/control-tower/master",),
        produces="GMV × camada da plataforma (registrado, devido, pago) por mês; participação; marketplace sem percentual; "
                 "uso de IA/API; contratos avulsos; a receber; banco; captura de valor (razão medida ou NÃO MEDIDO).",
        never="Não inventa saldo: banco é 'DADO FINANCEIRO NÃO CONECTADO'; GMV nunca se soma à receita; razão de captura "
              "sem denominador é NÃO MEDIDO, não zero; não há MRR porque não há assinatura."),
    Engine(
        key="ai_usage_control", name="Controle de uso e custo da IA (autoriza → reserva → executa → liquida)",
        module="impacto.engines.ai.usage_control", entrypoint="preview", kind="deterministic",
        version="usage-control@1.0", group="ia",
        routes=("/v1/ai/center", "/v1/ai/operations", "/v1/ai/preview", "/v1/ai/executions", "/v1/ai/executions/{execution_id}",
                "/v1/ai/executions/{execution_id}/cancel", "/v1/ai/credit-packs", "/v1/ai/credit-orders", "/v1/ai/credit-orders/{order_id}",
                "/v1/ai/credit-orders/{order_id}/cancel", "/v1/ai/sponsorships", "/v1/ai/sponsorships/{sponsorship_id}",
                "/v1/ai/sponsorships/{sponsorship_id}/close", "/v1/webhooks/payments/{provider}", "/v1/admin/ai/finance",
                "/v1/admin/ai/credit-orders", "/v1/admin/ai/credit-orders/{order_id}/confirm", "/v1/admin/ai/credit-orders/{order_id}/approve-pilot",
                "/v1/admin/ai/operations", "/v1/admin/ai/credit-packs", "/v1/admin/ai/quota-policies/{key}"),
        public_routes=("/v1/webhooks/payments/{provider}",),
        produces="Prévia com custo em créditos, custo externo estimado ou 'sem preço', fonte de custeio (gratuita → patrocínio → cota → "
                 "comprado) e saldo; execução com estados e trilha; débito só em sucesso; pedidos de crédito (piloto/real), patrocínio "
                 "com prestação de contas agregada; painel financeiro medido × NÃO MEDIDO.",
        never="Nunca debita sem execução concluída; nunca credita compra sem pagamento confirmado por webhook assinado ou conciliação "
              "com referência; nunca migra patrocínio esgotado para cobrança do beneficiário; o frontend nunca decide preço, saldo ou fonte.",
        config=("PAYMENT_WEBHOOK_SECRET", "PLATFORM_PIX_KEY")),
    Engine(
        key="similarity", name="Originalidade, similaridade, complementaridade e integridade do financiamento",
        module="impacto.engines.similarity.engine", entrypoint="compare", kind="deterministic",
        version="similarity@1.0", group="ia",
        routes=("/v1/projects/{project_id}/similarity", "/v1/similarity/analyses", "/v1/similarity/analyses/{analysis_id}",
                "/v1/similarity/analyses/{analysis_id}/dispute", "/v1/admin/ai/disputes", "/v1/admin/ai/disputes/{dispute_id}/review"),
        produces="Oito dimensões separadas (texto, escopo, público, território, período, orçamento, financiamento, indicadores) com score, "
                 "fatores, qualidade do dado e limitação; leituras separadas (textual ≠ escopo ≠ territorial ≠ duplicidade de despesa ≠ "
                 "complementaridade ≠ reprodução textual como INDÍCIO); confiança; recomendações; contestação com revisão humana; cache por "
                 "insumo e versão; contagem k-anônima do que o solicitante não enxerga.",
        never="Nunca conclui plágio, fraude ou duplicidade; nunca bloqueia financiamento, altera reputação, match ou ranking; nunca compara "
              "projeto invisível ao solicitante; nunca sai da instalação (faixa 3); o custo da análise não altera o resultado."),
    Engine(
        key="today_cards", name="Para você hoje (cartões e contadores do menu)",
        module="impacto.network.today", entrypoint="today", kind="deterministic",
        version=None, group="rede",
        routes=("/v1/me/today",),
        produces="Cartões derivados de registros reais (pendências, obrigações de acordo, participações a aceitar, repasses a "
                 "confirmar, transferências a registrar, recomendações, trajetória) e contadores por tela para o menu dinâmico.",
        never="Não cria estado novo. Não vende nada: nenhum cartão de plano, assinatura ou upgrade. Não conta no navegador."),
    Engine(
        key="impacto_ready", name="Estado verificável 'Projeto IMPACTO Ready'",
        module="impacto.network.control_tower", entrypoint="ready", kind="deterministic",
        version="impacto-ready@1.0.0", version_attr="READY_ENGINE", group="prontidão",
        routes=("/v1/projects/{project_id}/ready",),
        produces="Quinze critérios (identidade, organização, documentos, diagnóstico, orçamento, necessidades, ODS, "
                 "indicadores, evidências, responsáveis, riscos, profissionais, governança, histórico, prestação de "
                 "contas), cada um com a tabela e a contagem que o sustenta, e o hash da avaliação.",
        never="Não é selo pago nem nota. Desconhecido não é zero: critério não legível fica 'unknown' e o estado "
              "'ready' exige todos atendidos. Quem não enxerga o projeto recebe 404, não um estado."),

    # ------------------------------------------------------------------ IA (os três pontos)
    Engine(
        key="ai_structure_need", name="Estruturação de necessidade (IA)",
        module="impacto.engines.ai.gateway", entrypoint="AiGateway.structure_need",
        kind="llm_assisted", version=None, group="ia",
        routes=("/v1/ai/structure-need",),
        produces="Projeto estruturado a partir de necessidade em texto livre: base determinística de "
                 "`local.structure_need()`, com o modelo sobrescrevendo APENAS campos de texto.",
        never="JSON inválido do modelo é descartado e vale a base local. Devolve `draft: true` e "
              "`human_review_required: true`. Não decide elegibilidade."),
    Engine(
        key="ai_draft", name="Reescrita de rascunho (IA)",
        module="impacto.engines.ai.gateway", entrypoint="AiGateway.draft", kind="llm_assisted",
        version=None, group="ia", routes=("/v1/ai/draft",),
        produces="O mesmo rascunho montado localmente, reescrito para clareza.",
        never="Instrução ao modelo manda preservar TODOS os números, nomes e marcações "
              "`[COMPLETAR]` e proíbe acrescentar dado. Saída curta demais é descartada."),
    Engine(
        key="ai_summarize", name="Resumo de projeto (IA)",
        module="impacto.engines.ai.gateway", entrypoint="AiGateway.summarize", kind="llm_assisted",
        version=None, group="ia", routes=("/v1/ai/summarize-project",),
        produces="Resumo do projeto em até quatro frases para o financiador.",
        never="Qualquer falha cai no resumo local. Nada é enviado sem redação de dado pessoal."),

    # ------------------------------------------------------------------ v0.20.0: os que existiam
    # e não estavam declarados. A auditoria desta rodada encontrou DOZE módulos que decidem algo
    # sobre organização ou projeto e não apareciam no registro — inclusive toda a camada de
    # impacto. Um registro incompleto é pior que registro nenhum: ele dá a impressão de inventário.
    Engine(
        key="firstrun", name="Primeiro acesso: o que já existe e o que falta",
        module="impacto.core.firstrun", entrypoint="state", kind="deterministic",
        version="firstrun@1.0.0", group="orientação",
        routes=("/v1/firstrun", "/v1/projects/{project_id}/context-return"),
        produces="Para cada uma das 12 áreas: o que é, o que já existe, o que falta, o que a área "
                 "devolve e se a tela existe — tudo a partir de CONTAGEM REAL no banco.",
        never="Não finge que uma tela existe: `screen_status` diz `to_be_designed` quando a tela "
              "ainda não foi feita. E `context_return` NUNCA é ranking entre organizações."),
    Engine(
        key="claim_integrity", name="Integridade de afirmação de impacto",
        module="impacto.impact.claims", entrypoint="check", kind="deterministic",
        version="claim-integrity@1.0.0", group="impacto",
        routes=("/v1/claims", "/v1/claims/{claim_id}/check", "/v1/claims/{claim_id}/review",
                "/v1/claims/rules"),
        produces="Rodada de verificação de uma afirmação, com o que sustenta e o que não sustenta.",
        never="Não declara a afirmação verdadeira nem falsa: devolve o que a evidência suporta. "
              "Revisão só existe por convite de quem declarou — não há revisão não solicitada, "
              "que seria canal para pressionar concorrente."),
    Engine(
        key="equity_context", name="Contexto de equidade e normalização",
        module="impacto.impact.equity", entrypoint="assess", kind="deterministic",
        version="equity-context@1.0.0", group="impacto",
        routes=("/v1/projects/{project_id}/equity", "/v1/projects/{project_id}/equity/assessments",
                "/v1/equity/compare", "/v1/equity/catalog"),
        produces="Avaliação de equidade com denominador declarado, método e barreiras.",
        never="Não compara projetos sem denominador comum declarado, e não transforma contexto em "
              "nota de desempenho."),
    Engine(
        key="reputation", name="Reputação por dimensão observada",
        module="impacto.impact.reputation", entrypoint="profile", kind="deterministic",
        version="reputation-dimensions@1.0.0", group="impacto",
        routes=("/v1/reputation/me", "/v1/organizations/{org_id}/reputation",
                "/v1/reputation/disputes", "/v1/reputation/dimensions"),
        produces="Valor, confiança e faixa por dimensão, com as observações que os sustentam.",
        never="Não produz nota única nem ranking, e NENHUMA faixa vem de denúncia: só infração "
              "apurada e concluída entra. Reputação aqui é leitura do observado, não punição.",
        notes="A leitura corrente é SEMPRE calculada; o snapshot existe para mostrar evolução."),
    Engine(
        key="seals", name="Selos: regra pública, concessão e revogação",
        module="impacto.impact.seals", entrypoint="award", kind="deterministic",
        version="seal-rules@1.0.0", group="impacto",
        routes=("/v1/seals/definitions", "/v1/seals/evaluate", "/v1/seals/awards",
                "/v1/seals/awards/{award_id}"),
        produces="Concessão com os critérios conferidos no banco, ou a RECUSA registrada com o "
                 "critério que faltou.",
        never="Não concede por tempo de casa nem por pagamento, e não apaga selo revogado: a "
              "revogação é fato novo. `recheck()` reavalia e revoga o que deixou de valer.",
        notes="v0.20.0: `recheck()` existia e nunca era chamada — agora é a tarefa `seal_recheck`."),
    Engine(
        key="report_integrity", name="Apuração de denúncia em quatro níveis",
        module="impacto.network.complaints", entrypoint="conclude", kind="deterministic",
        version="report-integrity@1.0.0", group="confiança",
        routes=("/v1/reports", "/v1/reports/vocabulary", "/v1/conta/denuncias",
                "/v1/admin/reports/queue"),
        produces="O trâmite DENÚNCIA → SUSPEITA → INFRAÇÃO APURADA → CONSEQUÊNCIA, com direito de "
                 "manifestação e recurso.",
        never="Denúncia NÃO tem efeito por si: nenhuma medida, nenhum ponto de reputação. Só "
              "`substantiated`, decidido por pessoa com fundamentação escrita, autoriza medida — "
              "e isso é travado por gatilho no banco, não por disciplina de quem programa. A "
              "plataforma registra ENCAMINHAMENTO jurídico; nunca declara crime."),
    Engine(
        key="deadline_sweep", name="Varredura de prazos",
        module="impacto.ops.deadlines", entrypoint="sweep", kind="deterministic",
        version="deadline-sweep@1.0.0", group="operação",
        produces="Avisos em D-30, D-7 e D-1 sobre marcos, chamadas, propostas, selos e marcos de "
                 "instrumento.",
        never="Não estima data nenhuma: varre apenas prazos DECLARADOS pelas próprias organizações.",
        notes="Tarefa `deadline_sweep`. Até a v0.20.0 a plataforma registrava cinco prazos e "
              "varria um."),
    Engine(
        key="risk_signals", name="Sinais de risco operacional",
        module="impacto.services.risk", entrypoint="scan", kind="deterministic",
        version=None, group="confiança",
        routes=("/v1/admin/risk/signals", "/v1/admin/risk/scan", "/v1/risk-rules",
                "/v1/projects/{project_id}/risks"),
        produces="Sinais de regra (documento repetido, evidência reaproveitada, despesa acima do "
                 "item, preço fora da curva, contas relacionadas) e nível de risco.",
        never="Sinal de regra NÃO é acusação nem fraude comprovada: é indício que pede olhar "
              "humano. Nenhum sinal aplica medida sozinho."),
    Engine(
        key="compliance_checks", name="Conferências de conformidade",
        module="impacto.services.compliance", entrypoint="run_checks", kind="deterministic",
        version=None, group="confiança",
        routes=("/v1/compliance", "/v1/organizations/{org_id}/compliance",
                "/v1/admin/compliance-reviews"),
        produces="Conferências com estado e o que falta para cada uma.",
        never="Não declara a organização idônea nem apta: diz o que foi conferido e o que não foi. "
              "Desde a v0.20.0 só denúncia APURADA entra na pontuação; denúncia aberta apenas "
              "informa."),
    Engine(
        key="enforcement_ladder", name="Escada de medidas de moderação",
        module="impacto.network.enforcement", entrypoint="apply", kind="deterministic",
        version=None, group="confiança",
        routes=("/v1/admin/enforcement", "/v1/admin/enforcement/history",
                "/v1/admin/enforcement/{action_id}/lift"),
        produces="Dez degraus de medida, com as capacidades que cada um restringe e prazo próprio.",
        never="Nenhum degrau é aplicado por máquina: medida é sempre decisão de pessoa, e exige "
              "denúncia apurada. Medida vencida expira (tarefa `enforcement_expiry`) — suspensão "
              "'de 30 dias' não vale para sempre."),
    Engine(
        key="glossary_drift", name="Detector de divergência de vocabulário",
        module="impacto.core.glossary", entrypoint="missing", kind="deterministic",
        version=None, group="vocabulário",
        routes=("/v1/public/glossary",),
        public_routes=("/v1/public/glossary",),
        produces="O que o código usa e o glossário não documenta (`undocumented`), e o que o "
                 "glossário documenta e o código não usa mais (`stale`).",
        never="Não inventa rótulo para termo não documentado: a lacuna FALHA a suíte."),
    Engine(
        key="retention_policy", name="Conferência da política de retenção",
        module="impacto.core.retention", entrypoint="links", kind="deterministic",
        version=None, group="governança",
        routes=("/v1/privacy/retention",),
        produces="Classe EFETIVA de cada vínculo, conferida contra os gatilhos reais do banco.",
        never="Não promete apagar o que o banco impede de apagar: tabela append-only aparece como "
              "`append_only`, e a plataforma declara que NÃO remove organização."),
    Engine(
        key="data_quality", name="Qualidade do dado declarado",
        module="impacto.impact.quality", entrypoint="assess", kind="deterministic",
        version="data-quality@1.0.0", group="impacto",
        routes=("/v1/projects/{project_id}/data-quality", "/v1/data-quality/vocabulary"),
        produces="Sete tipos de achado sobre o DADO — não preenchido, contado duas vezes, não "
                 "fecha, parado no tempo, fora da unidade, contraditório, sem como conferir — cada "
                 "um apontando para a linha exata.",
        never="NÃO transforma baixa qualidade de dado em baixo desempenho do projeto, e não produz "
              "nota, faixa nem percentual. Nada daqui alimenta reputação, selo ou compatibilidade: "
              "projeto em território sem dado público produz dado incompleto, e pontuar isso faria "
              "a plataforma medir orçamento de monitoramento e chamar o resultado de impacto."),
    Engine(
        key="risk_levels", name="Inventário de risco por operação",
        module="impacto.core.risk_levels", entrypoint="inventory", kind="deterministic",
        version=None, group="governança",
        routes=("/v1/admin/risk-levels",),
        produces="Nível (LOW/MEDIUM/HIGH/CRITICAL) de cada uma das operações da API, o controle "
                 "humano que cada nível exige e se esse controle existe no código.",
        never="Não bloqueia nada em tempo de execução: o bloqueio está nas políticas do banco, nos "
              "gatilhos e nas verificações de cada rota. Aqui se responde ONDE o controle precisa "
              "existir — e o teste confere se ele existe."),
)

#: Os ÚNICOS pontos do código autorizados a chamar o modelo. O teste de arquitetura compara esta
#: lista com uma varredura do código: ponto novo sem declaração FALHA a suíte.
AI_CALL_SITES = ("impacto/api/ai_routes.py",)

#: Controles que valem para TODA chamada ao modelo (implementados em `engines/ai/gateway.py`).
AI_CONTROLS = (
    "cota mensal por organização, com erro 402 quando estoura",
    "redação de dado pessoal (CPF, e-mail, telefone, CEP, RG) ANTES de qualquer envio externo",
    "limite de tamanho de contexto",
    "timeout e duas retentativas, com queda para o provedor local em qualquer exceção",
    "registro de uso sem conteúdo: só hash da entrada, tamanhos, tokens, latência e nº de redações",
    "custo estimado só quando há preço declarado — a tabela de preços de IA nasce vazia",
    "toda saída marcada como rascunho que exige revisão humana",
)


def resolve(engine: Engine):
    """Devolve o objeto chamável declarado, ou levanta. Usado pelo teste e pela rota de registro."""
    mod = importlib.import_module(engine.module)
    obj = mod
    for part in engine.entrypoint.split("."):
        obj = getattr(obj, part)
    return obj


def describe() -> dict:
    groups: dict[str, list[dict]] = {}
    for e in ENGINES:
        groups.setdefault(e.group, []).append({
            "key": e.key, "name": e.name, "kind": e.kind, "version": e.version,
            "module": e.module, "entrypoint": e.entrypoint, "routes": list(e.routes),
            "produces": e.produces, "never": e.never, "notes": e.notes, "config": list(e.config),
        })
    by_kind = {k: sum(1 for e in ENGINES if e.kind == k) for k in KINDS}
    return {
        "groups": groups,
        "total": len(ENGINES),
        "by_kind": by_kind,
        "ai_call_sites": list(AI_CALL_SITES),
        "ai_controls": list(AI_CONTROLS),
        "note": ("IA aqui é motor operacional, não conversa: dos "
                 f"{len(ENGINES)} motores, {by_kind['deterministic']} são determinísticos, "
                 f"{by_kind['grounded_retrieval']} respondem por extração do conteúdo cadastrado sem "
                 f"gerar texto, e {by_kind['llm_assisted']} chamam modelo — sempre sobre base "
                 "determinística que continua valendo se o modelo falhar, e sempre devolvendo "
                 "rascunho para revisão humana."),
    }
