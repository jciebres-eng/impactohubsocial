import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import { Link, match, navigate, useLocation } from "./router";
import { useSession } from "./session";
import { Button, StateView, useAction } from "./ui/kit";
import * as Pub from "./pages/public";
import * as Home from "./pages/home";
import * as Calls from "./pages/calls";
import * as Proj from "./pages/projects";
import * as Apps from "./pages/applications";
import * as Docs from "./pages/documents";
import * as Org from "./pages/org";
import * as Admin from "./pages/admin";
import * as Impact from "./pages/impact";
import * as Fin from "./pages/finance";
import * as Net from "./pages/network";
import * as Rep from "./pages/reports";
import * as Ops from "./pages/ops";
import * as Sol from "./pages/solutions";
import * as SolM from "./pages/solutions_manage";
import * as Inst from "./pages/institution";

type R = [string, (p: Record<string, string>) => ReactNode, string[]?];

// [padrão, página, tipos de organização permitidos (vazio = todos)]
const ROUTES: R[] = [
  ["/", () => <Home.Dashboard />],
  ["/notificacoes", () => <Home.Notifications />],
  ["/oportunidades", () => <Calls.Opportunities />, ["osc"]],
  ["/oportunidades/:id", (p) => <Calls.CallDetail id={p.id} />],
  ["/editais", () => <Calls.MyCalls />, ["company", "government"]],
  ["/editais/novo", () => <Calls.CallForm />, ["company", "government"]],
  ["/editais/:id/editar", (p) => <Calls.CallForm id={p.id} />, ["company", "government"]],
  ["/editais/:id/candidaturas", (p) => <Calls.CallApplications id={p.id} />, ["company", "government"]],
  ["/projetos", () => <Proj.Projects />, ["osc"]],
  ["/projetos/novo", () => <Proj.NewProject />, ["osc"]],
  ["/projetos/:id", (p) => <Proj.ProjectDetail id={p.id} />],
  ["/explorar", () => <Proj.Feed />, ["company", "individual"]],
  ["/carteira", () => <Proj.Portfolio />, ["company", "government", "individual"]],
  ["/candidaturas", () => <Apps.Applications />],
  ["/candidaturas/:id", (p) => <Apps.ApplicationDetail id={p.id} />],
  ["/documentos", () => <Docs.Documents />],
  ["/rascunhos", () => <Docs.Drafts />],
  ["/rascunhos/:id", (p) => <Docs.DraftEditor id={p.id} />],
  ["/profissionais", () => <Docs.Directory />],
  ["/revisoes", () => <Docs.Reviews />],
  ["/revisoes/:id", (p) => <Docs.ReviewDetail id={p.id} />],
  ["/organizacao", () => <Org.OrgProfile />],
  ["/organizacao/compliance", () => <Org.Compliance />],
  ["/organizacao/equipe", () => <Org.Team />],
  ["/conta", () => <Org.Account />],
  ["/conta/plano", () => <Org.Plan />],
  ["/fiscal", () => <Org.Fiscal />, ["company"]],
  ["/materiais", () => <Org.Materials />],
  ["/dados-territoriais", () => <Org.GovData />, ["government", "platform"]],
  ["/projetos/:id/impacto", (p) => <Impact.ProjectImpact id={p.id} />],
  ["/projetos/:id/grafo", (p) => <Impact.ImpactGraph id={p.id} />],
  ["/projetos/:id/compras", (p) => <Fin.Procurement id={p.id} />, ["osc"]],
  ["/projetos/:id/contribuicao", (p) => <Fin.ContributionModels id={p.id} />],
  ["/projetos/:id/apoio-profissional", (p) => <Net.ProjectNeeds id={p.id} />, ["osc"]],
  ["/projetos/:id/localizacao", (p) => <Rep.LocationEditor id={p.id} />, ["osc"]],
  ["/compras/:id", (p) => <Fin.ProcurementDetail id={p.id} />, ["osc"]],
  ["/necessidades/:id", (p) => <Net.NeedDetail id={p.id} />, ["osc"]],
  ["/diagnosticos", () => <Impact.Diagnoses />, ["osc"]],
  ["/diagnosticos/:id", (p) => <Impact.DiagnosisEditor id={p.id} />, ["osc"]],
  ["/determinantes", () => <Impact.Determinants />, ["government", "platform"]],
  ["/pagamentos", () => <Fin.Payments />, ["osc", "company", "individual", "government"]],
  ["/pagamentos/:id", (p) => <Fin.PaymentDetail id={p.id} />, ["osc", "company", "individual", "government"]],
  ["/extratos", () => <Fin.Statements />, ["osc"]],
  ["/mensagens", () => <Net.Messages />],
  ["/mensagens/:id", (p) => <Net.Messages cid={p.id} />],
  ["/oportunidades-profissionais", () => <Net.Opportunities />, ["provider"]],
  ["/conquistas", () => <Net.Badges />, ["osc", "provider", "company"]],
  ["/relatorios", () => <Rep.ReportCenter />],
  ["/mapa", () => <Rep.MapView />],
  ["/solucoes", () => <Sol.Library />],
  ["/solucoes/nova", () => <SolM.SolutionForm />, ["osc", "individual", "company", "government", "provider"]],
  ["/solucoes/minhas", () => <SolM.MyArea />],
  ["/solucoes/pedidos", () => <SolM.MyArea />],
  ["/solucoes/replicacoes", () => <SolM.MyArea />],
  ["/solucoes/comparar", () => <Sol.Compare />],
  ["/solucoes/replicacao", () => <SolM.Marketplace />],
  ["/solucoes/preferencias", () => <SolM.Preferences />],
  ["/solucoes/:id", (p) => <Sol.Profile id={p.id} />],
  ["/solucoes/:id/editar", (p) => <SolM.SolutionForm id={p.id} />, ["osc", "individual", "company", "government", "provider"]],
  ["/instituicao", () => <Inst.Institution />, ["osc", "company", "government", "provider", "individual"]],
  ["/instituicoes/:id", (p) => <Inst.PublicOrg id={p.id} />],
  ["/admin/institucional", () => <Inst.InstitutionAdmin />, ["platform"]],
  ["/admin/solucoes", () => <SolM.AdminSolutions />, ["platform"]],
  ["/admin/risco", () => <Ops.Risk />, ["platform"]],
  ["/admin/erros", () => <Ops.Errors />, ["platform"]],
  ["/admin/contribuicao", () => <Ops.ContributionReview />, ["platform"]],
  ["/admin", () => <Admin.Overview />, ["platform"]],
  ["/admin/compliance", () => <Admin.ComplianceQueue />, ["platform"]],
  ["/admin/credenciais", () => <Admin.Credentials />, ["platform"]],
  ["/admin/editais", () => <Admin.CuratedCalls />, ["platform"]],
  ["/admin/fiscal", () => <Admin.FiscalRules />, ["platform"]],
  ["/admin/vouchers", () => <Admin.Vouchers />, ["platform"]],
  ["/admin/usuarios", () => <Admin.Users />, ["platform"]],
  ["/admin/organizacoes", () => <Admin.Orgs />, ["platform"]],
  ["/admin/denuncias", () => <Admin.Reports />, ["platform"]],
  ["/admin/auditoria", () => <Admin.Audit />, ["platform"]],
];

