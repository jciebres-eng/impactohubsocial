const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const num = new Intl.NumberFormat("pt-BR");
const dateFmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
const dtFmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

export const money = (cents?: number | null) => (cents === null || cents === undefined ? "—" : brl.format(cents / 100));
export const n = (v?: number | null) => (v === null || v === undefined ? "—" : num.format(v));
export const pct = (v?: number | null) => (v === null || v === undefined ? "—" : `${Math.round(v)}%`);

export function date(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v.length === 10 ? v + "T12:00:00" : v);
  return isNaN(d.getTime()) ? v : dateFmt.format(d);
}
export function dateTime(v?: string | null): string {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d.getTime()) ? v : dtFmt.format(d);
}
export function daysUntil(v?: string | null): number | null {
  if (!v) return null;
  return Math.ceil((new Date(v).getTime() - Date.now()) / 86400000);
}
/** Converte "1.234,56" ou "1234.56" em centavos. */
export function parseMoney(s: string): number | null {
  const t = s.trim().replace(/[R$\s]/g, "");
  if (!t) return null;
  const normalized = t.includes(",") ? t.replace(/\./g, "").replace(",", ".") : t;
  const v = Number(normalized);
  return Number.isFinite(v) && v >= 0 ? Math.round(v * 100) : null;
}
export const centsToInput = (c?: number | null) => (c === null || c === undefined ? "" : (c / 100).toFixed(2).replace(".", ","));

export const STATUS_LABEL: Record<string, string> = {
  draft: "Rascunho", published: "Publicado", funding: "Em captação", funded: "Financiado", in_execution: "Em execução",
  completed: "Concluído", cancelled: "Cancelado", open: "Aberto", closed: "Encerrado", archived: "Arquivado", suspended: "Suspenso",
  interest: "Interesse do financiador", submitted: "Enviada", screening: "Em triagem", due_diligence: "Em diligência",
  approved: "Aprovada", rejected: "Não aprovada", withdrawn: "Retirada", committed: "Aporte registrado", reporting: "Prestação de contas",
  pending: "Pendente", in_review: "Em análise", pending_scan: "Aguardando antivírus", clean: "Verificado", infected: "Bloqueado",
  accepted: "Aceita", needs_info: "Precisa de informações", validated: "Validada", questioned: "Questionada", recorded: "Registrada",
  pledged: "Comprometido", disbursed: "Desembolsado", confirmed: "Recebimento confirmado", requested: "Solicitada",
  declined: "Recusada", changes_requested: "Ajustes pedidos", signed: "Assinado", superseded: "Substituído",
  planned: "Planejado", evidence_submitted: "Evidência enviada", todo: "A fazer", in_progress: "Em andamento", done: "Concluída",
  blocked: "Bloqueada", not_applicable: "Não se aplica", self_declared: "Autodeclarada", document_submitted: "Comprovante enviado",
  verified: "Verificada", expired: "Vencida", active: "Ativa", past_due: "Pagamento pendente", canceled: "Cancelada",
  pending_review: "Em revisão", retired: "Retirada", pending_approval: "Aguardando 2ª aprovação", revoked: "Revogado",
  triaged: "Em triagem", actioned: "Providência tomada", dismissed: "Arquivada", info_requested: "Informações solicitadas",
  incomplete: "Incompleta", review: "Em revisão",
};
export const label = (s?: string | null) => (s ? STATUS_LABEL[s] || s : "—");

export const MATCH_STATE: Record<string, { label: string; tone: string }> = {
  prioritaria: { label: "Prioritária", tone: "good" },
  compativel: { label: "Compatível", tone: "good" },
  potencial_com_lacunas: { label: "Potencial, com lacunas", tone: "warn" },
  revisao_humana: { label: "Requer revisão humana", tone: "warn" },
  bloqueada: { label: "Bloqueada", tone: "bad" },
};
