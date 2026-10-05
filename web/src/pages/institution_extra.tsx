import { useState } from "react";
import type { ReactNode } from "react";
import { api, qs } from "../api";
import { date, dateTime, money, parseMoney } from "../format";
import { Button, Field, Input, KeyValue, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

const TYPE_OPTIONS: [string, string][] = [["management_contract", "Contrato de gestão"], ["partnership_term", "Termo de parceria"], ["collaboration_term", "Termo de colaboração"],
  ["fomento_term", "Termo de fomento"], ["cooperation_agreement", "Acordo de cooperação"], ["other", "Outro instrumento"]];
const VERIFY_TONE: Record<string, string> = { verified: "good", declared: "muted", document_submitted: "warn", rejected: "bad" };
const PROFILE_LABEL: Record<string, string> = { os: "Organização Social (OS)", oscip: "OSCIP", osc: "Organização da Sociedade Civil (OSC)", structuring: "Iniciativa em estruturação" };
const TOPICS: [string, string][] = [["formalization", "Formalização"], ["documentation", "Documentação"], ["project", "Projeto"], ["fundraising", "Captação de recursos"], ["accountability", "Prestação de contas"], ["institutional", "Fortalecimento institucional"], ["other", "Outro"]];
const MENTORING_LABEL: Record<string, string> = { open: "Aberto", in_progress: "Em atendimento", scheduled: "Agendado", done: "Concluído", cancelled: "Cancelado" };

// ------------------------------------------------------------------------------------------------ perfis OS / OSCIP / OSC
export function PersonaTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/persona");
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <p className="muted">Perfis identificados a partir do que foi registrado: {data.profiles.length ? data.profiles.map((p: string) => PROFILE_LABEL[p] || p).join(", ") : "nenhum ainda"}.</p>
          {data.views.map((v: any) => (
            <Panel key={v.profile} title={PROFILE_LABEL[v.profile] || v.profile}>
              {v.qualifications?.length > 0 && (
                <ul className="rows">{v.qualifications.map((q: any) => (
                  <li key={q.id}><span>{q.issuing_authority || "autoridade não informada"} · nº {q.certificate_number || "—"} · validade {date(q.expiration_date)}
                    {q.areas?.length > 0 && <><br /><span className="muted">Áreas: {q.areas.join(", ")}</span></>}</span><Pill tone={VERIFY_TONE[q.status] || "muted"}>{q.status_label}</Pill></li>
                ))}</ul>
              )}
              {v.alerts?.length > 0 && <ul role="alert">{v.alerts.map((a: any, i: number) => <li key={i}><Pill tone="warn">Atenção</Pill> {a.message}</li>)}</ul>}
              {v.agreements?.length > 0 && <p><strong>Instrumentos deste perfil:</strong> {v.agreements.map((a: any) => `${a.type_label} ${a.instrument_number || ""}`.trim()).join("; ")}</p>}
              {v.next_steps?.length > 0 && <><strong>Próximos passos</strong><ul>{v.next_steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></>}
              <p className="muted small">{v.disclaimer}</p>
            </Panel>
          ))}
          {data.modalities?.length > 0 && (
            <Panel title="Modalidades de financiamento (análise de apoio)">
              <ul className="rows">{data.modalities.map((m: any) => (
                <li key={m.code}><span><strong>{m.code.replace(/_/g, " ")}</strong>{m.missing.length > 0 && <><br /><span className="muted">Falta: {m.missing.join("; ")}</span></>}</span><Pill tone="muted">{m.state_label}</Pill></li>
              ))}</ul>
            </Panel>
          )}
          <p className="muted small">{data.note}</p>
        </>
      )}
    </StateView>
  );
}

// ------------------------------------------------------------------------------------------------ instrumentos (contratos de gestão, termos)
const EMPTY_AG = { agreement_type: "", counterpart_name: "", counterpart_authority: "", instrument_number: "", object_summary: "", start_date: "", end_date: "", value: "", verification_url: "" };

