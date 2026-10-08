/** v0.27.0 — Participação de autoria e desenvolvimento da ideia.
 *
 * A executora propõe; o proponente aceita; o projeto publicado consolida; o acordo de financiamento em vigor
 * acumula a linha na matriz; o repasse confirmado paga. Nunca é automática para todo projeto.
 */
import { useState } from "react";
import { api } from "../api";
import { date, money } from "../format";
import { Link } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useLoad } from "../ui/kit";

const PART_STATUS: Record<string, [string, string]> = {
  proposed: ["proposta — aguarda seu aceite", "warn"], under_review: ["em análise", "warn"], accepted: ["aceita", "good"], consolidated: ["consolidada (projeto publicado)", "good"],
  eligible: ["elegível (acordo em vigor)", "good"], accrued: ["na matriz do acordo", "good"], validated: ["validada", "good"], payable: ["a pagar", "warn"],
  paid: ["paga", "good"], disputed: ["em disputa", "bad"], cancelled: ["cancelada", "muted"],
};
const STEPS = ["proposed", "accepted", "consolidated", "eligible", "accrued", "paid"];

export function Participations() {
  const { data, error, loading, reload } = useLoad<any>("/v1/participations");
  const { me } = useSession();
  const myOrg = me?.active_org?.id;
  const { busy, run } = useAction();
  const [cancelId, setCancelId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const act = (fn: () => Promise<any>, msg: string) => run(async () => { await fn(); reload(); return msg; });
  return (
    <>
      <PageHead title="Participação de autoria" sub="Quem propôs a ideia acompanha o que ela virou — e, quando há acordo de financiamento com participação contratada, recebe a sua parte diretamente de quem financia." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <ul className="rows">{data.items.map((p: any) => {
            const mineAsProponent = p.proponent_org_id === myOrg;
            const idx = STEPS.indexOf(p.status);
            return (
              <li key={p.id}>
                <span>
                  <strong>{p.project_title || "Projeto ainda não publicado"}</strong>
                  <br /><span className="muted small">{mineAsProponent ? `executora: ${p.executor_name}` : `proponente: ${p.proponent_name}`} · {p.authorship_type === "author" ? "autoria" : "coautoria"} · fração {(p.share_bps / 100).toFixed(2)}% da participação</span>
                  <br /><span className="muted small">{p.contribution}</span>
                  {idx >= 0 && <><br /><span className="muted small">trajetória: {STEPS.map((s, i) => (i <= idx ? "●" : "○")).join(" ")} {STEPS.slice(0, idx + 1).map((s) => PART_STATUS[s][0].split(" ")[0]).join(" → ")}</span></>}
                  {p.agreement_id && <><br /><Link to={`/acordos/${p.agreement_id}`} className="small">Abrir o acordo de financiamento</Link></>}
                </span>
                <span>
                  <Pill tone={PART_STATUS[p.status]?.[1] || "muted"}>{PART_STATUS[p.status]?.[0] || p.status}</Pill>{" "}
                  {mineAsProponent && ["proposed", "under_review"].includes(p.status) && (
                    <Button variant="primary" busy={busy} onClick={() => act(() => api.post(`/v1/participations/${p.id}/accept`), "Participação aceita.")}>Aceitar</Button>
                  )}
                  {!["paid", "cancelled"].includes(p.status) && (
                    <Button busy={busy} onClick={() => { setCancelId(p.id); setReason(""); }}>Cancelar</Button>
                  )}
                </span>
              </li>
            );
          })}</ul>
        )}
      </StateView>
      <Modal open={!!cancelId} title="Cancelar a participação" onClose={() => setCancelId(null)}
             footer={<><Button onClick={() => setCancelId(null)}>Voltar</Button>
               <Button variant="danger" busy={busy} disabled={reason.trim().length < 10}
                       onClick={() => act(() => api.post(`/v1/participations/${cancelId}/cancel`, { reason }), "Participação cancelada.").then(() => setCancelId(null))}>Cancelar participação</Button></>}>
        <Field label="Motivo"><TextArea value={reason} onChange={setReason} rows={3} /></Field>
      </Modal>
    </>
  );
}

