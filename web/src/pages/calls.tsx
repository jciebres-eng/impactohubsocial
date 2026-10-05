import { useEffect, useState } from "react";
import { api, qs } from "../api";
import { centsToInput, date, daysUntil, label, money, parseMoney, MATCH_STATE } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Button, Chips, Field, Input, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad, useTaxonomy } from "../ui/kit";
import { MatchVerdict } from "../ui/trail";

const SPHERES: [string, string][] = [["private", "Privado"], ["federal", "Federal"], ["state", "Estadual"], ["municipal", "Municipal"], ["local", "Local"], ["international", "Internacional"]];
const INSTRUMENTS: [string, string][] = [["edital", "Edital"], ["grant", "Doação/grant"], ["fund", "Fundo"], ["financing", "Financiamento"], ["prize", "Prêmio"], ["incentive_law", "Lei de incentivo"], ["donation", "Doação direta"], ["other", "Outro"]];
const sphereLabel = (s: string) => SPHERES.find((x) => x[0] === s)?.[1] || s;
const instrumentLabel = (s: string) => INSTRUMENTS.find((x) => x[0] === s)?.[1] || s;

function Deadline({ at }: { at?: string | null }) {
  const d = daysUntil(at);
  if (d === null) return <Pill tone="muted">Fluxo contínuo</Pill>;
  if (d < 0) return <Pill tone="bad">Encerrado</Pill>;
  return <Pill tone={d <= 7 ? "bad" : d <= 21 ? "warn" : "muted"}>{d === 0 ? "Encerra hoje" : `Encerra em ${d} dia(s)`}</Pill>;
}

function CallRow({ c }: { c: any }) {
  const st = c.match ? MATCH_STATE[c.match.recommended_state] : null;
  return (
    <li className="call">
      <div className="call-main">
        <p className="call-funder">{c.funder_name} · {sphereLabel(c.sphere)} · {instrumentLabel(c.instrument)}</p>
        <h3><Link to={`/oportunidades/${c.id}`}>{c.title}</Link></h3>
        {c.summary && <p className="call-summary">{c.summary}</p>}
        <p className="call-facts">
          <Deadline at={c.closes_at} />
          {(c.ticket_min_cents || c.ticket_max_cents) && <span>{money(c.ticket_min_cents)} a {money(c.ticket_max_cents)}</span>}
          {c.is_example && <Pill tone="warn">Exemplo fictício</Pill>}
          {!c.managed_on_platform && <span className="muted">Inscrição no portal do financiador</span>}
        </p>
      </div>
      {c.match && st && (
        <div className={`call-match tone-${st.tone}`}>
          <strong>{st.label}</strong>
          {c.match.score !== null && <span>{Math.round(c.match.score)}/100</span>}
          {Array.isArray(c.match.unmet) && c.match.unmet.length > 0 && <span className="muted">{c.match.unmet.length} requisito(s) pendente(s)</span>}
          {typeof c.match.unmet === "number" && c.match.unmet > 0 && <span className="muted">{c.match.unmet} requisito(s) pendente(s)</span>}
        </div>
      )}
    </li>
  );
}

