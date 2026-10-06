import { useState } from "react";
import { api } from "../api";
import { date, dateTime } from "../format";
import { Button, Field, Input, PageHead, Pager, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// MODERAÇÃO — escada proporcional, com regra, motivo, prazo e direito de contestar.
//
// Três coisas que esta tela mostra porque o produto precisa que estejam visíveis:
//   1. o HISTÓRICO do alvo e o que ele autoriza como próxima medida (proporcionalidade verificável);
//   2. o efeito prático de cada degrau, antes de alguém escolher;
//   3. que contornar a escada exige justificativa longa — e que ela fica marcada na medida.
//
// Nenhuma medida é aplicada automaticamente: a heurística prioriza a fila, nunca decide.

const TONE: Record<string, string> = { active: "bad", under_appeal: "warn", upheld: "bad", overturned: "good",
  lifted: "good", expired: "" };

export function MyModeration() {
  const { data, error, loading, reload } = useLoad<any>("/v1/conta/moderacao");
  const act = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const appeal = async (id: string) => {
    const n = note[id] || "";
    if (n.trim().length < 10) { alert("Descreva a contestação em pelo menos 10 caracteres."); return; }
    if (await act.run(() => api.post(`/v1/conta/moderacao/${id}/contestar`, { note: n }),
                      "Contestação registrada")) reload();
  };
  return (
    <>
      <PageHead title="Medidas de moderação" sub="O que foi aplicado, com a regra, o motivo e o prazo." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <p className="muted small">{data.note}</p>
            {data.items.map((m: any) => (
              <Panel key={m.id} title={m.label} actions={<Pill tone={TONE[m.status]}>{m.status}</Pill>}>
                <p>{m.reason}</p>
                <ul className="small">
                  <li>Regra aplicada: <strong>{m.rule_ref}</strong></li>
                  <li>Efeito: {m.effect}</li>
                  <li>Vigora desde {date(m.starts_at)}{m.ends_at ? ` até ${date(m.ends_at)}` : " (sem prazo)"}</li>
                </ul>
                {m.evidence_note && <p className="small muted">{m.evidence_note}</p>}
                {m.appeal_at && (
                  <Panel title="Sua contestação" quiet>
                    <p>{m.appeal_note}</p>
                    <p className="muted small">registrada em {dateTime(m.appeal_at)}</p>
                    {m.appeal_decision && <><h3>Decisão</h3><p>{m.appeal_decision}</p></>}
                  </Panel>
                )}
                {m.can_appeal && (
                  <>
                    <Field label="Contestar esta medida"
                           hint="Quem julga a contestação não é quem aplicou a medida." wide>
                      <TextArea value={note[m.id] || ""} rows={3}
                                onChange={(v) => setNote({ ...note, [m.id]: v })} /></Field>
                    <Button variant="ink" busy={act.busy} onClick={() => appeal(m.id)}>Contestar</Button>
                  </>
                )}
              </Panel>
            ))}
          </>
        )}
      </StateView>
    </>
  );
}

