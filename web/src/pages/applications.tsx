import { useState } from "react";
import { api } from "../api";
import { date, dateTime, label, money, parseMoney } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useLoad } from "../ui/kit";
import { EXTERNAL_TRAIL, INTEREST_TRAIL, MatchVerdict, PLATFORM_TRAIL, Trail } from "../ui/trail";
import { DocLink } from "./projects";
import { UploadButton } from "./documents";

export function Applications() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/applications?offset=${offset}${status ? `&status=${status}` : ""}`, [status, offset]);
  return (
    <>
      <PageHead title="Candidaturas" sub="Cada candidatura segue uma trilha: preparação, envio, diligência, aporte, execução e prestação de contas." />
      <div className="filters">
        <Field label="Situação"><Select value={status} onChange={(v) => { setStatus(v); setOffset(0); }} placeholder="Todas"
          options={["interest", "draft", "submitted", "screening", "due_diligence", "approved", "committed", "in_execution", "reporting", "closed", "rejected", "withdrawn"].map((s) => [s, label(s)])} /></Field>
      </div>
      <StateView loading={loading} error={error} onRetry={reload}
        empty={data?.items.length === 0 && <><p>Nenhuma candidatura por aqui.</p><Link to="/oportunidades">Encontrar oportunidades</Link></>}>
        <table className="table">
          <thead><tr><th>Oportunidade</th><th>Projeto</th><th>Parte</th><th>Situação</th><th>Checklist</th><th>Atualizada</th></tr></thead>
          <tbody>
            {data?.items.map((a: any) => (
              <tr key={a.id}>
                <td><Link to={`/candidaturas/${a.id}`}>{a.call_title || (a.origin === "funder_interest" ? "Interesse direto do financiador" : "—")}</Link>
                  <br /><span className="muted">{a.origin === "external_tracking" ? "Edital externo" : a.funder_name || a.funder_org_name}</span></td>
                <td>{a.project_title || "—"}</td>
                <td>{a.side === "osc" ? a.funder_org_name || a.funder_name || "—" : a.osc_name}</td>
                <td><Pill status={a.status} /></td>
                <td>{a.steps_done}/{a.steps_total}</td>
                <td>{date(a.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}

const STEP_KIND: Record<string, string> = { requirement: "Requisito", document: "Documento", writing: "Redação", review: "Validação profissional",
  signature: "Assinatura", submission: "Envio", followup: "Acompanhamento" };

export function ApplicationDetail({ id }: { id: string }) {
  const { data: a, error, loading, reload } = useLoad<any>(`/v1/applications/${id}`);
  const { me } = useSession();
  const { busy, run } = useAction();
  const [move, setMove] = useState<any>(null);
  const [note, setNote] = useState("");
  const [protocol, setProtocol] = useState("");
  const [amount, setAmount] = useState("");
  const [milestone, setMilestone] = useState("");
  const project = useLoad<any>(a?.project_id ? `/v1/projects/${a.project_id}` : null, [a?.project_id]);
  const trail = a?.origin === "external_tracking" ? EXTERNAL_TRAIL : a?.origin === "funder_interest" ? INTEREST_TRAIL : PLATFORM_TRAIL;
  const ended = ["rejected", "withdrawn"].includes(a?.status) ? a.status : undefined;
  const lastActive = ended ? a.timeline.filter((t: any) => !["rejected", "withdrawn"].includes(t.to_status)).slice(-1)[0]?.to_status : a?.status;

  async function doMove() {
    const r = await run(() => api.post(`/v1/applications/${id}/transition`, { to_status: move.to, note: note || null, external_protocol: protocol || null }), "Etapa atualizada");
    if (r) { setMove(null); setNote(""); reload(); }
  }
  return (
    <StateView loading={loading && !a} error={error} onRetry={reload}>
      {a && (
        <>
          <PageHead back={<Link to="/candidaturas" className="back">Candidaturas</Link>}
            title={a.call_title || a.project_title || "Candidatura"}
            sub={<>{a.side === "osc" ? (a.funder_org_name || a.funder_name || "Edital externo") : a.osc_name}
              {a.project_title && <> · projeto <Link to={`/projetos/${a.project_id}`}>{a.project_title}</Link></>}
              {a.external_protocol && <> · protocolo {a.external_protocol}</>}</>}
            actions={a.next_transitions.map((t: any) => (
              <Button key={t.to} variant={["rejected", "withdrawn"].includes(t.to) ? "ghost" : "primary"} onClick={() => setMove(t)}>{transitionLabel(t.to, a.status)}</Button>
            ))} />
          <Trail steps={trail} current={lastActive} ended={ended} />
          <div className="detail">
            <div className="detail-main">
              <Panel title="Passo a passo" actions={<span className="muted">{a.steps.filter((s: any) => s.status === "done" || s.status === "not_applicable").length} de {a.steps.length}</span>}>
                <ol className="checklist">
                  {a.steps.map((s: any) => <Step key={s.id} s={s} a={a} reload={reload} />)}
                </ol>
              </Panel>
              {a.match && <MatchVerdict m={a.match} />}
            </div>
            <aside className="detail-side">
              {(a.commitments.length > 0 || (a.side === "funder" && ["approved", "committed", "in_execution"].includes(a.status))) && (
                <Panel title="Aportes" quiet>
                  <p className="fineprint">O dinheiro é transferido diretamente entre as partes; a plataforma registra e rastreia.</p>
                  <ul className="rows">
                    {a.commitments.map((c: any) => (
                      <li key={c.id}>
                        <span>{money(c.amount_cents)}<br /><Pill status={c.status} /></span>
                        <span className="row-actions">
                          {a.side === "funder" && c.status === "pledged" && <Button variant="link" onClick={() => run(() => api.post(`/v1/commitments/${c.id}/status`, { status: "disbursed", reference: prompt("Referência da transferência (opcional)") || null }), "Desembolso informado").then(reload)}>Informar desembolso</Button>}
                          {a.side === "osc" && c.status === "disbursed" && <Button variant="link" onClick={() => run(() => api.post(`/v1/commitments/${c.id}/status`, { status: "confirmed" }), "Recebimento confirmado").then(reload)}>Confirmar recebimento</Button>}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {a.side === "funder" && ["approved", "committed", "in_execution"].includes(a.status) && (
                    <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/applications/${id}/commitments`, { amount_cents: parseMoney(amount), milestone_id: milestone || null }), "Aporte registrado").then((r) => { if (r) { setAmount(""); reload(); } }); }}>
                      <Field label="Valor (R$)"><Input inputMode="decimal" value={amount} onChange={setAmount} /></Field>
                      <Field label="Etapa apoiada"><Select value={milestone} onChange={setMilestone} placeholder="Projeto como um todo"
                        options={(project.data?.milestones || []).map((m: any) => [m.id, `${m.seq}. ${m.title} (${money(m.amount_cents - m.funded_cents)} em aberto)`])} /></Field>
                      <Button type="submit" variant="ink" busy={busy}>Registrar aporte</Button>
                    </form>
                  )}
                </Panel>
              )}
              {a.side === "funder" && ["due_diligence", "screening", "submitted"].includes(a.status) && (
                <Panel title="Conflito de interesse" quiet>
                  {a.my_conflict_declaration ? (
                    <p>Você declarou {a.my_conflict_declaration.has_conflict ? <strong>ter conflito</strong> : "não ter conflito"} em {dateTime(a.my_conflict_declaration.declared_at)}.</p>
                  ) : <p className="muted">Obrigatório antes de aprovar.</p>}
                  <div className="stack">
                    <Button variant="ghost" onClick={() => run(() => api.post(`/v1/applications/${id}/conflict`, { has_conflict: false }), "Declaração registrada").then(reload)}>Declaro não ter conflito</Button>
                    <Button variant="link" onClick={() => { const d = prompt("Descreva o conflito:"); if (d) run(() => api.post(`/v1/applications/${id}/conflict`, { has_conflict: true, description: d }), "Conflito registrado").then(reload); }}>Tenho conflito</Button>
                  </div>
                </Panel>
              )}
              {a.documents && (
                <Panel title={a.side === "funder" ? "Documentos da OSC" : "Documentos vinculados"} quiet>
                  {a.side === "funder" && !["due_diligence", "approved", "committed", "in_execution", "reporting", "closed"].includes(a.status) ? (
                    <p className="muted">Os documentos ficam disponíveis a partir da diligência.</p>
                  ) : (
                    <ul className="rows">{a.documents.map((d: any) => <li key={d.id}><span>{d.title}<br /><span className="muted">vence {date(d.valid_until)}</span></span><DocLink id={d.id} /></li>)}
                      {a.documents.length === 0 && <li className="muted">Nenhum documento.</li>}</ul>
                  )}
                </Panel>
              )}
              <Panel title="Linha do tempo" quiet>
                <ol className="timeline">
                  {a.timeline.map((t: any, i: number) => (
                    <li key={i}><strong>{label(t.to_status)}</strong><span className="muted"> · {t.actor_org} · {dateTime(t.at)}</span>{t.note && <p>{t.note}</p>}</li>
                  ))}
                </ol>
              </Panel>
              {a.side === "osc" && me && <Panel title="Precisa de ajuda?" quiet>
                <p className="muted">Profissionais parceiros com credencial verificada podem revisar e assinar a proposta e a prestação de contas.</p>
                <Button variant="ghost" onClick={() => navigate("/profissionais")}>Encontrar profissional</Button>
              </Panel>}
            </aside>
          </div>
          <Modal open={!!move} title={move ? transitionLabel(move.to, a.status) : ""} onClose={() => setMove(null)}
            footer={<Button variant="primary" busy={busy} onClick={doMove}>Confirmar</Button>}>
            {move?.to === "submitted" && a.origin === "external_tracking" && (
              <Field label="Número do protocolo no portal do financiador"><Input value={protocol} onChange={setProtocol} /></Field>
            )}
            <Field label={move?.to === "rejected" ? "Devolutiva para a OSC (obrigatória)" : "Observação (opcional)"}>
              <TextArea rows={4} value={note} onChange={setNote} />
            </Field>
          </Modal>
        </>
      )}
    </StateView>
  );
}

