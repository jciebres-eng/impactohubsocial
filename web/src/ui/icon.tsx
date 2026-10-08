// Ícones da identidade oficial: 75 SVGs de traço em grade 24×24, `currentColor`, nomeados pelo
// `web/brand/icon-catalog.json`. Entram inline (não via <img>) para herdarem a cor do texto, como o
// guia da marca pede. O conteúdo é estático e versionado neste repositório — não é entrada de usuário.
import navAnalytics from "../../brand/icons/nav/analytics.svg";
import navCompany from "../../brand/icons/nav/company.svg";
import navCompliance from "../../brand/icons/nav/compliance.svg";
import navDashboard from "../../brand/icons/nav/dashboard.svg";
import navDocuments from "../../brand/icons/nav/documents.svg";
import navFinance from "../../brand/icons/nav/finance.svg";
import navIdeas from "../../brand/icons/nav/ideas.svg";
import navIntegrations from "../../brand/icons/nav/integrations.svg";
import navLock from "../../brand/icons/nav/lock.svg";
import navOpportunities from "../../brand/icons/nav/opportunities.svg";
import navOrganizations from "../../brand/icons/nav/organizations.svg";
import navProjects from "../../brand/icons/nav/projects.svg";
import navReports from "../../brand/icons/nav/reports.svg";
import navSupport from "../../brand/icons/nav/support.svg";
import navUsers from "../../brand/icons/nav/users.svg";
import navHome from "../../brand/icons/navigation/home.svg";
import navMenu from "../../brand/icons/navigation/menu.svg";
import navSearch from "../../brand/icons/navigation/search.svg";
import sysBell from "../../brand/icons/system/bell.svg";
import sysSettings from "../../brand/icons/system/settings.svg";
import sysUser from "../../brand/icons/system/user.svg";
import impactMatch from "../../brand/icons/impact/match.svg";
import impactTerritory from "../../brand/icons/impact/territory.svg";
import impactTarget from "../../brand/icons/impact/target.svg";
import impactOds from "../../brand/icons/impact/ods.svg";
import impactPeople from "../../brand/icons/impact/people.svg";
import statusVerified from "../../brand/icons/status/verified.svg";
import statusCheck from "../../brand/icons/status/check.svg";
import statusAlert from "../../brand/icons/status/alert.svg";
import statusBlocked from "../../brand/icons/status/blocked.svg";
import docEvidence from "../../brand/icons/documents/evidence.svg";
import docDocument from "../../brand/icons/documents/document.svg";
import finFunding from "../../brand/icons/finance/funding.svg";
import finFiscal from "../../brand/icons/finance/fiscal.svg";
import fiscalTax from "../../brand/icons/fiscal/tax.svg";
import adminSecurity from "../../brand/icons/admin/security.svg";
import adminLogs from "../../brand/icons/admin/logs.svg";
import adminPermissions from "../../brand/icons/admin/permissions.svg";
import complianceAudit from "../../brand/icons/compliance/audit.svg";
import complianceRisk from "../../brand/icons/compliance/risk.svg";
import matchConnection from "../../brand/icons/match/connection.svg";
import matchRecommendation from "../../brand/icons/match/recommendation.svg";
import profNonprofit from "../../brand/icons/profiles/nonprofit.svg";
import profGovernment from "../../brand/icons/profiles/government.svg";
import patternsSearchFilter from "../../brand/icons/patterns/search-filter.svg";
import projReplicable from "../../brand/icons/projects/replicable.svg";
import projDraft from "../../brand/icons/projects/draft.svg";
import esgGovernance from "../../brand/icons/esg/governance.svg";

//: nome no catálogo → svg. Só os que a interface usa; o catálogo inteiro mora em web/brand/icons.
export const ICONES = {
  "nav/analytics": navAnalytics, "nav/company": navCompany, "nav/compliance": navCompliance,
  "nav/dashboard": navDashboard, "nav/documents": navDocuments, "nav/finance": navFinance,
  "nav/ideas": navIdeas, "nav/integrations": navIntegrations, "nav/lock": navLock,
  "nav/opportunities": navOpportunities, "nav/organizations": navOrganizations, "nav/projects": navProjects,
  "nav/reports": navReports, "nav/support": navSupport, "nav/users": navUsers,
  "navigation/home": navHome, "navigation/menu": navMenu, "navigation/search": navSearch,
  "system/bell": sysBell, "system/settings": sysSettings, "system/user": sysUser,
  "impact/match": impactMatch, "impact/territory": impactTerritory, "impact/target": impactTarget,
  "impact/ods": impactOds, "impact/people": impactPeople,
  "status/verified": statusVerified, "status/check": statusCheck, "status/alert": statusAlert, "status/blocked": statusBlocked,
  "documents/evidence": docEvidence, "documents/document": docDocument,
  "finance/funding": finFunding, "finance/fiscal": finFiscal, "fiscal/tax": fiscalTax,
  "admin/security": adminSecurity, "admin/logs": adminLogs, "admin/permissions": adminPermissions,
  "compliance/audit": complianceAudit, "compliance/risk": complianceRisk,
  "match/connection": matchConnection, "match/recommendation": matchRecommendation,
  "profiles/nonprofit": profNonprofit, "profiles/government": profGovernment,
  "patterns/search-filter": patternsSearchFilter, "projects/replicable": projReplicable, "projects/draft": projDraft,
  "esg/governance": esgGovernance,
} as const;
export type NomeIcone = keyof typeof ICONES;