export function Opportunities() {
  const [tab, setTab] = useState<"rec" | "search" | "saved">("rec");
  return (
    <>
      <PageHead title="Oportunidades" sub="Editais, fundos e financiamentos privados, públicos e internacionais — com a compatibilidade da sua organização." />
      <div className="tabs" role="tablist">
        {([["rec", "Recomendadas"], ["search", "Buscar"], ["saved", "Rastreio e alertas"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "tab on" : "tab"} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "rec" && <Recommended />}
      {tab === "search" && <Search />}
      {tab === "saved" && <SavedSearches />}
    </>
  );
}

function Recommended() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/calls/recommended?offset=${offset}`, [offset]);
  return (
    <StateView loading={loading} error={error} onRetry={reload}
      empty={data?.items.length === 0 && <><p>Nenhuma oportunidade aberta compatível com as causas do seu perfil.</p><Link to="/organizacao">Revisar causas e território</Link></>}>
      <p className="fineprint">{data?.engine_note}</p>
      <ul className="calls">{data?.items.map((c: any) => <CallRow key={c.id} c={c} />)}</ul>
      <Pager data={data} offset={offset} setOffset={setOffset} />
    </StateView>
  );
}

function Search() {
  const tax = useTaxonomy();
  const f = useForm({ q: "", sphere: "", instrument: "", cause: "", territory: "", status: "open" });
  const [query, setQuery] = useState("?status=open");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/calls${query}${query ? "&" : "?"}offset=${offset}`, [query, offset]);
  return (
    <>
      <form className="filters" onSubmit={(e: any) => { e.preventDefault(); setOffset(0); setQuery(qs(f.v)); }}>
        <Field label="Palavras-chave"><Input value={f.v.q} onChange={f.set("q")} placeholder="ex.: música, cisterna, primeira infância" /></Field>
        <Field label="Esfera"><Select value={f.v.sphere} onChange={f.set("sphere")} placeholder="Todas" options={SPHERES} /></Field>
        <Field label="Tipo"><Select value={f.v.instrument} onChange={f.set("instrument")} placeholder="Todos" options={INSTRUMENTS} /></Field>
        <Field label="Causa"><Select value={f.v.cause} onChange={f.set("cause")} placeholder="Todas" options={Object.entries(tax?.causes || {}) as any} /></Field>
        <Field label="Território" hint="BR-MT ou BR-MT-5105259"><Input value={f.v.territory} onChange={(v) => f.set("territory")(v.toUpperCase())} /></Field>
        <Field label="Situação"><Select value={f.v.status} onChange={f.set("status")} options={[["open", "Abertas"], ["closed", "Encerradas"], ["all", "Todas"]]} /></Field>
        <Button type="submit" variant="ink">Buscar</Button>
      </form>
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhum resultado. Experimente filtros mais amplos."}>
        <ul className="calls">{data?.items.map((c: any) => <CallRow key={c.id} c={c} />)}</ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}

function SavedSearches() {
  const { can } = useSession();
  const tax = useTaxonomy();
  const { data, error, loading, reload } = useLoad<any>("/v1/saved-searches");
  const f = useForm({ name: "", cause: "", sphere: "", territory: "", min_score: "", frequency: "daily" });
  const { busy, run } = useAction();
  if (!can("alerts.saved_search")) return (
    <Panel title="Rastreio automático de editais">
      <p>Salve buscas e receba alertas no app e por e-mail quando surgir um edital compatível. Disponível nos planos pagos ou por voucher.</p>
      <Button variant="primary" onClick={() => navigate("/conta/plano")}>Ver planos</Button>
    </Panel>
  );
  async function create(e: any) {
    e.preventDefault();
    const filters: any = {};
    for (const k of ["cause", "sphere", "territory"] as const) if (f.v[k]) filters[k] = f.v[k];
    if (f.v.min_score) filters.min_score = Number(f.v.min_score);
    const r = await run(() => api.post("/v1/saved-searches", { name: f.v.name, filters, frequency: f.v.frequency }), "Busca salva");
    if (r) { f.setV({ ...f.v, name: "" }); reload(); }
  }
  return (
    <div className="split">
      <Panel title="Nova busca com alerta">
        <form className="form" onSubmit={create}>
          <Field label="Nome"><Input value={f.v.name} onChange={f.set("name")} placeholder="Cultura no Mato Grosso" /></Field>
          <Field label="Causa"><Select value={f.v.cause} onChange={f.set("cause")} placeholder="Qualquer" options={Object.entries(tax?.causes || {}) as any} /></Field>
          <Field label="Esfera"><Select value={f.v.sphere} onChange={f.set("sphere")} placeholder="Qualquer" options={SPHERES} /></Field>
          <Field label="Território"><Input value={f.v.territory} onChange={(v) => f.set("territory")(v.toUpperCase())} placeholder="BR-MT" /></Field>
          <Field label="Compatibilidade mínima" hint="0 a 100 (opcional)"><Input inputMode="numeric" value={f.v.min_score} onChange={f.set("min_score")} /></Field>
          <Field label="Frequência"><Select value={f.v.frequency} onChange={f.set("frequency")} options={[["instant", "A cada rodada"], ["daily", "Diária"], ["weekly", "Semanal"]]} /></Field>
          <Button type="submit" variant="primary" busy={busy}>Salvar e acompanhar</Button>
        </form>
      </Panel>
      <Panel title="Buscas acompanhadas">
        <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma busca salva."}>
          <ul className="rows">
            {data?.items.map((s: any) => (
              <li key={s.id}>
                <span><strong>{s.name}</strong><br /><span className="muted">{s.hits} oportunidade(s) encontrada(s) · última rodada {date(s.last_run_at)}</span></span>
                <span className="row-actions">
                  <Button variant="ghost" onClick={() => run(() => api.post(`/v1/saved-searches/${s.id}/run`)).then((r: any) => { if (r) { reload(); } })}>Rodar agora</Button>
                  <Button variant="link" onClick={() => run(() => api.del(`/v1/saved-searches/${s.id}`), "Busca removida").then(reload)}>Remover</Button>
                </span>
              </li>
            ))}
          </ul>
        </StateView>
      </Panel>
    </div>
  );
}

export function CallDetail({ id }: { id: string }) {
  const { me } = useSession();
  const [project, setProject] = useState("");
  const { data, error, loading, reload } = useLoad<any>(`/v1/calls/${id}${project ? `?project_id=${project}` : ""}`, [project]);
  const projects = useLoad<any>(me?.active_org?.kind === "osc" ? "/v1/projects?limit=100" : null);
  const { busy, run } = useAction();
  const tax = useTaxonomy();
  const c = data?.call;
  async function start(external: boolean) {
    const r = await run(() => api.post("/v1/applications", { call_id: id, project_id: project || null, track_external: external }), "Candidatura iniciada");
    if (r) navigate(`/candidaturas/${r.id}`);
  }
  return (
    <StateView loading={loading && !data} error={error} onRetry={reload}>
      {c && (
        <>
          <PageHead back={<Link to={me?.active_org?.kind === "osc" ? "/oportunidades" : "/editais"} className="back">Oportunidades</Link>}
            title={c.title} sub={<>{c.funder_name} · {sphereLabel(c.sphere)} · {instrumentLabel(c.instrument)} {c.is_example && <Pill tone="warn">Exemplo fictício</Pill>}</>}
            actions={data.call.owner_org_id === me?.active_org?.id && (
              <><Button variant="ghost" onClick={() => navigate(`/editais/${id}/editar`)}>Editar</Button>
                <Button variant="ink" onClick={() => navigate(`/editais/${id}/candidaturas`)}>Candidaturas ({data.applications_count})</Button></>)} />
          <div className="detail">
            <div className="detail-main">
              {data.match && (
                <MatchVerdict m={data.match} actions={
                  data.application ? <Button variant="ink" onClick={() => navigate(`/candidaturas/${data.application.id}`)}>Abrir candidatura</Button> : null} />
              )}
              <Panel title="Sobre a oportunidade">
                {c.summary && <p className="lead">{c.summary}</p>}
                {c.description && <p className="pre">{c.description}</p>}
                {c.url && <p><a href={c.url} target="_blank" rel="noopener noreferrer">Página oficial do edital</a></p>}
              </Panel>
            </div>
            <aside className="detail-side">
              <Panel title="Resumo" quiet>
                <dl className="kv">
                  <div><dt>Prazo</dt><dd><Deadline at={c.closes_at} /> {c.closes_at && date(c.closes_at)}</dd></div>
                  <div><dt>Valores</dt><dd>{money(c.ticket_min_cents)} a {money(c.ticket_max_cents)}</dd></div>
                  {c.budget_total_cents && <div><dt>Orçamento total</dt><dd>{money(c.budget_total_cents)}</dd></div>}
                  <div><dt>Causas</dt><dd>{(c.causes || []).map((x: string) => tax?.causes?.[x] || x).join(", ") || "Qualquer"}</dd></div>
                  <div><dt>Território</dt><dd>{(c.territories || []).join(", ") || "Sem restrição"}</dd></div>
                  {c.counterpart_pct && <div><dt>Contrapartida</dt><dd>{c.counterpart_pct}%</dd></div>}
                  <div><dt>Conferido na fonte</dt><dd>{date(c.last_verified_at)}</dd></div>
                </dl>
              </Panel>
              {me?.active_org?.kind === "osc" && !data.application && (
                <Panel title="Candidatar-se" quiet>
                  <Field label="Projeto para esta candidatura" hint="A compatibilidade é recalculada com o projeto escolhido">
                    <Select value={project} onChange={setProject} placeholder="Avaliar só a organização"
                      options={(projects.data?.items || []).map((p: any) => [p.id, p.title])} />
                  </Field>
                  {c.managed_on_platform && c.owner_org_id ? (
                    <Button variant="primary" busy={busy} onClick={() => start(false)}>Iniciar candidatura assistida</Button>
                  ) : (
                    <>
                      <p className="muted">A inscrição acontece no portal do financiador. A plataforma organiza o passo a passo, os documentos e o acompanhamento.</p>
                      <Button variant="primary" busy={busy} onClick={() => start(true)}>Acompanhar este edital</Button>
                    </>
                  )}
                </Panel>
              )}
            </aside>
          </div>
        </>
      )}
    </StateView>
  );
}

export function MyCalls() {
  const { data, error, loading, reload } = useLoad<any>("/v1/calls?mine=true&status=all&limit=100");
  const { me } = useSession();
  const isGov = me?.active_org?.kind === "government";
  return (
    <>
      <PageHead title={isGov ? "Editais" : "Programas"} sub={isGov ? "Editais e chamamentos publicados pelo órgão." : "Chamadas próprias da empresa para receber projetos."}
        actions={<Button variant="primary" onClick={() => navigate("/editais/novo")}>{isGov ? "Novo edital" : "Novo programa"}</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma chamada criada ainda."}>
        <table className="table">
          <thead><tr><th>Título</th><th>Situação</th><th>Encerramento</th><th>Valores</th><th /></tr></thead>
          <tbody>
            {data?.items.map((c: any) => (
              <tr key={c.id}>
                <td><Link to={`/oportunidades/${c.id}`}>{c.title}</Link></td>
                <td><Pill status={c.status} /></td>
                <td>{date(c.closes_at)}</td>
                <td>{money(c.ticket_min_cents)} – {money(c.ticket_max_cents)}</td>
                <td className="row-actions"><Link to={`/editais/${c.id}/candidaturas`}>Candidaturas</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </StateView>
    </>
  );
}

export function CallForm({ id }: { id?: string }) {
  const tax = useTaxonomy();
  const { me } = useSession();
  const isGov = me?.active_org?.kind === "government";
  const existing = useLoad<any>(id ? `/v1/calls/${id}` : null);
  const f = useForm<any>({ title: "", summary: "", description: "", url: "", sphere: isGov ? "municipal" : "private", instrument: "edital", causes: [], ods: [],
    territories: "", ticket_min: "", ticket_max: "", budget_total: "", min_org_age_months: "", required_document_types: [], opens_at: "", closes_at: "", status: "draft",
    requirements: "", funding_modality: "", accepted_legal_natures: [], required_certifications: [], min_maturity: "" });
  const instCat = useLoad<any>("/v1/institutional/catalogs");
  const catOpts = (k: string) => ((instCat.data?.catalogs?.[k] || []) as any[]).map((x) => [x.code, x.label] as [string, string]);
  const { busy, run } = useAction();
  useEffect(() => {
    const c = existing.data?.call;
    if (!c) return;
    f.setV({ ...f.v, ...c, territories: (c.territories || []).join(", "), ticket_min: centsToInput(c.ticket_min_cents), ticket_max: centsToInput(c.ticket_max_cents),
      budget_total: centsToInput(c.budget_total_cents), min_org_age_months: c.min_org_age_months ?? "", opens_at: c.opens_at?.slice(0, 10) || "",
      closes_at: c.closes_at?.slice(0, 10) || "", requirements: (c.requirements || []).map((r: any) => r.label).join("\n"), summary: c.summary || "",
      description: c.description || "", url: c.url || "", funding_modality: c.funding_modality || "", accepted_legal_natures: c.accepted_legal_natures || [],
      required_certifications: c.required_certifications || [], min_maturity: c.min_maturity ?? "" });
  }, [existing.data]);  // eslint-disable-line
  async function save(e: any) {
    e.preventDefault();
    const body = {
      title: f.v.title, summary: f.v.summary || null, description: f.v.description || null, url: f.v.url || null, sphere: f.v.sphere, instrument: f.v.instrument,
      causes: f.v.causes, ods: f.v.ods.map(Number), territories: f.v.territories.split(",").map((s: string) => s.trim().toUpperCase()).filter(Boolean),
      ticket_min_cents: parseMoney(f.v.ticket_min), ticket_max_cents: parseMoney(f.v.ticket_max), budget_total_cents: parseMoney(f.v.budget_total),
      min_org_age_months: f.v.min_org_age_months === "" ? null : Number(f.v.min_org_age_months), required_document_types: f.v.required_document_types,
      opens_at: f.v.opens_at ? f.v.opens_at + "T00:00:00Z" : null, closes_at: f.v.closes_at ? f.v.closes_at + "T23:59:00-03:00" : null, status: f.v.status,
      managed_on_platform: true, funding_modality: f.v.funding_modality || null, accepted_legal_natures: f.v.accepted_legal_natures,
      required_certifications: f.v.required_certifications, min_maturity: f.v.min_maturity === "" ? null : Number(f.v.min_maturity),
      requirements: f.v.requirements.split("\n").map((s: string) => s.trim()).filter(Boolean).map((l: string, i: number) => ({ code: `req_${i + 1}`, label: l, mandatory: true })),
    };
    const r = await run(() => (id ? api.put(`/v1/calls/${id}`, body) : api.post("/v1/calls", body)), id ? "Alterações salvas" : "Chamada criada");
    if (r) navigate(`/oportunidades/${id || r.id}`);
  }
  const docOpts = Object.entries(tax?.document_types || {}).map(([k, v]: any) => [k, v.label]) as [string, string][];
  return (
    <>
      <PageHead title={id ? "Editar chamada" : isGov ? "Novo edital" : "Novo programa"} back={<Link to="/editais" className="back">Voltar</Link>} />
      <form className="form form-wide" onSubmit={save}>
        <Field label="Título" wide><Input value={f.v.title} onChange={f.set("title")} required /></Field>
        <Field label="Resumo" wide><TextArea rows={2} value={f.v.summary} onChange={f.set("summary")} /></Field>
        <Field label="Descrição e regras" wide><TextArea rows={6} value={f.v.description} onChange={f.set("description")} /></Field>
        {isGov && <Field label="Esfera"><Select value={f.v.sphere} onChange={f.set("sphere")} options={SPHERES.filter((s) => s[0] !== "private")} /></Field>}
        <Field label="Tipo"><Select value={f.v.instrument} onChange={f.set("instrument")} options={INSTRUMENTS} /></Field>
        <Field label="Página oficial (opcional)"><Input value={f.v.url} onChange={f.set("url")} placeholder="https://" /></Field>
        <Field label="Causas" wide><Chips options={Object.entries(tax?.causes || {}) as any} value={f.v.causes} onChange={f.set("causes")} /></Field>
        <Field label="ODS" wide><Chips options={Object.entries(tax?.ods || {}).map(([k, v]: any) => [k, `${k}. ${v}`]) as any} value={f.v.ods.map(String)} onChange={f.set("ods")} /></Field>
        <Field label="Territórios elegíveis" hint="Separados por vírgula: BR, BR-MT, BR-MT-5105259 ou INT"><Input value={f.v.territories} onChange={f.set("territories")} /></Field>
        <Field label="Tempo mínimo de existência (meses)"><Input inputMode="numeric" value={f.v.min_org_age_months} onChange={f.set("min_org_age_months")} /></Field>
        <Field label="Valor mínimo por projeto (R$)"><Input inputMode="decimal" value={f.v.ticket_min} onChange={f.set("ticket_min")} /></Field>
        <Field label="Valor máximo por projeto (R$)"><Input inputMode="decimal" value={f.v.ticket_max} onChange={f.set("ticket_max")} /></Field>
        <Field label="Orçamento total (R$)"><Input inputMode="decimal" value={f.v.budget_total} onChange={f.set("budget_total")} /></Field>
        <Field label="Abertura"><Input type="date" value={f.v.opens_at} onChange={f.set("opens_at")} /></Field>
        <Field label="Encerramento"><Input type="date" value={f.v.closes_at} onChange={f.set("closes_at")} /></Field>
        <Field label="Documentos obrigatórios" wide><Chips options={docOpts} value={f.v.required_document_types} onChange={f.set("required_document_types")} /></Field>
        <Field label="Modalidade de financiamento" hint="Define quais regras publicadas (com fonte) se aplicam a este edital."><Select value={f.v.funding_modality} onChange={f.set("funding_modality")} placeholder="Não informada" options={catOpts("funding_modality")} /></Field>
        <Field label="Maturidade institucional mínima (0–6)"><Input inputMode="numeric" value={f.v.min_maturity} onChange={f.set("min_maturity")} /></Field>
        <Field label="Naturezas jurídicas aceitas" wide hint="Vazio = qualquer. Quem não atende aparece bloqueado, com o motivo explicado."><Chips options={catOpts("legal_nature")} value={f.v.accepted_legal_natures} onChange={f.set("accepted_legal_natures")} /></Field>
        <Field label="Qualificações exigidas (verificadas)" wide hint="Só vale qualificação verificada pela plataforma."><Chips options={catOpts("qualification_type")} value={f.v.required_certifications} onChange={f.set("required_certifications")} /></Field>
        <Field label="Outros requisitos" hint="Um por linha — viram itens do checklist da candidatura" wide><TextArea rows={4} value={f.v.requirements} onChange={f.set("requirements")} /></Field>
        <Field label="Situação"><Select value={f.v.status} onChange={f.set("status")} options={[["draft", "Rascunho"], ["open", "Aberta para inscrições"], ["closed", "Encerrada"], ["archived", "Arquivada"]]} /></Field>
        <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>{id ? "Salvar alterações" : "Criar chamada"}</Button></div>
      </form>
    </>
  );
}

export function CallApplications({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/calls/${id}/applications?offset=${offset}`, [offset]);
  const [open, setOpen] = useState<any>(null);
  return (
    <>
      <PageHead title="Candidaturas recebidas" sub="Ordene pela compatibilidade e abra cada candidatura para triagem e diligência."
        back={<Link to={`/oportunidades/${id}`} className="back">Chamada</Link>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma candidatura recebida ainda."}>
        <table className="table">
          <thead><tr><th>OSC</th><th>Projeto</th><th>Situação</th><th>Compatibilidade</th><th>Compliance</th></tr></thead>
          <tbody>
            {data?.items.map((a: any) => (
              <tr key={a.id}>
                <td><Link to={`/candidaturas/${a.id}`}>{a.osc_name}</Link></td>
                <td>{a.project_title || "—"}</td>
                <td><Pill status={a.status} /></td>
                <td>{a.match ? <button className="linkish" onClick={() => setOpen(a)}>{MATCH_STATE[a.match.recommended_state]?.label} {a.match.score !== null && `· ${Math.round(a.match.score)}`}</button> : "—"}</td>
                <td><Pill status={a.compliance_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={!!open} title="Bloqueios identificados" onClose={() => setOpen(null)}>
        {open?.match?.blockers?.length ? <ul className="list-bad">{open.match.blockers.map((b: string) => <li key={b}>{b}</li>)}</ul> : <p>Sem bloqueios. Abra a candidatura para ver a explicação completa.</p>}
        <p className="muted">Situação: {label(open?.status)}</p>
      </Modal>
    </>
  );
}
