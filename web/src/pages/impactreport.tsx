import { useState } from "react";
import { api } from "../api";
import { date, dateTime } from "../format";
import { Link, navigate } from "../router";
import { Button, Field, Input, Modal, PageHead, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// RELATÓRIO DE IMPACTO — o elo que devolve resultado a quem apoiou.
//
// Três coisas que esta tela torna visíveis de propósito:
//   1. os NÚMEROS são apurados pelo servidor, e a prévia mostra exatamente o que será colhido antes do envio;
//   2. quem revisa não é quem escreveu (o banco recusa), e a tela diz isso;
//   3. "limitações" é um campo do relatório — dizer o que o dado NÃO prova faz parte de relatar com honestidade.

const ST_LABEL: Record<string, string> = { draft: "rascunho", submitted: "enviado", under_review: "em análise",
  changes_requested: "ajuste solicitado", accepted: "aceito", published: "publicado" };
const ACTION_LABEL: Record<string, string> = { submitted: "Enviar para análise", under_review: "Pôr em análise",
  changes_requested: "Pedir ajuste", accepted: "Aceitar", published: "Publicar", draft: "Retirar para ajuste" };

export function ProjectImpactReports({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/impact-updates?project_id=${id}&limit=30`, [id]);
  const [open, setOpen] = useState(false);
  return (
    <>
      <PageHead title="Relatórios de impacto" back={`/projetos/${id}`}
                sub="Um relatório por período. Os números vêm das medições e marcos — não do formulário."
                actions={<Button variant="ink" onClick={() => setOpen(true)}>Novo período</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <ul className="list">
            {data.items.map((u: any) => (
              <li key={u.id} className="list-row">
                <div className="grow">
                  <Link to={`/relatorios-impacto/${u.id}`}>
                    <strong>{date(u.period_start)} a {date(u.period_end)}</strong></Link>
                  <p className="muted small">
                    {u.evidence_count} evidência(s)
                    {u.reviewed_by_org_name && <> · analisado por {u.reviewed_by_org_name}</>}
                    {u.submitted_at && <> · enviado {date(u.submitted_at)}</>}
                  </p>
                </div>
                <Pill status={u.status}>{u.status_label || ST_LABEL[u.status]}</Pill>
              </li>
            ))}
          </ul>
        )}
      </StateView>
      <NewReportModal projectId={id} open={open} onClose={() => setOpen(false)} onDone={reload} />
    </>
  );
}

function NewReportModal({ projectId, open, onClose, onDone }: any) {
  const f = useForm({ period_start: "", period_end: "", summary: "", outputs: "", outcomes: "",
                      limitations: "", risks_note: "" });
  const act = useAction();
  const preview = useLoad<any>(
    f.v.period_start && f.v.period_end
      ? `/v1/impact-updates/gather?project_id=${projectId}&period_start=${f.v.period_start}&period_end=${f.v.period_end}`
      : null, [f.v.period_start, f.v.period_end]);
  const create = async () => {
    const r = await act.run(() => api.post("/v1/impact-updates", { project_id: projectId, ...f.v }),
                            "Relatório criado em rascunho");
    if (r) { onClose(); onDone(); navigate(`/relatorios-impacto/${(r as any).id}`); }
  };
  return (
    <Modal open={open} title="Novo relatório de impacto" onClose={onClose}
           footer={<Button variant="ink" busy={act.busy} disabled={!f.v.period_start || !f.v.period_end || f.v.summary.length < 20}
                           onClick={create}>Criar rascunho</Button>}>
      <div className="row gap">
        <Field label="Início do período"><Input type="date" value={f.v.period_start} onChange={f.set("period_start")} /></Field>
        <Field label="Fim do período"><Input type="date" value={f.v.period_end} onChange={f.set("period_end")} /></Field>
      </div>
      {preview.data && (
        <Panel title="O que o servidor vai apurar neste período" quiet>
          <ul className="small">
            <li>{preview.data.indicators?.length || 0} indicador(es) no projeto</li>
            <li>{preview.data.measurements} medição(ões), {preview.data.validated_measurements} validada(s)</li>
            <li>{preview.data.completed_milestones} marco(s) concluído(s)</li>
            <li>{preview.data.evidence_count} evidência(s) no período</li>
          </ul>
          {/* A ressalva vem com os números, do backend: medição não validada não comprova resultado. */}
          <p className="muted small">{preview.data.caveat}</p>
        </Panel>
      )}
      <Field label="Resumo do período" hint="Mínimo 20 caracteres" wide>
        <TextArea value={f.v.summary} onChange={f.set("summary")} rows={4} /></Field>
      <Field label="O que foi entregue (produtos)" wide><TextArea value={f.v.outputs} onChange={f.set("outputs")} rows={3} /></Field>
      <Field label="O que mudou (resultados)" wide><TextArea value={f.v.outcomes} onChange={f.set("outcomes")} rows={3} /></Field>
      <Field label="Limitações" hint="O que estes dados NÃO provam. Dizer isso faz parte do relatório." wide>
        <TextArea value={f.v.limitations} onChange={f.set("limitations")} rows={3} /></Field>
      <Field label="Riscos observados" wide><TextArea value={f.v.risks_note} onChange={f.set("risks_note")} rows={2} /></Field>
    </Modal>
  );
}

export function ImpactReportDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/impact-updates/${id}`, [id]);
  const act = useAction();
  const [note, setNote] = useState("");
  const [ask, setAsk] = useState<string | null>(null);
  const move = async (to: string, requiresNote: boolean) => {
    if (requiresNote && note.trim().length < 3) { setAsk(to); return; }
    if (await act.run(() => api.post(`/v1/impact-updates/${id}/transition`, { to, note: note || undefined }),
                      "Relatório atualizado")) { setNote(""); setAsk(null); reload(); }
  };
  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  const u = data;
  const m = u.metrics || {};
  return (
    <>
      <PageHead title={`${date(u.period_start)} a ${date(u.period_end)}`} sub={u.project_title}
                back={`/projetos/${u.project_id}/relatorios`}
                actions={<Pill status={u.status}>{u.status_label || ST_LABEL[u.status]}</Pill>} />
      <Panel title="O que a organização relatou">
        <p>{u.summary}</p>
        {u.outputs && <><h3>Produtos</h3><p>{u.outputs}</p></>}
        {u.outcomes && <><h3>Resultados</h3><p>{u.outcomes}</p></>}
        {u.limitations && <><h3>Limitações</h3><p>{u.limitations}</p></>}
        {u.risks_note && <><h3>Riscos observados</h3><p>{u.risks_note}</p></>}
      </Panel>

      <Panel title="O que o servidor apurou">
        {u.status === "draft"
          ? <p className="muted">A apuração acontece no envio. Até então, nada aqui está congelado.</p>
          : <>
              <ul className="small">
                <li>{m.measurements ?? 0} medição(ões), {m.validated_measurements ?? 0} validada(s)</li>
                <li>{m.completed_milestones ?? 0} marco(s) concluído(s)</li>
                <li>{u.evidence_count} evidência(s) no período</li>
              </ul>
              {m.caveat && <p className="muted small">{m.caveat}</p>}
              {!!m.indicators?.length && (
                <table className="table small">
                  <thead><tr><th>Indicador</th><th>Linha de base</th><th>Meta</th><th>No período</th><th>Validadas</th></tr></thead>
                  <tbody>
                    {m.indicators.map((i: any) => (
                      <tr key={i.code}>
                        <td>{i.name} <span className="muted">({i.unit})</span></td>
                        <td>{i.baseline ?? "—"}</td><td>{i.target ?? "—"}</td>
                        <td>{i.value_in_period ?? "—"}</td><td>{i.validated ?? 0}/{i.measurements ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>}
      </Panel>

      {u.review_note && (
        <Panel title="Devolutiva de quem analisou" quiet>
          <p>{u.review_note}</p>
          <p className="muted small">
            {u.reviewed_by_name && <>por {u.reviewed_by_name}</>}
            {u.reviewed_by_org_name && <> ({u.reviewed_by_org_name})</>}
            {u.reviewed_at && <> · {dateTime(u.reviewed_at)}</>}
          </p>
        </Panel>
      )}

      {!!u.actions?.length && (
        <Panel title={u.side === "owner" ? "O que você pode fazer" : "Sua análise"}>
          <div className="row gap wrap">
            {u.actions.map((a: any) => (
              <Button key={a.to_status} variant={a.to_status === "accepted" ? "ink" : "ghost"} busy={act.busy}
                      onClick={() => move(a.to_status, a.requires_note)}>
                {ACTION_LABEL[a.to_status] || a.to_status}
              </Button>
            ))}
          </div>
          {u.side === "owner" && (
            <p className="muted small">Quem executa não analisa o próprio relatório: a análise é de quem apoia o projeto.</p>
          )}
        </Panel>
      )}

      <Modal open={!!ask} title="Justificativa" onClose={() => setAsk(null)}
             footer={<Button variant="ink" busy={act.busy} onClick={() => ask && move(ask, false)}>Confirmar</Button>}>
        <Field label="O que precisa ser ajustado" hint="Mínimo 3 caracteres. Quem executa vê este texto.">
          <TextArea value={note} onChange={setNote} rows={4} /></Field>
      </Modal>
    </>
  );
}

export function ImpactReportInbox() {
  const { data, error, loading, reload } = useLoad<any>("/v1/impact-updates/inbox");
  return (
    <>
      <PageHead title="Relatórios para analisar"
                sub="Dos projetos que a sua organização apoia, enviados e ainda sem decisão." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <ul className="list">
            {data.items.map((u: any) => (
              <li key={u.id} className="list-row">
                <div className="grow">
                  <Link to={`/relatorios-impacto/${u.id}`}><strong>{u.project_title}</strong></Link>
                  <p className="muted small">{u.org_name} · {date(u.period_start)} a {date(u.period_end)} ·
                    {" "}{u.evidence_count} evidência(s)</p>
                </div>
                <Pill status={u.status}>{ST_LABEL[u.status]}</Pill>
              </li>
            ))}
          </ul>
        )}
      </StateView>
    </>
  );
}

// ============================================================================ prontidão por finalidade
export function ReadinessPurposes() {
  const projects = useLoad<any>("/v1/projects?limit=50");
  const [pid, setPid] = useState("");
  const { data, error, loading, reload } = useLoad<any>(
    `/v1/readiness/purposes${pid ? `?project_id=${pid}` : ""}`, [pid]);
  const act = useAction();
  return (
    <>
      <PageHead title="Prontidão por finalidade"
                sub="Pronto para quê? Seis respostas diferentes sobre o mesmo projeto, cada número com os critérios que o compuseram."
                actions={<Button variant="ghost" busy={act.busy}
                  onClick={() => act.run(() => api.post(`/v1/readiness/snapshots${pid ? `?project_id=${pid}` : ""}`, {}),
                                         "Retrato guardado")}>Guardar retrato</Button>} />
      <Panel quiet>
        <Field label="Projeto" hint="Sem projeto, só as prontidões institucionais fazem sentido">
          <Select value={pid} onChange={setPid} placeholder="Somente a organização"
                  options={(projects.data?.items || []).map((p: any) => [p.id, p.title])} /></Field>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title={`Geral: ${data.overall}% (${data.band})`} quiet>
              <p className="muted small">{data.note}</p>
            </Panel>
            {Object.entries(data.dimensions).map(([k, d]: any) => (
              <Panel key={k} title={`${d.label} — ${d.score}% (${d.band})`}>
                <p className="muted small">{d.question}</p>
                <table className="table small">
                  <thead><tr><th>Critério</th><th>O que foi encontrado</th><th>Peso</th><th>Pontos</th></tr></thead>
                  <tbody>
                    {d.checks.map((c: any) => (
                      <tr key={c.key}>
                        <td>{c.label}</td><td>{c.found}</td><td>{c.of}</td><td>{c.points}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!!d.blockers?.length && (
                  <><h3>O que falta</h3><ul className="small">{d.blockers.map((b: string, i: number) => <li key={i}>{b}</li>)}</ul></>
                )}
                {d.note && <p className="muted small">{d.note}</p>}
              </Panel>
            ))}
          </>
        )}
      </StateView>
    </>
  );
}