//: Rota de menu → ícone. É uma tabela de decisão de design, revisável pelo Designer no painel de
//: telas; rota sem entrada aqui recebe um espaçador do mesmo tamanho, para a coluna alinhar.
export const ICONE_DA_ROTA: Record<string, NomeIcone> = {
  "/": "nav/dashboard", "/admin": "nav/dashboard", "/area": "navigation/home",
  "/oportunidades": "nav/opportunities", "/editais": "nav/opportunities", "/explorar": "nav/opportunities",
  "/oportunidades-profissionais": "nav/opportunities",
  "/projetos": "nav/projects", "/candidaturas": "projects/draft", "/ideias": "nav/ideas",
  "/documentos": "nav/documents", "/documentos/montagens": "documents/document", "/documentos/modelos": "documents/document",
  "/rascunhos": "projects/draft", "/materiais": "documents/evidence",
  "/pagamentos": "nav/finance", "/carteira": "finance/funding", "/torre": "finance/funding", "/participacoes": "finance/funding", "/torre-territorial": "impact/territory", "/cotas": "finance/funding", "/fiscal": "fiscal/tax",
  "/relatorios": "nav/reports", "/relatorios-impacto": "nav/reports", "/afirmacoes": "impact/target",
  "/reputacao": "status/verified", "/selos": "status/verified", "/verificacoes": "status/check",
  "/responsabilidade": "esg/governance", "/prontidao": "impact/target", "/prontidao/finalidades": "impact/target",
  "/diagnosticos": "patterns/search-filter", "/instituicao": "nav/organizations", "/organizacao": "nav/organizations",
  "/marketplace": "match/connection", "/marketplace/meus": "match/connection", "/propostas": "match/recommendation",
  "/rede/relacoes": "impact/people", "/rede/experiencias": "impact/people", "/rede/atividade": "nav/analytics",
  "/conversas": "nav/support", "/mensagens": "nav/support", "/perfil-publico": "system/user",
  "/perfil-publico/experiencias": "system/user", "/vocabulario": "documents/document",
  "/solucoes": "projects/replicable", "/solucoes/minhas": "projects/replicable", "/solucoes/replicacao": "projects/replicable",
  "/mapa": "impact/territory", "/territorio/necessidades": "impact/territory", "/dados-territoriais": "impact/territory",
  "/determinantes": "impact/ods", "/conquistas": "status/verified", "/campanha-gestao": "finance/funding",
  "/acordos": "documents/document", "/profissionais": "nav/users", "/revisoes": "compliance/audit",
  "/minhas-atividades": "nav/analytics", "/identidade": "admin/permissions", "/ia": "match/recommendation",
  "/conta/seguranca": "nav/lock", "/conta": "system/user", "/conta/plano": "nav/finance",
  "/notificacoes": "system/bell", "/ajuda": "nav/support", "/admin/central": "nav/support",
  "/admin/compliance": "nav/compliance", "/admin/identidade": "admin/permissions", "/admin/credenciais": "admin/permissions",
  "/admin/credenciais-profissionais": "admin/permissions", "/admin/honorarios": "nav/finance", "/admin/editais": "nav/opportunities",
  "/admin/fiscal": "fiscal/tax", "/admin/institucional": "nav/organizations", "/admin/vouchers": "finance/funding",
  "/admin/convenios": "documents/document", "/admin/cobranca": "nav/finance", "/admin/organizacoes": "nav/organizations",
  "/admin/usuarios": "nav/users", "/admin/denuncias": "status/alert", "/admin/medidas": "status/blocked",
  "/admin/solucoes": "projects/replicable", "/admin/risco": "compliance/risk", "/admin/contribuicao": "finance/funding",
  "/admin/erros": "status/alert", "/admin/chaves": "nav/lock", "/admin/auditoria": "compliance/audit",
  "/admin/linha-do-tempo": "admin/logs", "/admin/rastro": "admin/logs", "/admin/proveniencia": "documents/evidence",
  "/admin/integridade": "admin/security", "/admin/interruptor": "status/blocked",
};

export function Icon({ name, className = "" }: { name: NomeIcone; className?: string }) {
  return <span className={`ico ${className}`.trim()} aria-hidden="true" dangerouslySetInnerHTML={{ __html: ICONES[name] }} />;
}

export function IconeDaRota({ to }: { to: string }) {
  const nome = ICONE_DA_ROTA[to.split("?")[0]];
  return nome ? <Icon name={nome} /> : <span className="ico ico-vazio" aria-hidden="true" />;
}
