// Biblioteca de Soluções — cadastro/edição, minha área (soluções, salvas, pedidos, interesses, replicações), marketplace, preferências e fila administrativa.
import { useEffect, useState } from "react";
import { api } from "../api";
import { centsToInput, dateTime, money, parseMoney } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Button, Chips, Field, Group, Input, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";
import { ODS_NAMES } from "./solutions";
import { UFS } from "./public";

const LICENSE: [string, string][] = [["all_rights_reserved", "Todos os direitos reservados"], ["cc_by", "CC BY (atribuição)"], ["cc_by_sa", "CC BY-SA"], ["cc_by_nc", "CC BY-NC"],
  ["cc_by_nc_sa", "CC BY-NC-SA"], ["public_domain", "Domínio público"], ["custom", "Condições próprias"]];

export function SolutionForm({ id }: { id?: string }) {
  const voc = useLoad<any>("/v1/solutions/vocabulary");
  const cur = useLoad<any>(id ? `/v1/solutions/${id}` : null);
  const f = useForm<any>({ kind: "project", stage: "proposal", title: "", summary: "", problem: "", approach: "", objectives: "", learnings: "", limitations: "", themes: [], population: [], institutions: [],
    ods: [], esg: [], uf: "", city: "", budget: "", needed: "", seeking_funding: false, license: "all_rights_reserved", allow_replication: false, allow_adaptation: false, attribution_required: true,
    usage_conditions: "", source_type: "author", source_name: "", ownership_type: "unknown", rights_holder: "", confidentiality: "public", authorization_publish: false, authorization_contact: false, ip_notes: "", legal_requirements: "", compatible_modalities: [] });
  const [loaded, setLoaded] = useState(false);
  const { busy, run } = useAction();
  useEffect(() => {
    const s = cur.data;
    if (s && !loaded) {
      f.setV((x: any) => ({ ...x, ...s, ods: (s.ods || []).map(String), budget: centsToInput(s.budget_cents), needed: centsToInput(s.needed_cents), uf: s.uf || "", city: s.city || "",
        problem: s.problem || "", approach: s.approach || "", objectives: s.objectives || "", learnings: s.learnings || "", limitations: s.limitations || "", usage_conditions: s.usage_conditions || "", source_name: s.source_name || "", rights_holder: s.rights_holder || "", ip_notes: s.ip_notes || "", legal_requirements: s.legal_requirements || "", ownership_type: s.ownership_type || "unknown", confidentiality: s.confidentiality || "public", compatible_modalities: s.compatible_modalities || [] }));
      setLoaded(true);
    }
    // eslint-disable-next-line
  }, [cur.data]);
  const v = f.v;
  const isIdea = v.kind === "idea";
  const body = () => ({
    kind: id ? undefined : v.kind, stage: isIdea && !["idea", "proposal"].includes(v.stage) ? "idea" : v.stage, title: v.title, summary: v.summary, problem: v.problem || null, approach: v.approach || null,
    objectives: v.objectives || null, learnings: v.learnings || null, limitations: v.limitations || null, themes: v.themes, population: v.population, institutions: v.institutions,
    ods: v.ods.map(Number), esg: v.esg, uf: v.uf || null, city: v.city || null, budget_cents: v.budget ? parseMoney(v.budget) : null, needed_cents: v.needed ? parseMoney(v.needed) : null,
    seeking_funding: v.seeking_funding, license: v.license, allow_replication: v.allow_replication, allow_adaptation: v.allow_adaptation, attribution_required: v.attribution_required,
    usage_conditions: v.usage_conditions || null, source_type: v.source_type, source_name: v.source_name || null,
    ownership_type: v.ownership_type, rights_holder: v.rights_holder || null, confidentiality: v.confidentiality, authorization_publish: !!v.authorization_publish,
    authorization_contact: !!v.authorization_contact, ip_notes: v.ip_notes || null, legal_requirements: v.legal_requirements || null, compatible_modalities: v.compatible_modalities || [],
  });
  const submit = (e: any) => {
    e.preventDefault();
    const b: any = body();
    if (id) delete b.kind;
    run(() => (id ? api.patch(`/v1/solutions/${id}`, b) : api.post("/v1/solutions", { ...b, kind: v.kind })), id ? "Solução atualizada" : "Rascunho criado").then((r: any) => r && navigate(`/solucoes/${id || r.id}`));
  };
  const stages: [string, string][] = isIdea ? [["idea", "Ideia"], ["proposal", "Proposta"]] : [["proposal", "Proposta"], ["developing", "Em desenvolvimento"], ["running", "Em execução"], ["completed", "Realizado"]];
  const ThemeChips = voc.data ? <Chips options={Object.entries(voc.data.theme_labels || {}) as [string, string][]} value={v.themes} onChange={f.set("themes")} max={12} /> : null;
  return (
    <>
      <PageHead title={id ? "Editar solução" : "Cadastrar solução"} sub="Informe o que é real. Tudo entra como autodeclarado até a administração conferir as evidências."
        back={<Link to={id ? `/solucoes/${id}` : "/solucoes"} className="back">Voltar</Link>} />
      <StateView loading={voc.loading || (!!id && cur.loading)} error={voc.error || cur.error}>
        <form className="form" onSubmit={submit}>
          <Panel title="Identificação">
            {!id && <Field label="Tipo"><Select value={v.kind} onChange={(k: string) => { f.set("kind")(k); f.set("stage")(k === "idea" ? "idea" : "proposal"); }} options={[["project", "Projeto"], ["idea", "Ideia"], ["methodology", "Metodologia"], ["social_tech", "Tecnologia social"], ["academic", "Projeto acadêmico"]]} /></Field>}
            <Field label="Estágio" hint={isIdea ? "Ideia não é case: não registra resultados nem é verificada como projeto executado." : undefined}><Select value={v.stage} onChange={f.set("stage")} options={stages} /></Field>
            <Field label="Título" wide><Input value={v.title} onChange={f.set("title")} maxLength={200} /></Field>
            <Field label="Resumo" wide hint="20 a 1.500 caracteres"><TextArea value={v.summary} onChange={f.set("summary")} rows={3} maxLength={1500} /></Field>
          </Panel>
          <Panel title="Conteúdo">
            <Field label="Problema" wide><TextArea value={v.problem} onChange={f.set("problem")} rows={3} /></Field>
            <Field label="Objetivos" wide><TextArea value={v.objectives} onChange={f.set("objectives")} rows={3} /></Field>
            <Field label="Solução / metodologia" wide><TextArea value={v.approach} onChange={f.set("approach")} rows={5} /></Field>
            <Field label="Aprendizados" wide><TextArea value={v.learnings} onChange={f.set("learnings")} rows={2} /></Field>
            <Field label="Limitações" wide hint="Dizer o que não funciona também gera confiança."><TextArea value={v.limitations} onChange={f.set("limitations")} rows={2} /></Field>
          </Panel>
          <Panel title="Classificação">
            <Group label="Temas">{ThemeChips}</Group>
            <Group label="Populações"><Chips options={(voc.data?.population || []).map((p: any) => [p.id, p.label])} value={v.population} onChange={f.set("population")} /></Group>
            <Group label="Instituições envolvidas"><Chips options={(voc.data?.institutions || []).map((p: any) => [p.id, p.label])} value={v.institutions} onChange={f.set("institutions")} /></Group>
            <Group label="ODS"><Chips options={Object.entries(ODS_NAMES).map(([k, n]) => [k, `${k} ${n}`])} value={v.ods} onChange={f.set("ods")} /></Group>
            <Group label="ESG"><Chips options={[["E", "Ambiental"], ["S", "Social"], ["G", "Governança"]]} value={v.esg} onChange={f.set("esg")} /></Group>
          </Panel>
          <Panel title="Território e orçamento">
            <Field label="UF"><Select value={v.uf} onChange={f.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
            <Field label="Município"><Input value={v.city} onChange={f.set("city")} /></Field>
            <Field label="Orçamento total (R$)"><Input value={v.budget} onChange={f.set("budget")} inputMode="decimal" /></Field>
            <label className="check"><input type="checkbox" checked={v.seeking_funding} onChange={(e: any) => f.set("seeking_funding")(e.target.checked)} /> Busco financiamento</label>
            {v.seeking_funding && <Field label="Valor necessário (R$)"><Input value={v.needed} onChange={f.set("needed")} inputMode="decimal" /></Field>}
          </Panel>
          <Panel title="Licença e propriedade intelectual">
            <Field label="Licença"><Select value={v.license} onChange={f.set("license")} options={LICENSE} /></Field>
            <label className="check"><input type="checkbox" checked={v.allow_replication} onChange={(e: any) => f.set("allow_replication")(e.target.checked)} /> Autorizo replicação</label>
            <label className="check"><input type="checkbox" checked={v.allow_adaptation} onChange={(e: any) => f.set("allow_adaptation")(e.target.checked)} /> Autorizo adaptação</label>
            <label className="check"><input type="checkbox" checked={v.attribution_required} onChange={(e: any) => f.set("attribution_required")(e.target.checked)} /> Exijo atribuição</label>
            <Field label="Condições de uso" wide><TextArea value={v.usage_conditions} onChange={f.set("usage_conditions")} rows={2} /></Field>
            <Field label="Fonte da informação"><Select value={v.source_type} onChange={f.set("source_type")} options={[["author", "Autor"], ["osc", "OSC"], ["university", "Universidade"], ["government", "Governo"], ["document", "Documento"], ["audit", "Auditoria"], ["public_source", "Fonte pública"], ["partner", "Parceiro"]]} /></Field>
            <Field label="Nome da fonte"><Input value={v.source_name} onChange={f.set("source_name")} /></Field>
          </Panel>
          <Panel title="Autoria, confidencialidade e compartilhamento">
            <Field label="Quem detém os direitos"><Select value={v.ownership_type} onChange={f.set("ownership_type")} options={[["author", "Autor"], ["organization", "Organização"], ["joint", "Coautoria"], ["institution", "Instituição parceira"], ["third_party", "Terceiro"], ["unknown", "Não sei informar"]]} /></Field>
            <Field label="Titular dos direitos"><Input value={v.rights_holder} onChange={f.set("rights_holder")} maxLength={300} /></Field>
            <Field label="Confidencialidade"><Select value={v.confidentiality} onChange={f.set("confidentiality")} options={[["public", "Pública"], ["shareable", "Compartilhável"], ["shareable_on_request", "Compartilhável sob solicitação"], ["confidential", "Confidencial"], ["restricted_use", "Uso restrito"]]} /></Field>
            <label className="check"><input type="checkbox" checked={!!v.authorization_publish} onChange={(e: any) => f.set("authorization_publish")(e.target.checked)} /> Tenho autorização para publicar esta solução</label>
            <label className="check"><input type="checkbox" checked={!!v.authorization_contact} onChange={(e: any) => f.set("authorization_contact")(e.target.checked)} /> Autorizo contato de interessados</label>
            <Group label="Modalidades de recurso compatíveis"><Chips options={[["donation", "Doação"], ["sponsorship", "Patrocínio"], ["partnership", "Parceria"], ["public_call", "Edital"], ["incentive_law", "Lei de incentivo"], ["amendment", "Emenda"]]} value={v.compatible_modalities || []} onChange={f.set("compatible_modalities")} /></Group>
            <Field label="Observações de propriedade intelectual" wide><TextArea value={v.ip_notes} onChange={f.set("ip_notes")} rows={2} /></Field>
            <Field label="Requisitos legais conhecidos" wide hint="Informe o que sabe; a plataforma não valida conformidade legal."><TextArea value={v.legal_requirements} onChange={f.set("legal_requirements")} rows={2} /></Field>
          </Panel>
          <div className="stack-row"><Button type="submit" variant="primary" busy={busy} disabled={v.title.length < 5 || v.summary.length < 20}>{id ? "Salvar alterações" : "Criar rascunho"}</Button></div>
        </form>
        {id && cur.data?.generated_draft !== undefined && null}
        {id && <GeneratedReview id={id} />}
      </StateView>
    </>
  );
}

function GeneratedReview({ id }: { id: string }) {
  const { run, busy } = useAction();
  const s = useLoad<any>(`/v1/solutions/${id}`);
  if (!s.data || !s.data.parent_id) return null;
  return (
    <Panel title="Rascunho derivado de outra solução">
      <p>Este rascunho foi gerado por regras a partir de outra solução e <strong>exige revisão humana</strong>: preencha os trechos [COMPLETAR], depois confirme a revisão para poder publicar.</p>
      <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/solutions/${id}/confirm-review`), "Revisão humana confirmada").then(() => s.reload())}>Confirmar revisão humana</Button>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ minha área
export function MyArea() {
  const [tab, setTab] = useState("mine");
  const { me } = useSession();
  const tabs: [string, string][] = [["mine", "Minhas soluções"], ["saved", "Salvas"], ["received", "Pedidos recebidos"], ["sent", "Pedidos enviados"], ["intents", "Meus interesses"], ["repl", "Replicações"]];
  return (
    <>
      <PageHead title="Minha área na biblioteca" actions={<Link to="/solucoes/nova" className="btn btn-primary">Cadastrar solução</Link>} back={<Link to="/solucoes" className="back">Biblioteca</Link>} />
      <div role="tablist" aria-label="Seções" className="chips" style={{ marginBottom: 12 }}>
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`chip${tab === k ? " chip-on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "mine" && <ListTab path="/v1/solutions/mine" empty="Você ainda não cadastrou soluções." row={(s: any) => (
        <li key={s.id}><span><Link to={`/solucoes/${s.id}`}>{s.title}</Link> <span className="muted small">{s.labels.kind}</span></span><span className="stack-row"><Pill>{s.visibility}</Pill><Pill tone={s.labels.proven ? "good" : "muted"}>{s.labels.trust}</Pill></span></li>)} />}
      {tab === "saved" && <ListTab path="/v1/solutions/saved" empty="Nada salvo ainda." row={(s: any) => <li key={s.id}><Link to={`/solucoes/${s.id}`}>{s.title}</Link><Pill tone="muted">{s.labels.primary}</Pill></li>} />}
      {tab === "received" && <Requests dir="received" />}
      {tab === "sent" && <Requests dir="sent" />}
      {tab === "intents" && <ListTab path="/v1/solution-intents/mine" empty="Você não declarou interesse em nenhuma solução." row={(i: any) => (
        <li key={i.id}><span><Link to={`/solucoes/${i.solution_id}`}>{i.title}</Link> <span className="muted small">{i.public_identity ? "identidade pública" : "identidade privada"}</span></span><Pill>{i.stage}</Pill></li>)} />}
      {tab === "repl" && <ListTab path="/v1/solution-replications/mine" empty="Sem replicações." row={(r: any) => (
        <li key={r.id}><span><Link to={`/solucoes/${r.solution_id}`}>{r.title}</Link> <span className="muted small">{r.target_city}/{r.target_uf} · {r.as_replicator ? "você replica" : `replicador: ${r.replicator_name || "identidade privada"}`}</span></span>
          <span className="stack-row"><Pill>{r.status}</Pill>{r.author_confirmed && <Pill tone="good">confirmada pelo autor</Pill>}
            {!r.as_replicator && !r.author_confirmed && ["started", "completed"].includes(r.status) && <ConfirmRepl id={r.id} />}</span></li>)} />}
      {me?.active_org?.kind && <p className="muted small">Personalização por histórico é opcional: <Link to="/solucoes/preferencias">ajustar</Link>.</p>}
    </>
  );
}

