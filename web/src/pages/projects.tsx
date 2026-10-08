import { useState } from "react";
import { api } from "../api";
import { centsToInput, date, label, money, n, parseMoney, MATCH_STATE } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { MatchFeedbackBox } from "./core";
import { Bars, Button, Chips, Field, Input, KeyValue, Modal, MoneyFlow, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad, useTaxonomy } from "../ui/kit";
import { ImpactTags } from "./taxonomy";
import { ContextHelp } from "./help";
import { MatchVerdict } from "../ui/trail";
import { UploadButton } from "./documents";

export function Projects() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects?offset=${offset}`, [offset]);
  return (
    <>
      <PageHead title="Projetos" sub="Necessidades estruturadas, com orçamento, etapas e prestação de contas."
        actions={<Button variant="primary" onClick={() => navigate("/projetos/novo")}>Novo projeto</Button>} />
      <StateView loading={loading} error={error} onRetry={reload}
        empty={data?.items.length === 0 && <><p>Descreva uma necessidade e a plataforma ajuda a transformá-la em projeto financiável.</p>
          <Button variant="primary" onClick={() => navigate("/projetos/novo")}>Criar o primeiro projeto</Button></>}>
        <ul className="projects">
          {data?.items.map((p: any) => {
            const pctFunded = p.budget_total_cents ? Math.min(100, (p.funding.committed_cents / p.budget_total_cents) * 100) : 0;
            return (
              <li key={p.id} className="project">
                <div>
                  <h3><Link to={`/projetos/${p.id}`}>{p.title}</Link></h3>
                  <p className="muted">{p.territory} · {n(p.beneficiaries_count)} beneficiários · {p.applications} candidatura(s)</p>
                </div>
                <Pill status={p.status} />
                <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pctFunded)} aria-label={`${Math.round(pctFunded)}% captado`}>
                  <span className="progress-fill" style={{ width: `${pctFunded}%` }} />
                </div>
                <p className="project-money">{money(p.funding.committed_cents)} de {money(p.budget_total_cents)}</p>
              </li>
            );
          })}
        </ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}

export function NewProject() {
  const tax = useTaxonomy();
  const [text, setText] = useState("");
  const [ai, setAi] = useState<any>(null);
  const f = useForm<any>({ title: "", summary: "", problem: "", objectives: "", causes: [], ods: [], territory: "", beneficiaries_count: "", budget: "", urgency: "medium" });
  const { busy, run } = useAction();
  const ai$ = useAction();
  async function assist() {
    const r = await ai$.run(() => api.post("/v1/ai/structure-need", { text }));
    if (!r) return;
    setAi(r);
    f.setV({ ...f.v, title: r.title, summary: r.summary, problem: r.problem || f.v.problem, objectives: r.objectives || f.v.objectives,
      causes: r.causes, ods: r.ods.map(String), beneficiaries_count: r.beneficiaries_count ?? "", budget: centsToInput(r.budget_total_cents) });
  }
  async function save(e: any) {
    e.preventDefault();
    const r = await run(() => api.post("/v1/projects", {
      title: f.v.title, summary: f.v.summary || null, problem: f.v.problem || null, objectives: f.v.objectives || null, causes: f.v.causes,
      ods: f.v.ods.map(Number), territory: f.v.territory, beneficiaries_count: f.v.beneficiaries_count === "" ? null : Number(f.v.beneficiaries_count),
      budget_total_cents: ai?.budget_items?.length ? null : parseMoney(f.v.budget), urgency: f.v.urgency, ai_assisted: !!ai,
    }), "Projeto criado");
    if (!r) return;
    if (ai?.budget_items?.length) {
      for (const it of ai.budget_items) await api.post(`/v1/projects/${r.id}/budget-items`, { description: it.description, quantity: it.quantity, unit_cost_cents: it.unit_cost_cents, category: it.category });
    }
    navigate(`/projetos/${r.id}`);
  }
  return (
    <>
      <PageHead title="Novo projeto" back={<Link to="/projetos" className="back">Projetos</Link>} />
      <ContextHelp ctxKey="project.new" />
      <div className="split">
        <Panel title="Descreva a necessidade com suas palavras">
          <TextArea rows={7} value={text} onChange={setText}
            placeholder="Ex.: Precisamos de 10 violões de R$ 500 cada para aulas de música para 40 crianças do bairro, durante 12 meses." />
          <Button variant="ink" busy={ai$.busy} disabled={text.length < 10} onClick={assist}>Estruturar com assistência</Button>
          {ai && (
            <div className="assist">
              <p className="fineprint">Rascunho gerado por {ai.engine}. Revise tudo antes de salvar — nada é enviado ou publicado sem sua confirmação.</p>
              {ai.budget_items.length > 0 && (
                <><h3>Itens de orçamento encontrados</h3>
                  <ul>{ai.budget_items.map((i: any, k: number) => <li key={k}>{i.quantity} × {i.description} — {money(i.unit_cost_cents)} ({money(i.total_cents)})</li>)}</ul></>
              )}
              <h3>Para completar o projeto</h3>
              <ul>{ai.questions.map((q: string) => <li key={q}>{q}</li>)}</ul>
            </div>
          )}
        </Panel>
        <form className="form" onSubmit={save}>
          <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} required /></Field>
          <Field label="Resumo"><TextArea rows={3} value={f.v.summary} onChange={f.set("summary")} /></Field>
          <Field label="Problema que o projeto enfrenta"><TextArea rows={3} value={f.v.problem} onChange={f.set("problem")} /></Field>
          <Field label="Objetivos"><TextArea rows={3} value={f.v.objectives} onChange={f.set("objectives")} /></Field>
          <Field label="Território de execução" hint="BR-UF-código IBGE do município, ex.: BR-MT-5105259">
            <Input value={f.v.territory} onChange={(v) => f.set("territory")(v.toUpperCase())} required />
          </Field>
          <div className="row2">
            <Field label="Beneficiários diretos"><Input inputMode="numeric" value={f.v.beneficiaries_count} onChange={f.set("beneficiaries_count")} /></Field>
            <Field label="Urgência"><Select value={f.v.urgency} onChange={f.set("urgency")} options={[["low", "Baixa"], ["medium", "Média"], ["high", "Alta"]]} /></Field>
          </div>
          {!ai?.budget_items?.length && <Field label="Orçamento total (R$)" hint="Você poderá detalhar itens depois"><Input inputMode="decimal" value={f.v.budget} onChange={f.set("budget")} /></Field>}
          <Field label="Causas"><Chips options={Object.entries(tax?.causes || {}) as any} value={f.v.causes} onChange={f.set("causes")} max={10} /></Field>
          <Field label="ODS"><Chips options={Object.entries(tax?.ods || {}).map(([k]) => [k, `ODS ${k}`]) as any} value={f.v.ods} onChange={f.set("ods")} /></Field>
          <Button type="submit" variant="primary" busy={busy}>Salvar projeto</Button>
        </form>
      </div>
    </>
  );
}

const TABS = [["overview", "Visão geral"], ["budget", "Orçamento e etapas"], ["execution", "Execução"], ["reports", "Relatórios"], ["ledger", "Histórico verificável"]] as const;

export function ProjectDetail({ id }: { id: string }) {
  const { data: p, error, loading, reload } = useLoad<any>(`/v1/projects/${id}`);
  const [tab, setTab] = useState<string>("overview");
  const { busy, run } = useAction();
  const { me } = useSession();
  const isCompany = ["company", "individual"].includes(me?.active_org?.kind || "");
  return (
    <StateView loading={loading && !p} error={error} onRetry={reload}>
      {p && (
        <>
          <PageHead title={p.title} back={<Link to={p.is_owner ? "/projetos" : "/explorar"} className="back">{p.is_owner ? "Projetos" : "Projetos para apoiar"}</Link>}
            sub={<>{p.org_name} · {p.territory} · <Pill status={p.status} /></>}
            actions={p.is_owner ? (
              p.visibility === "published"
                ? <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/projects/${id}/unpublish`), "Projeto retirado do feed").then(reload)}>Retirar do feed</Button>
                : <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/projects/${id}/publish`), "Projeto publicado").then(reload)}>Publicar para financiadores</Button>
            ) : isCompany && (
              <>
                <Button variant="ghost" onClick={() => run(() => p.favorite ? api.del(`/v1/feed/projects/${id}/favorite`) : api.post(`/v1/feed/projects/${id}/favorite`)).then(reload)}>
                  {p.favorite ? "Remover dos salvos" : "Salvar"}</Button>
                {p.my_application ? <Button variant="ink" onClick={() => navigate(`/candidaturas/${p.my_application.id}`)}>Abrir diligência</Button>
                  : <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/applications/interest", { project_id: id }), "Interesse enviado à OSC").then((r: any) => r && navigate(`/candidaturas/${r.id}`))}>Manifestar interesse</Button>}
              </>
            )} />
          <div className="tabs" role="tablist">
            {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "tab on" : "tab"} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          {tab === "overview" && <><Overview p={p} /><ImpactTags subjectType="project" subjectId={id} /></>}
          {tab === "budget" && <Budget p={p} reload={reload} />}
          {tab === "execution" && <Execution p={p} />}
          {tab === "reports" && <Report id={id} />}
          {tab === "ledger" && <Ledger id={id} />}
        </>
      )}
    </StateView>
  );
}

function Overview({ p }: { p: any }) {
  const tax = useTaxonomy();
  const f = p.funding;
  return (
    <div className="detail">
      <div className="detail-main">
        <Panel title="Aprofundar">
          <ul className="rows">
            <li><Link to={`/projetos/${p.id}/impacto`}>Impacto, ODS e indicadores</Link></li>
            <li><Link to={`/projetos/${p.id}/grafo`}>Impact Graph</Link></li>
            {p.is_owner && <><li><Link to={`/projetos/${p.id}/situacao`}>Situação e transições</Link></li>
            <li><Link to={`/projetos/${p.id}/linha-do-tempo`}>Linha de tempo</Link></li>
            <li><Link to={`/projetos/${p.id}/retratos`}>Retratos comparáveis</Link></li>
            <li><Link to={`/projetos/${p.id}/riscos`}>Riscos</Link></li>
            <li><Link to={`/projetos/${p.id}/compras`}>Compras e cotações</Link></li>
            <li><Link to={`/projetos/${p.id}/contribuicao`}>Modelos de contribuição</Link></li>
            <li><Link to={`/projetos/${p.id}/apoio-profissional`}>Apoio profissional</Link></li>
            <li><Link to={`/projetos/${p.id}/localizacao`}>Localização pública</Link></li></>}
          </ul>
        </Panel>
        {p.match && <MatchVerdict m={p.match} />}
        {p.match?.match_run_id && <MatchFeedbackBox matchRunId={p.match.match_run_id} />}
        <Panel title="O projeto">
          {p.summary && <p className="lead">{p.summary}</p>}
          {p.problem && <><h3>Problema</h3><p className="pre">{p.problem}</p></>}
          {p.objectives && <><h3>Objetivos</h3><p className="pre">{p.objectives}</p></>}
          {p.indicators?.length > 0 && <><h3>Indicadores</h3><ul>{p.indicators.map((i: any) => <li key={i.name}>{i.name}: meta {i.target} {i.unit}</li>)}</ul></>}
        </Panel>
      </div>
      <aside className="detail-side">
        <Panel title="Recursos" quiet>
          <MoneyFlow stages={[["Orçamento", p.budget_total_cents], ["Comprometido", f.committed_cents], ["Desembolsado", f.disbursed_cents], ["Gasto comprovado", f.spent_cents]]} />
          <p className="muted">{f.funders} financiador(es) · {f.accepted_evidences} evidência(s) aceita(s)</p>
        </Panel>
        <Panel title="Ficha" quiet>
          <KeyValue items={[["Beneficiários", n(p.beneficiaries_count)], ["Causas", p.causes.map((c: string) => tax?.causes?.[c] || c).join(", ") || "—"],
            ["ODS", p.ods.join(", ") || "—"], ["Período", `${date(p.starts_on)} a ${date(p.ends_on)}`], ["Compliance da OSC", <Pill key="c" status={p.org_compliance} />],
            ["Elaboração", p.ai_assisted ? "Com assistência de IA, revisado pela OSC" : "Pela OSC"]]} />
        </Panel>
      </aside>
    </div>
  );
}

function Budget({ p, reload }: { p: any; reload: () => void }) {
  const item = useForm({ description: "", quantity: "1", unit: "", category: "material" });
  const ms = useForm({ title: "", amount: "", due_on: "" });
  const { busy, run } = useAction();
  const editable = p.is_owner && ["draft", "published"].includes(p.status);
  const msSum = p.milestones.reduce((a: number, m: any) => a + m.amount_cents, 0);
  return (
    <div className="split">
      <Panel title="Itens de orçamento" actions={<span className="muted">Total {money(p.budget_total_cents)}</span>}>
        <table className="table">
          <thead><tr><th>Item</th><th>Qtd.</th><th>Unitário</th><th>Total</th>{editable && <th />}</tr></thead>
          <tbody>
            {p.budget_items.map((i: any) => (
              <tr key={i.id}><td>{i.description}</td><td>{i.quantity}</td><td>{money(i.unit_cost_cents)}</td><td>{money(i.total_cents)}</td>
                {editable && <td><Button variant="link" onClick={() => run(() => api.del(`/v1/projects/${p.id}/budget-items/${i.id}`)).then(reload)}>Remover</Button></td>}</tr>
            ))}
            {p.budget_items.length === 0 && <tr><td colSpan={5} className="muted">Sem itens detalhados.</td></tr>}
          </tbody>
        </table>
        {editable && (
          <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${p.id}/budget-items`, { description: item.v.description, quantity: Number(item.v.quantity.replace(",", ".")), unit_cost_cents: parseMoney(item.v.unit), category: item.v.category }), "Item adicionado").then((r) => { if (r) { item.setV({ description: "", quantity: "1", unit: "", category: "material" }); reload(); } }); }}>
            <Field label="Descrição"><Input value={item.v.description} onChange={item.set("description")} /></Field>
            <Field label="Qtd."><Input inputMode="decimal" value={item.v.quantity} onChange={item.set("quantity")} /></Field>
            <Field label="Valor unitário (R$)"><Input inputMode="decimal" value={item.v.unit} onChange={item.set("unit")} /></Field>
            <Field label="Categoria"><Select value={item.v.category} onChange={item.set("category")} options={[["material", "Material"], ["service", "Serviço"], ["personnel", "Pessoal"], ["equipment", "Equipamento"], ["infrastructure", "Infraestrutura"], ["travel", "Deslocamento"], ["administrative", "Administrativo"], ["other", "Outro"]]} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Adicionar</Button>
          </form>
        )}
      </Panel>
      <Panel title="Etapas financiáveis (fracionamento)" actions={<span className="muted">{money(msSum)} de {money(p.budget_total_cents)} distribuídos</span>}>
        <ol className="milestones">
          {p.milestones.map((m: any) => (
            <li key={m.id}>
              <div><strong>{m.title}</strong><span className="muted"> · previsão {date(m.due_on)}</span></div>
              <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                   aria-valuenow={Math.round(m.amount_cents ? Math.min(100, (m.funded_cents / m.amount_cents) * 100) : 0)}
                   aria-label={`Marco ${m.seq}: captado`}><span className="progress-fill" style={{ width: `${m.amount_cents ? Math.min(100, (m.funded_cents / m.amount_cents) * 100) : 0}%` }} /></div>
              <div className="ms-foot"><span>{money(m.funded_cents)} de {money(m.amount_cents)}</span><Pill status={m.status} /></div>
            </li>
          ))}
        </ol>
        {p.milestones.length === 0 && <p className="muted">Divida o projeto em etapas: financiadores podem apoiar uma parte sem assumir o projeto inteiro.</p>}
        {p.is_owner && (
          <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${p.id}/milestones`, { title: ms.v.title, amount_cents: parseMoney(ms.v.amount), due_on: ms.v.due_on || null }), "Etapa adicionada").then((r) => { if (r) { ms.setV({ title: "", amount: "", due_on: "" }); reload(); } }); }}>
            <Field label="Etapa"><Input value={ms.v.title} onChange={ms.set("title")} /></Field>
            <Field label="Valor (R$)"><Input inputMode="decimal" value={ms.v.amount} onChange={ms.set("amount")} /></Field>
            <Field label="Previsão"><Input type="date" value={ms.v.due_on} onChange={ms.set("due_on")} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Adicionar etapa</Button>
          </form>
        )}
      </Panel>
    </div>
  );
}

function Execution({ p }: { p: any }) {
  const exp = useLoad<any>(`/v1/projects/${p.id}/expenses?limit=100`);
  const ev = useLoad<any>(`/v1/projects/${p.id}/evidences?limit=100`);
  const fb = useLoad<any>(`/v1/projects/${p.id}/feedbacks`);
  const { me } = useSession();
  const funder = ["company", "government", "individual"].includes(me?.active_org?.kind || "");
  const { busy, run } = useAction();
  const e1 = useForm({ description: "", amount: "", paid_on: "", supplier_name: "", milestone_id: "", document_id: "" });
  const e2 = useForm({ kind: "photo", title: "", milestone_id: "", indicator_name: "", indicator_value: "", document_id: "" });
  const e3 = useForm({ kind: funder ? "funder_feedback" : "progress_report", body: "", rating: "" });
  const msOpts = p.milestones.map((m: any) => [m.id, `Etapa ${m.seq}: ${m.title}`]) as [string, string][];
  const review = (path: string, status: string, reload: () => void) => {
    const note = status === "accepted" || status === "validated" ? null : prompt("Explique o motivo para a OSC:") || null;
    run(() => api.post(path, { status, note }), "Revisão registrada").then(reload);
  };
  return (
    <div className="stack-lg">
      <Panel title="Despesas comprovadas" actions={<a href={`/v1/projects/${p.id}/expenses.csv`}>Exportar CSV</a>}>
        <StateView loading={exp.loading} error={exp.error} onRetry={exp.reload}>
          <table className="table">
            <thead><tr><th>Data</th><th>Descrição</th><th>Fornecedor</th><th>Valor</th><th>Comprovante</th><th>Situação</th>{funder && <th />}</tr></thead>
            <tbody>
              {exp.data?.items.map((x: any) => (
                <tr key={x.id}><td>{date(x.paid_on)}</td><td>{x.description}</td><td>{x.supplier_name || "—"}</td><td>{money(x.amount_cents)}</td>
                  <td>{x.document_id ? <DocLink id={x.document_id} /> : <Pill tone="warn">ausente</Pill>}</td><td><Pill status={x.status} /></td>
                  {funder && <td className="row-actions">{x.status === "recorded" && <>
                    <Button variant="link" onClick={() => review(`/v1/expenses/${x.id}/review`, "validated", exp.reload)}>Validar</Button>
                    <Button variant="link" onClick={() => review(`/v1/expenses/${x.id}/review`, "questioned", exp.reload)}>Questionar</Button></>}</td>}</tr>
              ))}
              {exp.data?.items.length === 0 && <tr><td colSpan={7} className="muted">Nenhuma despesa registrada.</td></tr>}
            </tbody>
          </table>
        </StateView>
        {p.is_owner && ["funding", "funded", "in_execution", "published"].includes(p.status) && (
          <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${p.id}/expenses`, { description: e1.v.description, amount_cents: parseMoney(e1.v.amount), paid_on: e1.v.paid_on, supplier_name: e1.v.supplier_name || null, milestone_id: e1.v.milestone_id || null, document_id: e1.v.document_id || null }), "Despesa registrada").then((r) => { if (r) { e1.setV({ description: "", amount: "", paid_on: "", supplier_name: "", milestone_id: "", document_id: "" }); exp.reload(); } }); }}>
            <Field label="Descrição"><Input value={e1.v.description} onChange={e1.set("description")} /></Field>
            <Field label="Valor (R$)"><Input inputMode="decimal" value={e1.v.amount} onChange={e1.set("amount")} /></Field>
            <Field label="Pago em"><Input type="date" value={e1.v.paid_on} onChange={e1.set("paid_on")} /></Field>
            <Field label="Fornecedor"><Input value={e1.v.supplier_name} onChange={e1.set("supplier_name")} /></Field>
            <Field label="Etapa"><Select value={e1.v.milestone_id} onChange={e1.set("milestone_id")} placeholder="—" options={msOpts} /></Field>
            <Field label="Comprovante"><UploadButton docType="nota_fiscal" projectId={p.id} onUploaded={(d) => e1.set("document_id")(d.id)} done={!!e1.v.document_id} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Registrar despesa</Button>
          </form>
        )}
      </Panel>
      <Panel title="Evidências por etapa">
        <StateView loading={ev.loading} error={ev.error} onRetry={ev.reload}>
          <ul className="feed">
            {ev.data?.items.map((x: any) => (
              <li key={x.id}>
                <div>
                  <strong>{x.title}</strong> <Pill status={x.status} />
                  <p className="muted">{x.milestone_title ? `${x.milestone_title} · ` : ""}{label(x.kind)} · {date(x.occurred_on || x.created_at)}
                    {x.indicator_name && ` · ${x.indicator_name}: ${x.indicator_value}`}</p>
                  {x.review_note && <p>Devolutiva: {x.review_note}</p>}
                </div>
                <div className="row-actions">
                  {x.document_id && <DocLink id={x.document_id} />}
                  {funder && x.status === "submitted" && <>
                    <Button variant="link" onClick={() => review(`/v1/evidences/${x.id}/review`, "accepted", ev.reload)}>Aceitar</Button>
                    <Button variant="link" onClick={() => review(`/v1/evidences/${x.id}/review`, "needs_info", ev.reload)}>Pedir informação</Button></>}
                </div>
              </li>
            ))}
            {ev.data?.items.length === 0 && <li className="muted">Nenhuma evidência postada.</li>}
          </ul>
        </StateView>
        {p.is_owner && (
          <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${p.id}/evidences`, { kind: e2.v.kind, title: e2.v.title, milestone_id: e2.v.milestone_id || null, indicator_name: e2.v.indicator_name || null, indicator_value: e2.v.indicator_value ? Number(e2.v.indicator_value) : null, document_id: e2.v.document_id || null, occurred_on: new Date().toISOString().slice(0, 10) }), "Evidência enviada para revisão").then((r) => { if (r) { e2.setV({ kind: "photo", title: "", milestone_id: "", indicator_name: "", indicator_value: "", document_id: "" }); ev.reload(); } }); }}>
            <Field label="Tipo"><Select value={e2.v.kind} onChange={e2.set("kind")} options={[["photo", "Foto"], ["attendance", "Lista de presença"], ["report", "Relatório"], ["result", "Resultado de indicador"], ["invoice", "Nota fiscal"], ["video", "Vídeo"], ["other", "Outro"]]} /></Field>
            <Field label="Título"><Input value={e2.v.title} onChange={e2.set("title")} /></Field>
            <Field label="Etapa"><Select value={e2.v.milestone_id} onChange={e2.set("milestone_id")} placeholder="—" options={msOpts} /></Field>
            <Field label="Indicador"><Select value={e2.v.indicator_name} onChange={e2.set("indicator_name")} placeholder="—" options={(p.indicators || []).map((i: any) => [i.name, i.name])} /></Field>
            <Field label="Valor alcançado"><Input inputMode="decimal" value={e2.v.indicator_value} onChange={e2.set("indicator_value")} /></Field>
            <Field label="Arquivo"><UploadButton docType="foto_evidencia" projectId={p.id} onUploaded={(d) => e2.set("document_id")(d.id)} done={!!e2.v.document_id} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Enviar evidência</Button>
          </form>
        )}
      </Panel>
      <Panel title={funder ? "Devolutivas e relatórios" : "Relatórios e devolutivas"}>
        <ul className="feed">
          {fb.data?.items.map((x: any) => (
            <li key={x.id}><div><strong>{x.author_org}</strong> · {label(x.kind === "funder_feedback" ? "devolutiva" : x.kind)} · <span className="muted">{date(x.created_at)}</span>
              <p className="pre">{x.body}</p>{x.rating && <p className="muted">Avaliação: {x.rating}/5</p>}</div></li>
          ))}
          {fb.data?.items.length === 0 && <li className="muted">Nada registrado ainda.</li>}
        </ul>
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${p.id}/feedbacks`, { kind: e3.v.kind, body: e3.v.body, rating: e3.v.rating ? Number(e3.v.rating) : null }), "Registrado").then((r) => { if (r) { e3.set("body")(""); fb.reload(); } }); }}>
          {!funder && <Field label="Tipo"><Select value={e3.v.kind} onChange={e3.set("kind")} options={[["progress_report", "Relatório parcial"], ["final_report", "Relatório final"]]} /></Field>}
          {funder && <Field label="Avaliação (opcional)"><Select value={e3.v.rating} onChange={e3.set("rating")} placeholder="—" options={[["5", "5"], ["4", "4"], ["3", "3"], ["2", "2"], ["1", "1"]]} /></Field>}
          <Field label={funder ? "Devolutiva para a OSC" : "Texto do relatório"}><TextArea rows={4} value={e3.v.body} onChange={e3.set("body")} /></Field>
          <Button type="submit" variant="ink" busy={busy}>{funder ? "Enviar devolutiva" : "Enviar relatório"}</Button>
        </form>
      </Panel>
    </div>
  );
}

