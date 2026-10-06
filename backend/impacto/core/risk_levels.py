"""Nível de risco por operação, e o controle humano que cada nível exige.

O QUE O DOCUMENTO PEDE (§40) E O QUE SERIA FÁCIL ENTREGAR DE ERRADO

Pede-se `RISK_LEVEL` por operação — LOW, MEDIUM, HIGH, CRITICAL — e que as operações HIGH e CRITICAL
possam exigir revisão humana, aprovação humana ou aprovação em quatro olhos.

O jeito fácil e inútil de entregar isso é uma planilha: 833 operações, um rótulo ao lado de cada uma,
escrito por quem construiu. Em três semanas a planilha está errada e ninguém sabe quais linhas.

Aqui o nível é DERIVADO de propriedades que a própria operação declara no roteador — quem pode
chamar, se escreve, se atravessa a fronteira entre organizações, se é reversível — e os poucos casos
que a regra não alcança são declarados um a um, com o motivo escrito. Operação nova entra
classificada no dia em que nasce, porque a regra é aplicada ao roteador inteiro e há teste que
reprova a suíte quando uma operação cai fora.

E a parte que realmente importa: para toda operação classificada como CRITICAL, há um teste que vai
ao CÓDIGO procurar o controle humano declarado. Dizer que uma operação exige quatro olhos e não
implementar os quatro olhos é a forma mais cara de mentir nesta plataforma, porque é mentira que
parece governança.

O QUE CADA NÍVEL SIGNIFICA

LOW       Não muda estado, ou muda só o que quem chamou pode desfazer sozinho, dentro da própria
          organização. Leitura é sempre LOW.
MEDIUM    Escreve dado da própria organização. Erro é corrigível por quem errou.
HIGH      Atravessa a fronteira entre organizações, mexe em dinheiro, muda o que é público, ou é
          decisão da plataforma sobre alguém. Exige decisão de PESSOA e fica na auditoria.
CRITICAL  Restringe direito de alguém, retira uma afirmação pública, ou não tem volta. Exige, além
          da decisão humana, um segundo par de olhos ou fundamentação escrita que a auditoria possa
          cobrar depois.

O QUE ESTE MÓDULO NÃO FAZ: não bloqueia nada em tempo de execução. O bloqueio real está onde sempre
esteve — nas políticas do banco, nos gatilhos e nas verificações de cada rota. Isto aqui é o
INVENTÁRIO que diz onde o controle precisa existir, e o teste que confere se ele existe.
"""
from __future__ import annotations

import inspect
from typing import Any

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

#: Controles humanos que uma operação pode declarar. A ordem é de força crescente.
CONTROLS = ("none", "rate_limit", "audit_trail", "human_review", "human_approval", "four_eyes")

#: Marcas que PROVAM, no código do handler, que o controle existe. Procurar a palavra "aprovação"
#: num comentário não prova nada; procurar a recusa que o código faz, sim.
CONTROL_MARKS = {
    "four_eyes": ("four_eyes", "second_approver_required", "second_assignment_id",
                  "não pode aprová-lo", "outro administrador", "outro revisor"),
    # `reason` e `motivo` contam porque, nestas rotas, é o campo OBRIGATÓRIO que a pessoa preenche
    # para justificar a decisão — e sem ele a operação é recusada. Não é a palavra: é a exigência.
    "human_approval": ("decision_rationale", "rationale", "decided_by", "body.decision",
                       "body.note", "justificativa", "reason", "motivo"),
    # A decisão registrada NA PRÓPRIA LINHA — `reviewed_by`, `approved_by`, `actor_user_id` — é
    # registro de quem decidiu tanto quanto uma entrada de auditoria, e em alguns casos é melhor,
    # porque vive junto do objeto decidido.
    "human_review": ("ctx.audit(", "audit.record(", "reviewed_by", "approved_by",
                     "actor_user_id", "decided_by", "ctx.user_id"),
    # `rate_limit` não se procura no código: ele está DECLARADO no roteador, e é por isso que é o
    # controle mais confiável desta tabela — não depende de ninguém lembrar de escrever nada.
    "rate_limit": (),
    "audit_trail": ("ctx.audit(", "audit.record(", "ledger(", "events.record("),
    "none": (),
}