function ConfirmRepl({ id }: { id: string }) {
  const { busy, run } = useAction();
  return <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/solution-replications/${id}/confirm`), "Replicação confirmada").then(() => location.reload())}>Confirmar</Button>;
}

function ListTab({ path, row, empty }: { path: string; row: (x: any) => any; empty: string }) {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`${path}?limit=15&offset=${offset}`, [offset]);
  const items = (data?.items || []).filter((x: any) => x && x.id);
  return (
    <StateView loading={loading} error={error} onRetry={reload} empty={!loading && items.length === 0 && <p>{empty}</p>}>
      <ul className="rows">{items.map(row)}</ul>
      <Pager data={data} offset={offset} setOffset={setOffset} />
    </StateView>
  );
}

function Requests({ dir }: { dir: "received" | "sent" }) {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/solution-requests/${dir}?limit=15&offset=${offset}`, [offset]);
  const [answer, setAnswer] = useState<Record<string, string>>({});
  const { busy, run } = useAction();
  const items = data?.items || [];
  return (
    <StateView loading={loading} error={error} onRetry={reload} empty={!loading && items.length === 0 && <p>Nenhum pedido.</p>}>
      <ul className="rows">{items.map((r: any) => (
        <li key={r.id}>
          <span><Link to={`/solucoes/${r.solution_id}`}>{r.solution_title}</Link> <span className="muted small">{r.kind}{dir === "received" ? ` · de ${r.requester_name}` : ""} · {dateTime(r.created_at)}</span><br />{r.message}
            {r.response && <><br /><em>Resposta: {r.response}</em></>}</span>
          <span className="stack-row"><Pill status={r.status === "new" ? "pending" : r.status} />
            {dir === "received" && ["new", "seen"].includes(r.status) && (<>
              <Input value={answer[r.id] || ""} onChange={(v: string) => setAnswer((a) => ({ ...a, [r.id]: v }))} placeholder="Resposta" aria-label="Resposta ao pedido" />
              <Button variant="primary" busy={busy} disabled={!answer[r.id]} onClick={() => run(() => api.post(`/v1/solution-requests/${r.id}/respond`, { status: "accepted", response: answer[r.id] }), "Pedido aceito").then(reload)}>Aceitar</Button>
              <Button variant="ghost" busy={busy} disabled={!answer[r.id]} onClick={() => run(() => api.post(`/v1/solution-requests/${r.id}/respond`, { status: "declined", response: answer[r.id] }), "Pedido recusado").then(reload)}>Recusar</Button></>)}
            {dir === "sent" && ["new", "seen"].includes(r.status) && <Button variant="ghost" onClick={() => run(() => api.post(`/v1/solution-requests/${r.id}/close`), "Pedido encerrado").then(reload)}>Encerrar</Button>}</span>
        </li>))}</ul>
      <Pager data={data} offset={offset} setOffset={setOffset} />
    </StateView>
  );
}