function transitionLabel(to: string, from: string): string {
  const map: Record<string, string> = { submitted: "Enviar candidatura", screening: "Iniciar triagem", due_diligence: from === "interest" ? "Aceitar e iniciar diligência" : "Iniciar diligência",
    approved: "Aprovar", rejected: "Não aprovar", withdrawn: "Retirar", in_execution: "Iniciar execução", reporting: "Enviar prestação de contas",
    closed: "Encerrar", committed: "Registrar aporte" };
  return map[to] || label(to);
}

function Step({ s, a, reload }: { s: any; a: any; reload: () => void }) {
  const { busy, run } = useAction();
  const mine = a.side === "osc" || s.code === "conflict" || s.code === "decision";
  const set = (status: string) => run(() => api.patch(`/v1/applications/${a.id}/steps/${s.id}`, { status })).then(reload);
  return (
    <li className={`check-item check-${s.status}`}>
      <span className="check-mark" aria-hidden="true">{s.status === "done" ? "✓" : s.status === "not_applicable" ? "–" : ""}</span>
      <div className="check-body">
        <p><strong>{s.title}</strong> <span className="muted">· {STEP_KIND[s.kind]}{!s.mandatory && " (recomendado)"}</span></p>
        {s.description && <p className="muted">{s.description}</p>}
        {s.note && <p>{s.note}</p>}
        {mine && s.status !== "done" && (
          <div className="row-actions">
            {s.kind === "document" && <UploadButton docType={s.code.replace(/^doc_/, "")} applicationId={a.id} onUploaded={() => reload()} label="Enviar documento" />}
            {s.kind === "writing" && <Button variant="link" onClick={() => navigate(`/rascunhos?novo=${a.id}&projeto=${a.project_id || ""}&edital=${a.call_id || ""}`)}>Redigir com assistência</Button>}
            {s.kind === "review" && <Button variant="link" onClick={() => navigate("/profissionais")}>Solicitar validação</Button>}
            {s.kind === "signature" && <Button variant="link" onClick={() => navigate("/rascunhos")}>Assinar documento</Button>}
            {s.code !== "submission" && <Button variant="ghost" busy={busy} onClick={() => set("done")}>Marcar como concluída</Button>}
            {!s.mandatory && <Button variant="link" onClick={() => set("not_applicable")}>Não se aplica</Button>}
          </div>
        )}
        {mine && s.status === "done" && s.code !== "submission" && <Button variant="link" onClick={() => set("todo")}>Reabrir</Button>}
      </div>
    </li>
  );
}