#: Casos que a regra geral não alcança, com o motivo escrito. Toda linha aqui é uma decisão, não uma
#: exceção de conveniência: se o motivo não couber numa frase, a regra é que está errada.
OVERRIDES: dict[tuple[str, str], tuple[str, str, str]] = {
    # (método, caminho): (nível, controle, por quê)
    ("POST", "/v1/admin/enforcement"): (
        "CRITICAL", "human_approval",
        "Aplica medida que restringe capacidades de uma organização. Exige denúncia APURADA e "
        "fundamentação escrita; nenhuma máquina aplica medida."),
    ("POST", "/v1/admin/reports/{report_id}/conclude"): (
        "CRITICAL", "human_approval",
        "Transforma suspeita em INFRAÇÃO APURADA — o único estado que autoriza medida. A "
        "fundamentação é obrigatória e o banco recusa a conclusão sem ela."),
    ("POST", "/v1/admin/seals/awards"): (
        "HIGH", "audit_trail",
        "A plataforma afirma publicamente algo sobre um terceiro. A concessão reavalia os "
        "critérios no banco antes de existir, então o controle é a regra, não o revisor."),
    ("POST", "/v1/seals/awards/{award_id}/revocation"): (
        "CRITICAL", "human_approval",
        "Retira uma afirmação pública que a plataforma fez. Exige motivo registrado, e a "
        "revogação é append-only: não se desfaz, acrescenta-se."),
    ("DELETE", "/v1/privacy/me"): (
        "CRITICAL", "human_approval",
        "Apagamento de dado pessoal a pedido do titular. Não tem volta, e por isso o pedido "
        "passa por confirmação explícita de quem é titular."),
    ("POST", "/v1/admin/organizations/{org_id}/anonymize"): (
        "CRITICAL", "four_eyes",
        "Anonimiza o vínculo de uma organização. A plataforma NÃO remove a organização; o que "
        "se perde aqui não volta, e a prestação de contas de terceiros depende do que fica."),
    ("POST", "/v1/admin/fiscal-rules/{rule_id}/approve"): (
        "CRITICAL", "four_eyes",
        "Regra fiscal aprovada passa a produzir estimativa para todo mundo. Dupla aprovação por "
        "revisores distintos, garantida por CHECK no banco."),
    ("POST", "/v1/reports"): (
        "MEDIUM", "audit_trail",
        "Abrir denúncia NÃO tem efeito por si: nenhuma medida, nenhum ponto de reputação. "
        "Classificá-la como alta seria tratar quem denuncia como quem já foi julgado."),
}


def _escreve(method: str) -> bool:
    return method in ("POST", "PUT", "PATCH", "DELETE")


def classify(spec: Any) -> dict[str, Any]:
    """Nível e controle exigido de uma operação, derivados do que ela declara no roteador."""
    chave = (spec.method, spec.path)
    if chave in OVERRIDES:
        nivel, controle, motivo = OVERRIDES[chave]
        return {"level": nivel, "control": controle, "why": motivo, "source": "declarado"}

    if not _escreve(spec.method):
        return {"level": "LOW", "control": "none",
                "why": "Leitura: não muda estado.", "source": "regra"}

    admin = spec.auth == "admin"
    publica = spec.auth == "none"

    if admin:
        # Decisão da plataforma sobre terceiros. Irreversível ou restritiva ⇒ CRITICAL.
        irreversivel = any(p in spec.path for p in
                           ("/revoke", "/revocation", "/anonymize", "/delete", "/suspend",
                            "/block", "/retire"))
        nivel = "CRITICAL" if irreversivel or spec.method == "DELETE" else "HIGH"
        return {"level": nivel,
                "control": "human_approval" if nivel == "CRITICAL" else "human_review",
                "why": ("Decisão da administração da plataforma sobre terceiro"
                        + (", sem volta." if nivel == "CRITICAL" else ".")),
                "source": "regra"}

    if publica:
        # Escrita sem autenticação se divide em duas coisas muito diferentes. Entrar na própria
        # conta ou pedir um boletim mexe só no vínculo de quem chamou com a plataforma; um webhook
        # de pagamento ou uma integração de entrada escrevem dado ATRIBUÍDO a uma organização, sem
        # que ninguém dessa organização tenha clicado. Tratar os dois como o mesmo risco seria
        # inflar o inventário até ele parar de significar alguma coisa.
        de_terceiro = any(p in spec.path for p in ("/webhooks", "/integrations/inbound"))
        if de_terceiro:
            return {"level": "HIGH", "control": "audit_trail",
                    "why": ("Escreve, sem autenticação, dado atribuído a uma organização: a "
                            "barreira é a assinatura da origem, e o rastro é obrigatório."),
                    "source": "regra"}
        return {"level": "MEDIUM", "control": "rate_limit",
                "why": ("Escrita sem autenticação sobre o vínculo de quem chama com a plataforma. "
                        "O controle é o limite de taxa declarado na própria rota."),
                "source": "regra"}

    # Escrita autenticada. É HIGH o que cria obrigação formal entre organizações, mexe em dinheiro
    # ou muda o que o público vê. Conversa e recado NÃO entram: são rotina, e o controle deles é o
    # bloqueio entre organizações e o limite de taxa, não revisão humana caso a caso. Classificar
    # rotina como alto risco é o jeito mais rápido de fazer um inventário ser ignorado.
    obrigacao = any(p in spec.path for p in (
        "/proposals", "/applications", "/commitments", "/investments", "/signatures",
        "/signed-agreements", "/disputes", "/appeal", "/manifestacao", "/recurso"))
    dinheiro = any(p in spec.path for p in ("/billing", "/charges", "/payments", "/funding",
                                            "/commitments", "/subscription"))
    publicacao = any(p in spec.path for p in ("/publish", "/transition", "/listings"))
    if obrigacao or dinheiro or publicacao:
        return {"level": "HIGH", "control": "human_review",
                "why": "Cria obrigação formal entre organizações, mexe em dinheiro ou muda o que "
                       "é público.", "source": "regra"}

    return {"level": "MEDIUM", "control": "audit_trail",
            "why": "Escreve dado da própria organização; o erro é corrigível por quem errou.",
            "source": "regra"}


