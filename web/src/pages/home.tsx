import { useState } from "react";
import { api } from "../api";
import { date, daysUntil, label, money, n } from "../format";
import { Link } from "../router";
import { useSession } from "../session";
import { Bars, Button, FirstRunPanel, MoneyFlow, PageHead, Pager, Panel, Pill, StateView, useAction, useLoad, useTaxonomy } from "../ui/kit";
import { GlossaryTerm, ContextualHelp } from "../ui/help";

function countOf(rows: any[] | undefined, status: string) {
  return rows?.find((r) => r.status === status)?.n ?? 0;
}

/** v0.27.0 — "Para você hoje": cartões flutuantes derivados de registros reais (pendência, decisão, repasse,
 * participação, recomendação, trajetória). Cada cartão diz por que existe e para onde leva; dispensar um cartão
 * é conveniência local (localStorage, por pessoa e por navegador) — o registro de origem continua lá. */
const CARD_KIND: Record<string, string> = {
  onboarding: "Primeiros passos", compliance: "Conformidade", document: "Documento", grant: "Concessão", support: "Suporte",
  event: "Evento", course: "Curso", obligation: "Decisão no acordo", participation: "Participação de autoria",
  payout_confirm: "Repasse a confirmar", payout_register: "Transferência a registrar", recommendation: "Próxima ação", trajectory: "Trajetória",
};
export function TodayCards() {
  const { data, loading, error, reload } = useLoad<any>("/v1/me/today");
  const [dismissed, setDismissed] = useState<string[]>(() => { try { return JSON.parse(localStorage.getItem("hoje.dispensados") || "[]"); } catch { return []; } });
  const [flipped, setFlipped] = useState<string | null>(null);
  const key = (c: any) => `${c.kind}:${c.title}`;
  const cards = (data?.cards || []).filter((c: any) => !dismissed.includes(key(c)));
  const dismiss = (c: any) => { const next = [...dismissed, key(c)]; setDismissed(next); try { localStorage.setItem("hoje.dispensados", JSON.stringify(next)); } catch { /* sem armazenamento: só nesta visita */ } };
  if (loading || error || !data) return error ? <StateView loading={false} error={error} onRetry={reload} /> : null;
  if (!cards.length) return null;
  return (
    <section className="deck" aria-label="Para você hoje">
      <div className="deck-head"><h2>Para você hoje</h2><span className="muted small">{cards.length} cartão(ões) · derivados de registros reais</span></div>
      <ul className="deck-cards">
        {cards.map((c: any) => {
          const k = key(c); const aberto = flipped === k;
          return (
            <li key={k} className={`deck-card deck-${c.severity}${aberto ? " deck-open" : ""}`}>
              <button type="button" className="deck-face" aria-expanded={aberto} onClick={() => setFlipped(aberto ? null : k)}>
                <span className="deck-kind">{CARD_KIND[c.kind] || c.kind}</span>
                <strong>{c.title}</strong>
                {aberto && c.why && <span className="deck-why">{c.why}</span>}
                {aberto && c.due_on && <span className="deck-why">até {date(c.due_on)}</span>}
              </button>
              <div className="deck-actions">
                {c.link && <Link to={c.link} className="btn btn-ink btn-sm">Abrir</Link>}
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => dismiss(c)}>Dispensar</button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function Dashboard() {
  const { me } = useSession();
  const { data, error, loading, reload } = useLoad<any>("/v1/dashboard");
  const tax = useTaxonomy();
  const name = me?.user.full_name.split(" ")[0];
  return (
    <>
      <PageHead title={`Olá, ${name}`} sub={me?.active_org?.legal_name} />
      <TodayCards />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data?.kind === "osc" && <OscHome d={data} />}
        {(data?.kind === "company" || data?.kind === "government" || data?.kind === "individual") && <FunderHome d={data} tax={tax} />}
        {data?.kind === "provider" && <ProviderHome d={data} />}
        {/* Primeiro acesso: só aparece o que está vazio, com o próximo passo lido do servidor. */}
        <FirstRunPanel onAct={(a) => { if (a.next_action?.screen) location.hash = `#${a.next_action.screen}`; }} />
      </StateView>
    </>
  );
}

function OscHome({ d }: { d: any }) {
  const { me } = useSession();
  const compliance = me?.active_org?.compliance_status;
  const apps = d.applications as any[];
  return (
    <div className="grid-home">
      <Panel title="Captação">
        <MoneyFlow stages={[["Necessidade dos projetos", d.projects.needed_cents], ["Comprometido por financiadores", d.funding.committed_cents],
          ["Recebimento confirmado", d.funding.received_cents]]} />
        <p className="muted">{n(d.projects.published)} projeto(s) publicado(s) · {n(d.projects.in_execution)} em execução</p>
      </Panel>
      <Panel title="Próximos prazos" actions={<Link to="/oportunidades">Ver oportunidades</Link>}>
        {d.deadlines.length === 0 ? (
          <p className="muted">Nenhuma candidatura em preparação. Há {n(d.open_calls)} oportunidade(s) aberta(s) no banco.</p>
        ) : (
          <ul className="rows">
            {d.deadlines.map((x: any) => {
              const days = daysUntil(x.closes_at);
              return (
                <li key={x.application_id}>
                  <Link to={`/candidaturas/${x.application_id}`}>{x.title}</Link>
                  <Pill tone={days !== null && days < 7 ? "bad" : "warn"}>{days === null ? "sem prazo" : `${days} dia(s)`}</Pill>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
      <Panel title="Pendências">
        <ul className="rows">
          {compliance !== "approved" && (
            <li><span>Cadastro ainda não verificado ({label(compliance)})</span><Link to="/organizacao/compliance">Resolver</Link></li>
          )}
          {d.documents.expired > 0 && <li><span>{d.documents.expired} documento(s) vencido(s)</span><Link to="/documentos">Atualizar</Link></li>}
          {d.documents.expiring > 0 && <li><span>{d.documents.expiring} documento(s) vencem em 30 dias</span><Link to="/documentos">Ver</Link></li>}
          {countOf(apps, "interest") > 0 && <li><span>{countOf(apps, "interest")} financiador(es) interessado(s)</span><Link to="/candidaturas">Responder</Link></li>}
          {compliance === "approved" && !d.documents.expired && !d.documents.expiring && !countOf(apps, "interest") && <li className="muted">Nada pendente.</li>}
        </ul>
      </Panel>
      <Panel title="Candidaturas por etapa">
        <Bars rows={apps.map((a) => ({ label: label(a.status), value: a.n }))} format={(v) => n(v)} />
      </Panel>
    </div>
  );
}

function FunderHome({ d, tax }: { d: any; tax: any }) {
  return (
    <div className="grid-home">
      <Panel title="Recurso investido" actions={<Link to="/carteira">Abrir carteira</Link>}>
        <MoneyFlow stages={[["Comprometido", d.portfolio.committed_cents], ["Desembolsado", d.portfolio.disbursed_cents]]} />
        <p className="muted">{n(d.portfolio.projects)} projeto(s) apoiado(s) · {n(d.pending_reviews)} evidência(s) aguardando sua revisão</p>
      </Panel>
      <Panel title="Funil de candidaturas" actions={<Link to="/candidaturas">Ver todas</Link>}>
        <Bars rows={(d.pipeline as any[]).map((a) => ({ label: label(a.status), value: a.n }))} format={(v) => n(v)} />
      </Panel>
      <Panel title="Por causa">
        <Bars rows={(d.by_cause as any[]).map((r) => ({ label: tax?.causes?.[r.cause] || r.cause, value: Number(r.committed_cents) }))} format={money} />
      </Panel>
      <Panel title={<>Por <GlossaryTerm id="ods">ODS</GlossaryTerm></>}>
        <Bars rows={(d.by_ods as any[]).map((r) => ({ label: `ODS ${r.ods}`, value: Number(r.committed_cents), tone: "leaf" }))} format={money} />
      </Panel>
      <Panel title="Por UF">
        <Bars rows={(d.by_territory as any[]).map((r) => ({ label: r.uf || "Nacional", value: Number(r.committed_cents), tone: "ochre" }))} format={money} />
      </Panel>
    </div>
  );
}

function ProviderHome({ d }: { d: any }) {
  return (
    <div className="grid-home">
      <Panel title={<>Validações <ContextualHelp id="quatro_olhos" /></>} actions={<Link to="/revisoes">Abrir</Link>}>
        <Bars rows={(d.reviews as any[]).map((r) => ({ label: label(r.status), value: r.n }))} format={(v) => n(v)} />
      </Panel>
      <Panel title="Credenciais" actions={<Link to="/organizacao">Gerenciar</Link>}>
        {d.credentials.length === 0 ? <p className="muted">Cadastre sua credencial profissional (CRC, OAB, CRA…) para validar e assinar.</p> :
          <Bars rows={(d.credentials as any[]).map((r) => ({ label: label(r.verification_status), value: r.n }))} format={(v) => n(v)} />}
      </Panel>
    </div>
  );
}

export function Notifications() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/notifications?offset=${offset}`, [offset]);
  const { reload: reloadMe } = useSession();
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Notificações" actions={
        <Button variant="ghost" busy={busy} onClick={() => run(() => api.post("/v1/notifications/read-all")).then(() => { reload(); reloadMe(); })}>Marcar todas como lidas</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma notificação por aqui."}>
        <ul className="feed">
          {data?.items.map((x: any) => (
            <li key={x.id} className={x.read_at ? "" : "unread"}>
              <div>
                <strong>{x.title}</strong>
                {x.body && <p>{x.body}</p>}
                <span className="muted">{date(x.created_at)}</span>
              </div>
              {x.link && <Link to={x.link} onClick={() => api.post(`/v1/notifications/${x.id}/read`).catch(() => {})}>Abrir</Link>}
            </li>
          ))}
        </ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}
