"""Robô de navegador que abre TODAS as telas do roteador, com cada perfil de demonstração.

v0.25.0. Até aqui a demonstração abria pelo navegador só as telas que o MENU de cada perfil oferece
(295 visitas). O inventário tem 218 telas, 119 só alcançáveis por link e 52 com parâmetro (`:id`,
`:slug`...). Uma tela que só abre por link, ou que depende de um registro, nunca tinha sido aberta.

O QUE ELE FAZ
  1. lê `docs/execution/screen_inventory.json` (as três tabelas do roteador, na ordem de casamento);
  2. para cada rota com parâmetro, busca no banco um registro REAL da demonstração (SQL abaixo).
     Se não houver registro, a visita é `SEM_REGISTRO` — falta dado na demonstração, não "passou";
  3. visita a rota com cada perfil que deve vê-la, e com um perfil que NÃO deve (a recusa tem de
     aparecer como "Esta área não está disponível para este perfil", nunca como erro);
  4. classifica cada visita pelo que a pessoa vê e pelo que o servidor respondeu.

O QUE ELE NÃO PROVA
  Que a tela está correta, completa ou bonita. Prova que abre com dado real, sem erro de JavaScript,
  sem 5xx, sem cair no "Página não encontrada", e que a recusa por perfil funciona. Interação
  (preencher, salvar) é provada pelas jornadas, não por este robô.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTARIO = ROOT / "docs" / "execution" / "screen_inventory.json"

#: rótulo do inventário → chave da persona de demonstração (seed_dev.DEMO_EMAILS)
PERSONA_DO_TIPO = {"OSC": "osc", "Empresa": "company", "Apoiador": "individual", "Profissional": "provider",
                   "Governo": "government", "Administração": "admin", "Equipe interna": "admin"}
#: quem visita as telas sem restrição de tipo
TODOS = ("osc", "company", "provider", "government", "individual", "admin")

#: rota com parâmetro → SQL que devolve um valor real da demonstração (primeira coluna da primeira linha).
#: `{org}` é a organização da persona que visita: cada perfil abre um registro DO QUAL PARTICIPA —
#: é o que a pessoa faria no produto. Abrir o registro de outra organização devolve 404 de propósito
#: (isolamento por organização), e isso é provado à parte pelos testes de autorização.
_PUB = "visibility <> 'public', created_at"
RESOLVE: dict[str, str] = {
    "/@:handle": "SELECT handle FROM public_profiles WHERE handle IS NOT NULL AND visibility = 'public' ORDER BY created_at LIMIT 1",
    "/ajuda/:slug": "SELECT slug FROM kb_articles WHERE published_at IS NOT NULL AND visibility = 'public' ORDER BY created_at LIMIT 1",
    # Conteúdo público primeiro: a mesma rota é visitada sem login, e conteúdo só para quem entrou
    # responde 404 ao anônimo de propósito (não revela que existe).
    "/ajuda/academia/:slug": f"SELECT slug FROM courses WHERE published_at IS NOT NULL ORDER BY {_PUB} LIMIT 1",
    "/ajuda/academia/aula/:id": "SELECT l.id::text FROM course_lessons l JOIN courses c ON c.id = l.course_id"
                                " WHERE c.published_at IS NOT NULL ORDER BY l.position LIMIT 1",
    "/ajuda/biblioteca/:slug": f"SELECT slug FROM kb_resources WHERE published_at IS NOT NULL ORDER BY {_PUB} LIMIT 1",
    "/ajuda/certificado/:code": "SELECT code FROM course_certificates LIMIT 1",
    "/ajuda/eventos/:slug": f"SELECT slug FROM hub_events WHERE published_at IS NOT NULL ORDER BY {_PUB} LIMIT 1",
    "/ajuda/faq/:id": "SELECT id::text FROM kb_faqs WHERE published_at IS NOT NULL ORDER BY created_at LIMIT 1",
    "/ajuda/suporte/:id": "SELECT id::text FROM support_tickets WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/campanha/:slug": "SELECT slug FROM campaigns WHERE published_at IS NOT NULL ORDER BY created_at LIMIT 1",
    "/verificar/:code": "SELECT code FROM verifiable_records ORDER BY created_at LIMIT 1",
    "/ia/analises/:id": "SELECT id::text FROM similarity_analyses WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/ia/patrocinios/:id": "SELECT id::text FROM ai_sponsorships WHERE sponsor_org_id = {org} ORDER BY created_at LIMIT 1",
    "/acordos/:id": "SELECT a.id::text FROM signed_agreements a WHERE a.org_id = {org}"
                    " OR EXISTS (SELECT 1 FROM signed_agreement_parties p WHERE p.agreement_id = a.id AND p.org_id = {org})"
                    # o acordo mais rico primeiro: vigente com matriz de distribuição e obrigações (v0.26.0)
                    " ORDER BY (a.status = 'active') DESC, (a.platform_fee_bps IS NOT NULL) DESC, a.created_at LIMIT 1",
    "/admin/central/artigos/:slug": "SELECT slug FROM kb_articles ORDER BY created_at LIMIT 1",
    "/admin/central/suporte/:id": "SELECT id::text FROM support_tickets ORDER BY created_at LIMIT 1",
    "/candidaturas/:id": "SELECT id::text FROM applications WHERE {org} IN (osc_org_id, funder_org_id) ORDER BY created_at LIMIT 1",
    "/compras/:id": "SELECT id::text FROM procurement_requests WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/conversas/:id": "SELECT id::text FROM conversations WHERE {org} IN (org_a, org_b) ORDER BY created_at LIMIT 1",
    "/cotas/:id/apoios": "SELECT id::text FROM funding_quotas WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/diagnosticos/:id": "SELECT id::text FROM diagnoses WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/documentos/montagens/:id": "SELECT id::text FROM document_assemblies WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/editais/:id": "SELECT id::text FROM calls WHERE owner_org_id = {org} ORDER BY created_at LIMIT 1",
    "/instituicoes/:id": "SELECT id::text FROM organizations WHERE kind = 'osc' ORDER BY created_at LIMIT 1",
    "/marketplace/:id": "SELECT id::text FROM marketplace_listings WHERE published_at IS NOT NULL ORDER BY created_at LIMIT 1",
    "/mensagens/:id": "SELECT id::text FROM conversations WHERE {org} IN (org_a, org_b) ORDER BY created_at LIMIT 1",
    "/necessidades/:id": "SELECT id::text FROM project_needs WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/oportunidades/:id": "SELECT id::text FROM calls WHERE status = 'open' ORDER BY created_at LIMIT 1",
    "/pagamentos/:id": "SELECT id::text FROM payment_records WHERE {org} IN (osc_org_id, funder_org_id) ORDER BY created_at LIMIT 1",
    "/perfil-publico/:id": "SELECT id::text FROM public_profiles WHERE org_id = {org} LIMIT 1",
    # Projeto da própria organização; para quem não executa projeto (financiador, governo, apoiador,
    # administração), um projeto PUBLICADO — é esse que essas pessoas abrem no produto.
    "/projetos/:id": "SELECT id::text FROM projects WHERE org_id = {org} OR visibility = 'published'"
                     " ORDER BY (org_id = {org}) DESC, created_at LIMIT 1",
    "/propostas/:id": "SELECT id::text FROM proposals WHERE {org} IN (sender_org_id, receiver_org_id) ORDER BY created_at LIMIT 1",
    "/rascunhos/:id": "SELECT id::text FROM drafts WHERE org_id = {org} ORDER BY created_at LIMIT 1",
    "/relatorios-impacto/:id": "SELECT id::text FROM impact_updates WHERE {org} IN (org_id, reviewed_by_org)"
                               " ORDER BY created_at LIMIT 1",
    "/revisoes/:id": "SELECT id::text FROM professional_reviews WHERE {org} IN (org_id, professional_org_id)"
                     " ORDER BY created_at LIMIT 1",
    "/solucoes/:id": "SELECT id::text FROM solutions WHERE visibility = 'published' ORDER BY created_at LIMIT 1",
}
#: subrotas que usam o mesmo registro da rota-mãe
for _sub in ("apoio-profissional", "compras", "contribuicao", "equidade", "equipe", "grafo", "impacto",
             "linha-do-tempo", "localizacao", "ods", "relatorios", "retratos", "riscos", "situacao"):
    RESOLVE[f"/projetos/:id/{_sub}"] = RESOLVE["/projetos/:id"]
# v0.30.0 (ADR-361): o dossiê é só para as PARTES — projeto publicado não basta. A persona abre o projeto que é dela ou que
# ela financia (compromisso); quem não tem relação fica "sem registro próprio", que é o comportamento correto, não falha.
RESOLVE["/projetos/:id/dossie"] = ("SELECT p.id::text FROM projects p WHERE p.org_id = {org} OR EXISTS (SELECT 1 FROM commitments c"
                                   " WHERE c.project_id = p.id AND c.funder_org_id = {org} AND c.status <> 'cancelled') ORDER BY p.created_at LIMIT 1")
RESOLVE["/diagnosticos/:id/roteiro"] = RESOLVE["/diagnosticos/:id/versoes"] = RESOLVE["/diagnosticos/:id"]
RESOLVE["/editais/:id/candidaturas"] = RESOLVE["/editais/:id/editar"] = RESOLVE["/editais/:id"]
RESOLVE["/perfil-publico/:id/identificadores"] = RESOLVE["/perfil-publico/:id"]
RESOLVE["/solucoes/:id/editar"] = "SELECT id::text FROM solutions WHERE org_id = {org} ORDER BY created_at LIMIT 1"

KIND_DA_PERSONA = {"osc": "osc", "company": "company", "provider": "provider", "government": "government",
                   "individual": "individual", "admin": "platform"}

#: classificações. As três primeiras são sucesso; as demais são achado.
OK, VAZIA, RECUSA_CERTA = "OK", "VAZIA", "RECUSA_CORRETA"
FALHAS = ("CHAMADA_RECUSADA", "SEM_ACAO", "ERRO_JS", "5XX", "ERRO_NA_TELA", "NAO_ENCONTRADA", "RECUSA_INDEVIDA", "NAO_RECUSOU",
          "SEM_REGISTRO", "LOGIN_PEDIDO", "TRAVOU")


#: Botões e links SEM AÇÃO na tela renderizada. O React guarda os manipuladores numa propriedade
#: `__reactProps$…` do elemento; botão que não é `submit` de formulário e não tem `onClick` (nem
#: ancestral que trate o clique) não faz nada quando a pessoa clica. Link `<a>` sem `href` idem.
SEM_ACAO_JS = """() => {
  const props = (el) => { const k = Object.keys(el).find((x) => x.startsWith('__reactProps$')); return k ? el[k] : {}; };
  const temClique = (el) => { for (let n = el; n && n !== document.body; n = n.parentElement) {
      const p = props(n); if (p.onClick || p.onMouseDown || p.onPointerDown) return true; } return false; };
  const fora = [];
  for (const b of document.querySelectorAll('button')) {
    if (b.disabled || b.closest('[hidden]') || b.offsetParent === null) continue;
    const tipo = (b.getAttribute('type') || 'submit').toLowerCase();
    if (tipo === 'submit' && b.form) continue;
    if (!temClique(b)) fora.push('botão: ' + (b.innerText || b.getAttribute('aria-label') || '?').trim().slice(0, 40));
  }
  for (const a of document.querySelectorAll('a')) {
    if (a.offsetParent === null) continue;
    if (!a.getAttribute('href') && !temClique(a)) fora.push('link: ' + (a.innerText || '?').trim().slice(0, 40));
  }
  return fora;
}"""


def inventario() -> list[dict]:
    return json.loads(INVENTARIO.read_text(encoding="utf-8"))["lista"]


def preencher(rota: str, email: str, consulta) -> tuple[str | None, str]:
    """Rota concreta para a persona, ou (None, motivo). `consulta(sql)` devolve o primeiro valor ou None."""
    if ":" not in rota:
        return rota, ""
    sql = RESOLVE.get(rota)
    if not sql:
        return None, "rota com parâmetro sem resolvedor no robô"
    org = ("(SELECT m.org_id FROM memberships m JOIN users u ON u.id = m.user_id"
           f" WHERE u.email = '{email}' ORDER BY m.created_at LIMIT 1)")
    try:
        valor = consulta(sql.replace("{org}", org))
    except Exception as exc:  # noqa: BLE001 — resolvedor errado é achado do robô, não da tela
        return None, f"resolvedor falhou: {str(exc).splitlines()[0][:120]}"
    if not valor:
        return None, "a persona não participa de nenhum registro deste tipo na demonstração"
    return re.sub(r":[a-z]+", str(valor), rota, count=1), ""


def plano(lista: list[dict]) -> list[tuple[dict, str, bool]]:
    """(entrada do inventário, persona, deve_ver). `persona` vazia = sem login."""
    visitas = []
    for t in lista:
        if t["tabela"] == "PUBLIC":
            visitas.append((t, "", True))
        elif t["tabela"] == "HELP":
            visitas.append((t, "", not t.get("exige_login")))
            visitas.append((t, "osc", True))
        else:
            if t["alcanca"] == ["todos os tipos"]:
                visitas += [(t, p, True) for p in TODOS]
            else:
                pode = [PERSONA_DO_TIPO[a] for a in t["alcanca"] if a in PERSONA_DO_TIPO]
                visitas += [(t, p, True) for p in pode]
                # um perfil que NÃO deve ver a tela; se todos os perfis de demonstração podem, não há recusa a testar
                fora = next((p for p in ("government", "osc", "company", "provider", "individual") if p not in pode), None)
                if fora:
                    visitas.append((t, fora, False))
    return visitas


def classificar(p, deve_ver: bool, eventos: dict, url_final: str, rota_pedida: str) -> tuple[str, str]:
    texto_h1 = (p.locator("h1").first.inner_text(timeout=1000) if p.locator("h1").count() else "").strip()
    recusa = "não está disponível para este perfil" in texto_h1
    if eventos["js"]:
        return "ERRO_JS", eventos["js"][0][:200]
    if eventos["5xx"]:
        return "5XX", " ".join(f"{s} {u}" for s, u in eventos["5xx"][:2])
    if texto_h1 == "Página não encontrada":
        return "NAO_ENCONTRADA", ""
    if "/entrar" in url_final and "/entrar" not in rota_pedida:
        # sem login, tela que exige login TEM de mandar para /entrar
        return (RECUSA_CERTA, "pediu login") if not deve_ver else ("LOGIN_PEDIDO", url_final)
    if not deve_ver:
        return (RECUSA_CERTA, "") if recusa else ("NAO_RECUSOU", texto_h1[:80])
    if recusa:
        return "RECUSA_INDEVIDA", ""
    if p.locator(".state-error").count():
        msg = p.locator(".state-error").first.inner_text(timeout=1000).strip().replace("\n", " ")[:160]
        return "ERRO_NA_TELA", msg
    if p.locator(".state-empty").count():
        return VAZIA, texto_h1[:80]
    return OK, texto_h1[:80]


#: axe-core (quando fornecido): regras WCAG 2.0/2.1 nível A e AA, sobre a página renderizada.
AXE_RUN_JS = """async () => {
  const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}});
  return r.violations.map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
                                 exemplo: (v.nodes[0] && v.nodes[0].target || []).join(' ').slice(0, 120)}));
}"""


class Robo:
    def __init__(self, browser, base: str, senha: str, totp_codigo, axe_src: str | None = None):
        self.browser, self.base, self.senha, self.totp_codigo = browser, base, senha, totp_codigo
        self.paginas: dict[str, object] = {}
        # axe roda UMA vez por rota (na primeira visita bem-sucedida): a regra é da tela, não da persona
        self.axe_src, self.axe_feitas = axe_src, set()

    def _nova(self):
        # Com axe ligado a CSP é ignorada SÓ nesta página de auditoria: o produto proíbe script injetado
        # (como deve), e o axe é um script injetado. Sem axe, a CSP real vale.
        ctx = self.browser.new_context(viewport={"width": 1366, "height": 900}, bypass_csp=bool(self.axe_src))
        p = ctx.new_page()
        p.ev = {"js": [], "5xx": [], "4xx": [], "api": 0}

        def console(m):
            if m.type == "error" and "Failed to load resource" not in m.text:
                p.ev["js"].append(m.text)
        p.on("pageerror", lambda e: p.ev["js"].append(str(e)))
        p.on("console", console)

        def resposta(r):
            if "/v1/" in r.url:
                p.ev["api"] += 1
                if r.status >= 500:
                    p.ev["5xx"].append((r.status, r.url.split(self.base)[-1][:100]))
                elif r.status >= 400:
                    p.ev["4xx"].append((r.status, r.url.split(self.base)[-1][:100]))
        p.on("response", resposta)
        return p

    def pagina(self, persona: str, email: str | None):
        if persona in self.paginas:
            return self.paginas[persona]
        p = self._nova()
        if email:
            p.goto(self.base + "/entrar")
            p.get_by_label("E-mail").fill(email)
            p.get_by_label("Senha").fill(self.senha)
            p.get_by_role("button", name="Entrar").click()
            p.wait_for_selector('nav#rail, .portal, h1:has-text("Verificação em duas etapas")', timeout=20000)
            if p.get_by_role("heading", name="Verificação em duas etapas").count():
                p.get_by_label("Código do aplicativo autenticador").fill(self.totp_codigo())
                p.get_by_role("button", name="Confirmar").click()
                p.wait_for_selector("nav#rail, .portal", timeout=20000)
        self.paginas[persona] = p
        return p

    def _confirmar_identidade(self, p) -> bool:
        """Operação sensível abre a confirmação de identidade (v0.25.0). O robô confirma de verdade —
        senha e código TOTP novo — e espera a tela recarregar o que pediu."""
        dlg = p.locator('dialog[open]:has(h2:has-text("Confirme sua identidade"))')
        if not dlg.count():
            return False
        dlg.get_by_label("Senha").fill(self.senha)
        if dlg.get_by_label("Código do aplicativo autenticador").count():
            dlg.get_by_label("Código do aplicativo autenticador").fill(self.totp_codigo())
        dlg.get_by_role("button", name="Confirmar").click()
        p.wait_for_function("() => !document.querySelector('dialog[open]')", timeout=10000)
        try:
            p.wait_for_load_state("networkidle", timeout=8000)
        except Exception:  # noqa: BLE001
            pass
        return True

    def visitar(self, persona: str, email: str | None, rota: str, deve_ver: bool) -> dict:
        p = self.pagina(persona, email)
        for k in ("js", "5xx", "4xx"):
            p.ev[k].clear()
        p.ev["api"] = 0
        t0 = time.monotonic()
        try:
            p.goto(self.base + rota, wait_until="domcontentloaded", timeout=20000)
            try:
                p.wait_for_load_state("networkidle", timeout=10000)
            except Exception:  # noqa: BLE001 — polling legítimo não pode virar falha
                pass
            p.wait_for_timeout(150)
            confirmou = self._confirmar_identidade(p)
            estado, detalhe = classificar(p, deve_ver, p.ev, p.url, rota)
            if confirmou and estado in (OK, VAZIA):
                detalhe = ("identidade confirmada; " + detalhe).strip()
        except Exception as exc:  # noqa: BLE001
            estado, detalhe = "TRAVOU", str(exc).splitlines()[0][:160]
        try:
            sem_acao = p.evaluate(SEM_ACAO_JS) if estado in (OK, VAZIA, RECUSA_CERTA) else []
        except Exception:  # noqa: BLE001
            sem_acao = []
        if sem_acao:
            estado, detalhe = "SEM_ACAO", "; ".join(sorted(set(sem_acao)))[:200]
        # Chamada RECUSADA por trás de uma tela que abriu (v0.25.0): a tela parece vazia, mas pediu à
        # API algo que o perfil não pode ter, ou pediu errado. 401 fica de fora (sessão do visitante
        # anônimo; confirmação de identidade, que o robô completa) e 402 também (plano: estado legítimo).
        recusadas = sorted({f"{s} {u.split('?')[0]}" for s, u in p.ev["4xx"] if s in (403, 404, 409, 422)})
        # Única exceção: visitante SEM LOGIN em conteúdo só para quem tem conta. O servidor responde 404
        # de propósito (não revela que existe) e a tela convida a entrar — é o comportamento certo.
        convite = persona == "" and recusadas and all(r.startswith("404 /v1/help/") for r in recusadas) \
            and p.get_by_text("Entre para ver este conteúdo").count() > 0
        if recusadas and estado in (OK, VAZIA) and not convite:
            estado, detalhe = "CHAMADA_RECUSADA", " | ".join(recusadas)[:200]
        elif convite:
            detalhe = "convite para entrar (conteúdo só para quem tem conta)"
        axe = None
        chave = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", ":id", rota)
        if self.axe_src and deve_ver and estado in (OK, VAZIA) and chave not in self.axe_feitas:
            self.axe_feitas.add(chave)
            try:
                p.add_script_tag(content=self.axe_src)
                axe = p.evaluate(AXE_RUN_JS)
            except Exception as exc:  # noqa: BLE001 — falha do axe é registrada, não escondida
                axe = [{"id": "axe-nao-rodou", "impact": "?", "help": str(exc)[:120], "nodes": 0, "exemplo": ""}]
        pasta = os.getenv("TELAS_PRINT_DIR")   # evidência visual opcional (página inteira, por persona)
        if pasta:
            try:
                nome = re.sub(r"[^a-z0-9]+", "-", (persona or "anonimo") + rota.lower()).strip("-")[:120]
                Path(pasta).mkdir(parents=True, exist_ok=True)
                p.screenshot(path=str(Path(pasta) / f"{nome}.png"), full_page=True)
            except Exception:  # noqa: BLE001 — a evidência é extra, nunca o veredito
                pass
        return {"estado": estado, "detalhe": detalhe, "ms": int((time.monotonic() - t0) * 1000), "axe": axe,
                "chamadas_api": p.ev["api"], "api_4xx": sorted({f"{s} {u}" for s, u in p.ev["4xx"]})[:4]}

    def fechar(self):
        for p in self.paginas.values():
            p.context.close()
        self.paginas.clear()


def rodar(browser, base: str, senha: str, emails: dict, consulta, totp_codigo, lista=None, axe_src=None) -> list[dict]:
    lista = lista or inventario()
    robo = Robo(browser, base, senha, totp_codigo, axe_src)
    linhas = []
    try:
        for t, persona, deve_ver in plano(lista):
            rota, motivo = preencher(t["rota"], emails[persona or "osc"], consulta)
            base_linha = {"rota": t["rota"], "tabela": t["tabela"], "componente": t["componente"],
                          "persona": persona or "anônimo", "deve_ver": deve_ver, "alcance": t["alcance"]}
            if rota is None:
                linhas.append({**base_linha, "url": "", "estado": "SEM_REGISTRO", "detalhe": motivo, "ms": 0,
                               "chamadas_api": 0, "api_4xx": [], "axe": None})
                continue
            r = robo.visitar(persona, emails.get(persona) if persona else None, rota, deve_ver)
            linhas.append({**base_linha, "url": rota, **r})
    finally:
        robo.fechar()
    return linhas