// ---------------------------------------------------------------------------- administração
export function EnforcementAdmin() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const qs = `${status ? `status=${status}&` : ""}limit=20&offset=${offset}`;
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/enforcement?${qs}`, [status, offset]);
  const ladder = useLoad<any>("/v1/moderation/ladder");
  const act = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const run = async (id: string, path: string, body: any, ok: string) => {
    if (await act.run(() => api.post(`/v1/admin/enforcement/${id}/${path}`, body), ok)) reload();
  };
  return (
    <>
      <PageHead title="Medidas de moderação" sub="Escada proporcional. Nenhuma medida é automática." />
      {ladder.data && (
        <Panel title="A escada" quiet>
          <table className="table small">
            <thead><tr><th>Degrau</th><th>Severidade</th><th>Prazo</th><th>O que faz</th></tr></thead>
            <tbody>
              {ladder.data.items.map((l: any) => (
                <tr key={l.measure}>
                  <td>{l.label}</td><td>{l.severity}</td>
                  <td>{l.requires_end_date ? "obrigatório" : "—"}</td><td>{l.effect}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">{ladder.data.note}</p>
        </Panel>
      )}
      <NewMeasure ladder={ladder.data} onDone={reload} />
      <Panel quiet>
        <Field label="Situação"><Select value={status} onChange={(v) => { setStatus(v); setOffset(0); }}
          placeholder="Todas" options={[["active", "Em vigor"], ["under_appeal", "Contestada"],
            ["upheld", "Mantida"], ["overturned", "Revertida"], ["lifted", "Levantada"],
            ["expired", "Expirada"]]} /></Field>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            {data.items.map((m: any) => (
              <Panel key={m.id} title={`${m.measure} · severidade ${m.severity}`}
                     actions={<Pill tone={TONE[m.status]}>{m.status}</Pill>}>
                <p className="muted small">
                  Alvo: {m.target_org_name || m.target_user_name} · regra {m.rule_ref} ·
                  {" "}aplicada por {m.decided_by_name} em {date(m.created_at)}
                  {m.ends_at && <> · até {date(m.ends_at)}</>}
                </p>
                <p>{m.reason}</p>
                {m.appeal_at && (
                  <Panel title="Contestação do alvo" quiet>
                    <p>{m.appeal_note}</p>
                    <p className="muted small">em {dateTime(m.appeal_at)}</p>
                    {m.appeal_decision && (
                      <p className="small">Decisão ({m.appeal_decided_by_name}): {m.appeal_decision}</p>
                    )}
                  </Panel>
                )}
                <Field label="Fundamentação" hint="Mínimo 10 caracteres, tanto para levantar quanto para julgar" wide>
                  <TextArea value={note[m.id] || ""} rows={2}
                            onChange={(v) => setNote({ ...note, [m.id]: v })} /></Field>
                <div className="row gap">
                  {m.status === "under_appeal" && <>
                    <Button variant="ghost" busy={act.busy}
                            onClick={() => run(m.id, "appeal-decision", { uphold: true, note: note[m.id] },
                                               "Contestação mantida")}>Manter a medida</Button>
                    <Button variant="ink" busy={act.busy}
                            onClick={() => run(m.id, "appeal-decision", { uphold: false, note: note[m.id] },
                                               "Contestação acolhida")}>Acolher a contestação</Button>
                  </>}
                  {["active", "upheld", "under_appeal"].includes(m.status) && (
                    <Button variant="ghost" busy={act.busy}
                            onClick={() => run(m.id, "lift", { note: note[m.id] }, "Medida levantada")}>
                      Levantar</Button>
                  )}
                </div>
                <p className="muted small">Quem aplicou a medida não julga a contestação dela.</p>
              </Panel>
            ))}
            <Pager data={data} offset={offset} setOffset={setOffset} />
          </>
        )}
      </StateView>
    </>
  );
}

function NewMeasure({ ladder, onDone }: any) {
  const f = useForm({ target_org_id: "", measure: "guidance", rule_ref: "", reason: "", ends_at: "",
                      evidence_note: "", override_reason: "" });
  const act = useAction();
  const hist = useLoad<any>(f.v.target_org_id ? `/v1/admin/enforcement/history?org_id=${f.v.target_org_id}` : null,
                            [f.v.target_org_id]);
  const chosen = (ladder?.items || []).find((l: any) => l.measure === f.v.measure);
  const allowed: string[] = hist.data?.next_allowed || [];
  const needsOverride = !!f.v.target_org_id && allowed.length > 0 && !allowed.includes(f.v.measure);
  const apply = async () => {
    const body: any = { measure: f.v.measure, target_org_id: f.v.target_org_id, rule_ref: f.v.rule_ref,
                        reason: f.v.reason };
    if (f.v.ends_at) body.ends_at = new Date(f.v.ends_at).toISOString();
    if (f.v.evidence_note) body.evidence_note = f.v.evidence_note;
    if (f.v.override_reason) body.override_reason = f.v.override_reason;
    if (await act.run(() => api.post("/v1/admin/enforcement", body), "Medida aplicada")) {
      f.setV({ ...f.v, reason: "", evidence_note: "", override_reason: "" });
      onDone();
    }
  };
  return (
    <Panel title="Aplicar medida">
      <Field label="Organização alvo" hint="Identificador da organização" wide>
        <Input value={f.v.target_org_id} onChange={f.set("target_org_id")} /></Field>
      {hist.data && (
        <Panel title="Histórico do alvo" quiet>
          {hist.data.items.length
            ? <ul className="list">{hist.data.items.map((h: any) => (
                <li key={h.id} className="list-row">
                  <span className="grow">{h.measure} (severidade {h.severity}) · {h.rule_ref}</span>
                  <Pill tone={TONE[h.status]}>{h.status}</Pill>
                </li>))}</ul>
            : <p className="muted">Nenhuma medida anterior.</p>}
          <p className="muted small">{hist.data.note}</p>
          <p className="small">Permitidas agora: {allowed.join(", ") || "—"}</p>
        </Panel>
      )}
      <Field label="Medida" wide>
        <Select value={f.v.measure} onChange={f.set("measure")}
                options={(ladder?.items || []).map((l: any) => [l.measure, `${l.label} (${l.severity})`])} /></Field>
      {chosen && <p className="muted small">{chosen.effect}</p>}
      <Field label="Regra aplicada" hint="Medida sem regra é arbítrio; o banco recusa" wide>
        <Input value={f.v.rule_ref} onChange={f.set("rule_ref")} placeholder="TERMOS-4.2" /></Field>
      <Field label="Motivo" hint="Mínimo 10 caracteres. O alvo vê este texto." wide>
        <TextArea value={f.v.reason} onChange={f.set("reason")} rows={3} /></Field>
      {chosen?.requires_end_date && (
        <Field label="Prazo de término" hint="Medida temporária sem prazo não existe nesta plataforma">
          <Input type="date" value={f.v.ends_at} onChange={f.set("ends_at")} /></Field>
      )}
      <Field label="Observação de evidência (opcional)" wide>
        <TextArea value={f.v.evidence_note} onChange={f.set("evidence_note")} rows={2} /></Field>
      {needsOverride && (
        <Field label="Justificativa para contornar a escada"
               hint="Mínimo 20 caracteres. Fica MARCADA na medida, para a auditoria conseguir listar os casos." wide>
          <TextArea value={f.v.override_reason} onChange={f.set("override_reason")} rows={3} /></Field>
      )}
      <Button variant="ink" busy={act.busy}
              disabled={!f.v.target_org_id || f.v.rule_ref.length < 3 || f.v.reason.length < 10
                        || (chosen?.requires_end_date && !f.v.ends_at)
                        || (needsOverride && f.v.override_reason.length < 20)}
              onClick={apply}>Aplicar</Button>
    </Panel>
  );
}


/** O que é imputado à minha organização — e o direito de ser ouvida.
 *
 * Esta tela não existia. Quem era denunciado não sabia, não era ouvido antes da conclusão e não
 * tinha como recorrer dela. A tela NUNCA mostra quem denunciou: a projeção servida pela API não
 * seleciona o denunciante, e a política de leitura do banco também não o alcança.
 */
export function MyReports() {
  const { data, error, loading, reload } = useLoad<any>("/v1/conta/denuncias");
  const { run } = useAction();
  const [aberta, setAberta] = useState<string | null>(null);
  const f = useForm({ texto: "" });
  const curto = f.v.texto.trim().length < 20;
  const enviar = (id: string, tipo: "manifestacao" | "recurso") =>
    run(() => api.post(`/v1/conta/denuncias/${id}/${tipo}`,
      tipo === "manifestacao" ? { body: f.v.texto } : { note: f.v.texto }),
      tipo === "manifestacao" ? "Manifestação registrada" : "Recurso registrado")
      .then(() => { f.set("texto")(""); setAberta(null); reload(); });

  return (
    <>
      <PageHead title="Denúncias sobre a minha organização"
        sub="Você vê o que lhe é imputado e pode se manifestar. Quem denunciou não é revelado." />
      <StateView loading={loading} error={error} onRetry={reload}
        empty={data?.items.length === 0 && "Nenhuma denúncia em situação que exija sua manifestação."}>
        <p className="muted">{data?.separation}</p>
        <div className="rows">
          {data?.items.map((r: any) => (
            <Panel key={r.id} title={`${r.category || r.reason} · ${r.status_label}`}>
              {r.finding_label && <p><strong>{r.finding_label}</strong></p>}
              {r.decision_rationale && <p>{r.decision_rationale}</p>}
              {r.legal_referral && <Pill tone="warn">encaminhado a autoridade competente</Pill>}
              <p className="small">Registrada em {date(r.created_at)} · {r.responses} manifestação(ões) sua(s)</p>
              {(r.can_respond || r.can_appeal) && (
                <>
                  <Button variant="link" onClick={() => setAberta(aberta === r.id ? null : r.id)}>
                    {r.can_respond ? "Manifestar-se" : "Recorrer da conclusão"}
                  </Button>
                  {aberta === r.id && (
                    <>
                      <Field label={r.can_respond ? "Sua manifestação" : "O que você contesta"} hint="Mínimo de 20 caracteres">
                        <TextArea rows={4} value={f.v.texto} onChange={f.set("texto")} />
                      </Field>
                      <Button variant="primary" disabled={curto}
                        onClick={() => enviar(r.id, r.can_respond ? "manifestacao" : "recurso")}>Enviar</Button>
                    </>
                  )}
                </>
              )}
            </Panel>
          ))}
        </div>
      </StateView>
    </>
  );
}