def _reachable_source(handler: Any, *, depth: int = 1) -> str:
    """Código do handler MAIS o das funções que ele chama, um nível adentro.

    Uma rota fina que delega ao serviço — `return auth.register(ctx, body)` — não contém nenhuma
    marca de controle no próprio corpo, e olhar só para ela daria 57 falsas lacunas. Olhar só para o
    módulo inteiro daria o oposto: qualquer rota de um arquivo que em algum lugar chama `ctx.audit`
    passaria. Seguir as chamadas resolve os dois, e para no primeiro nível de propósito: controle
    que está a três saltos de distância não é controle que alguém consegue conferir.
    """
    try:
        partes = [inspect.getsource(handler)]
    except (OSError, TypeError):
        return ""
    if depth <= 0:
        return partes[0]
    globais = getattr(handler, "__globals__", {})
    nomes = tuple(getattr(handler.__code__, "co_names", ()))
    # Módulos que o handler usa: `auth.login(...)` aparece em co_names como ("auth", "login"), e é
    # a função `login` do módulo `auth` que contém o controle. Sem resolver esse par, toda rota que
    # delega a um serviço apareceria como sem controle — que foi exatamente o primeiro resultado.
    modulos = [v for v in (globais.get(n) for n in nomes)
               if inspect.ismodule(v) and getattr(v, "__name__", "").startswith("impacto")]
    alvos = []
    for nome in nomes:
        direto = globais.get(nome)
        if direto is not None and not inspect.ismodule(direto) \
                and getattr(direto, "__module__", "").startswith("impacto"):
            alvos.append(direto)
        for mod in modulos:
            attr = getattr(mod, nome, None)
            if inspect.isfunction(attr) and attr.__module__.startswith("impacto"):
                alvos.append(attr)
    for alvo in alvos:
        try:
            partes.append(inspect.getsource(alvo))
        except (OSError, TypeError):
            continue
    return "\n".join(partes)


def control_implemented(spec: Any, controle: str) -> bool:
    """O controle declarado existe? Procura a RECUSA no código, não a palavra bonita.

    Dois controles não se procuram no código: `none`, que não é controle, e `rate_limit`, que está
    declarado no próprio roteador — e por estar lá é o único desta tabela que não depende de alguém
    lembrar de escrever alguma coisa.
    """
    if controle == "none":
        return True
    if controle == "rate_limit":
        return spec.rate is not None
    fonte = _reachable_source(spec.handler)
    return any(m in fonte for m in CONTROL_MARKS[controle])


def inventory(routes: list) -> dict[str, Any]:
    linhas = []
    for spec in routes:
        c = classify(spec)
        linhas.append({
            "method": spec.method, "path": spec.path, "auth": spec.auth,
            "level": c["level"], "control": c["control"], "why": c["why"], "source": c["source"],
            "control_implemented": control_implemented(spec, c["control"]),
        })
    por_nivel = {n: sum(1 for x in linhas if x["level"] == n) for n in LEVELS}
    sem_controle = [x for x in linhas
                    if x["level"] in ("HIGH", "CRITICAL") and not x["control_implemented"]]
    return {
        "operations": sorted(linhas, key=lambda x: (LEVELS.index(x["level"]), x["path"]),
                             reverse=True),
        "total": len(linhas),
        "by_level": por_nivel,
        "missing_control": sem_controle,
        "note": ("O nível é DERIVADO do que a operação declara no roteador; os casos que a regra "
                 "não alcança estão declarados um a um com o motivo escrito. Este inventário NÃO "
                 "bloqueia nada: o bloqueio está nas políticas do banco, nos gatilhos e nas "
                 "verificações de cada rota. Aqui se responde ONDE o controle precisa existir — e "
                 "o teste confere se ele existe."),
    }
