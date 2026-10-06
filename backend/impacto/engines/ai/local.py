"""Provedor LOCAL (determinístico, sem IA generativa, sem envio de dados a terceiros).

Funciona offline e é o fallback de todos os recursos. Saídas são sempre RASCUNHOS com marcação
``[COMPLETAR: ...]`` onde falta informação — nunca inventa números, metas ou fatos.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from ...clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

CAUSE_KEYWORDS = {
    "educacao": ["escola", "aluno", "educa", "alfabetiz", "reforço escolar", "ensino", "biblioteca", "leitura", "professor"],
    "cultura": ["música", "musica", "violão", "violao", "instrumento", "teatro", "dança", "danca", "arte", "cultura", "coral", "orquestra", "cinema"],
    "esporte": ["esporte", "futebol", "vôlei", "volei", "atletismo", "judô", "judo", "natação", "natacao", "quadra"],
    "saude": ["saúde", "saude", "hospital", "médic", "medic", "tratamento", "prevenção", "vacina", "odontol", "psicol"],
    "criancas_adolescentes": ["criança", "crianca", "adolescente", "infância", "infancia", "menor", "juvenil"],
    "pessoa_idosa": ["idoso", "idosa", "terceira idade", "envelhec", "longevidade"],
    "pessoa_com_deficiencia": ["deficiência", "deficiencia", "acessibilidade", "autis", "libras", "cadeira de rodas", "tea"],
    "seguranca_alimentar": ["aliment", "fome", "cesta", "refeiç", "refeic", "horta", "cozinha comunitária"],
    "meio_ambiente": ["meio ambiente", "ambiental", "reciclagem", "árvore", "arvore", "reflorest", "clima", "resíduo", "residuo", "nascente"],
    "geracao_renda": ["renda", "emprego", "capacitação profissional", "capacitacao profissional", "empreend", "cooperativa", "qualificação"],
    "inclusao_digital": ["computador", "internet", "digital", "informática", "informatica", "tablet", "programação"],
    "agua_saneamento": ["água potável", "agua potavel", "saneamento", "poço", "cisterna", "esgoto"],
    "habitacao": ["moradia", "habitação", "habitacao", "casa", "reforma de casas"],
    "igualdade_genero": ["mulher", "mulheres", "gênero", "genero", "violência doméstica", "violencia domestica", "feminino"],
    "igualdade_racial": ["racial", "racismo", "negra", "negro", "quilombola", "antirracis"],
    "assistencia_social": ["vulnerabilidade", "assistência social", "assistencia social", "acolhimento", "situação de rua"],
    "protecao_animal": ["animal", "animais", "castração", "castracao", "abrigo de animais"],
    "juventude": ["jovem", "jovens", "juventude"],
}
CAUSE_ODS = {"educacao": [4], "cultura": [4, 11], "esporte": [3], "saude": [3], "criancas_adolescentes": [4, 16],
             "pessoa_idosa": [3, 10], "pessoa_com_deficiencia": [10], "seguranca_alimentar": [2], "meio_ambiente": [13, 15],
             "geracao_renda": [8, 1], "inclusao_digital": [4, 9], "agua_saneamento": [6], "habitacao": [11],
             "igualdade_genero": [5], "igualdade_racial": [10], "assistencia_social": [1, 10], "protecao_animal": [15],
             "juventude": [8, 4]}
BENEF_WORDS = r"(crianças|criancas|jovens|adolescentes|idosos|idosas|famílias|familias|pessoas|alunos|alunas|estudantes|mulheres|beneficiári\w+|atletas|pacientes)"

_MONEY = r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{1,2})?|[0-9]+(?:,[0-9]{1,2})?)"


def _money_to_cents(s: str) -> int:
    s = s.replace(".", "").replace(",", ".")
    return int(round(float(s) * 100))


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def structure_need(text: str) -> dict:
    t = _norm(text)
    low = t.lower()
    items = []
    for m in re.finditer(r"(\d{1,6})\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ \-]{1,40}?)\s+(?:de|a|por|x|×|no valor de|ao custo de)\s*" + _MONEY
                         + r"(?:\s*(?:cada|a unidade|por unidade|/un))?", t):
        qty, desc, price = int(m.group(1)), m.group(2).strip(), _money_to_cents(m.group(3))
        items.append({"description": desc[:1].upper() + desc[1:], "quantity": qty, "unit_cost_cents": price,
                      "total_cents": qty * price, "category": "material"})
    totals = [_money_to_cents(x) for x in re.findall(_MONEY, t)]
    budget = sum(i["total_cents"] for i in items) if items else (max(totals) if totals else None)
    benef = None
    m = re.search(r"(\d[\d\.]*)\s+" + BENEF_WORDS, low)
    if m:
        benef = int(m.group(1).replace(".", ""))
    causes = [c for c, kws in CAUSE_KEYWORDS.items() if any(k in low for k in kws)]
    ods = sorted({o for c in causes for o in CAUSE_ODS.get(c, [])})
    first = re.split(r"(?<=[.!?])\s+", t.strip())[0]
    title = first[:90].rstrip(" ,.;") if first else "Projeto sem título"
    questions = []
    if not budget:
        questions.append("Qual o valor total necessário? Detalhe itens, quantidades e custos unitários.")
    if not benef:
        questions.append("Quantas pessoas serão beneficiadas diretamente e qual o perfil delas?")
    if not re.search(r"\b(mês|meses|semana|semanas|ano|anos|até|prazo)\b", low):
        questions.append("Qual o prazo de execução e as principais etapas?")
    questions.append("Como o resultado será medido? Defina ao menos um indicador com meta.")
    questions.append("Em qual município (código IBGE) o projeto será executado?")
    return {"title": title, "summary": t.strip()[:600], "causes": causes[:5], "ods": ods[:6], "budget_items": items,
            "budget_total_cents": budget, "beneficiaries_count": benef, "questions": questions,
            "engine": "local-rules@1.0", "draft": True, "human_review_required": True}


def _money(c):
    if c is None:
        return "[COMPLETAR: valor]"
    return ("R$ " + f"{c / 100:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")


def draft_document(kind: str, project: dict, org: dict, call: dict | None, budget_items: list[dict], milestones: list[dict],
                   instructions: str | None = None) -> str:
    """Rascunho estruturado a partir dos dados cadastrados (modelo, não texto inventado)."""
    def f(v, label):
        return v if v not in (None, "", []) else f"[COMPLETAR: {label}]"

    lines = []
    head = {"project_proposal": "PROPOSTA DE PROJETO", "work_plan": "PLANO DE TRABALHO", "budget_justification": "JUSTIFICATIVA ORÇAMENTÁRIA",
            "cover_letter": "CARTA DE APRESENTAÇÃO", "progress_report": "RELATÓRIO PARCIAL DE EXECUÇÃO",
            "final_report": "RELATÓRIO FINAL E PRESTAÇÃO DE CONTAS"}[kind]
    lines += [head, "", "Rascunho gerado a partir dos dados cadastrados na plataforma. Revise, complete os campos marcados e",
              "submeta à validação de profissional habilitado antes de assinar ou enviar.", ""]
    lines += [f"Proponente: {f(org.get('legal_name'), 'razão social')}", f"CNPJ: {f(org.get('cnpj'), 'CNPJ')}",
              f"Município/UF: {f(org.get('city'), 'município')}/{f(org.get('uf'), 'UF')}", ""]
    if call:
        lines += [f"Chamada/Edital: {call.get('title')}", f"Financiador: {call.get('funder_name')}", ""]
    lines += ["1. IDENTIFICAÇÃO DO PROJETO", f"Título: {f(project.get('title'), 'título')}",
              f"Território de execução: {f(project.get('territory'), 'território')}",
              f"Período: {f(project.get('starts_on'), 'início')} a {f(project.get('ends_on'), 'término')}", ""]
    if kind in ("project_proposal", "cover_letter", "work_plan"):
        lines += ["2. CONTEXTO E PROBLEMA", f(project.get("problem"), "descrição do problema com dados do território (fonte e ano)"), "",
                  "3. OBJETIVOS", f(project.get("objectives"), "objetivo geral e objetivos específicos"), "",
                  "4. PÚBLICO BENEFICIÁRIO", f"Quantidade: {f(project.get('beneficiaries_count'), 'nº de beneficiários')}",
                  f(project.get("beneficiaries_description"), "perfil e critérios de seleção dos beneficiários"), "",
                  "5. METODOLOGIA E ATIVIDADES", f(project.get("methodology"), "atividades, frequência, responsáveis"), ""]
    if kind in ("project_proposal", "work_plan", "budget_justification"):
        lines += ["6. ORÇAMENTO"]
        if budget_items:
            for i in budget_items:
                lines.append(f"- {i['description']}: {i['quantity']:g} × {_money(i['unit_cost_cents'])} = {_money(i['total_cents'])}")
        else:
            lines.append("[COMPLETAR: itens de orçamento com quantidade e custo unitário]")
        lines += [f"Total: {_money(project.get('budget_total_cents'))}", "Justificativa dos custos: [COMPLETAR: cotações/referências de preço]", ""]
        lines += ["7. CRONOGRAMA E MARCOS"]
        if milestones:
            for m in milestones:
                lines.append(f"- Marco {m['seq']}: {m['title']} — {_money(m['amount_cents'])} — previsão {m.get('due_on') or '[COMPLETAR: data]'}")
        else:
            lines.append("[COMPLETAR: etapas com datas e valores]")
        lines.append("")
    lines += ["8. INDICADORES E METAS"]
    inds = project.get("indicators") or []
    if inds:
        for i in inds:
            lines.append(f"- {i.get('name')}: linha de base {i.get('baseline', '[COMPLETAR]')} → meta {i.get('target', '[COMPLETAR]')} {i.get('unit') or ''}")
    else:
        lines.append("[COMPLETAR: ao menos um indicador mensurável com linha de base e meta]")
    if kind in ("progress_report", "final_report"):
        lines += ["", "9. EXECUÇÃO FÍSICA E FINANCEIRA", "[COMPLETAR: atividades realizadas × previstas; despesas comprovadas anexas]",
                  "", "10. EVIDÊNCIAS", "[COMPLETAR: listar evidências aceitas (fotos, listas de presença, notas fiscais)]"]
    if instructions:
        lines += ["", "Orientações adicionais informadas pelo usuário:", instructions[:2000]]
    lines += ["", f"Data: {_hoje_utc().isoformat()}", "Responsável legal: [COMPLETAR]",
              "Validação profissional: pendente (solicite revisão a um profissional parceiro habilitado)"]
    return "\n".join(lines)


def summarize_project(project: dict) -> str:
    parts = [project.get("summary") or "", project.get("problem") or "", project.get("objectives") or ""]
    text = " ".join(p.strip() for p in parts if p).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(sentences[:3])[:700]
    facts = []
    if project.get("beneficiaries_count"):
        facts.append(f"{project['beneficiaries_count']} beneficiários")
    if project.get("budget_total_cents"):
        facts.append(f"orçamento de {_money(project['budget_total_cents'])}")
    if project.get("territory"):
        facts.append(f"território {project['territory']}")
    return (out + (" — " + "; ".join(facts) if facts else "")).strip() or "Projeto sem descrição suficiente para resumo."


DOC_RULES = [
    ("cnd_federal", ["débitos relativos aos tributos federais", "debitos relativos aos tributos federais", "dívida ativa da união", "divida ativa da uniao", "receita federal"]),
    ("crf_fgts", ["certificado de regularidade do fgts", "fgts", "caixa econômica federal"]),
    ("cndt_trabalhista", ["certidão negativa de débitos trabalhistas", "justiça do trabalho", "justica do trabalho", "cndt"]),
    ("cartao_cnpj", ["comprovante de inscrição e de situação cadastral", "cadastro nacional da pessoa jurídica", "cnpj"]),
    ("estatuto_social", ["estatuto social", "estatuto", "da denominação, sede", "capítulo i"]),
    ("ata_eleicao_diretoria", ["ata de eleição", "ata da assembleia", "eleição da diretoria", "posse da diretoria"]),
    ("balanco_patrimonial", ["balanço patrimonial", "balanco patrimonial", "demonstração do resultado"]),
    ("nota_fiscal", ["nota fiscal", "danfe", "nf-e", "nfs-e"]),
    ("recibo", ["recibo", "recebi de"]),
    ("lista_presenca", ["lista de presença", "lista de presenca", "assinatura dos participantes"]),
    ("plano_trabalho", ["plano de trabalho"]),
    ("relatorio_atividades", ["relatório de atividades", "relatorio de atividades"]),
]


def classify_document(text: str, filename: str) -> dict:
    low = (text or "").lower() + " " + (filename or "").lower()
    scores = []
    for doc_type, kws in DOC_RULES:
        hits = sum(1 for k in kws if k in low)
        if hits:
            scores.append((hits, doc_type))
    scores.sort(reverse=True)
    valid_until = None
    m = re.search(r"(válid[ao]|validade|vencimento)[^0-9]{0,40}(\d{2})/(\d{2})/(\d{4})", low)
    if m:
        try:
            valid_until = date(int(m.group(4)), int(m.group(3)), int(m.group(2))).isoformat()
        except ValueError:
            valid_until = None
    cnpjs = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", text or "")
    return {"suggested_type": scores[0][1] if scores else "outro", "confidence": min(1.0, scores[0][0] / 3) if scores else 0.0,
            "alternatives": [d for _, d in scores[1:3]], "valid_until": valid_until, "cnpjs_found": cnpjs[:3],
            "engine": "local-rules@1.0", "human_review_required": True}
