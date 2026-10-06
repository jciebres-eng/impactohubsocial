"""Motor de uso: contadores, alertas de 70/90/100% e teto de gasto.

A DIVISÃO DE TRABALHO COM `entitlements.check_limit`

`check_limit` continua sendo quem BLOQUEIA, por contagem ao vivo. Não é redundância: a contagem ao
vivo é a única que não pode errar, porque ela é lida no instante da ação. Um contador persistido
pode ficar para trás — uma transação que falha depois de incrementar, um job que não rodou — e um
contador atrasado que BLOQUEIA recusa trabalho legítimo.

Este módulo é a camada que AVISA e que LEMBRA. Ele sincroniza o contador a partir da mesma contagem
ao vivo, guarda o histórico (que a retenção dos registros originais apaga) e dispara os três
alertas. Se ele atrasar, a pessoa recebe o aviso tarde; não perde acesso a nada.

POR QUE 70, 90 E 100

70% é quando ainda dá para mudar de plano, redistribuir trabalho ou pedir orçamento. 90% é quando
dá para terminar o que está em curso. 100% é informação, não aviso — a pessoa já bateu. Avisar só
em 100% é avisar depois.
"""
from __future__ import annotations

THRESHOLDS = (70, 90, 100)

# Métricas medidas, com o rótulo que a pessoa lê. Declaradas aqui para que a API, a tela e os
# alertas usem a mesma lista — e para que acrescentar uma métrica sem rótulo quebre o teste em vez
# de aparecer como chave crua na interface.
METRICS = {
    "ai_requests_month": "pedidos de IA no mês",
    "active_projects": "projetos ativos",
    "programs": "programas",
    "seats": "pessoas na equipe",
    "storage_mb": "armazenamento (MB)",
    "saved_searches": "buscas salvas",
}

ACTIONS = ("warn", "hard_stop")


def _live(c, org_id: str, metric: str) -> int:
    """A contagem ao vivo de cada métrica — a MESMA que `check_limit` usa para bloquear.

    Repetir a consulta aqui seria criar a segunda cópia da regra, que é exatamente o defeito que
    esta rodada encontrou na cota de IA (bloqueio e painel contavam diferente). Então cada consulta
    abaixo é a única do sistema para aquela métrica, e os chamadores de `check_limit` passam a ler
    daqui.
    """
    if metric == "ai_requests_month":
        return int(c.scalar("SELECT ai_usage_this_month($1)", org_id) or 0)
    if metric == "active_projects":
        return int(c.scalar("SELECT count(*) FROM projects WHERE org_id = $1"
                            " AND status = ANY($2::text[])", org_id,
                            ["draft", "active", "in_execution"]) or 0)
    if metric == "programs":
        return int(c.scalar("SELECT count(*) FROM calls WHERE owner_org_id = $1"
                            " AND status IN ('draft','open')", org_id) or 0)
    if metric == "seats":
        return int(c.scalar("SELECT count(*) FROM memberships WHERE org_id = $1", org_id) or 0)
    if metric == "storage_mb":
        return int(c.scalar("SELECT coalesce(sum(size_bytes),0) / 1048576 FROM documents"
                            " WHERE org_id = $1 AND deleted_at IS NULL", org_id) or 0)
    if metric == "saved_searches":
        return int(c.scalar("SELECT count(*) FROM saved_searches WHERE org_id = $1", org_id) or 0)
    raise ValueError(f"métrica sem contagem definida: {metric!r}")


def sync(c, org_id: str, org_kind: str) -> list[dict]:
    """Atualiza os contadores do período corrente e devolve a leitura de cada métrica."""
    from .entitlements import effective
    ent = effective(c, org_id, org_kind)
    ilimitado = "*" in ent["features"]
    out = []
    for metric in METRICS:
        usado = _live(c, org_id, metric)
        limite = None if ilimitado else ent["limits"].get(metric)
        c.run("INSERT INTO usage_counters(org_id, metric, period_start, period_end, used, limit_value)"
              " VALUES ($1,$2, date_trunc('month', now())::date,"
              "         (date_trunc('month', now()) + interval '1 month')::date, $3, $4)"
              " ON CONFLICT (org_id, metric, period_start)"
              " DO UPDATE SET used = EXCLUDED.used, limit_value = EXCLUDED.limit_value,"
              " updated_at = now()", org_id, metric, usado, limite)
        pct = None if not limite else min(100, int(usado * 100 / limite))
        out.append({"metric": metric, "label": METRICS[metric], "used": usado,
                    "limit": limite, "percent": pct})
    return out