const PUBLIC: [string, () => ReactNode][] = [
  ["/entrar", () => <Pub.Login />], ["/cadastro", () => <Pub.Register />], ["/verificar-email", () => <Pub.VerifyEmail />],
  ["/esqueci-senha", () => <Pub.Forgot />], ["/redefinir-senha", () => <Pub.Reset />], ["/convite", () => <Pub.AcceptInvite />],
  ["/legal/termos", () => <Pub.Legal doc="termos" />], ["/legal/privacidade", () => <Pub.Legal doc="privacidade" />],
];

const NAV: Record<string, [string, string][]> = {
  osc: [["/", "Início"], ["/oportunidades", "Oportunidades"], ["/projetos", "Projetos"], ["/candidaturas", "Candidaturas"],
    ["/instituicao", "Instituição"], ["/diagnosticos", "Diagnóstico"], ["/pagamentos", "Pagamentos"], ["/documentos", "Documentos"], ["/rascunhos", "Rascunhos"], ["/profissionais", "Profissionais parceiros"],
    ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/solucoes/replicacao", "Replicação"],
    ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/mensagens", "Mensagens"], ["/conquistas", "Conquistas"], ["/materiais", "Materiais"]],
  company: [["/", "Início"], ["/explorar", "Projetos para apoiar"], ["/editais", "Programas"], ["/candidaturas", "Candidaturas"],
    ["/carteira", "Carteira e resultados"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/pagamentos", "Pagamentos"], ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/mensagens", "Mensagens"],
    ["/fiscal", "Incentivos fiscais"], ["/instituicao", "Instituição"], ["/documentos", "Documentos"], ["/materiais", "Materiais"]],
  individual: [["/", "Início"], ["/explorar", "Projetos para apoiar"], ["/candidaturas", "Candidaturas"], ["/carteira", "Meu apoio e resultados"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/pagamentos", "Pagamentos"],
    ["/instituicao", "Perfil institucional"], ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/mensagens", "Mensagens"]],
  provider: [["/", "Início"], ["/instituicao", "Perfil institucional"], ["/oportunidades-profissionais", "Oportunidades"], ["/revisoes", "Validações"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/mensagens", "Mensagens"], ["/conquistas", "Conquistas"], ["/rascunhos", "Rascunhos"], ["/documentos", "Documentos"], ["/materiais", "Materiais"]],
  government: [["/", "Início"], ["/editais", "Editais"], ["/candidaturas", "Candidaturas"], ["/carteira", "Execução e resultados"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"],
    ["/instituicao", "Instituição"], ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/materiais", "Materiais"], ["/dados-territoriais", "Dados do território"], ["/determinantes", "Determinantes sociais"], ["/documentos", "Documentos"]],
  platform: [["/admin", "Visão geral"], ["/admin/compliance", "Compliance"], ["/admin/credenciais", "Credenciais"], ["/admin/editais", "Editais curados"],
    ["/admin/fiscal", "Regras fiscais"], ["/admin/institucional", "Institucional"], ["/admin/vouchers", "Vouchers"], ["/admin/organizacoes", "Organizações"], ["/admin/usuarios", "Usuários"],
    ["/admin/denuncias", "Denúncias"], ["/admin/solucoes", "Soluções (verificação)"], ["/solucoes", "Biblioteca de soluções"], ["/admin/risco", "Sinais de risco"], ["/admin/contribuicao", "Modelos de contribuição"], ["/admin/erros", "Erros"], ["/admin/auditoria", "Auditoria"], ["/dados-territoriais", "Dados do território"]],
};
const KIND_LABEL: Record<string, string> = { osc: "OSC", company: "Empresa", individual: "Apoiador", provider: "Profissional", government: "Governo", platform: "Administração" };

export function App() {
  const { me, loading } = useSession();
  const { path } = useLocation();
  for (const [pat, render] of PUBLIC) if (match(pat, path)) return <>{render()}</>;
  if (loading) return <div className="boot"><StateView loading /></div>;
  if (!me) {
    if (path === "/") return <Pub.Landing />;
    navigate(`/entrar?proximo=${encodeURIComponent(path + location.search)}`, true);
    return null;
  }
  if (!me.active_org) return <Shell><Org.CreateOrg /></Shell>;
  const kind = me.active_org.kind;
  for (const [pat, render, kinds] of ROUTES) {
    const params = match(pat, path);
    if (!params) continue;
    if (kinds && kinds.length && !kinds.includes(kind)) return <Shell><NotHere /></Shell>;
    if (pat === "/" && kind === "platform") return <Shell><Admin.Overview /></Shell>;
    return <Shell>{render(params)}</Shell>;
  }
  return <Shell><NotHere notFound /></Shell>;
}

function NotHere({ notFound }: { notFound?: boolean }) {
  return (
    <div className="state state-empty">
      <h1>{notFound ? "Página não encontrada" : "Esta área não está disponível para este perfil"}</h1>
      <p>{notFound ? "O endereço pode ter mudado." : "Troque de organização no menu ou volte ao início."}</p>
      <Button variant="ink" onClick={() => navigate("/")}>Voltar ao início</Button>
    </div>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const { me, logout, reload } = useSession();
  const { path } = useLocation();
  const [open, setOpen] = useState(false);
  const { run } = useAction();
  useEffect(() => setOpen(false), [path]);
  if (!me) return null;
  const kind = me.active_org?.kind || "osc";
  const nav = NAV[kind] || NAV.osc;
  const active = (to: string) => (to === "/" ? path === "/" : path === to || path.startsWith(to + "/"));
  return (
    <div className="shell">
      <a className="skip" href="#conteudo">Pular para o conteúdo</a>
      <header className="topbar">
        <button className="icon-btn menu-btn" aria-expanded={open} aria-controls="rail" onClick={() => setOpen(!open)} aria-label="Menu">☰</button>
        <Link to="/" className="brand"><span className="brand-mark" aria-hidden="true" />Impacto</Link>
        <Link to="/notificacoes" className="notif" aria-label={`Notificações: ${me.unread_notifications} não lidas`}>
          Notificações{me.unread_notifications > 0 && <span className="notif-count">{me.unread_notifications}</span>}
        </Link>
      </header>
      <nav id="rail" className={`rail${open ? " rail-open" : ""}`} aria-label="Navegação principal">
        <Link to="/" className="brand brand-light rail-brand"><span className="brand-mark" aria-hidden="true" />Impacto</Link>
        {me.active_org && (
          <div className="org-switch">
            <span className="org-kind">{KIND_LABEL[kind]}</span>
            {me.organizations.length > 1 ? (
              <select aria-label="Organização ativa" value={me.active_org.id}
                onChange={(e: any) => run(() => api.post("/v1/me/switch-org", { org_id: e.target.value })).then(async () => { await reload(); navigate("/"); })}>
                {me.organizations.map((o) => <option key={o.id} value={o.id}>{o.trade_name || o.legal_name}</option>)}
              </select>
            ) : <strong>{me.active_org.trade_name || me.active_org.legal_name}</strong>}
          </div>
        )}
        <ul>
          {nav.map(([to, label]) => (
            <li key={to}><Link to={to} className={active(to) ? "on" : ""} aria-current={active(to) ? "page" : undefined}>{label}</Link></li>
          ))}
        </ul>
        <ul className="rail-foot">
          <li><Link to="/notificacoes" className={active("/notificacoes") ? "on" : ""}>Notificações {me.unread_notifications > 0 && <span className="notif-count">{me.unread_notifications}</span>}</Link></li>
          {kind !== "platform" && <li><Link to="/organizacao" className={active("/organizacao") ? "on" : ""}>Organização</Link></li>}
          {kind !== "platform" && <li><Link to="/conta/plano" className={active("/conta/plano") ? "on" : ""}>Plano</Link></li>}
          <li><Link to="/conta" className={path === "/conta" ? "on" : ""}>Minha conta</Link></li>
          <li><button className="rail-logout" onClick={async () => { await logout(); navigate("/entrar"); }}>Sair</button></li>
        </ul>
      </nav>
      {open && <div className="scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
      <main className="content" id="conteudo" tabIndex={-1}>
        {!me.user.email_verified && <EmailBanner />}
        {children}
      </main>
    </div>
  );
}

function EmailBanner() {
  const { busy, run } = useAction();
  return (
    <div className="banner" role="status">
      Confirme seu e-mail para publicar, enviar candidaturas e convidar pessoas.
      <Button variant="link" busy={busy} onClick={() => run(() => api.post("/v1/auth/resend-verification"), "Link reenviado")}>Reenviar link</Button>
    </div>
  );
}
