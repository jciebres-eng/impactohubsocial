"""Jornadas completas da demonstração, executadas pela API real com as contas de demonstração (v0.25.0).

POR QUE EXISTE
  O seed cria o mínimo (organizações, 1 projeto, editais). Com só isso, 149 visitas do robô de telas
  caíam em "nenhum registro": não havia diagnóstico, candidatura, proposta, conversa, pagamento,
  relatório, acordo, cotas... Inserir esses registros direto no banco produziria uma demonstração
  bonita e falsa. Aqui cada registro nasce do MESMO caminho que a tela usa: a pessoa entra, chama a
  API, e a regra de negócio aceita ou recusa. Se uma jornada não fecha, isso é um achado.

TUDO PELA API — inclusive o plano pago das contas de demonstração, concedido pela administração
  (`POST /v1/admin/organizations/{id}/grants`, com confirmação de identidade), como faria um voucher.
  Nenhuma linha é escrita direto no banco. Por isso o mesmo roteiro roda contra o servidor de teste
  e contra a pilha Docker montada do zero (`scripts/demo_stack.py`): só muda de onde vêm o código de
  assinatura (e-mail) e o segredo do segundo fator.

RESULTADO
  `run()` devolve {"passos": [...], "falhas": [...], "atalhos": [...], "ids": {...}}. Cada passo tem
  jornada, descrição, método, rota, status HTTP e se deu o resultado esperado.
"""
from __future__ import annotations

import datetime as dt
import urllib.parse
import uuid

import json
import re
import urllib.request

from tests.support import Client, fresh_totp

_RESULTADO: dict | None = None


def _d(dias: int) -> str:
    return (dt.date.today() + dt.timedelta(days=dias)).isoformat()


class Http(Client):
    """O `Client` dos testes, apontado para qualquer base (servidor de teste ou pilha Docker)."""

    def __init__(self, base: str, mode: str = "token"):
        import http.cookiejar
        self.base, self.mode = base, mode
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.access = self.refresh_token = self.csrf = None
        self.user = None


def codigo_por_mailpit(api: str):
    """Código de assinatura lido do Mailpit (SMTP descartável da pilha Docker)."""
    def ler(email: str) -> str:
        with urllib.request.urlopen(f"{api}/api/v1/search?query=" + urllib.parse.quote(f"to:{email}"), timeout=10) as r:
            msgs = json.loads(r.read())["messages"]
        for m in msgs:   # mais recente primeiro
            if "assinar" in (m.get("Subject") or "").lower():
                with urllib.request.urlopen(f"{api}/api/v1/message/{m['ID']}", timeout=10) as r:
                    corpo = json.loads(r.read()).get("Text", "")
                achado = re.search(r"\b(\d{6})\b", corpo)
                if achado:
                    return achado.group(1)
        raise AssertionError(f"código de assinatura não encontrado no Mailpit para {email}")
    return ler


