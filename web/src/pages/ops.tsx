// Administração: sinais de risco (revisão humana), erros agregados, modelos de contribuição pendentes.
import { useState } from "react";
import { api } from "../api";
import { dateTime, label } from "../format";
import { Button, Field, Input, PageHead, Panel, Pill, StateView, useAction, useLoad } from "../ui/kit";

const LEVEL: Record<string, [string, string]> = { none: ["Sem sinais", "good"], monitor: ["Acompanhar", "muted"], manual_review: ["Revisão manual", "warn"], blocked: ["Bloqueada por decisão humana", "bad"] };

export function Risk() {
  const sig = useLoad<any>("/v1/admin/risk/signals?limit=50");
  const ass = useLoad<any>("/v1/admin/risk/assessments");
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  const reload = () => { sig.reload(); ass.reload(); };
  return (
    <>
      <PageHead title="Sinais de risco" sub="São itens para revisão humana, não conclusões nem acusações. Nenhum bloqueio é automático."
        actions={<Button variant="ghost" busy={busy} onClick={() => run(() => api.post("/v1/admin/risk/scan", {}), "Varredura concluída").then(reload)}>Rodar varredura</Button>} />
      <StateView loading={sig.loading || ass.loading} error={sig.error || ass.error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Justificativa para a próxima ação"><Field label="Obrigatória (mín. 5 caracteres)" wide><Input value={note} onChange={setNote} /></Field></Panel>
          <Panel title="Organizações">
            {(ass.data?.items || []).length === 0 ? <p className="muted">Nenhuma avaliação.</p> : (
              <ul className="rows">{ass.data.items.map((a: any) => { const [t, tone] = LEVEL[a.level] || [a.level, "muted"]; return (
                <li key={a.org_id}><span>{a.org_name || a.org_id}</span><span className="stack-row"><Pill tone={tone}>{t}</Pill>
                  {a.level === "blocked"
                    ? <Button variant="ghost" busy={busy} disabled={note.length < 5} onClick={() => run(() => api.post(`/v1/admin/risk/orgs/${a.org_id}/unblock`, { note }), "Desbloqueada").then(reload)}>Desbloquear</Button>
                    : <Button variant="danger" busy={busy} disabled={note.length < 5} onClick={() => run(() => api.post(`/v1/admin/risk/orgs/${a.org_id}/block`, { note }), "Organização bloqueada").then(reload)}>Bloquear</Button>}</span></li>); })}</ul>
            )}
          </Panel>
          <Panel title="Sinais abertos">
            {(sig.data?.items || []).length === 0 ? <p className="muted">Nenhum sinal.</p> : (
              <ul className="rows">{sig.data.items.map((s: any) => (
                <li key={s.id}><span><strong>{label(s.signal_type)}</strong><div className="muted">{s.summary}</div></span>
                  <span className="stack-row"><Pill status={s.status} />{s.status === "open" && <>
                    <Button variant="ghost" busy={busy} disabled={note.length < 5} onClick={() => run(() => api.post(`/v1/admin/risk/signals/${s.id}/review`, { status: "dismissed", note }), "Sinal descartado").then(reload)}>Descartar</Button>
                    <Button variant="ink" busy={busy} disabled={note.length < 5} onClick={() => run(() => api.post(`/v1/admin/risk/signals/${s.id}/review`, { status: "reviewed_relevant", note }), "Sinal mantido em revisão").then(reload)}>Manter em revisão</Button></>}</span></li>))}</ul>
            )}
          </Panel>
        </div>
      </StateView>
    </>
  );
}

export function Errors() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/errors?limit=50");
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Erros agrupados" sub="Agrupados por impressão digital, com dados pessoais removidos da mensagem." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {(data?.items || []).length === 0 ? <p className="muted">Nenhum erro registrado.</p> : (
          <table className="table"><thead><tr><th>Rota</th><th>Tipo</th><th>Ocorrências</th><th>Última</th><th></th></tr></thead>
            <tbody>{data.items.map((e: any) => <tr key={e.id}><td>{e.route}</td><td>{e.exception_type}<div className="muted">{e.message}</div></td><td>{e.occurrences}</td><td>{dateTime(e.last_seen)}</td>
              <td>{!e.resolved && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/admin/errors/${e.id}/resolve`), "Marcado como resolvido").then(reload)}>Resolver</Button>}</td></tr>)}</tbody></table>
        )}
      </StateView>
    </>
  );
}

export function ContributionReview() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/contribution-models");
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Modelos de contribuição" sub="Decisão jurídica registrada antes de qualquer uso. A plataforma não oferece parecer jurídico automático." />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Parecer"><Field label="Justificativa da decisão" wide><Input value={note} onChange={setNote} /></Field></Panel>
          {(data?.items || []).length === 0 ? <p className="muted">Nenhum modelo aguardando análise.</p> : data.items.map((m: any) => (
            <Panel key={m.id} title={m.title}>
              <p className="muted">{label(m.kind)} · {m.org_name}</p>
              <p>{m.legal_structure || "Sem estrutura jurídica informada."}</p>
              <div className="stack-row">
                <Button variant="primary" busy={busy} disabled={note.length < 5} onClick={() => run(() => api.post(`/v1/admin/contribution-models/${m.id}/decide`, { approve: true, note }), "Modelo aprovado").then(reload)}>Aprovar</Button>
                <Button variant="danger" busy={busy} disabled={note.length < 5} onClick={() => run(() => api.post(`/v1/admin/contribution-models/${m.id}/decide`, { approve: false, note }), "Modelo recusado").then(reload)}>Recusar</Button>
              </div>
            </Panel>))}
        </div>
      </StateView>
    </>
  );
}