export function AgreementsTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/agreements");
  const f = useForm<any>(EMPTY_AG);
  const { busy, run } = useAction();
  async function add(e: any) {
    e.preventDefault();
    const b: any = {};
    for (const [k, v] of Object.entries(f.v)) if (v !== "" && k !== "value") b[k] = v;
    if (f.v.value) b.value_cents = parseMoney(f.v.value);
    const r = await run(() => api.post("/v1/institutional/agreements", b), "Instrumento registrado como declarado");
    if (r) { f.setV(EMPTY_AG); reload(); }
  }
  async function remove(id: string) { await run(() => api.del(`/v1/institutional/agreements/${id}`), "Removido"); reload(); }
  async function setStatus(id: string, agreement_status: string) { await run(() => api.patch(`/v1/institutional/agreements/${id}`, { agreement_status }), "Status atualizado"); reload(); }
  return (
    <div className="split">
      <Panel title="Contratos de gestão, termos e acordos">
        <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nenhum instrumento registrado.</p> : false}>
          <ul className="rows">{data?.items.map((a: any) => (
            <li key={a.id}>
              <span><strong>{a.type_label}</strong> {a.instrument_number && `nº ${a.instrument_number}`} <Pill tone={VERIFY_TONE[a.verification_status] || "muted"}>{a.verification_label}</Pill><br />
                <span className="muted">{a.counterpart_name} · {a.status_label} · {date(a.start_date)} a {date(a.end_date)}{a.value_cents != null && ` · ${money(a.value_cents)}`}</span>
                {a.alert && <><br /><Pill tone="warn">Atenção</Pill> {a.alert.message}</>}
                {a.validation_note && <><br /><span className="muted">Nota da verificação: {a.validation_note}</span></>}</span>
              <span className="row-actions">
                {a.agreement_status === "active" && <Button variant="link" onClick={() => setStatus(a.id, "completed")}>Marcar concluído</Button>}
                {a.verification_status !== "verified" && <Button variant="link" onClick={() => remove(a.id)}>Remover</Button>}
              </span>
            </li>
          ))}</ul>
          <p className="muted">Registrar não comprova. A administração só marca como verificado com número do instrumento e comprovante validado ou consulta oficial.</p>
        </StateView>
      </Panel>
      <Panel title="Registrar instrumento">
        <form className="form" onSubmit={add}>
          <Field label="Tipo"><Select value={f.v.agreement_type} onChange={f.set("agreement_type")} placeholder="Selecione" options={TYPE_OPTIONS} /></Field>
          <Field label="Órgão ou parte contratante"><Input value={f.v.counterpart_name} onChange={f.set("counterpart_name")} /></Field>
          <Field label="Número do instrumento"><Input value={f.v.instrument_number} onChange={f.set("instrument_number")} /></Field>
          <Field label="Início"><Input type="date" value={f.v.start_date} onChange={f.set("start_date")} /></Field>
          <Field label="Fim"><Input type="date" value={f.v.end_date} onChange={f.set("end_date")} /></Field>
          <Field label="Valor (R$)"><Input value={f.v.value} onChange={f.set("value")} inputMode="decimal" /></Field>
          <Field label="Endereço de verificação oficial" hint="https://…"><Input value={f.v.verification_url} onChange={f.set("verification_url")} /></Field>
          <Field label="Objeto" wide><TextArea rows={2} value={f.v.object_summary} onChange={f.set("object_summary")} /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={!f.v.agreement_type || f.v.counterpart_name.length < 2}>Registrar</Button>
        </form>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ trilha de formalização + mentoria
