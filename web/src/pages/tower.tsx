/** v0.26.0 — Torres de controle e o estado "Projeto IMPACTO Ready".
 *
 * A torre não decide nada: ela responde a cadeia "meu capital → onde está → ... → o que preciso decidir"
 * com os registros existentes e aponta para a tela onde cada decisão é tomada.
 */
import { date, dateTime, money, n } from "../format";
import { Link } from "../router";
import { KeyValue, MoneyFlow, PageHead, Panel, Pill, StateView, useLoad } from "../ui/kit";

const READY_STATE: Record<string, [string, string]> = {
  ready: ["IMPACTO Ready", "good"], in_progress: ["Em construção", "warn"], not_assessable: ["Não avaliável", "muted"],
};
const CRIT_TONE: Record<string, string> = { met: "good", unmet: "warn", unknown: "muted" };
const CRIT_LABEL: Record<string, string> = { met: "atendido", unmet: "pendente", unknown: "desconhecido" };

function evidenceText(e: Record<string, any>): string {
  return Object.entries(e || {})
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "boolean" ? (v ? "sim" : "não") : String(v)}`)
    .join(" · ");
}

/** Painel do estado verificável, usado na ficha do projeto (dono e financiador veem o MESMO resultado). */
export function ReadyPanel({ projectId }: { projectId: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${projectId}/ready`, [projectId]);
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <Panel title="Projeto IMPACTO Ready" actions={<Pill tone={READY_STATE[data.state]?.[1] || "muted"}>{READY_STATE[data.state]?.[0] || data.state}</Pill>}>
          <p className="muted small">{data.met} de {data.total} critérios atendidos{data.unknown ? ` · ${data.unknown} desconhecido(s) — desconhecido não conta como zero` : ""}.
            Estado verificável, não selo: cada critério mostra a tabela e a contagem que o sustenta.</p>
          <ul className="rows">{data.criteria.map((c: any) => (
            <li key={c.key}>
              <span>{c.label}<br /><span className="muted small">{c.question}</span>
                <br /><span className="muted small">{c.source}{c.evidence && Object.keys(c.evidence).length ? ` — ${evidenceText(c.evidence)}` : ""}</span></span>
              <Pill tone={CRIT_TONE[c.status]}>{CRIT_LABEL[c.status]}</Pill>
            </li>
          ))}</ul>
          <p className="muted small">Avaliação <code className="small">{data.evaluation_hash.slice(0, 16)}…</code> · {data.engine_version} · {dateTime(data.computed_at)}</p>
        </Panel>
      )}
    </StateView>
  );
}

