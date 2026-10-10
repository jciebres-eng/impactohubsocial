import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import { Link, match, navigate, useLocation } from "./router";
import { useSession } from "./session";
import { Button, StateView, useAction, useLoad } from "./ui/kit";
import * as Pub from "./pages/public";
import * as Com from "./pages/commercial";
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
import * as Help from "./pages/help";
import * as HelpA from "./pages/helpAdmin";
import * as Verify from "./pages/verify";
import * as Trust from "./pages/trust";
import * as TrustA from "./pages/trustAdmin";
import * as Funding from "./pages/funding";
import * as Prefs from "./pages/prefs";
import * as DiagGuide from "./pages/diagnosisGuide";
import * as Core from "./pages/core";
// v0.16.0 — camada de rede
import * as Ws from "./pages/workspace";
import * as NetX from "./pages/net";
import * as Mkt from "./pages/market";
import * as Talk from "./pages/talk";
import * as IR from "./pages/impactreport";
import * as PP from "./pages/publicprofile";
import * as Don from "./pages/donations";
import * as Terr from "./pages/territory";
import * as Tower from "./pages/tower";
import * as Part from "./pages/participations";
import * as Mod from "./pages/moderation";
import * as IL from "./pages/impactlayer";
// v0.22.0 — login inteligente e operação interna da plataforma
import * as Portal from "./pages/portal";
import * as Int from "./pages/internal";
import { useAccess } from "./access";
import { Brand } from "./ui/brand";
import { Icon, IconeDaRota } from "./ui/icon";
import * as Sec from "./pages/security";
import * as AI from "./pages/aicenter";
import * as Trace from "./pages/traceability";

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
  ["/ideias", () => <Core.Ideas />, ["osc"]],
  ["/prontidao", () => <Core.Readiness />, ["osc"]],
  ["/projetos/:id/situacao", (p) => <Core.Lifecycle id={p.id} />, ["osc"]],
  ["/projetos/:id/linha-do-tempo", (p) => <Core.Timeline id={p.id} />, ["osc"]],
  ["/projetos/:id/retratos", (p) => <Core.Snapshots id={p.id} />, ["osc"]],
  ["/projetos/:id/riscos", (p) => <Core.Risks id={p.id} />, ["osc"]],
  ["/diagnosticos/:id/versoes", (p) => <Core.DiagnosisVersions id={p.id} />, ["osc"]],
  ["/documentos/montagens", () => <Core.Assemblies />],
  ["/documentos/modelos", () => <Core.Templates />],
  ["/documentos/montagens/:id", (p) => <Core.AssemblyDetail id={p.id} />],
  ["/assinatura/provedores", () => <Core.SignatureProviders />],
  ["/assinatura/politica", () => <Core.SignaturePolicies />],
  ["/explorar", () => <Proj.Feed />, ["company", "individual"]],
  ["/carteira", () => <Proj.Portfolio />, ["company", "government", "individual"]],
  // v0.26.0 — torres de controle: a torre responde a cadeia inteira e aponta para a tela da decisão
  ["/torre", () => <Tower.FunderTower />, ["company", "individual"]],
  ["/participacoes", () => <Part.Participations />, ["osc", "individual", "provider", "company"]],
  ["/torre-territorial", () => <Tower.GovernmentTower />, ["government", "platform"]],
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
  ["/conta/preferencias", () => <Prefs.Preferences standalone />],
  // v0.23.0 — Centro de Segurança e painel de IA. As informações já existiam (sessões numa rota
  // que nenhuma tela lia, uso de IA em três números que ninguém consumia); o que faltava era o
  // lugar onde quem suspeita de acesso indevido olha UMA vez em vez de percorrer quatro telas.
  ["/conta/seguranca", () => <Sec.CentroDeSeguranca />],
  // v0.28.0 — Central de IA (ADR-347): saldo, cotas, operações com preço e quem paga, pedidos, patrocínio, análises
  ["/ia", () => <AI.AiCenter />],
  ["/ia/orcamento", () => <Sec.PainelDeIa />],
  ["/ia/analises/:id", (p) => <AI.SimilarityAnalysis id={p.id} />],
  ["/ia/patrocinios/:id", (p) => <AI.SponsorshipReport id={p.id} />],
  ["/identidade", () => <Trust.Identity />],
  ["/verificacoes", () => <Trust.VerifiableRecords />],
  ["/acordos", () => <Trust.Agreements />],
  ["/acordos/novo", () => <Trust.AgreementForm />],
  ["/acordos/:id", (p) => <Trust.AgreementDetail id={p.id} />],
  ["/cotas", () => <Funding.Quotas />, ["osc"]],
  ["/cotas/:id/apoios", (p) => <Funding.QuotaPledges id={p.id} />, ["osc"]],
  ["/campanha-gestao", () => <Funding.Campaigns />, ["osc"]],
  ["/minhas-atividades", () => <TrustA.MyServices />, ["provider", "individual"]],
  ["/admin/identidade", () => <TrustA.IdentityQueue />, ["platform"]],
  ["/admin/credenciais-profissionais", () => <TrustA.CredentialQueue />, ["platform"]],
  ["/admin/honorarios", () => <TrustA.FeeTables />, ["platform"]],
  // v0.27.0 (ADR-341): "/conta/plano" virou "/conta/acesso" — não existe assinatura. A rota antiga redireciona.
  ["/conta/acesso", () => <Org.Plan />],
  ["/conta/plano", () => <Org.Plan />],
  ["/conta/comercial", () => <Com.Commercial />], ["/conta/consumo", () => <Com.Usage />],
  ["/settings/billing", () => <Org.Plan />],
  ["/fiscal", () => <Org.Fiscal />, ["company"]],
  ["/materiais", () => <Org.Materials />],
  ["/dados-territoriais", () => <Org.GovData />, ["government", "platform"]],
  ["/projetos/:id/impacto", (p) => <Impact.ProjectImpact id={p.id} />],
  ["/projetos/:id/dossie", (p) => <Impact.ProjectDossier id={p.id} />],   // v0.30.0 — dossiê longitudinal (ADR-361)
  // v0.20.0 (§94) — as seis áreas que tinham API, serviço, banco, eventos, permissões, testes e
  // documentação, e nenhuma tela. UI mínima funcional, para o fluxo poder ser validado por uma
  // pessoa antes do refinamento visual do Designer.
  ["/reputacao", () => <IL.Reputation />],
  ["/selos", () => <IL.Seals />],
  ["/afirmacoes", () => <IL.Claims />],
  ["/responsabilidade", () => <IL.Responsibility />],
  ["/projetos/:id/equidade", (p) => <IL.Equity id={p.id} />],
  ["/projetos/:id/ods", (p) => <IL.OdsTargets id={p.id} />],
  ["/projetos/:id/grafo", (p) => <Impact.ImpactGraph id={p.id} />],
  ["/projetos/:id/compras", (p) => <Fin.Procurement id={p.id} />, ["osc"]],
  ["/projetos/:id/contribuicao", (p) => <Fin.ContributionModels id={p.id} />],
  ["/projetos/:id/apoio-profissional", (p) => <Net.ProjectNeeds id={p.id} />, ["osc"]],
  ["/projetos/:id/localizacao", (p) => <Rep.LocationEditor id={p.id} />, ["osc"]],
  ["/compras/:id", (p) => <Fin.ProcurementDetail id={p.id} />, ["osc"]],
  ["/necessidades/:id", (p) => <Net.NeedDetail id={p.id} />, ["osc"]],
  ["/diagnosticos", () => <Impact.Diagnoses />, ["osc"]],
  ["/diagnosticos/:id", (p) => <Impact.DiagnosisEditor id={p.id} />, ["osc"]],
  ["/diagnosticos/:id/roteiro", (p) => <DiagGuide.DiagnosisGuide id={p.id} />, ["osc"]],
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
  ["/admin/doacoes", () => <Don.DonationReview />, ["platform"]],
  ["/admin/doacoes/risco", () => <Don.DonationRiskCases />, ["platform"]],
  ["/admin/remuneracao", () => <Don.AdminRemuneration />, ["platform"]],
  ["/admin/conciliacao", () => <Don.AdminReconciliation />, ["platform"]],
  ["/admin/erros", () => <Ops.Errors />, ["platform"]],
  ["/admin/contribuicao", () => <Ops.ContributionReview />, ["platform"]],
  ["/admin/central", () => <HelpA.Overview />, ["platform"]],
  ["/admin/central/artigos", () => <HelpA.Articles />, ["platform"]],
  ["/admin/central/artigos/:slug", (p) => <HelpA.ArticleEditor slug={p.slug} />, ["platform"]],
  ["/admin/central/recursos", () => <HelpA.Resources />, ["platform"]],
  ["/admin/central/faqs", () => <HelpA.Faqs />, ["platform"]],
  ["/admin/central/cursos", () => <HelpA.Courses />, ["platform"]],
  ["/admin/central/eventos", () => <HelpA.EventsAdmin />, ["platform"]],
  ["/admin/central/suporte", () => <HelpA.SupportQueue />, ["platform"]],
  ["/admin/central/suporte/:id", (p) => <HelpA.SupportTicket id={p.id} />, ["platform"]],
  ["/admin/central/parcerias", () => <HelpA.Partnerships />, ["platform"]],
  ["/admin/central/analytics", () => <HelpA.Analytics />, ["platform"]],
  ["/admin/central/equipe", () => <HelpA.StaffRoles />, ["platform"]],
  ["/admin", () => <Admin.Overview />, ["platform"]],
  ["/admin/compliance", () => <Admin.ComplianceQueue />, ["platform"]],
  ["/admin/credenciais", () => <Admin.Credentials />, ["platform"]],
  ["/admin/editais", () => <Admin.CuratedCalls />, ["platform"]],
  ["/admin/fiscal", () => <Admin.FiscalRules />, ["platform"]],
  ["/admin/vouchers", () => <Admin.Vouchers />, ["platform"]],
  ["/admin/convenios", () => <Admin.Agreements />, ["platform"]],
  ["/admin/cobranca", () => <Admin.OrgBilling />, ["platform"]],
  ["/admin/usuarios", () => <Admin.Users />, ["platform"]],
  ["/admin/organizacoes", () => <Admin.Orgs />, ["platform"]],
  ["/admin/denuncias", () => <Admin.Reports />, ["platform"]],
  ["/admin/auditoria", () => <Admin.Audit />, ["platform"]],
  ["/admin/chaves", () => <Core.EncryptionKeys />, ["platform"]],

  // -------------------------------------------------------------------- v0.16.0 — IMPACT NETWORK
  // O workspace é a entrada de todas as personas: o backend decide persona, capacidades e ordem das seções.
  ["/area", () => <Ws.Workspace />],
  ["/rede/relacoes", () => <NetX.Relationships />],
  ["/rede/grafo", () => <NetX.NetworkGraph />],
  ["/rede/atividade", () => <Talk.NetworkEvents />],
  ["/propostas", () => <NetX.Proposals />],
  ["/propostas/nova", () => <NetX.NewProposal />],
  ["/propostas/:id", (p) => <NetX.ProposalDetail id={p.id} />],
  ["/conversas", () => <Talk.Conversations />],
  ["/conversas/:id", (p) => <Talk.Conversation id={p.id} />],
  ["/marketplace", () => <Mkt.Marketplace />],
  ["/marketplace/novo", () => <Mkt.NewListing />],
  ["/marketplace/meus", () => <Mkt.MyListings />],
  ["/marketplace/:id", (p) => <Mkt.ListingDetail id={p.id} />],
  ["/projetos/:id/relatorios", (p) => <IR.ProjectImpactReports id={p.id} />],
  ["/projetos/:id/equipe", (p) => <Talk.ProjectTeam id={p.id} />],
  ["/relatorios-impacto", () => <IR.ImpactReportInbox />],
  ["/relatorios-impacto/:id", (p) => <IR.ImpactReportDetail id={p.id} />],
  ["/prontidao/finalidades", () => <IR.ReadinessPurposes />],
  ["/perfil-publico", () => <PP.MyPublicProfile />],
  ["/minhas-doacoes", () => <Don.MyDonations />],
  ["/remuneracao", () => <Don.OrgRemuneration />, ["osc", "company", "provider", "government"]],
  ["/contribuicoes", () => <Don.OrgContributions />, ["company", "government"]],
  ["/perfil-publico/experiencias", () => <PP.Experiences />],
  ["/perfil-publico/:id/identificadores", (p) => <PP.HandleHistory id={p.id} />],
  ["/rede/experiencias", () => <PP.ExperienceRequests />],
  ["/territorio/necessidades", () => <Terr.TerritoryNeeds />],
  ["/vocabulario", () => <Terr.Taxonomies />],
  ["/conta/moderacao", () => <Mod.MyModeration />],
  ["/conta/denuncias", () => <Mod.MyReports />],
  ["/admin/medidas", () => <Mod.EnforcementAdmin />, ["platform"]],

  // ------------------------------------------------------------- v0.22.0 — OPERAÇÃO INTERNA
  // Quem entra aqui é decidido pela PERMISSÃO na rota da API, não pelo tipo da organização ativa:
  // alguém da controladoria pode ter a própria OSC como organização ativa e continuar sendo da
  // controladoria. O marcador `["staff"]` (v0.25.0) só diz ao roteador que a tela é da EQUIPE
  // INTERNA: quem não tem papel interno nem é administrador vê "área não disponível" em vez da
  // tela de erro com "Tentar novamente" que o 403 do servidor produzia. A permissão fina continua
  // sendo decidida no servidor.
  ["/portal", () => <Portal.Portal />],
  ["/organizacao/nova", () => <Org.CreateOrg />],
  ["/controladoria", () => <Int.Controladoria />, ["staff"]],
  ["/controladoria/conciliacao", () => <Int.Conciliacao />, ["staff"]],
  ["/controladoria/torre", () => <Int.TorreMaster />, ["staff"]],
  ["/admin/ia/financeiro", () => <AI.AdminAiFinance />, ["staff"]],
  ["/aprovacoes", () => <Int.Aprovacoes />, ["staff"]],
  ["/financeiro", () => <Int.Financeiro />, ["staff"]],
  ["/financeiro/despesas", () => <Int.Despesas />, ["staff"]],
  ["/financeiro/instrucoes", () => <Int.Instrucoes />, ["staff"]],
  ["/financeiro/periodos-gratuitos", () => <Int.PeriodosGratuitos />, ["staff"]],
  ["/contabilidade", () => <Int.Contabilidade />, ["staff"]],
  ["/contabilidade/plano-de-contas", () => <Int.PlanoDeContas />, ["staff"]],
  ["/tesouraria", () => <Int.Tesouraria />, ["staff"]],
  ["/administrativo/orcamento", () => <Int.Orcamento />, ["staff"]],
  ["/operacoes", () => <Int.Operacoes />, ["staff"]],
  ["/operacoes/alertas", () => <Int.Alertas />, ["staff"]],
  ["/auditoria", () => <Int.AcessoPrivilegiado />, ["staff"]],
  ["/admin/permissoes", () => <Int.MatrizPermissoes />, ["staff"]],
  ["/admin/integracoes", () => <Int.Integracoes />, ["staff"]],
  // v0.23.0 — rastreabilidade, integridade e emergência. Nenhuma destas telas tem dado de
  // exemplo: tela de auditoria com dado fictício é pior que tela ausente, porque treina quem
  // opera a confiar no que está vendo.
  ["/admin/linha-do-tempo", () => <Trace.LinhaDoTempo />, ["staff"]],
  ["/admin/rastro", () => <Trace.Rastro />, ["staff"]],
  ["/admin/proveniencia", () => <Trace.Proveniencia />, ["staff"]],
  ["/admin/integridade", () => <Trace.Integridade />, ["staff"]],
  ["/admin/interruptor", () => <Trace.Interruptor />, ["staff"]],
];


