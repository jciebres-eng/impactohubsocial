// Impacto: ODS, indicadores (reportado × validado), Impact Graph, diagnóstico social.
import { useState } from "react";
import { api } from "../api";
import { label, n, pct } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Button, Chips, Field, Input, KeyValue, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

const EDGE_TONE: Record<string, string> = { validated_causality: "good", observed_evidence: "good", correlation: "warn", association: "muted", inference: "muted", hypothesis: "muted" };
const EDGE_LABEL: Record<string, string> = { validated_causality: "Causalidade validada", observed_evidence: "Evidência observada", correlation: "Correlação", association: "Associação", inference: "Inferência", hypothesis: "Hipótese" };

export function ProjectImpact({ id }: { id: string }) {
  const { me } = useSession();
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/impact`);
  const proj = useLoad<any>(`/v1/projects/${id}`);
  const cat = useLoad<any>("/v1/indicators/catalog");
  const { busy, run } = useAction();
  const owner = proj.data?.is_owner;
  const funder = ["company", "government", "individual"].includes(me?.active_org?.kind || "");
  const f = useForm<any>({ indicator_id: "", baseline: "", target: "", method: "" });
  return (
    <>
      <PageHead title="Impacto e indicadores" sub={data?.title} back={<Link to={`/projetos/${id}`} className="back">Projeto</Link>}
        actions={<><Button variant="ghost" onClick={() => navigate(`/projetos/${id}/grafo`)}>Impact Graph</Button></>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <p className="muted">{data.wording}</p>
            <Panel title="Alinhamento aos ODS">
              {data.ods_alignment.length === 0 ? <p className="muted">Nenhum ODS vinculado ainda.</p> : (
                <ul className="rows">
                  {data.ods_alignment.map((a: any) => (
                    <li key={a.ods}><span>ODS {a.ods}</span>
                      <Pill tone={a.alignment_level === "supported_by_evidence" ? "good" : "muted"}>{a.alignment_level === "supported_by_evidence" ? "Com evidência de alinhamento" : "Declarado pela OSC"}</Pill></li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title="Indicadores do projeto">
              {data.indicators.length === 0 ? <p className="muted">Nenhum indicador. {owner ? "Escolha um do catálogo abaixo." : ""}</p> : (
                <table className="table">
                  <thead><tr><th>Indicador</th><th>Reportado</th><th>Validado</th><th>Meta</th><th></th></tr></thead>
                  <tbody>
                    {data.indicators.map((i: any) => <IndicatorRow key={i.id} i={i} id={id} owner={!!owner} funder={funder} reload={reload} />)}
                  </tbody>
                </table>
              )}
            </Panel>
            {owner && (
              <Panel title="Adicionar indicador">
                <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${id}/indicators`, {
                  indicator_id: f.v.indicator_id, baseline: f.v.baseline === "" ? null : Number(f.v.baseline), target: f.v.target === "" ? null : Number(f.v.target), method: f.v.method || null }), "Indicador adicionado").then(reload); }}>
                  <Field label="Indicador do catálogo"><Select value={f.v.indicator_id} onChange={f.set("indicator_id")} placeholder="Escolha…"
                    options={(cat.data?.items || []).map((c: any) => [c.id, `${c.name} (${c.unit})`])} /></Field>
                  <Field label="Linha de base"><Input type="number" value={f.v.baseline} onChange={f.set("baseline")} /></Field>
                  <Field label="Meta"><Input type="number" value={f.v.target} onChange={f.set("target")} /></Field>
                  <Field label="Como será medido" wide><Input value={f.v.method} onChange={f.set("method")} /></Field>
                  <Button type="submit" variant="primary" busy={busy} disabled={!f.v.indicator_id}>Adicionar</Button>
                </form>
              </Panel>
            )}
          </div>
        )}
      </StateView>
    </>
  );
}