export function DocLink({ id, children }: { id: string; children?: any }) {
  const { run } = useAction();
  return <button className="linkish" onClick={() => run(() => api.post(`/v1/documents/${id}/download-url`)).then((r: any) => r && window.open(r.url, "_blank", "noopener"))}>{children || "Abrir"}</button>;
}

function Report({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/report`);
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="grid-home">
          <Panel title="Recurso: do orçamento à comprovação">
            <MoneyFlow stages={[["Orçamento", data.project.budget_total_cents], ["Comprometido", data.funding.committed_cents], ["Desembolsado", data.funding.disbursed_cents],
              ["Recebimento confirmado", data.funding.confirmed_cents], ["Gasto comprovado", data.funding.spent_cents]]} />
          </Panel>
          <Panel title="Indicadores">
            {data.indicators.length === 0 ? <p className="muted">Nenhum resultado aceito ainda.</p> : (
              <ul className="rows">{data.indicators.map((i: any) => <li key={i.name}><span>{i.name}</span><strong>{i.achieved} {i.target ? `de ${i.target}` : ""} {i.unit || ""}</strong></li>)}</ul>
            )}
          </Panel>
          <Panel title="Por etapa">
            <Bars rows={data.milestones.map((m: any) => ({ label: `${m.seq}. ${m.title}`, value: Number(m.spent_cents) }))} format={money} />
          </Panel>
          <Panel title="Gasto por categoria">
            <Bars rows={data.budget_by_category.map((c: any) => ({ label: label(c.category), value: Number(c.spent_cents), tone: "leaf" }))} format={money} />
          </Panel>
        </div>
      )}
    </StateView>
  );
}

function Ledger({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/ledger`);
  const ENTRY: Record<string, string> = { need_published: "Necessidade publicada", budget_defined: "Orçamento definido", milestone_defined: "Etapa definida",
    interest_registered: "Interesse registrado", application_submitted: "Candidatura enviada", application_approved: "Candidatura aprovada",
    funding_committed: "Aporte comprometido", disbursement_reported: "Desembolso informado", disbursement_confirmed: "Recebimento confirmado",
    expense_recorded: "Despesa registrada", evidence_submitted: "Evidência enviada", evidence_reviewed: "Evidência revisada", result_reported: "Resultado informado",
    report_submitted: "Relatório enviado", feedback_given: "Devolutiva", professional_signature: "Assinatura", project_completed: "Projeto concluído" };
  return (
    <StateView loading={loading} error={error} onRetry={reload} empty={data?.entries.length === 0 && "O histórico começa quando o projeto é publicado."}>
      {data && (
        <Panel title="Histórico verificável" actions={data.verification.valid ? <Pill tone="good">Cadeia íntegra · {data.verification.entries} registros</Pill> : <Pill tone="bad">Inconsistência no registro {data.verification.first_broken_seq}</Pill>}>
          <p className="fineprint">Cada registro guarda o hash do anterior. Qualquer alteração posterior quebra a cadeia e aparece aqui.</p>
          <ol className="ledger">
            {data.entries.map((e: any) => (
              <li key={e.seq}>
                <span className="ledger-seq">{e.seq}</span>
                <div>
                  <strong>{ENTRY[e.entry_type] || e.entry_type}</strong>{e.amount_cents ? ` · ${money(e.amount_cents)}` : ""}
                  <p className="muted">{e.org_name} · {date(e.at)}</p>
                  <code className="hash" title={e.entry_hash}>{e.entry_hash.slice(0, 16)}…</code>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      )}
    </StateView>
  );
}

export function Feed() {
  const tax = useTaxonomy();
  const [filters, setFilters] = useState({ cause: "", territory: "", call_id: "", include_blocked: "" });
  const [offset, setOffset] = useState(0);
  const query = new URLSearchParams(Object.entries({ ...filters, offset: String(offset) }).filter(([, v]) => v) as any).toString();
  const { data, error, loading, reload } = useLoad<any>(`/v1/feed/projects?${query}`, [query]);
  const programs = useLoad<any>("/v1/calls?mine=true&status=all&limit=100");
  const [compare, setCompare] = useState<string[]>([]);
  const [cmp, setCmp] = useState<any>(null);
  const { run } = useAction();
  return (
    <>
      <PageHead title="Projetos para apoiar" sub="Projetos publicados por OSCs, ordenados pela compatibilidade com o seu perfil de investimento." />
      <div className="filters">
        <Field label="Programa"><Select value={filters.call_id} onChange={(v) => setFilters({ ...filters, call_id: v })} placeholder="Perfil da empresa" options={(programs.data?.items || []).map((c: any) => [c.id, c.title])} /></Field>
        <Field label="Causa"><Select value={filters.cause} onChange={(v) => setFilters({ ...filters, cause: v })} placeholder="Todas" options={Object.entries(tax?.causes || {}) as any} /></Field>
        <Field label="Território"><Input value={filters.territory} onChange={(v) => setFilters({ ...filters, territory: v.toUpperCase() })} placeholder="BR-MT" /></Field>
        {compare.length >= 2 && <Button variant="ink" onClick={() => run(() => api.get(`/v1/feed/compare?ids=${compare.join(",")}`)).then(setCmp)}>Comparar {compare.length}</Button>}
      </div>
      <StateView loading={loading} error={error} onRetry={reload}
        empty={data?.items.length === 0 && <><p>Nenhum projeto compatível agora{data.hidden_blocked ? ` (${data.hidden_blocked} oculto(s) por impedimentos)` : ""}.</p>
          {data.hidden_blocked > 0 && <Button variant="ghost" onClick={() => setFilters({ ...filters, include_blocked: "true" })}>Ver projetos bloqueados e motivos</Button>}
          <Link to="/organizacao">Ajustar perfil de investimento</Link></>}>
        <p className="fineprint">{data?.engine_note}</p>
        {data?.hidden_blocked > 0 && !filters.include_blocked && (
          <p className="muted">{data.hidden_blocked} projeto(s) oculto(s) por impedimentos da sua política (documentos, território, ticket…).{" "}
            <Button variant="link" onClick={() => setFilters({ ...filters, include_blocked: "true" })}>Mostrar com os motivos</Button></p>
        )}
        <ul className="calls">
          {data?.items.map((it: any) => {
            const st = MATCH_STATE[it.match.recommended_state];
            return (
              <li key={it.project.id} className="call">
                <div className="call-main">
                  <p className="call-funder">{it.organization.legal_name} · {it.project.territory}</p>
                  <h3><Link to={`/projetos/${it.project.id}`}>{it.project.title}</Link></h3>
                  <p className="call-facts">
                    <span>{money(it.project.funded_cents)} captados de {money(it.project.budget_total_cents)}</span>
                    <span>{n(it.project.beneficiaries_count)} beneficiários</span>
                    {it.favorite && <Pill tone="good">Salvo</Pill>}
                  </p>
                  {it.match.why_match.length > 0 && <p className="muted">Combina por: {it.match.why_match.map((w: any) => w.label.toLowerCase()).join(", ")}</p>}
                  {it.match.blockers.length > 0 && <p className="field-error">{it.match.blockers.map((b: any) => b.message).join("; ")}</p>}
                </div>
                <div className={`call-match tone-${st?.tone}`}>
                  <strong>{st?.label}</strong>
                  {it.match.score !== null && <span>{Math.round(it.match.score)}/100</span>}
                  <label className="check"><input type="checkbox" checked={compare.includes(it.project.id)}
                    onChange={(e: any) => setCompare(e.target.checked ? [...compare, it.project.id].slice(0, 4) : compare.filter((x) => x !== it.project.id))} /> comparar</label>
                  <Button variant="link" onClick={() => { const reason = prompt("Por que descartar? (ajuda a melhorar suas recomendações)"); if (reason !== null) run(() => api.post(`/v1/feed/projects/${it.project.id}/feedback`, { action: "dismiss", reason })).then(reload); }}>Descartar</Button>
                </div>
              </li>
            );
          })}
        </ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={!!cmp} title="Comparação" onClose={() => setCmp(null)}>
        {cmp && (
          <table className="table">
            <thead><tr><th>Critério</th>{cmp.items.map((i: any) => <th key={i.project.id}>{i.project.title}</th>)}</tr></thead>
            <tbody>
              <tr><td>Compatibilidade</td>{cmp.items.map((i: any) => <td key={i.project.id}>{i.match.score === null ? "—" : Math.round(i.match.score)}</td>)}</tr>
              <tr><td>Confiança</td>{cmp.items.map((i: any) => <td key={i.project.id}>{Math.round(i.match.confidence)}%</td>)}</tr>
              {cmp.items[0].match.signals.map((s: any, k: number) => (
                <tr key={s.key}><td>{s.label}</td>{cmp.items.map((i: any) => <td key={i.project.id}>{i.match.signals[k].value === null ? "sem dado" : `${Math.round(i.match.signals[k].value * 100)}%`}</td>)}</tr>
              ))}
              <tr><td>Orçamento</td>{cmp.items.map((i: any) => <td key={i.project.id}>{money(i.project.budget_total_cents)}</td>)}</tr>
              <tr><td>Beneficiários</td>{cmp.items.map((i: any) => <td key={i.project.id}>{n(i.project.beneficiaries_count)}</td>)}</tr>
              <tr><td>Riscos</td>{cmp.items.map((i: any) => <td key={i.project.id}>{i.match.risks.map((r: any) => r.message).join("; ") || "—"}</td>)}</tr>
            </tbody>
          </table>
        )}
      </Modal>
    </>
  );
}

export function Portfolio() {
  const { data, error, loading, reload } = useLoad<any>("/v1/portfolio");
  const t = data?.totals;
  return (
    <>
      <PageHead title="Carteira e resultados" sub="Rastreio do recurso investido: do compromisso à despesa comprovada e ao resultado." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Quando você registrar o primeiro aporte, ele aparece aqui."}>
        {t && (
          <Panel title="Todos os projetos">
            <MoneyFlow stages={[["Comprometido", t.committed_cents], ["Desembolsado", t.disbursed_cents], ["Recebimento confirmado", t.confirmed_cents],
              ["Gasto comprovado", t.spent_cents], ["Gasto validado por você", t.validated_spent_cents]]} />
            <p className="muted">{t.projects} projeto(s) · {n(t.beneficiaries)} beneficiários previstos · {t.accepted_evidences} evidência(s) aceita(s) · {t.pending_evidences} aguardando revisão</p>
          </Panel>
        )}
        <table className="table">
          <thead><tr><th>Projeto</th><th>OSC</th><th>Comprometido</th><th>Gasto comprovado</th><th>Evidências</th><th>Situação</th></tr></thead>
          <tbody>
            {data?.items.map((r: any) => (
              <tr key={r.project_id}><td><Link to={`/projetos/${r.project_id}`}>{r.title}</Link></td><td>{r.osc_name}</td><td>{money(Number(r.committed_cents))}</td>
                <td>{money(Number(r.spent_cents))}</td><td>{r.accepted_evidences} aceitas{r.pending_evidences > 0 && ` · ${r.pending_evidences} pendentes`}</td><td><Pill status={r.status} /></td></tr>
            ))}
          </tbody>
        </table>
      </StateView>
    </>
  );
}