// Central de Conhecimento: páginas públicas (sem login) e privadas. Com sessão, usam o Shell; sem, a moldura pública.
type HR = [string, (p: Record<string, string>) => ReactNode, boolean?];   // [padrão, página, exige login]
const HELP: HR[] = [
  // Verificação pública e campanha: abrem SEM login (moldura pública) e também dentro do app.
  ["/verificar", () => <Verify.VerifyPage />],
  ["/verificar/:code", () => <Verify.VerifyPage />],
  ["/campanha/:slug", () => <Funding.PublicCampaign />],
  ["/doacao/:id", () => <Don.DonationStatus />],
  // Perfil público: o endereço que a pessoa compartilha. Abre SEM login (é o ponto de ser público) e também
  // dentro do app. A página lê só a projeção curada que o servidor monta.
  ["/@:handle", (p) => <PP.PublicProfilePage handle={p.handle} />],
  ["/ajuda", () => <Help.HelpHome />],
  ["/ajuda/busca", () => <Help.HelpSearch />],
  ["/ajuda/comece-aqui", () => <Help.Start />, true],
  ["/ajuda/pendencias", () => <Help.Pending />, true],
  ["/ajuda/atividades", () => <Help.Activities />, true],
  ["/ajuda/preferencias", () => <Help.Prefs />, true],
  ["/ajuda/biblioteca", () => <Help.Library />],
  ["/ajuda/biblioteca/:slug", (p) => <Help.Resource slug={p.slug} />],
  ["/ajuda/faq", () => <Help.Faq />],
  ["/ajuda/faq/:id", (p) => <Help.Faq focus={p.id} />],
  ["/ajuda/academia", () => <Help.Academy />],
  ["/ajuda/academia/aula/:id", (p) => <Help.Lesson id={p.id} />, true],
  ["/ajuda/academia/:slug", (p) => <Help.Course slug={p.slug} />],
  ["/ajuda/certificado/:code", (p) => <Help.Certificate code={p.code} />],
  ["/ajuda/eventos", () => <Help.Events />],
  ["/ajuda/eventos/:slug", (p) => <Help.EventPage slug={p.slug} />],
  ["/ajuda/suporte", () => <Help.Tickets />, true],
  ["/ajuda/suporte/novo", () => <Help.NewTicket />, true],
  ["/ajuda/suporte/:id", (p) => <Help.Ticket id={p.id} />, true],
  ["/ajuda/parcerias", () => <Help.PartnershipForm />],
  ["/ajuda/demonstracao", () => <Help.DemoForm />],
  ["/ajuda/boletim", () => <Help.Newsletter />],
  ["/ajuda/boletim/confirmar", () => <Help.NewsletterToken mode="confirm" />],
  ["/ajuda/boletim/cancelar", () => <Help.NewsletterToken mode="unsubscribe" />],
  ["/ajuda/glossario", () => <Help.Glossary />],   // v0.29.0 — antes do catch-all /ajuda/:slug
  ["/ajuda/:slug", (p) => <Help.Article slug={p.slug} />],
];