/** Painel na ficha do projeto (executora): propor participação a quem propôs a ideia. */
export function ProposeParticipation({ projectId, onDone }: { projectId: string; onDone: () => void }) {
  const { busy, run } = useAction();
  const [open, setOpen] = useState(false);
  const [org, setOrg] = useState("");
  const [refType, setRefType] = useState("solution");
  const [refId, setRefId] = useState("");
  const [authorship, setAuthorship] = useState("author");
  const [share, setShare] = useState("100");
  const [contribution, setContribution] = useState("");
  return (
    <>
      <Button onClick={() => setOpen(true)}>Propor participação de autoria</Button>
      <Modal open={open} title="Participação de autoria e desenvolvimento da ideia" onClose={() => setOpen(false)}
             footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button>
               <Button variant="primary" busy={busy} disabled={!org || !refId || contribution.trim().length < 20}
                       onClick={() => run(async () => {
                         await api.post(`/v1/projects/${projectId}/participations`, {
                           proponent_org_id: org, idea_ref_type: refType, idea_ref_id: refId, authorship_type: authorship,
                           share_bps: Math.round(parseFloat(share.replace(",", ".")) * 100), contribution });
                         setOpen(false); onDone();
                         return "Participação proposta. Só vale com o aceite do proponente.";
                       })}>Propor</Button></>}>
        <p className="small">Só existe participação com autoria registrada, aceita pelo proponente, projeto publicado e acordo de financiamento em vigor com o proponente como parte. Nunca é automática.</p>
        <Field label="Organização ou pessoa proponente (identificador)"><Input value={org} onChange={setOrg} placeholder="UUID" /></Field>
        <Field label="Origem da ideia"><Select value={refType} onChange={setRefType} options={[["solution", "Biblioteca de soluções (ideia publicada)"], ["idea", "Ideias desta organização"]]} /></Field>
        <Field label="Identificador da ideia"><Input value={refId} onChange={setRefId} placeholder="UUID" /></Field>
        <Field label="Natureza"><Select value={authorship} onChange={setAuthorship} options={[["author", "Autoria"], ["coauthor", "Coautoria"]]} /></Field>
        <Field label="Fração da participação (%)" hint="Quando há mais de um proponente, as frações somam até 100%."><Input value={share} onChange={setShare} inputMode="decimal" /></Field>
        <Field label="Contribuição efetiva" wide><TextArea value={contribution} onChange={setContribution} rows={3} placeholder="O que esta pessoa fez pela ideia e pelo projeto." /></Field>
      </Modal>
    </>
  );
}

export function TrajectoryCard({ trajectory }: { trajectory: any }) {
  if (!trajectory) return null;
  const r = trajectory.recognitions || {};
  const LABEL: Record<string, string> = { operation_settled: "operações concluídas e quitadas", funding_settled: "aportes integralmente confirmados",
    delivery_accepted: "entregas aceitas", participation_paid: "participações de autoria pagas", evidence_validated: "medições validadas" };
  const items = Object.keys(LABEL).filter((k) => r[k]);
  return (
    <Panel title="Trajetória" quiet>
      {items.length ? <ul className="rows">{items.map((k) => (
        <li key={k}><span>{LABEL[k]}{r[k].amount_cents ? <><br /><span className="muted small">{money(r[k].amount_cents)} · último em {date(r[k].last_at)}</span></> : null}</span><strong>{r[k].count}</strong></li>
      ))}</ul> : <p className="muted small">Nenhum reconhecimento ainda. Eles nascem de entrega aceita, repasse confirmado por quem recebe e operação quitada — nunca de pagamento à plataforma.</p>}
    </Panel>
  );
}