function IndicatorRow({ i, id, owner, funder, reload }: { i: any; id: string; owner: boolean; funder: boolean; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const f = useForm<any>({ value: "", measured_on: new Date().toISOString().slice(0, 10) });
  const { busy, run } = useAction();
  return (
    <>
      <tr>
        <td><strong>{i.name}</strong><div className="muted">{i.unit}{i.esg_dimension ? ` · ESG ${i.esg_dimension}` : ""}</div></td>
        <td>{n(i.latest_reported)} <span className="muted">{pct(i.progress_reported_pct)}</span></td>
        <td>{i.latest_validated === null || i.latest_validated === undefined ? <span className="muted">ainda não validado</span> : <>{n(i.latest_validated)} <span className="muted">{pct(i.progress_validated_pct)}</span></>}</td>
        <td>{n(i.target)}</td>
        <td>{owner && <Button variant="ghost" onClick={() => setOpen(!open)}>Registrar valor</Button>}{funder && <ReviewLatest i={i} reload={reload} />}</td>
      </tr>
      {open && (
        <tr><td colSpan={5}>
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/project-indicators/${i.id}/values`, { value: Number(f.v.value), measured_on: f.v.measured_on }), "Valor registrado como reportado").then(() => { setOpen(false); reload(); }); }}>
            <Field label="Valor"><Input type="number" step="any" value={f.v.value} onChange={f.set("value")} /></Field>
            <Field label="Data da medição"><Input type="date" value={f.v.measured_on} onChange={f.set("measured_on")} /></Field>
            <Button type="submit" variant="primary" busy={busy} disabled={f.v.value === ""}>Salvar</Button>
          </form>
          <p className="muted">O valor fica como “reportado” até outra organização validá-lo com evidência anexada.</p>
        </td></tr>
      )}
    </>
  );
}

function ReviewLatest({ i, reload }: { i: any; reload: () => void }) {
  const { busy, run } = useAction();
  const v = (i.values || []).find((x: any) => x.status !== "validated" && x.status !== "rejected");
  if (!v) return null;
  return <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/indicator-values/${v.id}/review`, { status: "validated", note: "Conferido com a evidência anexada" }), "Valor validado").then(reload)}>Validar último valor</Button>;
}

export function ImpactGraph({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/graph`);
  const proj = useLoad<any>(`/v1/projects/${id}`);
  const nf = useForm<any>({ kind: "activity", label: "" });
  const ef = useForm<any>({ from_node: "", to_node: "", link_type: "hypothesis" });
  const { busy, run } = useAction();
  const owner = proj.data?.is_owner;
  const nodes: any[] = data?.nodes || [];
  const byId: Record<string, any> = Object.fromEntries(nodes.map((x) => [x.id, x]));
  const kinds: [string, string][] = [["need", "Necessidade"], ["activity", "Atividade"], ["output", "Produto"], ["outcome", "Resultado"], ["impact", "Impacto"]];
  return (
    <>
      <PageHead title="Impact Graph" sub={proj.data?.title} back={<Link to={`/projetos/${id}/impacto`} className="back">Impacto e indicadores</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <p className="muted">{data.note}</p>
            <Panel title="Elementos">
              {nodes.length === 0 ? <p className="muted">Sem elementos. Descreva a cadeia: necessidade → atividade → produto → resultado → impacto.</p> :
                <ul className="rows">{nodes.map((x) => <li key={x.id}><span><Pill tone="muted">{label(x.kind) === x.kind ? (kinds.find((k) => k[0] === x.kind)?.[1] || x.kind) : label(x.kind)}</Pill> {x.label}</span>
                  {owner && <Button variant="link" onClick={() => run(() => api.del(`/v1/projects/${id}/graph/nodes/${x.id}`), "Elemento removido").then(reload)}>Remover</Button>}</li>)}</ul>}
            </Panel>
            <Panel title="Relações e força da afirmação">
              {data.edges.length === 0 ? <p className="muted">Sem relações.</p> : (
                <ul className="rows">{data.edges.map((e: any) => (
                  <li key={e.id}><span>{byId[e.from_node]?.label || "?"} → {byId[e.to_node]?.label || "?"}</span>
                    <Pill tone={EDGE_TONE[e.link_type]}>{EDGE_LABEL[e.link_type] || e.link_type}</Pill></li>
                ))}</ul>
              )}
              <details><summary>Como ler os tipos de relação</summary>
                <ul>{Object.entries(data.legend).map(([k, v]) => <li key={k}><strong>{EDGE_LABEL[k]}:</strong> {String(v)}</li>)}</ul></details>
            </Panel>
            {owner && (
              <>
                <Panel title="Novo elemento">
                  <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${id}/graph/nodes`, nf.v), "Elemento criado").then(() => { nf.set("label")(""); reload(); }); }}>
                    <Field label="Tipo"><Select value={nf.v.kind} onChange={nf.set("kind")} options={kinds} /></Field>
                    <Field label="Descrição" wide><Input value={nf.v.label} onChange={nf.set("label")} /></Field>
                    <Button type="submit" variant="primary" busy={busy} disabled={nf.v.label.length < 2}>Adicionar</Button>
                  </form>
                </Panel>
                <Panel title="Nova relação">
                  <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${id}/graph/edges`, ef.v), "Relação criada").then(reload); }}>
                    <Field label="De"><Select value={ef.v.from_node} onChange={ef.set("from_node")} placeholder="—" options={nodes.map((x) => [x.id, x.label])} /></Field>
                    <Field label="Para"><Select value={ef.v.to_node} onChange={ef.set("to_node")} placeholder="—" options={nodes.map((x) => [x.id, x.label])} /></Field>
                    <Field label="Tipo" hint="“Causalidade validada” só pode ser atribuída por revisão externa com evidência."><Select value={ef.v.link_type} onChange={ef.set("link_type")}
                      options={[["hypothesis", "Hipótese"], ["association", "Associação"], ["correlation", "Correlação"], ["inference", "Inferência"]]} /></Field>
                    <Button type="submit" variant="primary" busy={busy} disabled={!ef.v.from_node || !ef.v.to_node}>Relacionar</Button>
                  </form>
                </Panel>
              </>
            )}
          </div>
        )}
      </StateView>
    </>
  );
}

export function Diagnoses() {
  const { data, error, loading, reload } = useLoad<any>("/v1/diagnoses");
  const f = useForm<any>({ title: "", need_statement: "" });
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Diagnóstico social" sub="Do problema às metas e ao plano de ação, antes de montar o projeto." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && data.items.length === 0 && false}>
        <div className="stack-lg">
          <Panel title="Seus diagnósticos">
            {(data?.items || []).length === 0 ? <p className="muted">Nenhum diagnóstico ainda.</p> : (
              <ul className="rows">{data.items.map((d: any) => <li key={d.id}><Link to={`/diagnosticos/${d.id}`}>{d.title}</Link><Pill status={d.status} /></li>)}</ul>
            )}
          </Panel>
          <Panel title="Novo diagnóstico">
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/diagnoses", f.v), "Diagnóstico criado").then((r: any) => r && navigate(`/diagnosticos/${r.id}`)); }}>
              <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
              <Field label="Qual é a necessidade?" wide><TextArea value={f.v.need_statement} onChange={f.set("need_statement")} rows={3} /></Field>
              <Button type="submit" variant="primary" busy={busy} disabled={f.v.title.length < 3}>Criar</Button>
            </form>
          </Panel>
        </div>
      </StateView>
    </>
  );
}

export function DiagnosisEditor({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/diagnoses/${id}`);
  const projects = useLoad<any>("/v1/projects");
  const f = useForm<any>({});
  const [loaded, setLoaded] = useState(false);
  const { busy, run } = useAction();
  if (data && !loaded) { f.setV({ ...data, causesText: (data.root_causes || []).map((c: any) => c.text).join("\n"), goalsText: (data.goals || []).map((g: any) => g.text).join("\n"),
    actionsText: (data.action_plan || []).map((a: any) => a.action).join("\n") }); setLoaded(true); }
  const lines = (s: string) => (s || "").split("\n").map((x) => x.trim()).filter(Boolean);
  const body = () => ({
    title: f.v.title, project_id: f.v.project_id || null, need_statement: f.v.need_statement, objective: f.v.objective || null,
    root_causes: lines(f.v.causesText).map((text) => ({ text, source: "informado pela organização", evidence_level: "declarado" })),
    goals: lines(f.v.goalsText).map((text) => ({ text })), action_plan: lines(f.v.actionsText).map((action) => ({ action })),
  });
  return (
    <>
      <PageHead title="Diagnóstico" sub={data?.title} back={<Link to="/diagnosticos" className="back">Diagnósticos</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.put(`/v1/diagnoses/${id}`, body()), "Diagnóstico salvo").then(reload); }}>
            <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
            <Field label="Projeto vinculado"><Select value={f.v.project_id} onChange={f.set("project_id")} placeholder="Nenhum" options={(projects.data?.items || []).map((p: any) => [p.id, p.title])} /></Field>
            <Field label="Necessidade" wide><TextArea value={f.v.need_statement} onChange={f.set("need_statement")} rows={3} /></Field>
            <Field label="Causas (uma por linha)" hint="Indique o que é observado e o que é suposição." wide><TextArea value={f.v.causesText} onChange={f.set("causesText")} rows={4} /></Field>
            <Field label="Objetivo" wide><TextArea value={f.v.objective} onChange={f.set("objective")} rows={2} /></Field>
            <Field label="Metas (uma por linha)" wide><TextArea value={f.v.goalsText} onChange={f.set("goalsText")} rows={3} /></Field>
            <Field label="Plano de ação (uma ação por linha)" wide><TextArea value={f.v.actionsText} onChange={f.set("actionsText")} rows={3} /></Field>
            {data.missing?.length > 0 && <p className="muted">Falta preencher: {data.missing.join(", ")}.</p>}
            <div className="stack-row">
              <Button type="submit" variant="primary" busy={busy}>Salvar</Button>
              <Button variant="ink" busy={busy} disabled={!data.project_id} onClick={() => run(() => api.post(`/v1/diagnoses/${id}/apply`), "Aplicado ao projeto").then(reload)}>Aplicar ao projeto</Button>
            </div>
          </form>
        )}
      </StateView>
    </>
  );
}

export function Determinants() {
  const { data, error, loading, reload } = useLoad<any>("/v1/determinants");
  return (
    <>
      <PageHead title="Determinantes sociais" sub="Distribuição dos projetos publicados por domínio" />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <p className="muted">{data.note}</p>
            <table className="table"><thead><tr><th>Domínio</th><th>Projetos</th></tr></thead>
              <tbody>{data.domains.map((d: any) => <tr key={d.domain}><td>{d.label || d.domain}</td><td>{d.suppressed ? <span className="muted">oculto (poucos projetos)</span> : n(d.projects)}</td></tr>)}</tbody></table>
          </div>
        )}
      </StateView>
    </>
  );
}

export { KeyValue, Chips };