// ------------------------------------------------------------------------------------------------ marketplace
export function Marketplace() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/replications/marketplace?limit=12&offset=${offset}`, [offset]);
  return (
    <>
      <PageHead title="Marketplace de replicação" sub="Soluções que o autor autorizou replicar. “Replicada” só vale com conclusão confirmada pelo autor." back={<Link to="/solucoes" className="back">Biblioteca</Link>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={!loading && (data?.items || []).length === 0 && <p>Nenhuma solução em execução ou realizada autorizou replicação ainda.</p>}>
        <div className="grid-home">{(data?.items || []).map((s: any) => (
          <article className="panel" key={s.id}>
            <Pill tone={s.labels.proven ? "good" : "muted"}>{s.labels.primary}</Pill> <Pill>{s.labels.trust}</Pill>
            <h3><Link to={`/solucoes/${s.id}`}>{s.title}</Link></h3>
            <p className="muted small">{s.uf || "—"} · orçamento {money(s.budget_cents)} · replicações confirmadas: {s.replications_confirmed}</p>
            <p className="small">Replicabilidade: {s.replicability_detail.score == null ? "dados insuficientes" : `${s.replicability_detail.score}/100`}{s.replicability_detail.negatives?.length ? ` — atenção: ${s.replicability_detail.negatives.slice(0, 2).join("; ")}` : ""}</p>
          </article>))}</div>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------------------------------------ preferências
export function Preferences() {
  const { me } = useSession();
  const kind = me?.active_org?.kind;
  const voc = useLoad<any>("/v1/solutions/vocabulary");
  const prefs = useLoad<any>("/v1/solutions/funder-preferences");
  const rec = useLoad<any>("/v1/solutions/recommendations");
  const f = useForm<any>({ populations: [], kinds: [], prefer_proven: false, risk_tolerance: "", horizon: "" });
  const [loaded, setLoaded] = useState(false);
  const { busy, run } = useAction();
  useEffect(() => {
    if (prefs.data && !loaded) { const p = prefs.data.preferences || {}; f.setV({ populations: p.populations || [], kinds: p.kinds || [], prefer_proven: !!p.prefer_proven, risk_tolerance: p.risk_tolerance || "", horizon: p.horizon_months ? String(p.horizon_months) : "" }); setLoaded(true); }
    // eslint-disable-next-line
  }, [prefs.data]);
  const funder = kind === "company" || kind === "government" || kind === "individual";
  return (
    <>
      <PageHead title="Tese e personalização" sub="Você decide o que a biblioteca pode usar para recomendar soluções." back={<Link to="/solucoes" className="back">Biblioteca</Link>} />
      <Panel title="Personalização por histórico">
        <p>Quando ativada, usamos suas soluções salvas e o resumo estruturado das suas buscas (nunca o texto digitado) para sugerir soluções. Desativar apaga o histórico de buscas.</p>
        <div className="stack-row">
          <Button variant="primary" busy={busy} onClick={() => run(() => api.put("/v1/solutions/personalization", { personalization_opt_in: true }), "Personalização ativada").then(rec.reload)}>Ativar</Button>
          <Button variant="ghost" busy={busy} onClick={() => run(() => api.put("/v1/solutions/personalization", { personalization_opt_in: false }), "Desativada; histórico de buscas apagado").then(rec.reload)}>Desativar e apagar histórico</Button>
        </div>
        <p className="muted small">Estado atual: {rec.data?.personalization_opt_in ? "ativada" : "desativada (padrão)"}.</p>
      </Panel>
      {funder && (
        <Panel title="Tese do financiador para soluções">
          <p className="muted small">Complementa o perfil de financiador (causas, ODS, territórios e faixa). O plano contratado não altera a aderência.</p>
          <StateView loading={voc.loading || prefs.loading} error={voc.error || prefs.error}>
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.put("/v1/solutions/funder-preferences", { populations: f.v.populations, kinds: f.v.kinds, prefer_proven: f.v.prefer_proven,
              risk_tolerance: f.v.risk_tolerance || null, horizon_months: f.v.horizon ? +f.v.horizon : null }), "Tese salva").then(rec.reload); }}>
              <Group label="Populações de interesse"><Chips options={(voc.data?.population || []).map((p: any) => [p.id, p.label])} value={f.v.populations} onChange={f.set("populations")} /></Group>
              <Group label="Tipos de solução"><Chips options={[["project", "Projeto"], ["idea", "Ideia"], ["methodology", "Metodologia"], ["social_tech", "Tecnologia social"], ["academic", "Acadêmico"]]} value={f.v.kinds} onChange={f.set("kinds")} /></Group>
              <Field label="Tolerância a risco"><Select value={f.v.risk_tolerance} onChange={f.set("risk_tolerance")} placeholder="—" options={[["low", "Baixa"], ["medium", "Média"], ["high", "Alta"]]} /></Field>
              <Field label="Horizonte (meses)"><Input value={f.v.horizon} onChange={f.set("horizon")} inputMode="numeric" /></Field>
              <label className="check"><input type="checkbox" checked={f.v.prefer_proven} onChange={(e: any) => f.set("prefer_proven")(e.target.checked)} /> Prefiro soluções com evidência verificada</label>
              <Button type="submit" variant="primary" busy={busy}>Salvar tese</Button>
            </form>
            {prefs.data && !prefs.data.profile?.causes?.length && <p role="note">Seu perfil de financiador está sem causas. <Link to="/organizacao">Complete o perfil</Link> para ver a aderência.</p>}
          </StateView>
        </Panel>)}
    </>
  );
}

// ------------------------------------------------------------------------------------------------ administração
export function AdminSolutions() {
  const q = useLoad<any>("/v1/admin/solutions/queue");
  const { busy, run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const d = q.data;
  const N = (k: string) => note[k] || "";
  return (
    <>
      <PageHead title="Soluções — verificação" sub="Evidências aceitas e resultados validados são os únicos caminhos para níveis de confiança mais altos." />
      <StateView loading={q.loading} error={q.error} onRetry={q.reload}>
        {d && (<div className="stack-lg">
          <Panel title={`Solicitações de verificação (${d.review_requested.length})`}>
            {d.review_requested.length === 0 ? <p className="muted">Nada pendente.</p> : <ul className="rows">{d.review_requested.map((s: any) => (
              <li key={s.id}><span><Link to={`/solucoes/${s.id}`}>{s.title}</Link> <span className="muted small">{s.trust_level}</span></span>
                <span className="stack-row"><Select value="" onChange={(lvl: string) => lvl && run(() => api.post(`/v1/admin/solutions/${s.id}/verify`, { trust_level: lvl, note: N(s.id) || "Verificação administrativa" }), "Nível atualizado").then(q.reload)}
                  placeholder="Definir nível…" options={[["documented", "Documentada"], ["evidenced", "Evidenciada"], ["verified", "Verificada"], ["self_declared", "Autodeclarada"]]} aria-label="Nível de confiança" />
                  <Input value={N(s.id)} onChange={(v: string) => setNote((n) => ({ ...n, [s.id]: v }))} placeholder="Nota" aria-label="Nota da verificação" /></span></li>))}</ul>}
          </Panel>
          <Panel title={`Evidências a revisar (${d.evidence_pending.length})`}>
            {d.evidence_pending.length === 0 ? <p className="muted">Nada pendente.</p> : <ul className="rows">{d.evidence_pending.map((e: any) => (
              <li key={e.id}><span><Link to={`/solucoes/${e.solution_id}`}>{e.title}</Link>: {e.evidence_title} <span className="muted small">{e.kind} · {e.url}</span></span>
                <span className="stack-row"><Input value={N(e.id)} onChange={(v: string) => setNote((n) => ({ ...n, [e.id]: v }))} placeholder="Nota da revisão" aria-label="Nota da revisão" />
                  <Button variant="primary" busy={busy} disabled={N(e.id).length < 3} onClick={() => run(() => api.post(`/v1/admin/solution-evidence/${e.id}/review`, { status: "accepted", note: N(e.id) }), "Aceita").then(q.reload)}>Aceitar</Button>
                  <Button variant="danger" busy={busy} disabled={N(e.id).length < 3} onClick={() => run(() => api.post(`/v1/admin/solution-evidence/${e.id}/review`, { status: "rejected", note: N(e.id) }), "Rejeitada").then(q.reload)}>Rejeitar</Button></span></li>))}</ul>}
          </Panel>
          <Panel title={`Resultados com evidência a validar (${d.results_reported.length})`}>
            {d.results_reported.length === 0 ? <p className="muted">Nada pendente.</p> : <ul className="rows">{d.results_reported.map((r: any) => (
              <li key={r.id}><span><Link to={`/solucoes/${r.solution_id}`}>{r.title}</Link>: {r.indicator} = {r.value}</span>
                <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/admin/solution-results/${r.id}/validate`), "Validado").then(q.reload)}>Validar</Button></li>))}</ul>}
          </Panel>
          <Panel title={`Contestações abertas (${d.disputes_open.length})`}>
            {d.disputes_open.length === 0 ? <p className="muted">Nada pendente.</p> : <ul className="rows">{d.disputes_open.map((x: any) => (
              <li key={x.id}><span><Link to={`/solucoes/${x.solution_id}`}>{x.title}</Link>: {x.claim}</span>
                <span className="stack-row"><Input value={N(x.id)} onChange={(v: string) => setNote((n) => ({ ...n, [x.id]: v }))} placeholder="Fundamentação" aria-label="Fundamentação da decisão" />
                  <Button variant="primary" busy={busy} disabled={N(x.id).length < 5} onClick={() => run(() => api.post(`/v1/admin/solution-disputes/${x.id}/decide`, { status: "upheld", note: N(x.id) }), "Procedente").then(q.reload)}>Procedente</Button>
                  <Button variant="ghost" busy={busy} disabled={N(x.id).length < 5} onClick={() => run(() => api.post(`/v1/admin/solution-disputes/${x.id}/decide`, { status: "rejected", note: N(x.id) }), "Improcedente").then(q.reload)}>Improcedente</Button></span></li>))}</ul>}
          </Panel>
        </div>)}
      </StateView>
    </>
  );
}
