"""Primeiro acesso: o que esta área é, por que está vazia e qual é o próximo passo.

O PROBLEMA. Uma organização que acabou de se cadastrar abre a plataforma e vê ausência em quase tudo:
reputação sem medida, nenhum selo, ODS não mapeado, território sem indicador, nenhuma alegação. Isso é
honesto — e é a resposta certa, porque inventar dado para encher tela é o pior defeito possível num
produto cuja tese é evidência. Mas ausência sozinha não ajuda ninguém: a pessoa não sabe se está vendo
um erro, uma permissão que falta ou um trabalho que ela precisa fazer.

A DECISÃO DE PROJETO. O estado de primeiro acesso é CONTRATO DE API, não texto escrito na tela. A tela
pergunta ao servidor o que está vazio, por quê, o que fazer em seguida e o que se ganha ao completar —
e a resposta sai de contagem real no banco, nunca de suposição. Com isso quem desenha recebe estado e
ação em vez de inventar as duas coisas, e o teste consegue provar que nenhuma área chega vazia sem
próximo passo.

O QUE ESTE MÓDULO NÃO FAZ.
* Não cria dado de demonstração. Nenhum valor devolvido aqui é fictício.
* Não transforma contexto declarado em vantagem de ranking. Ver ``context_return``.
* Não decide permissão: ele informa o pré-requisito que falta, e quem autoriza continua sendo a rota.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..db.pq import Connection
from ..impact import equity as EQ

ENGINE_VERSION = "firstrun@1.0.0"


@dataclass(frozen=True)
class Area:
    """Uma área da plataforma e as respostas que ela deve dar quando está vazia."""

    key: str
    title: str
    what_it_is: str
    why_empty: str
    action_label: str
    action_method: str
    action_route: str
    #: rota REAL da interface, ou None quando a tela ainda não existe (a camada de design vai criá-la).
    screen: str | None
    what_you_gain: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    data_origin: str = "A própria organização informa."
    how_verified: str = "Fica como declarado até alguém de fora conferir."
    #: pré-requisitos (chaves de outras áreas) sem os quais a ação não pode ser executada
    requires: tuple[str, ...] = ()
    #: conta registros da área; recebe (conn, org_id, project_id)
    counter: Any = field(default=None, compare=False)
    #: a área só existe no escopo de um projeto
    project_scoped: bool = False


def _n(sql: str, *, project: bool = False):
    def counter(conn: Connection, org_id: str, project_id: str | None) -> int:
        if project:
            if not project_id:
                return 0
            return int(conn.scalar(sql, project_id) or 0)
        return int(conn.scalar(sql, org_id) or 0)
    return counter


AREAS: tuple[Area, ...] = (
    Area(
        key="diagnostic", title="Diagnóstico",
        what_it_is="A conversa guiada que transforma o que a organização sabe sobre o problema em problema "
                   "descrito, público afetado, causas, metas e plano — com as fontes citadas.",
        why_empty="Nenhum diagnóstico foi aberto ainda.",
        action_label="Abrir o primeiro diagnóstico",
        action_method="POST", action_route="/v1/diagnoses", screen="/diagnosticos",
        what_you_gain="Oito prontidões explicáveis (projeto, organização, captação, evidência, conformidade, "
                      "dado, governança, impacto), cada uma dizendo quais dimensões olhou e o que falta.",
        required=("necessidade declarada", "público afetado"),
        optional=("causas", "metas", "plano de ação", "riscos", "fontes de dados"),
        data_origin="A organização responde; a plataforma lê também o que já está cadastrado.",
        how_verified="Prontidão não é nota: cada dimensão aponta a evidência que a sustenta, com data.",
        counter=_n("SELECT count(*) FROM diagnoses WHERE org_id = $1"),
    ),
    Area(
        key="indicators", title="Indicadores",
        what_it_is="O que o projeto mede, com unidade, periodicidade e linha de base.",
        why_empty="O projeto ainda não tem indicador cadastrado.",
        action_label="Cadastrar o primeiro indicador",
        action_method="POST", action_route="/v1/projects/{project_id}/indicators", screen="/projetos/:id/impacto",
        what_you_gain="Sem indicador não existe medição, e sem medição nenhuma alegação de resultado se sustenta.",
        required=("indicador do catálogo ou próprio", "unidade"),
        optional=("linha de base com fonte", "meta", "periodicidade"),
        data_origin="Catálogo da plataforma ou indicador próprio da organização.",
        how_verified="O indicador é declarado; o que se verifica é cada MEDIÇÃO dele.",
        requires=("project",), project_scoped=True,
        counter=_n("SELECT count(*) FROM project_indicators WHERE project_id = $1", project=True),
    ),
    Area(
        key="evidence", title="Evidência",
        what_it_is="O arquivo, o documento ou o registro que sustenta o que o projeto afirma.",
        why_empty="Nenhuma evidência foi registrada para este projeto.",
        action_label="Registrar a primeira evidência",
        action_method="POST", action_route="/v1/projects/{project_id}/evidences", screen="/projetos/:id",
        what_you_gain="Medição com evidência anexada é o que separa resultado relatado de resultado validado — "
                      "e é a base da disciplina de evidência na reputação.",
        required=("tipo de evidência", "arquivo ou referência", "data"),
        optional=("metodologia", "responsável pela coleta"),
        data_origin="A organização envia; o cofre guarda com data e autor.",
        how_verified="Passa a contar como verificada quando alguém com competência confere e registra.",
        requires=("project",), project_scoped=True,
        counter=_n("SELECT count(*) FROM evidences WHERE project_id = $1", project=True),
    ),
    Area(
        key="equity", title="Contexto e equidade",
        what_it_is="Necessidade com fonte, barreiras que o território impõe, adicionalidade e denominador — "
                   "o que permite comparar projetos sem confundir alcance com impacto.",
        why_empty="O contexto do projeto ainda não foi declarado.",
        action_label="Declarar contexto e barreiras",
        action_method="PUT", action_route="/v1/projects/{project_id}/equity/context", screen=None,
        what_you_gain="Métodos de normalização ficam disponíveis, o sinal de impacto do match sai de "
                      "DESCONHECIDO e critérios de selo passam a ser alcançáveis. Não dá ganho de ranking.",
        required=("necessidade declarada", "adicionalidade"),
        optional=("fonte da necessidade com data", "contrafactual", "barreiras do catálogo", "denominador com fonte"),
        data_origin="A organização declara; o catálogo de barreiras é editorial da plataforma.",
        how_verified="Cada afirmação carrega sua firmeza: declarada, documentada ou evidenciada.",
        requires=("project",), project_scoped=True,
        counter=_n("SELECT count(*) FROM equity_contexts WHERE project_id = $1", project=True),
    ),
    Area(
        key="ods", title="ODS",
        what_it_is="A ligação entre o que o projeto faz e as metas dos Objetivos de Desenvolvimento Sustentável.",
        why_empty="Nenhuma meta de ODS foi mapeada para este projeto.",
        action_label="Mapear o projeto a uma meta de ODS",
        action_method="PUT", action_route="/v1/projects/{project_id}/ods-targets", screen=None,
        what_you_gain="Mapear é o primeiro degrau da escada do referencial. Alinhado NÃO é alcançado, e a "
                      "plataforma nunca converte um no outro.",
        required=("meta de ODS",),
        optional=("indicador correspondente", "justificativa do mapeamento"),
        data_origin="Catálogo oficial de ODS e metas carregado na plataforma.",
        how_verified="Começa como alinhado/mapeado; sobe a escada só com análise, publicação e conferência externa.",
        requires=("project",), project_scoped=True,
        counter=_n("SELECT count(*) FROM project_ods_targets WHERE project_id = $1", project=True),
    ),
    Area(
        key="claims", title="Alegações",
        what_it_is="O que a organização afirma publicamente sobre resultado, contribuição ou eficiência.",
        why_empty="Nenhuma alegação foi declarada.",
        action_label="Declarar uma alegação apoiada em evidência",
        action_method="POST", action_route="/v1/claims", screen=None,
        what_you_gain="Cada alegação passa por regras determinísticas e volta com a situação derivada do que "
                      "está registrado — antes de um financiador apontar a fragilidade.",
        required=("texto da alegação", "tipo", "assunto"),
        optional=("período", "indicadores citados", "evidências citadas"),
        data_origin="A organização declara.",
        how_verified="Conferência automática por regra; alegação marcada só sai com revisão de pessoa de OUTRA organização.",
        counter=_n("SELECT count(*) FROM claims WHERE org_id = $1"),
    ),
    Area(
        key="territory", title="Território",
        what_it_is="Indicadores do território onde o projeto atua, para situar a necessidade com dado externo.",
        why_empty="Nenhum indicador territorial carregado para os territórios desta organização.",
        action_label="Ver quais indicadores territoriais existem e qual território declarar",
        action_method="GET", action_route="/v1/equity/denominators", screen="/dados-territoriais",
        what_you_gain="Denominador territorial com fonte oficial é o que permite normalizar resultado "
                      "sem estimativa.",
        required=("território do projeto",),
        optional=("denominador declarado com fonte e data",),
        data_origin="Carga oficial da plataforma (com fonte e data) ou declaração da organização com fonte citada.",
        how_verified="Carga oficial traz fonte e data; declaração sem fonte não vira denominador vigente.",
        counter=_n("SELECT count(*) FROM equity_denominators WHERE org_id = $1"),
    ),
    Area(
        key="impact", title="Cadeia de impacto",
        what_it_is="A ligação explícita entre atividade, produto, resultado e impacto — cada elo com sua evidência.",
        why_empty="A cadeia de impacto do projeto ainda não foi montada.",
        action_label="Montar o primeiro elo da cadeia",
        action_method="POST", action_route="/v1/projects/{project_id}/graph/nodes", screen="/projetos/:id/grafo",
        what_you_gain="A cadeia é o que permite dizer onde a evidência existe e onde ainda é hipótese, "
                      "sem transformar mudança observada em causa comprovada.",
        required=("um nó de atividade", "um nó de resultado"),
        optional=("elo entre nós", "evidência por elo", "contrafactual"),
        data_origin="A organização monta.",
        how_verified="Cada elo diz se tem evidência registrada; elo sem evidência aparece como hipótese.",
        requires=("project",), project_scoped=True,
        counter=_n("SELECT count(*) FROM impact_nodes WHERE project_id = $1", project=True),
    ),
    Area(
        key="reputation", title="Reputação",
        what_it_is="Seis dimensões independentes sobre o RASTRO da organização na plataforma. Não existe nota única.",
        why_empty="Ainda não há observações suficientes em nenhuma dimensão: sem base, não existe valor.",
        action_label="Ver o que cada dimensão mede e quantas observações faltam",
        action_method="GET", action_route="/v1/reputation/me", screen=None,
        what_you_gain="Cada dimensão diz o que mede, o que NÃO mede e de quais sinais vem — e a banda de "
                      "confiança impede que indício fraco seja lido como recomendação.",
        required=("mínimo de observações por dimensão (varia por dimensão)",),
        optional=(),
        data_origin="Derivada do que já está registrado: medições, comprovantes, prazos, conferências.",
        how_verified="Nada é declarado pela organização. Dado de origem errado se contesta e o histórico fica.",
        counter=_n("SELECT count(*) FROM reputation_snapshots WHERE org_id = $1"),
    ),
    Area(
        key="seals", title="Selos",
        what_it_is="Reconhecimentos cujos critérios o próprio banco confere — a aplicação não tem permissão "
                   "para conceder selo.",
        why_empty="Nenhum selo concedido. Normal no começo: todo critério depende de registro que ainda não existe.",
        action_label="Ver critério por critério o que falta para cada selo",
        action_method="POST", action_route="/v1/seals/evaluate", screen=None,
        what_you_gain="A avaliação mostra exatamente qual critério falta, com o mesmo cálculo que a concessão usa.",
        required=("uma definição de selo publicada", "critérios satisfeitos no banco"),
        optional=(),
        data_origin="Definição e critérios são da plataforma; o que é conferido é o registro da organização.",
        how_verified="Conferido em SQL no momento da concessão. Pagamento não compra selo.",
        counter=_n("SELECT count(*) FROM seal_awards WHERE org_id = $1"),
    ),
    Area(
        key="governance", title="Responsabilidade",
        what_it_is="Quem responde por quê: papéis com período de mandato, e decisões que exigem duas pessoas.",
        why_empty="Nenhum papel de responsabilidade atribuído.",
        action_label="Atribuir o primeiro responsável",
        action_method="POST", action_route="/v1/responsibility/assignments", screen=None,
        what_you_gain="Decisão crítica passa a ter nome, papel e período — e assinatura deixa de ser confundida "
                      "com responsabilidade.",
        required=("pessoa", "papel", "alcance", "início do mandato"),
        optional=("base do mandato", "fim do mandato"),
        data_origin="A organização atribui.",
        how_verified="O banco recusa decisão fora do período do mandato e exige duas pessoas diferentes quando a regra pede.",
        counter=_n("SELECT count(*) FROM responsibility_assignments WHERE org_id = $1"),
    ),
    Area(
        key="match", title="Oportunidades compatíveis",
        what_it_is="A comparação explicável entre o que o projeto precisa e o que cada oportunidade oferece.",
        why_empty="Nenhuma recomendação calculada ainda.",
        action_label="Buscar oportunidades compatíveis",
        action_method="GET", action_route="/v1/calls/recommended", screen="/oportunidades",
        what_you_gain="Cada resultado vem com os sinais que somaram e os que ficaram DESCONHECIDO, com o "
                      "motivo — em vez de um número sem explicação.",
        required=("um projeto cadastrado",),
        optional=("contexto declarado", "indicadores", "orçamento", "território"),
        data_origin="Calculado pela plataforma a partir do que está registrado nas duas pontas.",
        how_verified="Sinal sem dado vale DESCONHECIDO e não conta como zero. Plano comercial não entra na conta.",
        requires=("project",),
        counter=_n("SELECT count(*) FROM match_runs WHERE viewer_org_id = $1"),
    ),
)

AREA_BY_KEY = {a.key: a for a in AREAS}


# ================================================================================= estado de primeiro acesso
def state(conn: Connection, *, org_id: str, project_id: str | None = None) -> dict:
    """Devolve, por área, se está vazia e qual é o próximo passo — com contagem real.

    ``project_id`` é opcional: sem projeto, as áreas de escopo de projeto voltam com o pré-requisito
    explícito (``blocked_by: project``) em vez de uma contagem falsa de zero.
    """
    tem_projeto = bool(project_id) or bool(conn.scalar(
        "SELECT count(*) FROM projects WHERE org_id = $1", org_id))
    areas, vazias = [], 0
    for area in AREAS:
        bloqueio = None
        if "project" in area.requires and not tem_projeto:
            bloqueio = {"requires": "project", "label": "Cadastre um projeto antes",
                        "method": "POST", "route": "/v1/projects", "screen": "projetos"}
        if area.project_scoped and not project_id:
            n, contado = None, False
        else:
            n, contado = area.counter(conn, org_id, project_id), True
        preenchida = bool(contado and n)
        if not preenchida:
            vazias += 1
        rota = area.action_route.replace("{project_id}", project_id) if project_id else area.action_route
        areas.append({
            "key": area.key,
            "title": area.title,
            "filled": preenchida,
            "count": n,
            "counted": contado,
            "what_it_is": area.what_it_is,
            "why_empty": None if preenchida else (
                "Falta o pré-requisito: " + bloqueio["label"].lower() + "." if bloqueio
                else "Esta área depende de um projeto escolhido." if not contado
                else area.why_empty),
            "next_action": {
                "label": area.action_label, "method": area.action_method, "route": rota,
                "screen": area.screen,
                "screen_status": "exists" if area.screen else "to_be_designed",
                "requires": list(area.required),
                "available": bloqueio is None and (contado or not area.project_scoped),
            },
            "blocked_by": bloqueio,
            "what_you_gain": area.what_you_gain,
            "required_fields": list(area.required),
            "optional_fields": list(area.optional),
            "data_origin": area.data_origin,
            "how_verified": area.how_verified,
        })
    return {
        "engine_version": ENGINE_VERSION,
        "project_id": project_id,
        "has_project": tem_projeto,
        "areas": areas,
        "empty_areas": vazias,
        "note": ("Ausência de dado aqui é ausência, não zero: nenhuma área devolve valor de exemplo. "
                 "Toda área vazia informa o próximo passo e o que se ganha ao completá-lo."),
    }


# ================================================================= o que declarar contexto devolve de volta
#: Chave de retorno -> o que ela significa. NENHUMA delas é vantagem de ranking ou de reputação.
RETURN_KEYS = (
    "CONTEXT_COMPLETENESS",
    "NORMALIZATION_METHODS_AVAILABLE",
    "MATCH_EXPLAINABILITY",
    "EVIDENCE_READINESS",
    "SEAL_READINESS",
    "DIAGNOSTIC_READINESS",
    "FUNDER_VISIBILITY",
    "ELIGIBILITY_VISIBILITY",
)

NO_RANKING_NOTE = (
    "Declarar contexto NÃO dá ganho de reputação, de ranking nem de exposição. O que muda é "
    "OPERACIONAL: cálculos que estavam indisponíveis passam a ser possíveis, sinais que valiam "
    "DESCONHECIDO passam a ter resposta, e critérios de selo deixam de ser inalcançáveis. "
    "'Mais contexto = mais ranking' seria o oposto da tese: premiaria quem escreve bem, não quem mede."
)


def context_return(conn: Connection, *, project_id: str, org_id: str) -> dict:
    """Mostra o que o contexto declarado DESTRAVOU e o que cada peça que falta destravaria.

    Cada item devolve ``available`` (quantos estão disponíveis agora), ``total`` e, quando algo falta,
    ``would_open``: a peça que falta e o que ela abre. É o retorno operacional do formulário mais caro
    do produto — sem virar nota.
    """
    ctx = conn.one(
        "SELECT need_statement, need_source_name, need_source_date, additionality, counterfactual,"
        " additionality_standing, additionality_evidence_id FROM equity_contexts WHERE project_id = $1",
        project_id) or {}
    proj = conn.one("SELECT visibility, budget_total_cents, territory, starts_on, ends_on,"
                    " array_length(ods, 1) AS n_ods FROM projects WHERE id = $1", project_id) or {}
    n_barreiras = int(conn.scalar("SELECT count(*) FROM project_barriers WHERE project_id = $1", project_id) or 0)
    n_ind = int(conn.scalar("SELECT count(*) FROM project_indicators WHERE project_id = $1", project_id) or 0)
    n_val = int(conn.scalar("SELECT count(*) FROM indicator_values WHERE project_id = $1"
                            " AND status = 'validated'", project_id) or 0)
    n_ev = int(conn.scalar("SELECT count(*) FROM evidences WHERE project_id = $1", project_id) or 0)
    compliance = conn.scalar("SELECT compliance_status FROM organizations WHERE id = $1", org_id)

    # ---- CONTEXT_COMPLETENESS: peças declaradas, nomeadas uma por uma. Não é nota.
    pecas = [
        ("need_statement", "necessidade declarada", bool(ctx.get("need_statement"))),
        ("need_source", "fonte da necessidade com nome e data",
         bool(ctx.get("need_source_name") and ctx.get("need_source_date"))),
        ("additionality", "adicionalidade declarada", bool(ctx.get("additionality"))),
        ("counterfactual", "contrafactual (o que aconteceria sem o projeto)", bool(ctx.get("counterfactual"))),
        ("barriers", "barreiras do território", n_barreiras > 0),
        ("denominator", "denominador vigente com fonte", False),  # preenchido abaixo
        ("indicators", "indicador cadastrado", n_ind > 0),
        ("validated_measurement", "medição validada", n_val > 0),
    ]

    # ---- NORMALIZATION_METHODS_AVAILABLE: método só existe com denominador vigente COM fonte.
    # A resolução é a do próprio cálculo (equity.methods_available): denominador de OUTRO projeto da
    # mesma organização não vale para este — a primeira versão desta rota herdava, e o teste pegou.
    met = EQ.methods_available(conn, project_id=project_id)
    disponiveis, faltantes = met["available"], met["missing"]
    pecas = [(k, lab, (bool(disponiveis) if k == "denominator" else ok)) for k, lab, ok in pecas]
    declaradas = [{"key": k, "label": lab, "declared": ok} for k, lab, ok in pecas]

    itens = [
        {"key": "CONTEXT_COMPLETENESS", "title": "Contexto declarado",
         "available": sum(1 for _k, _l, ok in pecas if ok), "total": len(pecas),
         "detail": "Peças declaradas, nomeadas uma por uma. Não é nota e não entra em nenhum cálculo de reputação.",
         "pieces": declaradas,
         "would_open": [{"missing": lab, "opens": "mais cálculos deixam de voltar 'indisponível'"}
                        for _k, lab, ok in pecas if not ok]},
        {"key": "NORMALIZATION_METHODS_AVAILABLE", "title": "Métodos de normalização disponíveis",
         "available": len(disponiveis), "total": len(EQ.METHODS),
         "detail": ("Cada método exige um denominador vigente declarado COM fonte. Sem ele o cálculo devolve "
                    "'indisponível' com o motivo — nunca uma estimativa."),
         "items": disponiveis,
         "would_open": [{"missing": f"denominador do tipo {m['denominator']}",
                         "opens": f"método “{m['label']}”"} for m in faltantes]},
    ]

    # ---- MATCH_EXPLAINABILITY: o sinal de impacto do match sai de DESCONHECIDO com contexto.
    ctx_row = conn.one("SELECT has_context, need_level, barrier_burden, additionality_score,"
                       " outcome_evidence_score, impact_evidence_score, denominator_quality, has_counterfactual"
                       " FROM project_impact_context($1)", project_id) or {}
    conhecidos = [k for k, v in ctx_row.items()
                  if k not in ("has_context", "has_counterfactual") and v is not None]
    itens.append({
        "key": "MATCH_EXPLAINABILITY", "title": "Explicabilidade do match",
        "available": len(conhecidos), "total": 6,
        "detail": ("Com contexto, o sinal de impacto do match deixa de valer DESCONHECIDO e passa a trazer "
                   "motivo. Número de beneficiários NÃO preenche este sinal: alcance não é impacto."),
        "items": conhecidos,
        "would_open": ([] if ctx_row.get("has_context") else
                       [{"missing": "contexto de impacto publicado",
                         "opens": "o sinal de impacto deixa de ser DESCONHECIDO para quem avalia de fora"}]),
    })

    # ---- EVIDENCE_READINESS e SEAL_READINESS: critérios conferidos pelo banco, um por um.
    itens.append({
        "key": "EVIDENCE_READINESS", "title": "Prontidão de evidência",
        "available": min(n_val, n_ev), "total": max(n_ind, 1),
        "detail": ("Medição validada com evidência anexada é o que separa resultado relatado de resultado "
                   "validado. Indicador sem medição não sustenta alegação de resultado."),
        "items": [{"indicators": n_ind, "validated_measurements": n_val, "evidences": n_ev}],
        "would_open": ([{"missing": "indicador cadastrado", "opens": "poder medir"}] if not n_ind else
                       [{"missing": "medição validada", "opens": "alegação de resultado sustentável"}] if not n_val else
                       [{"missing": "evidência anexada à medição", "opens": "disciplina de evidência na reputação"}]
                       if not n_ev else []),
    })

    selos = []
    for d in conn.query("SELECT id::text AS id, code, title, scope FROM seal_definitions"
                        " WHERE status = 'published' ORDER BY code, version"):
        subject = project_id if d["scope"] == "project" else org_id
        crit = conn.query("SELECT rule_code, met, detail FROM seal_evaluate($1, $2)", d["id"], subject)
        if not crit:
            continue
        selos.append({"code": d["code"], "name": d["title"], "scope": d["scope"],
                      "met": sum(1 for c in crit if c["met"]), "total": len(crit),
                      "missing": [{"rule": c["rule_code"], "detail": c["detail"]} for c in crit if not c["met"]]})
    itens.append({
        "key": "SEAL_READINESS", "title": "Prontidão para selo",
        "available": sum(1 for s in selos if s["met"] == s["total"]), "total": len(selos),
        "detail": ("A mesma avaliação que a concessão usa, critério por critério. A aplicação não tem permissão "
                   "para conceder selo: quem confere é o banco."),
        "items": selos,
        "would_open": [{"missing": m["rule"], "opens": f"selo {s['code']}"}
                       for s in selos for m in s["missing"]][:12],
    })

    # ---- DIAGNOSTIC_READINESS: existe diagnóstico? as oito prontidões vêm da análise dele.
    n_diag = int(conn.scalar("SELECT count(*) FROM diagnoses WHERE org_id = $1", org_id) or 0)
    itens.append({
        "key": "DIAGNOSTIC_READINESS", "title": "Prontidão calculável pelo diagnóstico",
        "available": 8 if n_diag else 0, "total": 8,
        "detail": ("As oito prontidões saem de GET /v1/diagnoses/{id}/analysis. Cada uma diz quais dimensões "
                   "olhou; nenhuma é nota geral do projeto."),
        "items": [{"diagnoses": n_diag}],
        "would_open": ([] if n_diag else [{"missing": "um diagnóstico aberto",
                                           "opens": "as oito prontidões explicáveis"}]),
    })

    # ---- FUNDER_VISIBILITY: o que um financiador consegue ver HOJE deste projeto.
    publicado = proj.get("visibility") == "published"
    itens.append({
        "key": "FUNDER_VISIBILITY", "title": "O que um financiador vê",
        "available": 1 if publicado else 0, "total": 1,
        "detail": ("Enquanto o projeto não está publicado, nem o contexto agregado chega a quem avalia de fora: "
                   "a função que serve esse contexto devolve vazio por projeto não publicado."),
        "items": [{"visibility": proj.get("visibility"), "aggregated_context_visible": bool(publicado and ctx_row.get("has_context"))}],
        "would_open": ([] if publicado else [{"missing": "publicar o projeto",
                                              "opens": "contexto agregado visível para quem avalia"}]),
    })

    # ---- ELIGIBILITY_VISIBILITY: o que trava elegibilidade por falta de dado (não por mérito).
    travas = []
    if compliance != "approved":
        travas.append({"missing": "cadastro institucional aprovado", "opens": "elegibilidade em editais que o exigem"})
    if not proj.get("budget_total_cents"):
        travas.append({"missing": "orçamento declarado", "opens": "comparação com a faixa do edital"})
    if not proj.get("territory"):
        travas.append({"missing": "território do projeto", "opens": "compatibilidade territorial"})
    if not (proj.get("starts_on") and proj.get("ends_on")):
        travas.append({"missing": "prazo do projeto", "opens": "compatibilidade de prazo com o edital"})
    itens.append({
        "key": "ELIGIBILITY_VISIBILITY", "title": "Elegibilidade visível",
        "available": 4 - len(travas), "total": 4,
        "detail": ("Estes quatro pontos travam a CONFERÊNCIA de elegibilidade por falta de dado, não por mérito. "
                   "Nada aqui recusa a organização: a conta simplesmente não pode ser feita."),
        "items": [{"compliance_status": compliance, "has_budget": bool(proj.get("budget_total_cents")),
                   "has_territory": bool(proj.get("territory")),
                   "has_schedule": bool(proj.get("starts_on") and proj.get("ends_on"))}],
        "would_open": travas,
    })

    return {
        "engine_version": ENGINE_VERSION,
        "project_id": project_id,
        "items": itens,
        "keys": list(RETURN_KEYS),
        "no_ranking_note": NO_RANKING_NOTE,
    }