const PUBLIC: [string, () => ReactNode][] = [
  ["/entrar", () => <Pub.Login />], ["/cadastro", () => <Pub.Register />], ["/verificar-email", () => <Pub.VerifyEmail />],
  ["/esqueci-senha", () => <Pub.Forgot />], ["/redefinir-senha", () => <Pub.Reset />], ["/convite", () => <Pub.AcceptInvite />],
  ["/planos", () => <Com.Pricing />], ["/legal/termos", () => <Pub.Legal doc="termos" />], ["/legal/privacidade", () => <Pub.Legal doc="privacidade" />],
];

const NAV: Record<string, [string, string][]> = {
  osc: [["/", "Início"], ["/area", "Área de trabalho"], ["/reputacao", "Reputação"], ["/selos", "Selos"], ["/afirmacoes", "Afirmações de impacto"], ["/responsabilidade", "Responsabilidade"], ["/propostas", "Propostas"], ["/marketplace/meus", "Meus anúncios"], ["/marketplace", "Marketplace"], ["/rede/relacoes", "Relações"], ["/conversas", "Conversas"], ["/perfil-publico", "Perfil público"], ["/prontidao/finalidades", "Prontidão por finalidade"], ["/rede/experiencias", "Experiências declaradas"], ["/rede/atividade", "Atividade da rede"], ["/vocabulario", "Vocabulário"], ["/oportunidades", "Oportunidades"], ["/ideias", "Ideias"], ["/projetos", "Projetos"], ["/candidaturas", "Candidaturas"],
    ["/instituicao", "Instituição"], ["/diagnosticos", "Diagnóstico"], ["/prontidao", "Prontidão"], ["/pagamentos", "Pagamentos"], ["/cotas", "Cotas"], ["/campanha-gestao", "Campanha"], ["/minhas-doacoes", "Minhas doações"], ["/remuneracao", "Remuneração da plataforma"], ["/documentos", "Documentos"], ["/documentos/montagens", "Montagem de documentos"], ["/documentos/modelos", "Modelos de documento"], ["/rascunhos", "Rascunhos"], ["/acordos", "Acordos"], ["/participacoes", "Participação de autoria"], ["/verificacoes", "Verificação pública"], ["/profissionais", "Profissionais parceiros"],
    ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/solucoes/replicacao", "Replicação"],
    ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/mensagens", "Mensagens"], ["/conquistas", "Conquistas"], ["/materiais", "Materiais"],
    ["/ia", "Central de IA"], ["/conta/seguranca", "Segurança da conta"]],
  company: [["/", "Início"], ["/torre", "Torre de controle"], ["/contribuicoes", "Contribuições"], ["/area", "Área de trabalho"], ["/reputacao", "Reputação"], ["/selos", "Selos"], ["/responsabilidade", "Responsabilidade"], ["/marketplace", "Marketplace"], ["/propostas", "Propostas"], ["/relatorios-impacto", "Relatórios para analisar"], ["/rede/relacoes", "Relações"], ["/conversas", "Conversas"], ["/perfil-publico", "Perfil público"], ["/rede/atividade", "Atividade da rede"], ["/explorar", "Projetos para apoiar"], ["/editais", "Programas"], ["/candidaturas", "Candidaturas"],
    ["/carteira", "Carteira e resultados"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/pagamentos", "Pagamentos"], ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/mensagens", "Mensagens"],
    ["/fiscal", "Incentivos fiscais"], ["/instituicao", "Instituição"], ["/documentos", "Documentos"], ["/acordos", "Acordos"], ["/verificacoes", "Verificação pública"], ["/documentos/montagens", "Montagem de documentos"], ["/documentos/modelos", "Modelos de documento"], ["/materiais", "Materiais"],
    ["/ia", "Central de IA"], ["/conta/seguranca", "Segurança da conta"]],
  individual: [["/", "Início"], ["/torre", "Torre de controle"], ["/participacoes", "Participação de autoria"], ["/area", "Área de trabalho"], ["/marketplace", "Marketplace"], ["/propostas", "Propostas"], ["/relatorios-impacto", "Prestação de contas recebida"], ["/rede/relacoes", "Relações"], ["/conversas", "Conversas"], ["/explorar", "Projetos para apoiar"], ["/candidaturas", "Candidaturas"], ["/carteira", "Meu apoio e resultados"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/pagamentos", "Pagamentos"],
    ["/instituicao", "Perfil institucional"], ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/acordos", "Acordos"], ["/mensagens", "Mensagens"],
    ["/ia", "Central de IA"], ["/conta/seguranca", "Segurança da conta"]],
  provider: [["/", "Início"], ["/area", "Área de trabalho"], ["/reputacao", "Reputação"], ["/selos", "Selos"], ["/marketplace", "Oportunidades no marketplace"], ["/propostas", "Propostas"], ["/perfil-publico", "Perfil público"], ["/perfil-publico/experiencias", "Minhas experiências"], ["/conversas", "Conversas"], ["/rede/relacoes", "Relações"], ["/instituicao", "Perfil institucional"], ["/oportunidades-profissionais", "Oportunidades"], ["/revisoes", "Validações"], ["/minhas-atividades", "Minhas atividades"], ["/identidade", "Identidade"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"], ["/acordos", "Acordos"], ["/verificacoes", "Verificação pública"], ["/mensagens", "Mensagens"], ["/conquistas", "Conquistas"], ["/rascunhos", "Rascunhos"], ["/documentos", "Documentos"], ["/documentos/montagens", "Montagem de documentos"], ["/documentos/modelos", "Modelos de documento"], ["/materiais", "Materiais"],
    ["/ia", "Central de IA"], ["/conta/seguranca", "Segurança da conta"]],
  government: [["/", "Início"], ["/torre-territorial", "Torre territorial"], ["/contribuicoes", "Contribuições"], ["/area", "Área de trabalho"], ["/reputacao", "Reputação"], ["/selos", "Selos"], ["/responsabilidade", "Responsabilidade"], ["/territorio/necessidades", "Necessidades do território"], ["/marketplace", "Marketplace"], ["/propostas", "Propostas"], ["/relatorios-impacto", "Relatórios para analisar"], ["/rede/relacoes", "Relações"], ["/conversas", "Conversas"], ["/perfil-publico", "Perfil público"], ["/editais", "Editais"], ["/candidaturas", "Candidaturas"], ["/carteira", "Execução e resultados"], ["/solucoes", "Biblioteca de soluções"], ["/solucoes/minhas", "Minhas soluções"],
    ["/instituicao", "Instituição"], ["/relatorios", "Relatórios"], ["/mapa", "Mapa"], ["/acordos", "Acordos"], ["/materiais", "Materiais"], ["/dados-territoriais", "Dados do território"], ["/determinantes", "Determinantes sociais"], ["/documentos", "Documentos"], ["/documentos/montagens", "Montagem de documentos"], ["/documentos/modelos", "Modelos de documento"],
    ["/ia", "Central de IA"], ["/conta/seguranca", "Segurança da conta"]],
  platform: [["/admin", "Visão geral"], ["/area", "Área de trabalho"], ["/vocabulario", "Vocabulário"], ["/admin/compliance", "Compliance"], ["/admin/identidade", "Identidade"], ["/admin/credenciais", "Credenciais"], ["/admin/credenciais-profissionais", "Credenciais profissionais"], ["/admin/honorarios", "Honorários"], ["/admin/editais", "Editais curados"],
    ["/admin/fiscal", "Regras fiscais"], ["/admin/institucional", "Institucional"], ["/admin/vouchers", "Vouchers"], ["/admin/convenios", "Convênios"], ["/admin/cobranca", "Cobrança por organização"], ["/admin/organizacoes", "Organizações"], ["/admin/usuarios", "Usuários"],
    ["/admin/denuncias", "Denúncias"], ["/admin/medidas", "Medidas de moderação"], ["/admin/solucoes", "Soluções (verificação)"], ["/solucoes", "Biblioteca de soluções"], ["/admin/risco", "Sinais de risco"], ["/admin/doacoes", "Campanhas de doação"], ["/admin/doacoes/risco", "Risco em doações"], ["/admin/remuneracao", "Remuneração (obrigações)"], ["/admin/conciliacao", "Conciliação"], ["/admin/contribuicao", "Modelos de contribuição"], ["/admin/erros", "Erros"], ["/admin/central", "Central de Conhecimento"], ["/admin/chaves", "Chaves de cifragem"], ["/admin/auditoria", "Auditoria"], ["/dados-territoriais", "Dados do território"],
    ["/admin/linha-do-tempo", "Linha do tempo"], ["/admin/rastro", "Cadeia de causa"], ["/admin/proveniencia", "Proveniência"], ["/admin/integridade", "Integridade dos dados"], ["/admin/interruptor", "Interruptor de emergência"]],
};
const KIND_LABEL: Record<string, string> = { osc: "OSC", company: "Empresa", individual: "Apoiador", provider: "Profissional", government: "Governo", platform: "Administração" };

export function App() {
  const { me, loading } = useSession();
  const { path } = useLocation();
  for (const [pat, render] of PUBLIC) if (match(pat, path)) return <>{render()}</>;
  if (loading) return <div className="boot"><StateView loading /></div>;
  for (const [pat, render, needsLogin] of HELP) {
    const params = match(pat, path);
    if (!params) continue;
    if (me?.active_org) return <Shell>{render(params)}</Shell>;
    if (me) return <Shell><Org.CreateOrg /></Shell>;
    return <Help.PublicFrame>{needsLogin ? <Help.NeedLogin>{render(params)}</Help.NeedLogin> : render(params)}</Help.PublicFrame>;
  }
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
    const staffHere = path.startsWith("/admin/central") && !!me.user.staff_roles?.length;   // papéis internos (editor/revisor/suporte)
    const interna = !!kinds?.includes("staff");
    const daEquipe = me.user.is_platform_admin || !!me.user.staff_roles?.length;
    if (interna && !daEquipe) return <Shell><NotHere /></Shell>;
    if (!interna && kinds && kinds.length && !kinds.includes(kind) && !staffHere) return <Shell><NotHere /></Shell>;
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
  const { ctx } = useAccess();
  const { path } = useLocation();
  const [open, setOpen] = useState(false);
  const { run } = useAction();
  useEffect(() => setOpen(false), [path]);
  // v0.27.0 — MENU DINÂMICO: contadores por tela vêm do servidor (`GET /v1/me/today`), derivados de registros
  // reais (obrigações, participações a aceitar, repasses a confirmar, notificações). A barra não conta nada sozinha.
  // O hook fica ANTES do retorno antecipado: a ordem dos hooks não pode depender de haver sessão.
  const hoje = useLoad<any>(me ? "/v1/me/today" : null, [path, !!me]);
  if (!me) return null;
  const kind = me.active_org?.kind || "osc";
  const active = (to: string) => (to === "/" ? path === "/" : path === to || path.startsWith(to + "/"));

  // O MENU INTERNO VEM DO SERVIDOR (v0.22.0).
  //
  // Até a v0.21.0 `NAV.platform` era uma lista fixa aqui, idêntica para toda a equipe: quem
  // atendia chamado via "Cobrança por organização", "Organizações" e "Auditoria" no menu e levava
  // 403 ao clicar. A regra de acesso existia em dois lugares e um deles estava errado.
  //
  // Agora `GET /v1/me/context` devolve os grupos que esta pessoa pode receber, derivados da mesma
  // matriz de permissões que a porta da API confere. O que não aparece aqui não passa lá.
  const grupos = ctx?.menu || [];
  const noMenuDoServidor = new Set(grupos.flatMap((g) => g.items.map((i) => i.to)));
  // Sobra da administração: rotas que ainda exigem o booleano `is_platform_admin` e não têm
  // permissão nomeada. Só quem tem o booleano as vê — porque é literalmente só quem as alcança.
  const nav = kind === "platform"
    ? (ctx?.staff.is_platform_admin ? NAV.platform.filter(([to]) => !noMenuDoServidor.has(to)) : [])
    : (NAV[kind] || NAV.osc);
  const badges: Record<string, number> = hoje.data?.badges || {};
  const Badge = ({ to }: { to: string }) => (badges[to] ? <span className="notif-count" aria-label={`${badges[to]} pendente(s)`}>{badges[to]}</span> : null);
  return (
    <div className="shell">
      <a className="skip" href="#conteudo">Pular para o conteúdo</a>
      <header className="topbar">
        <button className="icon-btn menu-btn" aria-expanded={open} aria-controls="rail" onClick={() => setOpen(!open)} aria-label="Menu"><Icon name="navigation/menu" /></button>
        <Brand size="bar" />
        <Link to="/notificacoes" className="notif" aria-label={`Notificações: ${me.unread_notifications} não lidas`}>
          Notificações{me.unread_notifications > 0 && <span className="notif-count">{me.unread_notifications}</span>}
        </Link>
      </header>
      <nav id="rail" className={`rail${open ? " rail-open" : ""}`} aria-label="Navegação principal">
        <Brand surface="navy" size="rail" className="rail-brand" />
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
            <li key={to}><Link to={to} className={active(to) ? "on" : ""} aria-current={active(to) ? "page" : undefined}><IconeDaRota to={to} />{label}<Badge to={to} /></Link></li>
          ))}
        </ul>
        {grupos.map((g) => (
          <div className="rail-group" key={g.group}>
            <span>{g.group}</span>
            <ul>
              {g.items.map((i) => (
                <li key={i.to}><Link to={i.to} className={active(i.to) ? "on" : ""} aria-current={active(i.to) ? "page" : undefined}><IconeDaRota to={i.to} />{i.label}</Link></li>
              ))}
            </ul>
          </div>
        ))}
        <ul className="rail-foot">
          <li><Link to="/ajuda" className={active("/ajuda") ? "on" : ""}><IconeDaRota to="/ajuda" />Ajuda</Link></li>
          {kind !== "platform" && !!me.user.staff_roles?.length && <li><Link to="/admin/central" className={active("/admin/central") ? "on" : ""}><IconeDaRota to="/admin/central" />Central (equipe)</Link></li>}
          <li><Link to="/notificacoes" className={active("/notificacoes") ? "on" : ""}><IconeDaRota to="/notificacoes" />Notificações {me.unread_notifications > 0 && <span className="notif-count">{me.unread_notifications}</span>}</Link></li>
          {kind !== "platform" && <li><Link to="/organizacao" className={active("/organizacao") ? "on" : ""}><IconeDaRota to="/organizacao" />Organização</Link></li>}
          {kind !== "platform" && <li><Link to="/conta/acesso" className={active("/conta/acesso") || active("/conta/plano") ? "on" : ""}><IconeDaRota to="/conta/acesso" />Acesso</Link></li>}
          {me.organizations.length > 1 && <li><Link to="/portal?escolher=1" className={path === "/portal" ? "on" : ""}>Trocar de contexto</Link></li>}
          <li><Link to="/conta" className={path === "/conta" ? "on" : ""}><IconeDaRota to="/conta" />Minha conta</Link></li>
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