class Jornadas:
    def __init__(self, base: str, senha: str, codigo_assinatura, segredo_totp):
        from impacto import seed_dev
        self.base, self.senha = base, senha
        self.codigo_assinatura, self.segredo_totp = codigo_assinatura, segredo_totp
        self.emails = seed_dev.DEMO_EMAILS
        self.passos: list[dict] = []
        self.atalhos: list[str] = []
        self.ids: dict[str, str] = {}
        self.c: dict[str, Client] = {}

    # ------------------------------------------------------------------ apoio
    def passo(self, jornada: str, descricao: str, cliente: Client, metodo: str, rota: str, corpo=None,
              esperado=(200, 201)):
        r = cliente.request(metodo, rota, corpo if corpo is not None or metodo == "GET" else {})
        try:
            dados = r.json if r.body else None
        except ValueError:
            dados = None
        ok = r.status in esperado
        perfil = next((k for k, v in self.c.items() if v is cliente), "anônimo")
        self.passos.append({"jornada": jornada, "passo": descricao, "perfil": perfil, "metodo": metodo,
                            "rota": rota, "status": r.status, "ok": ok,
                            "erro": "" if ok else str(dados if dados is not None else r.body[:200])[:300]})
        return dados if ok else None

    def entrar(self, papel: str) -> Client:
        c = Http(self.base)
        email = self.emails[papel]
        r = c.post("/v1/auth/login", {"email": email, "password": self.senha})
        assert r.status == 200, f"{papel} não entrou: {r}"
        if r.json.get("mfa_required"):
            segredo = self.segredo_totp(email)
            c.mfa_secret = segredo
            r = c.post("/v1/auth/mfa/verify", {"mfa_token": r.json["mfa_token"], "code": fresh_totp(segredo)})
            assert r.status == 200, f"{papel}: segundo fator recusado: {r}"
        c._absorb(r.json)
        me = c.get("/v1/me").json
        c.email, c.user, c.org_id = email, me["user"], (me["active_org"] or {}).get("id")
        self.c[papel] = c
        return c

    def confirmar_identidade(self, c: Client, jornada: str):
        corpo = {"password": self.senha}
        if getattr(c, "mfa_secret", None):
            corpo["mfa_code"] = fresh_totp(c.mfa_secret)
        self.passo(jornada, "confirma a identidade (operação sensível)", c, "POST", "/v1/auth/reauth", corpo)

    def assinar(self, jornada: str, c: Client, subject_type: str, subject_id: str, rota: str, corpo_extra: dict):
        self.passo(jornada, f"pede código de assinatura ({subject_type})", c, "POST", "/v1/signatures/challenge",
                   {"subject_type": subject_type, "subject_id": subject_id})
        codigo = self.codigo_assinatura(c.email)
        return self.passo(jornada, f"assina ({subject_type})", c, "POST", rota,
                          {**corpo_extra, "password": self.senha, "code": codigo})

    # ------------------------------------------------------------------ jornadas
    def preparar(self):
        J = "Preparação: contas de demonstração e plano concedido pela administração"
        for papel in ("osc", "company", "provider", "government", "individual", "admin", "editor", "reviewer", "support"):
            self.entrar(papel)
        adm = self.c["admin"]
        self.confirmar_identidade(adm, J)
        planos = {"osc": "osc_premium", "company": "company_premium", "provider": "provider_premium",
                  "government": "gov_institutional", "individual": "individual_basic"}
        for papel, plano in planos.items():
            self.passo(J, f"administração concede plano {plano} ({papel})", adm, "POST",
                       f"/v1/admin/organizations/{self.c[papel].org_id}/grants",
                       {"plan_key": plano, "days": 365, "source": "promotion",
                        "reason": "Conta de demonstração: plano concedido para apresentar o produto."})
        projetos = self.passo(J, "OSC lista seus projetos", self.c["osc"], "GET", "/v1/projects") or {}
        self.ids["projeto"] = projetos["items"][-1]["id"] if projetos.get("items") else None
        ed = self.passo(J, "empresa lista seus programas", self.c["company"], "GET", "/v1/calls?mine=true&status=all") or {}
        self.ids["edital_empresa"] = (ed.get("items") or [{}])[0].get("id")
        ficha = self.passo(J, "OSC abre o projeto", self.c["osc"], "GET", f"/v1/projects/{self.ids['projeto']}") or {}
        self.ids["marco"] = (ficha.get("milestones") or [{}])[0].get("id")

    def candidatar(self, J: str, osc: Client, call_id: str, project_id: str, valor: int) -> str | None:
        """OSC abre, prepara (plano de trabalho assinado + passos) e envia a candidatura."""
        a = self.passo(J, "OSC abre candidatura", osc, "POST", "/v1/applications",
                       {"call_id": call_id, "project_id": project_id, "requested_cents": valor})
        if not a:
            return None
        aid = a["id"]
        det = self.passo(J, "OSC lê os passos da candidatura", osc, "GET", f"/v1/applications/{aid}") or {}
        rasc = self.passo(J, "OSC escreve o plano de trabalho (rascunho)", osc, "POST", "/v1/drafts", {
            "title": "Plano de trabalho (exemplo)", "kind": "project_proposal", "application_id": aid,
            "content": "Objetivo, metas, cronograma e orçamento do projeto (texto de demonstração)."})
        if rasc:
            self.ids.setdefault("rascunho", rasc["id"])
            self.assinar(J, osc, "draft", rasc["id"], "/v1/signatures",
                         {"subject_type": "draft", "subject_id": rasc["id"], "role": "legal_representative",
                          "statement": "Declaro que o plano de trabalho é verdadeiro."})
        for s in det.get("steps", []):
            if s.get("mandatory") and s.get("status") != "done":
                self.passo(J, f"OSC conclui o passo '{s.get('label') or s.get('code')}'", osc, "PATCH",
                           f"/v1/applications/{aid}/steps/{s['id']}", {"status": "done"})
        self.passo(J, "OSC envia a candidatura", osc, "POST", f"/v1/applications/{aid}/transition", {"to_status": "submitted"})
        return aid

    def avaliar(self, J: str, avaliador: Client, aid: str):
        for st in ("screening", "due_diligence"):
            self.passo(J, f"avaliador move para {st}", avaliador, "POST", f"/v1/applications/{aid}/transition", {"to_status": st})
        self.passo(J, "avaliador declara não ter conflito", avaliador, "POST", f"/v1/applications/{aid}/conflict", {"has_conflict": False})
        self.passo(J, "avaliador aprova", avaliador, "POST", f"/v1/applications/{aid}/transition",
                   {"to_status": "approved", "note": "Aprovado pela comissão (exemplo)."})

    def osc_projeto_e_diagnostico(self):
        J, osc, pid = "OSC: projeto → diagnóstico → impacto", self.c["osc"], self.ids["projeto"]
        # segundo projeto, criado do zero e publicado
        p2 = self.passo(J, "cria projeto novo", osc, "POST", "/v1/projects", {
            "title": "Horta Escolar Comunitária (exemplo)", "summary": "Hortas pedagógicas em 3 escolas municipais (dados fictícios).",
            "problem": "Escolas sem espaço de educação alimentar (exemplo).", "objectives": "Implantar 3 hortas e formar 60 estudantes.",
            "territory": "BR-MT-5105259", "causes": ["educacao", "meio_ambiente"], "ods": [2, 4], "beneficiaries_count": 60,
            "starts_on": _d(-200), "ends_on": _d(160)})
        if p2:
            self.ids["projeto2"] = p2["id"]
            self.passo(J, "orça o projeto novo", osc, "POST", f"/v1/projects/{p2['id']}/budget-items",
                       {"description": "Ferramentas e sementes", "quantity": 3, "unit_cost_cents": 150000})
            self.passo(J, "publica o projeto novo", osc, "POST", f"/v1/projects/{p2['id']}/publish")
        d = self.passo(J, "abre diagnóstico do projeto", osc, "POST", "/v1/diagnoses", {
            "title": "Diagnóstico da Orquestra Comunitária", "project_id": pid,
            "need_statement": "40 crianças do bairro sem acesso a educação musical (levantamento da escola, exemplo).",
            "affected_group": "Crianças de 8 a 14 anos da rede municipal", "objective": "Formar 40 crianças em 12 meses."})
        if d:
            did = self.ids["diagnostico"] = d["id"]
            self.passo(J, "preenche o diagnóstico", osc, "PUT", f"/v1/diagnoses/{did}", {
                "title": "Diagnóstico da Orquestra Comunitária", "project_id": pid,
                "need_statement": "40 crianças do bairro sem acesso a educação musical (levantamento da escola, exemplo).",
                "root_causes": [{"text": "Nenhuma oferta pública de música no bairro", "source": "Secretaria de Educação (exemplo)",
                                 "evidence_level": "observado"}],
                "objective": "Formar 40 crianças em 12 meses.",
                "goals": [{"text": "Realizar 40 encontros", "indicator_code": "sessions_held", "target": 40}],
                "action_plan": [{"action": "Comprar instrumentos", "owner": "Coordenação"},
                                {"action": "Contratar professor", "owner": "Diretoria"}]})
            self.passo(J, "responde a etapa de contexto do roteiro", osc, "PUT", f"/v1/diagnoses/{did}/guide/context",
                       {"answers": {"territory": "Lucas do Rio Verde", "population": "Crianças da rede municipal"}, "complete": True})
            self.passo(J, "aplica o diagnóstico ao projeto", osc, "POST", f"/v1/diagnoses/{did}/apply")
            self.passo(J, "grava a versão 1 do diagnóstico", osc, "POST", f"/v1/diagnoses/{did}/versions")
            self.passo(J, "lê a análise de prontidão (8 dimensões)", osc, "GET", f"/v1/diagnoses/{did}/analysis")
        self.passo(J, "declara contexto de equidade", osc, "PUT", f"/v1/projects/{pid}/equity/context", {
            "need_statement": "Bairro sem equipamento cultural a menos de 5 km (levantamento municipal, exemplo).",
            "additionality": "Nenhuma outra organização oferece música no contraturno deste bairro (exemplo)."})
        self.passo(J, "declara denominador com fonte", osc, "POST", "/v1/equity/denominators", {
            "project_id": pid, "kind": "eligible_population", "value": 120, "unit": "pessoas",
            "reference_date": _d(-300), "source_name": "Censo escolar municipal (exemplo)", "source_date": _d(-200),
            "method_note": "Matriculados de 8 a 14 anos nas duas escolas do bairro (exemplo)."})
        self.passo(J, "alinha ODS (declarado)", osc, "PUT", f"/v1/projects/{pid}/ods-targets",
                   {"items": [{"ods": 4, "rationale": "Educação musical no contraturno."}]})
        cat = self.passo(J, "consulta catálogo de indicadores", osc, "GET", "/v1/indicators/catalog?ods=4")
        ind = next((i for i in (cat or {}).get("items", []) if i["code"] == "trained_people"), None)
        if ind:
            pi = self.passo(J, "cria indicador com linha de base e fonte", osc, "POST", f"/v1/projects/{pid}/indicators", {
                "indicator_id": ind["id"], "baseline": 0, "baseline_source": "Lista de presença do primeiro encontro",
                "baseline_date": _d(-180), "target": 40, "method": "Lista de presença e avaliação prática"})
            if pi:
                self.ids["indicador"] = pi["id"]
                self.ids["medicoes"] = []
                for dias, valor in ((-150, 8), (-100, 17), (-50, 26), (-5, 33)):
                    ev = self.passo(J, f"registra evidência ({_d(dias)})", osc, "POST", f"/v1/projects/{pid}/evidences",
                                    {"kind": "attendance", "title": f"Lista de presença — {_d(dias)}"})
                    v = self.passo(J, f"registra medição {valor} em {_d(dias)}", osc, "POST",
                                   f"/v1/project-indicators/{pi['id']}/values",
                                   {"value": valor, "measured_on": _d(dias), "evidence_id": (ev or {}).get("id")})
                    if v:
                        self.ids["medicoes"].append(v["id"])
        self.passo(J, "registra risco", osc, "POST", f"/v1/projects/{pid}/risks", {
            "category": "financial", "title": "Atraso no repasse", "probability": "medium", "impact": "high",
            "description": "Repasse do apoiador pode atrasar e suspender as aulas (exemplo)."})
        self.passo(J, "grava retrato do projeto", osc, "POST", f"/v1/projects/{pid}/snapshots", {"label": "início da execução"})
        papeis = (self.passo(J, "consulta os papéis de responsabilidade", osc, "GET", "/v1/responsibility/roles") or {}).get("items", [])
        for escopo, sujeito in (("organization", osc.org_id), ("project", pid)):
            papel = next((r["code"] for r in papeis if escopo in (r.get("scopes") or [])), None)
            if not papel:
                continue
            a = self.passo(J, f"designa responsável ({escopo})", osc, "POST", "/v1/responsibility/assignments", {
                "scope": escopo, "subject_id": sujeito, "role_code": papel,
                "mandate_basis": "Designação em ata da diretoria (exemplo), item 3.", "user_id": osc.user["id"]})
            if a and escopo == "organization":
                self.passo(J, "registra decisão do responsável", osc, "POST", "/v1/responsibility/decisions", {
                    "assignment_id": a["id"], "kind": "approval",
                    "statement": "Aprovo o plano de trabalho do segundo semestre da orquestra (exemplo)."})

    def financiador(self):
        J, osc, emp, pid = "Financiador: edital → candidatura → aporte → validação", self.c["osc"], self.c["company"], self.ids["projeto"]
        self.passo(J, "declara perfil de financiador", emp, "PUT", "/v1/org/funder-profile",
                   {"causes": ["educacao", "cultura"], "territories": ["BR-MT"]})
        cid = self.ids["edital_empresa"]
        self.passo(J, "OSC vê o match do edital com o projeto", osc, "GET", f"/v1/calls/{cid}?project_id={pid}")
        aid = self.candidatar(J, osc, cid, pid, 1500000)
        if not aid:
            return
        self.ids["candidatura"] = aid
        self.avaliar(J, emp, aid)
        com = self.passo(J, "financiador registra o aporte comprometido", emp, "POST", f"/v1/applications/{aid}/commitments",
                         {"amount_cents": 500000, "milestone_id": self.ids["marco"], "reference": "TERMO-DEMO-001"})
        if com:
            self.ids["compromisso"] = com["id"]
            self.passo(J, "financiador informa o desembolso", emp, "POST", f"/v1/commitments/{com['id']}/status",
                       {"status": "disbursed", "reference": "PIX-DEMO-001"})
            self.passo(J, "OSC confirma o recebimento", osc, "POST", f"/v1/commitments/{com['id']}/status", {"status": "confirmed"})
            pg = self.passo(J, "financiador registra pagamento", emp, "POST", f"/v1/commitments/{com['id']}/payments",
                            {"amount_cents": 250000, "method": "pix", "external_ref": "PIX-DEMO-002"})
            if pg:
                self.ids["pagamento"] = pg["id"]
                self.passo(J, "pagamento aguarda confirmação", emp, "POST", f"/v1/payments/{pg['id']}/transition", {"to": "awaiting_confirmation"})
                self.passo(J, "OSC confirma o pagamento", osc, "POST", f"/v1/payments/{pg['id']}/transition", {"to": "confirmed"})
        self.passo(J, "OSC inicia a execução", osc, "POST", f"/v1/applications/{aid}/transition", {"to_status": "in_execution"})
        for vid in self.ids.get("medicoes", [])[:3]:
            self.passo(J, "financiador valida medição", emp, "POST", f"/v1/indicator-values/{vid}/review", {"status": "validated"})
        self.passo(J, "financiador vê a série do projeto (reportado × validado)", emp, "GET", f"/v1/projects/{pid}/impact")

    def rede(self):
        J, osc, emp, pid = "Rede: proposta → conversa → prestação de contas", self.c["osc"], self.c["company"], self.ids["projeto"]
        p = self.passo(J, "financiador propõe apoio", emp, "POST", "/v1/proposals", {
            "kind": "investment", "receiver_org_id": osc.org_id, "project_id": pid,
            "title": "Apoio ao segundo semestre da orquestra", "support_mode": "financial", "amount_cents": 900000,
            "purpose": "Financiar as aulas do segundo semestre e a apresentação de encerramento (exemplo)."})
        if p:
            self.ids["proposta"] = p["id"]
            self.passo(J, "financiador envia a proposta", emp, "POST", f"/v1/proposals/{p['id']}/transition", {"to": "sent"})
            self.passo(J, "OSC abre a proposta", osc, "GET", f"/v1/proposals/{p['id']}")
            self.passo(J, "OSC aceita a proposta", osc, "POST", f"/v1/proposals/{p['id']}/transition", {"to": "accepted"})
        self.passo(J, "financiador registra relação com a OSC", emp, "POST", "/v1/network/relationships",
                   {"kind": "contact", "target_type": "org", "target_id": osc.org_id, "note": "Contato do edital (exemplo)."})
        cv = self.passo(J, "financiador abre conversa sobre o projeto", emp, "POST", "/v1/conversations",
                        {"other_org_id": osc.org_id, "project_id": pid, "subject": "Cronograma do segundo semestre"})
        if cv:
            self.ids["conversa"] = cv["id"]
            self.passo(J, "financiador escreve", emp, "POST", f"/v1/conversations/{cv['id']}/messages",
                       {"body": "Podemos alinhar o cronograma das aulas do segundo semestre?"})
            self.passo(J, "OSC responde", osc, "POST", f"/v1/conversations/{cv['id']}/messages",
                       {"body": "Sim. Enviamos a proposta de calendário até sexta."})
        m = self.passo(J, "financiador manda mensagem direta", emp, "POST", f"/v1/messages/{osc.org_id}",
                       {"body": "Recebemos a lista de presença, obrigado."})
        if m:
            self.ids["mensagem_conversa"] = m.get("conversation_id")
        u = self.passo(J, "OSC escreve relatório de impacto do período", osc, "POST", "/v1/impact-updates", {
            "project_id": pid, "period_start": _d(-150), "period_end": _d(-1),
            "summary": "Primeiro semestre: 33 crianças com frequência registrada em listas de presença (exemplo).",
            "outputs": "40 encontros realizados; 1 apresentação.", "limitations": "Sem grupo de comparação; não prova causalidade."})
        if u:
            self.ids["relatorio_impacto"] = u["id"]
            self.passo(J, "OSC envia o relatório ao apoiador", osc, "POST", f"/v1/impact-updates/{u['id']}/transition", {"to": "submitted"})
            self.passo(J, "apoiador aceita o relatório", emp, "POST", f"/v1/impact-updates/{u['id']}/transition", {"to": "accepted"})

    def profissional(self):
        J, osc, pro, pid = "Profissional: necessidade → oferta → revisão técnica", self.c["osc"], self.c["provider"], self.ids["projeto"]
        self.passo(J, "profissional declara perfil", pro, "PUT", "/v1/org/provider-profile",
                   {"categories": ["contador"], "remote": True, "services": ["Contabilidade para OSC", "Prestação de contas"]})
        n = self.passo(J, "OSC publica necessidade do projeto", osc, "POST", f"/v1/projects/{pid}/needs",
                       {"category": "contador", "title": "Prestação de contas do primeiro semestre"})
        if n:
            self.ids["necessidade"] = n["id"]
            o = self.passo(J, "profissional oferece ajuda", pro, "POST", f"/v1/needs/{n['id']}/offers",
                           {"message": "Faço a prestação de contas com relatório de despesas por rubrica."})
            if o:
                self.passo(J, "OSC aceita a oferta", osc, "POST", f"/v1/offers/{o['id']}/decide", {"decision": "accepted"})
        creds = self.passo(J, "profissional lista suas credenciais", pro, "GET", "/v1/org/credentials") or {}
        cred = next((x["id"] for x in creds.get("items", []) if x.get("verification_status") == "verified"), None)
        r = self.passo(J, "OSC escreve justificativa orçamentária", osc, "POST", "/v1/drafts", {
            "kind": "budget_justification", "title": "Justificativa orçamentária (exemplo)",
            "content": "Violões: 10 × R$ 500. Professor: 12 × R$ 1.500. Valores de 3 orçamentos (exemplo)."})
        if r:
            rv = self.passo(J, "OSC pede revisão técnica ao profissional", osc, "POST", "/v1/professional-reviews", {
                "professional_org_id": pro.org_id, "subject_type": "draft", "subject_id": r["id"],
                "scope": "Revisar a justificativa orçamentária"})
            if rv:
                self.ids["revisao"] = rv["id"]
                self.passo(J, "profissional aceita a revisão", pro, "POST", f"/v1/professional-reviews/{rv['id']}/respond", {"status": "accepted"})
                self.passo(J, "profissional aprova com credencial verificada", pro, "POST",
                           f"/v1/professional-reviews/{rv['id']}/respond", {"status": "approved", "credential_id": cred})

    def governo(self):
        J, gov = "Governo: edital público → necessidade do território", self.c["government"]
        c = self.passo(J, "governo publica chamamento", gov, "POST", "/v1/calls", {
            "title": "[EXEMPLO FICTÍCIO] Chamamento Cultura nos Bairros", "sphere": "municipal", "instrument": "edital",
            "causes": ["cultura"], "territories": ["BR-MT-5105259"], "ticket_min_cents": 100000, "ticket_max_cents": 2000000,
            "status": "open", "closes_at": f"{_d(45)}T23:59:00-04:00"})
        if c:
            self.ids["edital_governo"] = c["id"]
        if c and self.ids.get("projeto2"):
            aid = self.candidatar(J, self.c["osc"], c["id"], self.ids["projeto2"], 800000)
            if aid:
                self.ids["candidatura_governo"] = aid
                self.passo(J, "governo lista as candidaturas do chamamento", gov, "GET", f"/v1/calls/{c['id']}/applications")
                self.avaliar(J, gov, aid)
        self.passo(J, "governo acompanha a carteira", gov, "GET", "/v1/portfolio")
        # v0.26.0 — a torre territorial só mostra linha a linha com 3+ projetos publicados no território (k-anonimato):
        # a OSC publica um terceiro projeto em MT, e a torre passa a responder território → OSCs → projetos → recursos.
        p3 = self.passo(J, "OSC publica um terceiro projeto no território", self.c["osc"], "POST", "/v1/projects", {
            "title": "Biblioteca Itinerante (exemplo)", "summary": "Acervo e mediação de leitura em 4 bairros (dados fictícios).",
            "problem": "Bairros sem biblioteca pública nem acesso a acervo infantil (exemplo).",
            "objectives": "Atender 300 crianças com rodas de leitura semanais.", "territory": "BR-MT-5105259",
            "causes": ["educacao", "cultura"], "ods": [4], "beneficiaries_count": 300, "starts_on": _d(-60), "ends_on": _d(300)})
        if p3:
            self.ids["projeto3"] = p3["id"]
            self.passo(J, "orça o terceiro projeto", self.c["osc"], "POST", f"/v1/projects/{p3['id']}/budget-items",
                       {"description": "Acervo e veículo adaptado", "quantity": 1, "unit_cost_cents": 2_400_000})
            self.passo(J, "publica o terceiro projeto", self.c["osc"], "POST", f"/v1/projects/{p3['id']}/publish")
        self.passo(J, "governo abre a torre territorial (território → programas → OSCs → projetos → indicadores → lacunas)", gov, "GET",
                   "/v1/control-tower/government")
        self.passo(J, "empresa abre a torre de controle (meu capital → ... → o que preciso decidir)", self.c["company"], "GET",
                   "/v1/control-tower/funder")
        self.passo(J, "financiador confere o estado IMPACTO Ready do projeto apoiado", self.c["company"], "GET",
                   f"/v1/projects/{self.ids['projeto']}/ready")
        self.passo(J, "governo registra necessidade do território com fonte", gov, "POST", "/v1/territory/needs", {
            "territory": "BR-MT-5105259", "title": "Vagas de contraturno cultural na região leste (exemplo)",
            "description": "Falta de oferta cultural no contraturno para crianças da região leste (exemplo).",
            "cause": "cultura", "people_estimate": 900, "source_name": "Diagnóstico municipal (exemplo)",
            "source_url": "https://example.org/diagnostico-ficticio", "source_date": _d(-90), "priority": "high",
            "beneficiary_groups": []})

    def captacao(self):
        J, osc, emp, ind, pid = ("Captação: cotas → apoios → campanha pública", self.c["osc"], self.c["company"],
                                 self.c["individual"], self.ids["projeto"])
        q = self.passo(J, "OSC cria cota de apoio", osc, "POST", "/v1/funding-quotas",
                       {"project_id": pid, "label": "Cota instrumento (violão)", "quota_cents": 50000, "total_quotas": 10})
        if q:
            self.ids["cota"] = q["id"]
            self.passo(J, "OSC abre a cota", osc, "PATCH", f"/v1/funding-quotas/{q['id']}", {"status": "open"})
            self.passo(J, "empresa apoia 3 cotas", emp, "POST", f"/v1/funding-quotas/{q['id']}/pledges", {"quantity": 3})
            self.passo(J, "apoiadora apoia 1 cota", ind, "POST", f"/v1/funding-quotas/{q['id']}/pledges",
                       {"quantity": 1, "display_name": "Elisa (exemplo)"})
        self.passo(J, "apoiadora declara interesse e causas", ind, "PUT", "/v1/org/funder-profile",
                   {"causes": ["cultura", "educacao"], "territories": ["BR-MT"]})
        if self.ids.get("projeto2"):
            self.passo(J, "apoiadora manifesta interesse no projeto da horta", ind, "POST", "/v1/applications/interest",
                       {"project_id": self.ids["projeto2"], "note": "Gostaria de apoiar a horta da escola do meu bairro."})
        slug = "orquestra-comunitaria-" + uuid.uuid4().hex[:6]
        cp = self.passo(J, "OSC cria campanha", osc, "POST", "/v1/campaigns", {
            "project_id": pid, "slug": slug, "title": "Uma orquestra para o bairro",
            "summary": "Ajude 40 crianças a aprender música no contraturno (campanha fictícia de demonstração)."})
        if cp:
            self.passo(J, "OSC publica a campanha", osc, "PATCH", f"/v1/campaigns/{cp['id']}", {"status": "published"})
            self.passo(J, "visitante sem login abre a campanha", Http(self.base), "GET", f"/v1/public/campaigns/{slug}")

    def documentos(self):
        J, osc, pro, pid = "Documentos: montagem → acordo assinado → registro verificável", self.c["osc"], self.c["provider"], self.ids["projeto"]
        tpl = self.passo(J, "lista modelos publicados", osc, "GET", "/v1/document-templates?status=published") or {}
        t = next((x for x in tpl.get("items", []) if x.get("code") == "plano_monitoramento_base"), None)
        if t:
            a = self.passo(J, "monta plano de monitoramento a partir do projeto", osc, "POST", "/v1/document-assemblies",
                           {"template_id": t["id"], "title": "Plano de monitoramento — Orquestra", "project_id": pid})
            if a:
                self.ids["montagem"] = a["id"]
                ficha = self.passo(J, "lê os campos da montagem", osc, "GET", f"/v1/document-assemblies/{a['id']}") or {}
                pend = (ficha.get("evaluation") or {}).get("missing", [])
                valores = {m["key"]: f"Texto de exemplo para {m['label']}." for m in pend
                           if m["kind"] == "field" and not m.get("derived_from")}
                evid = {}
                for m in pend:
                    if m["kind"] == "evidence":
                        up = osc.upload("/v1/documents", f"evidencia-{m['key']}.pdf", b"%PDF-1.4\n% evidencia ficticia\n%%EOF\n",
                                        {"doc_type": "outro", "title": f"Evidência (exemplo): {m['label']}"})
                        if up.status == 201:
                            evid[m["key"]] = up.json["id"]
                put = self.passo(J, "preenche campos e anexa evidências", osc, "PUT",
                                 f"/v1/document-assemblies/{a['id']}", {"values": valores, "evidence": evid}) or {}
                self.ids["montagem_faltando"] = put.get("missing")
                self.passo(J, "gera o documento", osc, "POST", f"/v1/document-assemblies/{a['id']}/generate", {"format": "pdf"})
        doc = osc.upload("/v1/documents", "contrato-exemplo.pdf", b"%PDF-1.4\n% contrato ficticio\n%%EOF\n",
                         {"doc_type": "contrato", "title": "Contrato de prestação de contas (exemplo)"})
        self.passos.append({"jornada": J, "passo": "envia o contrato", "perfil": "osc", "metodo": "POST", "rota": "/v1/documents",
                            "status": doc.status, "ok": doc.status == 201, "erro": "" if doc.status == 201 else str(doc.json)[:300]})
        if doc.status == 201:
            ac = self.passo(J, "cria acordo com o profissional", osc, "POST", "/v1/signed-agreements", {
                "kind": "service", "title": "Prestação de contas do 1º semestre (exemplo)",
                "summary": "Elaboração da prestação de contas com relatório por rubrica.", "document_id": doc.json["id"],
                "value_cents": 180000})
            if ac:
                aid = self.ids["acordo"] = ac["id"]
                self.passo(J, "inclui o profissional como parte", osc, "POST", f"/v1/signed-agreements/{aid}/parties",
                           {"org_id": pro.org_id, "role": "provider"})
                self.passo(J, "publica para assinatura", osc, "POST", f"/v1/signed-agreements/{aid}/publish")
                for c in (osc, pro):
                    self.assinar(J, c, "agreement", aid, f"/v1/signed-agreements/{aid}/sign",
                                 {"statement": "Assino este acordo e me responsabilizo pelo combinado."})
                vr = self.passo(J, "emite registro verificável do acordo", osc, "POST", "/v1/verifiable-records",
                                {"subject_type": "agreement", "subject_id": aid})
                if vr:
                    self.passo(J, "visitante confere o registro sem login", Http(self.base), "GET",
                               f"/v1/public/verify/{vr['code']}")
        pr = self.passo(J, "abre compra do projeto", osc, "POST", f"/v1/projects/{pid}/procurement",
                        {"description": "Compra de 10 violões", "estimated_cents": 500000})
        if pr:
            self.ids["compra"] = pr["id"]
            cot = []
            for loja, valor in (("Loja Exemplo A", 520000), ("Loja Exemplo B", 480000), ("Loja Exemplo C", 505000)):
                q = self.passo(J, f"registra orçamento ({loja})", osc, "POST", f"/v1/procurement/{pr['id']}/quotes",
                               {"supplier_name": loja, "amount_cents": valor})
                if q:
                    cot.append(q["id"])
            if len(cot) == 3:
                self.passo(J, "decide pelo menor orçamento", osc, "POST", f"/v1/procurement/{pr['id']}/decide", {"quotation_id": cot[1]})

    def _party(self, c: Client, aid: str) -> str:
        d = c.get(f"/v1/signed-agreements/{aid}").json
        return next(p["id"] for p in d["parties"] if p["org_id"] == c.org_id)

    def contrato_como_regra(self):
        """Tese v0.26.0: o contrato vira regra de operação — versões, obrigações, aceite a quatro olhos e matriz de distribuição."""
        J, osc, emp, pid = "Contrato como regra: financiamento → vigência → entrega → aceite → obrigações → nova versão", self.c["osc"], self.c["company"], self.ids["projeto"]
        doc = osc.upload("/v1/documents", "acordo-financiamento.pdf", b"%PDF-1.4\n% acordo de financiamento ficticio v1\n%%EOF\n",
                         {"doc_type": "contrato", "title": "Acordo de financiamento (exemplo)"})
        if doc.status != 201:
            self.passos.append({"jornada": J, "passo": "envia o acordo", "perfil": "osc", "metodo": "POST", "rota": "/v1/documents",
                                "status": doc.status, "ok": False, "erro": str(doc.json)[:300]})
            return
        # v0.27.0 — participação de autoria: a apoiadora (pessoa física) propôs a ideia; a OSC propõe a participação; ela aceita.
        apo = self.c["individual"]
        ideia = self.passo(J, "apoiadora registra a ideia na biblioteca de soluções", apo, "POST", "/v1/solutions", {
            "kind": "idea", "stage": "idea", "title": "Orquestra na escola — ideia original (exemplo)",
            "summary": "Ideia proposta por uma pessoa física: aulas de música no contraturno com instrumentos emprestados (dados fictícios).",
            "problem": "Crianças sem acesso a educação musical no bairro.", "approach": "Oficinas semanais com instrumentos da escola.",
            "themes": ["educacao"], "ownership_type": "author", "authorization_publish": True})
        part = None
        if ideia:
            self.passo(J, "apoiadora publica a ideia", apo, "POST", f"/v1/solutions/{ideia['id']}/publish")
            part = self.passo(J, "OSC propõe participação de autoria à apoiadora (1,5% quando elegível; nunca automática)", osc, "POST",
                              f"/v1/projects/{pid}/participations", {"proponent_org_id": apo.org_id, "idea_ref_type": "solution",
                                                                     "idea_ref_id": ideia["id"], "authorship_type": "author", "share_bps": 10000,
                                                                     "contribution": "Propôs a ideia original, participou da estruturação e da consolidação do projeto."})
            if part:
                self.ids["participacao"] = part["id"]
                self.passo(J, "apoiadora aceita a participação (projeto já publicado → consolidada)", apo, "POST", f"/v1/participations/{part['id']}/accept")
                self.passo(J, "apoiadora acompanha as próprias participações", apo, "GET", "/v1/participations")
        ac = self.passo(J, "OSC cria acordo de financiamento (camada econômica vem do catálogo 2027.01: 3,5% plataforma + 1,5% autoria, aporte único direcionado)", osc, "POST",
                        "/v1/signed-agreements", {
                            "kind": "funding", "title": "Financiamento — Orquestra na escola (exemplo)",
                            "summary": "R$ 100.000 em 2 marcos; o financiador faz um aporte único direcionado a cada destinatário pela chave PIX do contrato.",
                            "document_id": doc.json["id"], "project_id": pid, "value_cents": 10_000_000,
                            "review_days": 10, "calendar_type": "business", "dispute_days": 5})
        if not ac:
            return
        aid = self.ids["acordo_financiamento"] = ac["id"]
        self.passo(J, "inclui a empresa como financiadora", osc, "POST", f"/v1/signed-agreements/{aid}/parties", {"org_id": emp.org_id, "role": "funder"})
        self.passo(J, "quem recebe informa a própria chave PIX no contrato", osc, "PUT",
                   f"/v1/signed-agreements/{aid}/parties/{self._party(osc, aid)}/pix", {"pix_key": "12345678000195", "pix_key_type": "cnpj"})
        if part:
            self.passo(J, "inclui a apoiadora como proponente (parte opcional)", osc, "POST", f"/v1/signed-agreements/{aid}/parties",
                       {"org_id": apo.org_id, "role": "proponent", "required": False})
            self.passo(J, "apoiadora informa a própria chave PIX", apo, "PUT",
                       f"/v1/signed-agreements/{aid}/parties/{self._party(apo, aid)}/pix", {"pix_key": "elisa@demo.impacto.local", "pix_key_type": "email"})
        marcos = []
        for seq, (titulo, valor, dias) in enumerate((("Compra dos instrumentos", 5_000_000, 30), ("Primeiro semestre de aulas", 5_000_000, 200)), 1):
            m = self.passo(J, f"define o marco {seq}: {titulo}", osc, "POST", f"/v1/signed-agreements/{aid}/milestones",
                           {"title": titulo, "due_on": _d(dias), "seq": seq, "amount_cents": valor})
            if m:
                marcos.append(m["id"])
        self.passo(J, "publica para assinatura (versão 1 congelada)", osc, "POST", f"/v1/signed-agreements/{aid}/publish")
        prev = self.passo(J, "financiador vê a PRÉVIA da distribuição antes de assinar (95.000 projeto / 3.500 plataforma / 1.500 autoria, nada gravado)", emp, "GET",
                          f"/v1/signed-agreements/{aid}/allocation") or {}
        self.ids["alocacao_previa"] = (prev.get("preview") or {}).get("platform_fee_cents")
        for c in (osc, emp):
            self.assinar(J, c, "agreement", aid, f"/v1/signed-agreements/{aid}/sign",
                         {"statement": "Assino este acordo e me responsabilizo pelo combinado."})
        d = self.passo(J, "acordo vigente: matriz gravada, obrigações derivadas, taxa registrada e NÃO cobrada (regra desligada)", osc, "GET",
                       f"/v1/signed-agreements/{aid}") or {}
        self.ids["alocacao"] = {k: (d.get("allocation") or {}).get(k) for k in ("gross_cents", "project_cents", "platform_fee_cents", "fee_chargeable", "platform_charge_id")}
        self.ids["obrigacoes"] = len(d.get("obligations") or [])
        po = self.passo(J, "financiador abre as instruções de repasse (quem, quanto, por qual chave)", emp, "GET", f"/v1/signed-agreements/{aid}/payouts") or {}
        proj = next((p for p in po.get("items", []) if p["line_kind"] == "project"), None)
        if proj:
            t = self.passo(J, "financiador registra a transferência PIX feita ao projeto (a qualquer momento)", emp, "POST",
                           f"/v1/payouts/{proj['id']}/transfers", {"amount_cents": proj["amount_cents"], "reference": "E2E-DEMO-0001", "paid_on": _d(0)})
            if t:
                self.passo(J, "OSC (quem recebe) confirma o recebimento — quem paga nunca confirma", osc, "POST", f"/v1/payout-transfers/{t['id']}/confirm")
                self.passo(J, "financiador tenta confirmar o que ele mesmo pagou → recusado", emp, "POST", f"/v1/payout-transfers/{t['id']}/confirm", esperado=(403,))
        prop_line = next((p for p in po.get("items", []) if p["line_kind"] == "proponent"), None)
        if prop_line:
            t2 = self.passo(J, "financiador registra a transferência da participação de autoria à apoiadora", emp, "POST",
                            f"/v1/payouts/{prop_line['id']}/transfers", {"amount_cents": prop_line["amount_cents"], "reference": "E2E-DEMO-0002", "paid_on": _d(0)})
            if t2:
                self.passo(J, "apoiadora confirma o recebimento da participação", apo, "POST", f"/v1/payout-transfers/{t2['id']}/confirm")
        self.passo(J, "o que o IMPACTO fez nesta operação (por registro)", emp, "GET", f"/v1/signed-agreements/{aid}/value")
        if marcos:
            self.passo(J, "OSC registra a entrega do marco 1", osc, "PATCH", f"/v1/signed-agreements/{aid}/milestones/{marcos[0]}", {"status": "delivered"})
            self.passo(J, "OSC tenta aceitar a própria entrega → recusado (quatro olhos)", osc, "PATCH",
                       f"/v1/signed-agreements/{aid}/milestones/{marcos[0]}", {"status": "accepted"}, esperado=(403, 409, 422))
            self.passo(J, "financiador vê o que precisa da sua decisão", emp, "GET", "/v1/agreements/pending")
            self.passo(J, "financiador aceita a entrega do marco 1 → obrigação de pagar nasce com prazo", emp, "PATCH",
                       f"/v1/signed-agreements/{aid}/milestones/{marcos[0]}", {"status": "accepted"})
        if len(marcos) > 1:
            self.passo(J, "OSC registra a entrega do marco 2", osc, "PATCH", f"/v1/signed-agreements/{aid}/milestones/{marcos[1]}", {"status": "delivered"})
            self.passo(J, "financiador recusa o marco 2 com motivo (volta para quem executa)", emp, "PATCH",
                       f"/v1/signed-agreements/{aid}/milestones/{marcos[1]}", {"status": "rejected", "note": "Faltou a lista de presença assinada das aulas."})
        self.passo(J, "razão do projeto registra ativação, alocação, entrega e aceite em cadeia", osc, "GET", f"/v1/projects/{pid}/ledger")
        doc2 = osc.upload("/v1/documents", "acordo-financiamento-v2.pdf", b"%PDF-1.4\n% acordo de financiamento ficticio v2\n%%EOF\n",
                          {"doc_type": "contrato", "title": "Acordo de financiamento v2 (exemplo)"})
        if doc2.status == 201:
            v2 = self.passo(J, "mudança no contrato → nova versão em rascunho; a anterior fica substituída e exige nova assinatura", osc, "POST",
                            f"/v1/signed-agreements/{aid}/new-version",
                            {"document_id": doc2.json["id"], "reason": "Prazo do segundo marco prorrogado em 60 dias a pedido da escola."})
            if v2:
                self.ids["acordo_financiamento_v2"] = v2["id"]
                self.passo(J, "versão antiga não recebe assinatura (substituída)", emp, "POST", f"/v1/signed-agreements/{aid}/sign",
                           {"statement": "Assino este acordo e me responsabilizo pelo combinado.", "password": self.senha, "code": "000000"},
                           esperado=(409,))

    def mercado_e_perfis(self):
        J, osc, pro, pid = "Marketplace, soluções e perfis públicos", self.c["osc"], self.c["provider"], self.ids["projeto"]
        lst = self.passo(J, "OSC anuncia o projeto no marketplace", osc, "POST", "/v1/marketplace/listings", {
            "subject_type": "project", "subject_id": pid, "seeking": ["investment"],
            "headline": "Orquestra comunitária busca apoio para o segundo semestre",
            "summary": "40 crianças, aulas semanais, prestação de contas aberta (exemplo)."})
        if lst:
            self.passo(J, "OSC publica o anúncio", osc, "POST", f"/v1/marketplace/listings/{lst['id']}/transition", {"to": "published"})
        sol = self.passo(J, "OSC cadastra a metodologia como solução", osc, "POST", "/v1/solutions", {
            "kind": "project", "stage": "running", "title": "Orquestra de violões no contraturno (exemplo)",
            "summary": "Metodologia de ensino coletivo de violão para crianças, com avaliação por frequência.",
            "problem": "Falta de acesso à educação musical.", "approach": "Aulas coletivas semanais e apresentação semestral.",
            "themes": ["cultura", "educacao"], "ownership_type": "organization", "authorization_publish": True})
        if sol:
            self.ids["solucao"] = sol["id"]
            self.passo(J, "OSC publica a solução", osc, "POST", f"/v1/solutions/{sol['id']}/publish")
        for papel, c, nome in (("osc", osc, "Instituto Exemplo de Música"), ("provider", pro, "Contabilidade Exemplo")):
            self.passo(J, f"{papel} cria perfil público", c, "POST", "/v1/profiles", {
                "handle": f"demo{papel}{uuid.uuid4().hex[:6]}", "display_name": nome,
                "headline": "Perfil de demonstração (fictício)", "owner": "org"})

    def suporte_e_conhecimento(self):
        J, osc, sup = "Suporte e Central de Conhecimento", self.c["osc"], self.c["support"]
        t = self.passo(J, "OSC abre chamado", osc, "POST", "/v1/support/tickets", {
            "category": "question", "subject": "Como anexo a ata de eleição?",
            "message": "Não encontrei onde enviar a ata de eleição da diretoria."})
        if t:
            self.ids["chamado"] = t["id"]
            self.passo(J, "suporte responde o chamado", sup, "POST", f"/v1/admin/support/tickets/{t['id']}/messages",
                       {"body": "Em Documentos, escolha o tipo 'Ata de eleição'."})
            self.passo(J, "OSC lê a resposta", osc, "GET", f"/v1/support/tickets/{t['id']}")
        cursos = self.passo(J, "OSC lista cursos", osc, "GET", "/v1/help/courses") or {}
        # o curso DA DEMONSTRAÇÃO (kb_seed), pelo nome: outros cursos com certificado podem existir
        from impacto.services import kb_seed
        curso = next((c for c in cursos.get("items", []) if c.get("slug") == kb_seed.COURSE["slug"]), None)
        if curso:
            self.passo(J, "OSC se inscreve no curso", osc, "POST", f"/v1/help/courses/{curso['slug']}/enroll")
            det = self.passo(J, "OSC abre o curso", osc, "GET", f"/v1/help/courses/{curso['slug']}") or {}
            for m in det.get("modules", []):
                for aula in m.get("lessons", []):
                    corpo = {}
                    if aula.get("kind") == "quiz":
                        # As respostas são as que a própria aula ensina (material do curso em kb_seed);
                        # a nota é calculada pelo servidor contra o gabarito que ele guarda.
                        from impacto.services import kb_seed
                        gab = next((ls for md in kb_seed.COURSE["modules"] for ls in md["lessons"]
                                    if ls["title"] == aula.get("title")), None)
                        corpo = {"answers": [q["answer"] for q in (gab or {}).get("quiz", [])]}
                    self.passo(J, f"OSC conclui a aula '{aula.get('title')}'", osc, "POST",
                               f"/v1/help/lessons/{aula['id']}/complete", corpo)
            self.passo(J, "OSC emite certificado", osc, "POST", f"/v1/help/courses/{curso['slug']}/certificate")

    def banco_de_ideias(self):
        J, osc = "Banco de Ideias: ideia → amadurecimento → projeto", self.c["osc"]
        i = self.passo(J, "OSC registra ideia", osc, "POST", "/v1/ideas", {
            "title": "Biblioteca itinerante nas escolas do campo (exemplo)", "stage": "raw",
            "problem": "Escolas rurais sem biblioteca (exemplo).", "causes": ["educacao"], "ods": [4]})
        if not i:
            return
        iid = self.ids["ideia"] = i["id"]
        self.passo(J, "OSC amadurece a ideia (hipótese, público, impacto)", osc, "PUT", f"/v1/ideas/{iid}", {
            "title": "Biblioteca itinerante nas escolas do campo (exemplo)", "stage": "ready",
            "problem": "Escolas rurais sem biblioteca (exemplo).", "hypothesis": "Acervo rotativo mensal aumenta o empréstimo de livros.",
            "audience": "Estudantes de 6 a 14 anos de 5 escolas rurais", "territory": "BR-MT-5105259",
            "solution_idea": "Van com acervo rotativo e mediadora de leitura.", "expected_impact": "Mais leitura, medida por empréstimos.",
            "causes": ["educacao"], "ods": [4]})
        self.passo(J, "OSC abre a ideia", osc, "GET", f"/v1/ideas/{iid}")
        p = self.passo(J, "OSC transforma a ideia em projeto", osc, "POST", f"/v1/ideas/{iid}/promote",
                       {"summary": "Projeto nascido da ideia da biblioteca itinerante (exemplo)."})
        if p:
            self.ids["projeto_da_ideia"] = p.get("project_id") or p.get("id")
            self.passo(J, "OSC abre o projeto criado", osc, "GET", f"/v1/projects/{self.ids['projeto_da_ideia']}")

    def administracao(self):
        J, adm = "Administração: visão geral → verificação → auditoria", self.c["admin"]
        self.passo(J, "abre a visão geral", adm, "GET", "/v1/admin/overview")
        self.passo(J, "lista organizações", adm, "GET", "/v1/admin/organizations")
        self.passo(J, "lista usuários", adm, "GET", "/v1/admin/users")
        sol = self.ids.get("solucao")
        if sol:
            self.passo(J, "classifica a solução nova como autodeclarada", adm, "POST", f"/v1/admin/solutions/{sol}/verify",
                       {"trust_level": "self_declared", "note": "Sem evidência anexada; segue autodeclarada (exemplo)."})
        self.passo(J, "confere a cadeia da auditoria", adm, "GET", "/v1/admin/audit/verify")
        self.confirmar_identidade(adm, J)
        self.passo(J, "lê o estado do interruptor de emergência", adm, "GET", "/v1/admin/kill-switch")

    def pendencias(self):
        """O que fica EM ABERTO na demonstração: caixa de entrada sem nada pendente não demonstra o produto."""
        J = "Pendências: o que espera decisão de alguém"
        osc, emp, pro, ind, pid = self.c["osc"], self.c["company"], self.c["provider"], self.c["individual"], self.ids["projeto"]
        p = self.passo(J, "profissional propõe serviço à OSC", pro, "POST", "/v1/proposals", {
            "kind": "service", "receiver_org_id": osc.org_id, "project_id": pid, "compensation": "paid",
            "support_mode": "service", "title": "Organização do arquivo de prestação de contas",
            "purpose": "Organizar comprovantes por rubrica antes do relatório final (exemplo)."})
        if p:
            self.passo(J, "profissional envia (fica aguardando a OSC)", pro, "POST", f"/v1/proposals/{p['id']}/transition", {"to": "sent"})
        u = self.passo(J, "OSC envia relatório do 2º período", osc, "POST", "/v1/impact-updates", {
            "project_id": pid, "period_start": _d(0), "period_end": _d(0),
            "summary": "Parcial do segundo semestre: aulas retomadas, listas de presença anexadas (exemplo).",
            "outputs": "8 encontros.", "limitations": "Período curto; sem comparação."})
        if u:
            self.passo(J, "relatório aguarda análise do apoiador", osc, "POST", f"/v1/impact-updates/{u['id']}/transition", {"to": "submitted"})
        for texto in ("Atendemos 33 crianças com frequência registrada em lista de presença.",
                      "O projeto erradicou a falta de acesso à música no bairro."):
            c = self.passo(J, "OSC declara afirmação de impacto", osc, "POST", "/v1/claims", {
                "subject_type": "project", "subject_id": pid, "claim_kind": "result", "statement": texto})
            if c:
                self.passo(J, "plataforma confere a afirmação", osc, "POST", f"/v1/claims/{c['id']}/check")
        self.passo(J, "profissional declara experiência com a OSC (aguarda confirmação)", pro, "POST", "/v1/profile/experiences", {
            "org_name": "Instituto Exemplo Fictício de Música e Cidadania", "org_id": osc.org_id, "role": "Contadora",
            "started_on": _d(-400), "ended_on": _d(-30), "visibility": "public",
            "description": "Prestação de contas de dois ciclos do projeto (exemplo)."})
        self.passo(J, "profissional cadastra nova credencial (aguarda conferência)", pro, "POST", "/v1/org/credentials", {
            "council": "CRC", "number": "MT-999999/O-9", "uf": "MT", "holder_name": "Carla Exemplo"})
        orgs = self.passo(J, "administração procura a organização em estruturação", self.c["admin"], "GET",
                          "/v1/admin/organizations?q=Coletivo") or {}
        alvo = (orgs.get("items") or [{}])[0].get("id")
        if alvo:
            self.passo(J, "apoiadora denuncia dado incorreto (vai para a moderação)", ind, "POST", "/v1/reports", {
                "target_type": "organization", "target_id": alvo, "reason": "incorrect_data", "category": "false_information",
                "details": "O endereço informado não corresponde ao da sede (denúncia fictícia de demonstração)."})

    def run(self) -> dict:
        self.preparar()
        for etapa in (self.osc_projeto_e_diagnostico, self.financiador, self.rede, self.profissional, self.governo,
                      self.captacao, self.documentos, self.contrato_como_regra, self.mercado_e_perfis, self.suporte_e_conhecimento,
                      self.banco_de_ideias, self.administracao, self.pendencias):
            try:
                etapa()
            except Exception as exc:  # noqa: BLE001 — uma jornada quebrada não pode esconder as outras
                self.passos.append({"jornada": etapa.__name__, "passo": "exceção no roteiro", "perfil": "", "metodo": "", "rota": "",
                                    "status": 0, "ok": False, "erro": repr(exc)[:300]})
        return {"passos": self.passos, "falhas": [p for p in self.passos if not p["ok"]],
                "atalhos": self.atalhos, "ids": self.ids}


def run(base: str, state) -> dict:
    """No servidor de teste: código de assinatura do outbox e segredo TOTP decifrado pelo próprio app.
    Executa uma vez por processo (o servidor de teste é compartilhado)."""
    global _RESULTADO
    if _RESULTADO is None:
        from tests.support import PASSWORD, last_signature_code

        def segredo(email: str) -> str:
            from impacto.db.pool import DbContext
            with state.pool.tx(DbContext(system=True)) as c:
                return state.cipher.decrypt(c.scalar("SELECT mfa_secret_enc FROM users WHERE email = $1", email))
        _RESULTADO = Jornadas(base, PASSWORD, last_signature_code, segredo).run()
    return _RESULTADO