export function FormalizationTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/formalization");
  const { run } = useAction();
  async function setState(code: string, state: string) { await run(() => api.put(`/v1/institutional/formalization/${code}`, { state }), "Etapa atualizada (declarada)"); reload(); }
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <Panel title={`Trilha de formalização — ${data.progress.done} de ${data.progress.total} etapas`}>
            <progress max={data.progress.total} value={data.progress.done} aria-label="Progresso da trilha" />
            <p className="muted small">{data.progress.note}</p>
            {data.next_step && <p><strong>Próxima etapa:</strong> {data.next_step.label} — {data.next_step.help}</p>}
            <ol className="rows">{data.steps.map((s: any) => (
              <li key={s.code}>
                <span><strong>{s.label}</strong> <Pill tone={s.state === "done" ? "good" : s.state === "in_progress" ? "warn" : "muted"}>{s.state === "done" ? "Concluída" : s.state === "in_progress" ? "Em andamento" : "A fazer"}</Pill> <span className="muted small">{s.basis_label}</span><br />
                  <span className="muted">{s.help}</span></span>
                {s.kind === "manual" && (
                  <Select aria-label={`Andamento de ${s.label}`} value={s.state === "done" ? "done_declared" : s.state === "in_progress" ? "in_progress" : "not_started"} onChange={(v: string) => setState(s.code, v)}
                    options={[["not_started", "Não iniciada"], ["in_progress", "Em andamento"], ["done_declared", "Concluída (declaro)"]]} />
                )}
              </li>
            ))}</ol>
            <p className="muted small">{data.status_note}. {data.disclaimer}</p>
          </Panel>
          <MentoringPanel />
        </>
      )}
    </StateView>
  );
}

function MentoringPanel() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/mentoring");
  const f = useForm<any>({ topic: "", message: "" });
  const { busy, run } = useAction();
  async function send(e: any) { e.preventDefault(); const r = await run(() => api.post("/v1/institutional/mentoring", f.v), "Pedido enviado"); if (r) { f.setV({ topic: "", message: "" }); reload(); } }
  async function cancel(id: string) { await run(() => api.post(`/v1/institutional/mentoring/${id}/cancel`, {}), "Pedido cancelado"); reload(); }
  return (
    <div className="split">
      <Panel title="Pedidos de mentoria">
        <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nenhum pedido ainda.</p> : false}>
          <ul className="rows">{data?.items.map((m: any) => (
            <li key={m.id}><span><strong>{TOPICS.find((t) => t[0] === m.topic)?.[1] || m.topic}</strong> <Pill tone="muted">{MENTORING_LABEL[m.status] || m.status}</Pill><br /><span className="muted">{m.message}</span>
              {m.admin_note && <><br /><span className="muted">Resposta da equipe: {m.admin_note}</span></>}</span>
              {["open", "in_progress", "scheduled"].includes(m.status) && <Button variant="link" onClick={() => cancel(m.id)}>Cancelar</Button>}</li>
          ))}</ul>
          <p className="muted small">{data?.note}</p>
        </StateView>
      </Panel>
      <Panel title="Pedir mentoria">
        <form className="form" onSubmit={send}>
          <Field label="Assunto"><Select value={f.v.topic} onChange={f.set("topic")} placeholder="Selecione" options={TOPICS} /></Field>
          <Field label="O que você precisa?" wide><TextArea rows={3} value={f.v.message} onChange={f.set("message")} /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={!f.v.topic || f.v.message.length < 10}>Enviar pedido</Button>
        </form>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ administração