def check_alerts(c, org_id: str, org_kind: str) -> int:
    """Dispara os alertas que ainda não foram dados neste período. Devolve quantos saíram."""
    from .monetization import notify_once
    enviados = 0
    # O mês vem do BANCO, uma vez só: é o mesmo relógio que `date_trunc('month', now())` usa para
    # delimitar o período na tabela de alertas. Formatar no processo abriria a chance de o aviso
    # ser gravado num mês e contado em outro na virada.
    mes = c.scalar("SELECT to_char(now(), 'YYYY-MM')")
    for linha in sync(c, org_id, org_kind):
        if not linha["limit"] or linha["percent"] is None:
            continue
        for limiar in THRESHOLDS:
            if linha["percent"] < limiar:
                continue
            novo = c.one(
                "INSERT INTO usage_alerts(org_id, metric, period_start, threshold, used, limit_value)"
                " VALUES ($1,$2, date_trunc('month', now())::date, $3,$4,$5)"
                " ON CONFLICT DO NOTHING RETURNING 1 AS ok",
                org_id, linha["metric"], limiar, linha["used"], linha["limit"])
            if not novo:
                continue
            if limiar == 100:
                titulo = f"Você atingiu o limite de {linha['label']}"
                corpo = (f"Você usou {linha['used']} de {linha['limit']} ({linha['label']}). "
                         "Nada foi cobrado a mais: o limite do plano interrompe o excedente em vez "
                         "de gerar fatura. Para continuar, mude de plano ou aguarde o próximo mês.")
            else:
                titulo = f"Você usou {limiar}% de {linha['label']}"
                corpo = (f"Você usou {linha['used']} de {linha['limit']} ({linha['label']}). "
                         "Este é um aviso, não um bloqueio — você continua trabalhando normalmente.")
            ref = f"{linha['metric']}:{limiar}:{mes}"
            if notify_once(c, org_id, "usage_threshold", ref, titulo, corpo):
                enviados += 1
    return enviados


# --- teto de gasto -----------------------------------------------------------------------------

def spend_limit(c, org_id: str) -> dict:
    row = c.one("SELECT limit_cents, action FROM spend_limits WHERE org_id = $1", org_id)
    return dict(row) if row else {"limit_cents": None, "action": "warn"}


def set_spend_limit(c, *, org_id: str, limit_cents: int | None, action: str,
                    set_by: str | None) -> dict:
    if action not in ACTIONS:
        raise ValueError(f"ação desconhecida de teto de gasto: {action!r}")
    row = c.one("INSERT INTO spend_limits(org_id, limit_cents, action, set_by)"
                " VALUES ($1,$2,$3,$4) ON CONFLICT (org_id)"
                " DO UPDATE SET limit_cents = EXCLUDED.limit_cents, action = EXCLUDED.action,"
                " set_by = EXCLUDED.set_by, updated_at = now()"
                " RETURNING limit_cents, action", org_id, limit_cents, action, set_by)
    return dict(row)


def spent_this_month(c, org_id: str) -> int:
    """Quanto já foi cobrado desta organização no mês. Só cobrança REAL entra na conta.

    Simulação não gasta dinheiro de ninguém; somá-la ao teto faria um ambiente de testes disparar
    o `hard_stop` de um cliente de verdade.
    """
    return int(c.scalar(
        "SELECT coalesce(sum(amount_cents),0) FROM platform_charges"
        " WHERE org_id = $1 AND NOT is_simulated"
        "   AND state IN ('authorized','paid','settled')"
        "   AND created_at >= date_trunc('month', now())", org_id) or 0)


def would_exceed(c, org_id: str, amount_cents: int) -> dict:
    """Esta cobrança passaria do teto? Devolve o veredito e o que fazer com ele.

    Quem decide o que fazer é o chamador, com `action`: `hard_stop` significa recusar, `warn`
    significa seguir e avisar. A função não decide sozinha porque a mesma resposta serve para
    mostrar um alerta na tela ANTES de a pessoa confirmar.
    """
    cfg = spend_limit(c, org_id)
    if cfg["limit_cents"] is None:
        return {"exceeds": False, "limit_cents": None, "action": cfg["action"],
                "spent_cents": spent_this_month(c, org_id)}
    gasto = spent_this_month(c, org_id)
    return {"exceeds": (gasto + amount_cents) > cfg["limit_cents"],
            "limit_cents": cfg["limit_cents"], "action": cfg["action"],
            "spent_cents": gasto, "would_total_cents": gasto + amount_cents}


def enforce(c, org_id: str, amount_cents: int) -> None:
    """Aplica o teto antes de cobrar. Com `hard_stop`, recusa; com `warn`, deixa passar e avisa."""
    from ..http import ApiError
    from .monetization import notify_once
    v = would_exceed(c, org_id, amount_cents)
    if not v["exceeds"]:
        return
    reais = f"R$ {v['limit_cents'] / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if v["action"] == "hard_stop":
        raise ApiError(402, "spend_limit_reached",
                       f"Teto de gasto mensal atingido ({reais}). Esta cobrança foi interrompida "
                       "antes de acontecer. Altere o teto para continuar.",
                       {"limit_cents": v["limit_cents"], "spent_cents": v["spent_cents"]})
    notify_once(c, org_id, "spend_limit_warning",
                c.scalar("SELECT to_char(now(), 'YYYY-MM')"),
                "Você passou do seu teto de gasto mensal",
                f"O teto que você definiu é {reais} e o gasto do mês ultrapassou esse valor. "
                "Como o teto está no modo 'avisar', nada foi interrompido. Para parar o consumo "
                "ao atingir o teto, mude a ação para 'parar'.")