// ============================================================ financiador
export function FunderTower() {
  const { data, error, loading, reload } = useLoad<any>("/v1/control-tower/funder");
  const cap = data?.capital;
  return (
    <>
      <PageHead title="Torre de controle" sub="Meu capital → onde está → para quem → para quê → o que foi executado → que evidência existe → o que mudou → o que atrasou → que riscos apareceram → o que precisa da minha decisão." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {data.decisions.length > 0 && (
              <Panel title={`O que precisa da minha decisão (${data.decisions.length})`}>
                <ul className="rows">{data.decisions.map((d: any) => (
                  <li key={`${d.kind}-${d.ref}`}>
                    <span><Link to={d.link}>{d.title}</Link>{d.due_on && <><br /><span className="muted small">até {date(d.due_on)}</span></>}</span>
                    {d.overdue ? <Pill tone="bad">vencida</Pill> : <Pill tone="warn">{d.kind === "obligation" ? "obrigação" : d.kind === "application" ? "candidatura" : d.kind === "impact_update" ? "relatório" : "evidência"}</Pill>}
                  </li>
                ))}</ul>
              </Panel>
            )}
            <div className="grid-home">
              <Panel title="Meu capital">
                <MoneyFlow stages={[["Comprometido", cap.committed_cents], ["Desembolsado", cap.disbursed_cents], ["Confirmado pela OSC", cap.confirmed_cents],
                                    ["Gasto declarado", cap.spent_cents], ["Gasto validado", cap.validated_spent_cents]]} />
                <KeyValue items={[["Projetos", n(cap.projects)], ["Entre as partes (comprometido, não desembolsado)", money(cap.in_transit_cents)],
                  ["Etapas aceitas", `${cap.milestones_accepted} de ${cap.milestones}`], ["Etapas atrasadas", n(cap.milestones_overdue)],
                  ["Evidências aceitas / aguardando", `${cap.accepted_evidences} / ${cap.pending_evidences}`]]} />
                <p className="muted small">{data.note}</p>
              </Panel>
              <Panel title={`O que atrasou (${data.delays.length})`}>
                {data.delays.length ? <ul className="rows">{data.delays.map((d: any) => (
                  <li key={d.id}><span><Link to={`/projetos/${d.project_id}`}>{d.project_title}</Link><br /><span className="muted small">{d.title} · prazo {date(d.due_on)}</span></span>
                    <Pill tone="bad">{d.days_late} dia(s)</Pill></li>))}</ul> : <p className="muted">Nenhuma etapa vencida nos projetos que você apoia.</p>}
              </Panel>
              <Panel title={`Riscos que apareceram (${data.counts.risks})`}>
                {data.risks.project_risks.length === 0 && data.risks.signals.length === 0 && <p className="muted">Nenhum risco alto ou crítico aberto, nenhum sinal em análise.</p>}
                {data.risks.project_risks.length > 0 && <ul className="rows">{data.risks.project_risks.map((r: any) => (
                  <li key={r.project_id}><span><Link to={`/projetos/${r.project_id}`}>{r.project_title}</Link><br /><span className="muted small">{r.registered} risco(s) registrado(s) pela OSC</span></span>
                    <Pill tone="bad">{r.open_high_or_critical} alto(s)/crítico(s) em aberto</Pill></li>))}</ul>}
                {data.risks.signals.length > 0 && <ul className="rows">{data.risks.signals.map((s: any) => (
                  <li key={s.id}><span>{s.summary}<br /><span className="muted small">sinal {s.signal_type} · {dateTime(s.detected_at)}</span></span><Pill tone="warn">{s.severity}</Pill></li>))}</ul>}
              </Panel>
            </div>
            <Panel title="Onde está, para quem e para quê">
              {data.projects.length ? (
                <table className="table">
                  <thead><tr><th>Projeto</th><th>Para quem</th><th>Para quê</th><th>Comprometido</th><th>Desembolsado</th><th>Validado</th><th>Executado</th><th>Evidência</th><th>IMPACTO Ready</th><th>Mudou (30 d)</th></tr></thead>
                  <tbody>{data.projects.map((p: any) => (
                    <tr key={p.project_id}>
                      <td><Link to={`/projetos/${p.project_id}`}>{p.title}</Link><br /><span className="muted small">{p.territory} · <Pill status={p.status} /></span></td>
                      <td className="small">{p.osc_name}</td>
                      <td className="small">{(p.purpose.causes || []).join(", ")}{p.purpose.ods?.length ? ` · ODS ${p.purpose.ods.join(", ")}` : ""}{p.purpose.beneficiaries ? ` · ${n(p.purpose.beneficiaries)} pessoas` : ""}</td>
                      <td>{money(p.committed_cents)}</td>
                      <td>{money(p.disbursed_cents)}</td>
                      <td>{money(p.validated_spent_cents)}</td>
                      <td className="small">{p.milestones_accepted}/{p.milestones} etapas{p.milestones_overdue > 0 ? ` · ${p.milestones_overdue} atrasada(s)` : ""}</td>
                      <td className="small">{p.accepted_evidences} aceita(s){p.pending_evidences > 0 ? ` · ${p.pending_evidences} aguardando` : ""}</td>
                      <td>{p.ready ? <Pill tone={READY_STATE[p.ready.state]?.[1] || "muted"}>{p.ready.met}/{p.ready.total}</Pill> : "—"}</td>
                      <td className="small">{p.changes_30d} registro(s){p.last_activity ? ` · ${date(p.last_activity)}` : ""}</td>
                    </tr>
                  ))}</tbody>
                </table>
              ) : <p className="muted">Você ainda não comprometeu recurso em nenhum projeto. <Link to="/explorar">Encontrar projetos para apoiar</Link>.</p>}
            </Panel>
            <Panel title={`O que mudou nos últimos 30 dias (${data.changes_30d.length})`}>
              {data.changes_30d.length ? <ul className="rows">{data.changes_30d.map((m: any, i: number) => (
                <li key={i}><span><Link to={`/projetos/${m.project_id}`}>{m.project_title}</Link> · {m.entry_type.replace(/_/g, " ")}{m.amount_cents ? ` · ${money(m.amount_cents)}` : ""}</span>
                  <span className="muted small">{dateTime(m.at)}</span></li>))}</ul> : <p className="muted">Nenhum registro novo no razão dos projetos apoiados.</p>}
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

// ============================================================ governo
export function GovernmentTower() {
  const { data, error, loading, reload } = useLoad<any>("/v1/control-tower/government");
  const t = data?.totals;
  return (
    <>
      <PageHead title="Torre territorial" sub="Meu território → recursos → programas → editais → OSCs → projetos → execução → evidências → indicadores declarados × validados → atrasos → territórios descobertos." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <div className="grid-home">
              <Panel title={`Território ${data.territory.prefix}`}>
                <KeyValue items={[["Projetos publicados", n(t.projects)], ["OSCs executoras", n(t.oscs)],
                  ["Orçamento declarado", money(t.budget_total_cents)], ["Comprometido por financiadores", money(t.committed_cents)],
                  ["Desembolsado", money(t.disbursed_cents)], ["Gasto validado", money(t.validated_spent_cents)],
                  ["Evidências aceitas", n(t.evidences_accepted)], ["Etapas atrasadas", n(t.milestones_overdue)]]} />
                {data.k_anonymity.suppressed && <p className="muted small">Menos de 3 projetos publicados neste território: os dados não saem linha a linha (k-anonimato).</p>}
                <p className="muted small">{data.note}</p>
              </Panel>
              <Panel title="Indicadores: declarado × validado">
                <KeyValue items={[["Indicadores definidos", n(t.indicators)], ["Medições declaradas", n(data.indicators.reported)], ["Medições validadas", n(data.indicators.validated)]]} />
                <p className="muted small">{data.indicators.note}</p>
              </Panel>
              <Panel title="Programas e editais do órgão">
                {data.programs.length === 0 && data.calls.length === 0 && <p className="muted">Nenhum programa ou edital registrado. <Link to="/editais/novo">Criar edital</Link>.</p>}
                {data.programs.length > 0 && <ul className="rows">{data.programs.map((p: any) => (
                  <li key={p.id}><span>{p.title}<br /><span className="muted small">programa · {p.sphere || "—"} · {money(p.budget_total_cents)}</span></span><Pill status={p.status} /></li>))}</ul>}
                {data.calls.length > 0 && <ul className="rows">{data.calls.map((c: any) => (
                  <li key={c.id}><span><Link to={`/editais/${c.id}/candidaturas`}>{c.title}</Link><br /><span className="muted small">edital · {c.applications} candidatura(s) · {money(c.budget_total_cents)}</span></span><Pill status={c.status} /></li>))}</ul>}
              </Panel>
            </div>
            {data.by_cause.length > 0 && (
              <Panel title="Por causa: projetos, recurso comprometido e medições">
                <table className="table"><thead><tr><th>Causa</th><th>Projetos</th><th>Comprometido</th><th>Medições declaradas</th><th>Medições validadas</th></tr></thead>
                  <tbody>{data.by_cause.map((c: any) => <tr key={c.cause}><td>{c.cause}</td><td>{c.projects}</td><td>{money(c.committed_cents)}</td><td>{c.values_reported}</td><td>{c.values_validated}</td></tr>)}</tbody></table>
              </Panel>
            )}
            <Panel title={`OSCs e projetos no território (${data.projects.length})`}>
              {data.projects.length ? (
                <table className="table">
                  <thead><tr><th>Projeto</th><th>OSC</th><th>Território</th><th>Comprometido</th><th>Validado</th><th>Indicadores (decl./valid.)</th><th>Evidências</th><th>Etapas</th><th>Profissionais</th><th>Última atividade</th></tr></thead>
                  <tbody>{data.projects.map((p: any) => (
                    <tr key={p.project_id}>
                      <td><Link to={`/projetos/${p.project_id}`}>{p.title}</Link></td>
                      <td className="small">{p.osc_name} <Pill status={p.osc_compliance} /></td>
                      <td className="small">{p.territory}</td>
                      <td>{money(p.committed_cents)}</td>
                      <td>{money(p.validated_spent_cents)}</td>
                      <td className="small">{p.values_reported} / {p.values_validated}</td>
                      <td className="small">{p.evidences_accepted}</td>
                      <td className="small">{p.milestones}{p.milestones_overdue > 0 ? <> · <Pill tone="bad">{p.milestones_overdue} atrasada(s)</Pill></> : ""}</td>
                      <td className="small">{p.professionals}</td>
                      <td className="small">{p.last_activity ? date(p.last_activity) : "—"}</td>
                    </tr>
                  ))}</tbody>
                </table>
              ) : <p className="muted">Sem projetos publicados suficientes para listar.</p>}
            </Panel>
            <Panel title="Territórios descobertos (demanda × oferta)">
              {(Array.isArray(data.gaps) ? data.gaps : data.gaps?.items || []).length ? (
                <table className="table"><thead><tr><th>Território</th><th>Necessidades abertas</th><th>Críticas</th><th>Com fonte</th><th>Projetos publicados</th><th>Programas abertos</th><th>Lacuna</th></tr></thead>
                  <tbody>{(Array.isArray(data.gaps) ? data.gaps : data.gaps.items).map((g: any) => (
                    <tr key={g.territory}><td>{g.territory}</td><td>{g.needs_open}</td><td>{g.needs_critical}</td><td>{g.needs_with_source}</td><td>{g.projects_published}</td><td>{g.programs_open}</td>
                      <td><Pill tone={g.gap === "demanda_sem_oferta" ? "bad" : g.gap === "demanda_acima_da_oferta" ? "warn" : "muted"}>{(g.gap || "").replace(/_/g, " ")}</Pill></td></tr>))}</tbody></table>
              ) : <p className="muted">Nenhuma necessidade territorial registrada. <Link to="/territorio/necessidades">Registrar necessidades do território</Link>.</p>}
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}