export function AdminAgreements() {
  const [status, setStatus] = useState("document_submitted");
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/agreements" + qs({ status }));
  const { run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const decide = (id: string, decision: string) => run(() => api.post(`/v1/admin/institutional/agreements/${id}/decide`, { decision, note: note[id] || "" }), "Decisão registrada").then(reload);
  return (
    <Panel title="Fila de instrumentos" actions={<Select value={status} onChange={setStatus} options={[["document_submitted", "Comprovante enviado"], ["declared", "Declarados"], ["verified", "Verificados"], ["rejected", "Rejeitados"]]} />}>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nada na fila.</p> : false}>
        <table className="table"><thead><tr><th>Organização</th><th>Instrumento</th><th>Comprovação</th><th>Decisão</th></tr></thead>
          <tbody>{data?.items.map((a: any) => (
            <tr key={a.id}>
              <td>{a.org_name}<br /><span className="muted">{a.cnpj}</span></td>
              <td><strong>{a.type_label}</strong> {a.instrument_number && `nº ${a.instrument_number}`}<br /><span className="muted">{a.counterpart_name}</span><br /><Pill tone={VERIFY_TONE[a.verification_status] || "muted"}>{a.verification_label}</Pill></td>
              <td>{a.verification_url && <a href={a.verification_url} target="_blank" rel="noopener noreferrer">Consulta oficial</a>}{a.document_id && <span className="muted"> documento {a.document_validation === "validated" ? "validado" : "não validado"}</span>}</td>
              <td><Input value={note[a.id] || ""} onChange={(v: string) => setNote({ ...note, [a.id]: v })} placeholder="Nota (obrigatória)" aria-label="Nota da decisão" />
                <span className="row-actions"><Button variant="link" onClick={() => decide(a.id, "verify")}>Verificar</Button><Button variant="link" onClick={() => decide(a.id, "reject")}>Rejeitar</Button></span></td>
            </tr>
          ))}</tbody></table>
      </StateView>
    </Panel>
  );
}

export function AdminMentoring() {
  const [status, setStatus] = useState("open");
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/mentoring" + qs({ status }));
  const { run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const upd = (id: string, st: string) => run(() => api.post(`/v1/admin/institutional/mentoring/${id}/update`, { status: st, admin_note: note[id] || null }), "Atualizado").then(reload);
  return (
    <Panel title="Pedidos de mentoria" actions={<Select value={status} onChange={setStatus} options={Object.entries(MENTORING_LABEL) as [string, string][]} />}>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nada na fila.</p> : false}>
        <ul className="rows">{data?.items.map((m: any) => (
          <li key={m.id}><span><strong>{m.org_name}</strong> · {TOPICS.find((t) => t[0] === m.topic)?.[1] || m.topic} <span className="muted small">{dateTime(m.created_at)}</span><br />{m.message}</span>
            <span><Input value={note[m.id] || ""} onChange={(v: string) => setNote({ ...note, [m.id]: v })} placeholder="Nota para a organização" aria-label="Nota" />
              <span className="row-actions">{(["in_progress", "scheduled", "done"] as const).map((s) => <Button key={s} variant="link" onClick={() => upd(m.id, s)}>{MENTORING_LABEL[s]}</Button>)}</span></span></li>
        ))}</ul>
      </StateView>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ rede da solução
const NODE_LABEL: Record<string, string> = { solution: "Solução", organization: "Organização", territory: "Território", ods: "ODS", theme: "Tema", related: "Solução relacionada", demand: "Demanda" };

export function NetworkView({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/solutions/${id}/network`);
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <ul className="rows" aria-label="Relações da solução">
            {data.edges.map((e: any, i: number) => {
              const n = data.nodes.find((x: any) => x.id === e.target);
              return n ? <li key={i}><span><span className="muted">{e.label}</span> · <strong>{n.label}</strong><br /><span className="muted small">{NODE_LABEL[n.type] || n.type}{n.detail ? ` — ${n.detail}` : ""}</span></span></li> : null;
            })}
          </ul>
          <KeyValue items={[["Interessadas", data.demand.interested_orgs], ["Pediram informações", data.demand.requested_info_orgs], ["Em avaliação", data.demand.in_evaluation_orgs], ["Pedidos de adaptação", data.demand.adaptation_requests],
            ["Replicações concluídas (confirmadas)", data.demand.replications.completed_confirmed]] as [string, ReactNode][]} />
          <p className="muted small">{data.note}</p>
        </>
      )}
    </StateView>
  );
}
