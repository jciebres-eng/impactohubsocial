// Biblioteca de Soluções de Impacto: busca por intenção, 7 modos de visão, perfil com proveniência, comparador e ações guiadas.
import { NetworkView } from "./institution_extra";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { date, money, pct } from "../format";
import { Link, navigate, useLocation } from "../router";
import { useSession } from "../session";
import { Bars, Button, Chips, Field, Group, Input, KeyValue, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";
import { UFS } from "./public";

export const ODS_NAMES: Record<number, string> = { 1: "Erradicação da pobreza", 2: "Fome zero", 3: "Saúde e bem-estar", 4: "Educação de qualidade", 5: "Igualdade de gênero", 6: "Água e saneamento",
  7: "Energia limpa", 8: "Trabalho e crescimento", 9: "Indústria e inovação", 10: "Redução das desigualdades", 11: "Cidades sustentáveis", 12: "Consumo responsável",
  13: "Ação climática", 14: "Vida na água", 15: "Vida terrestre", 16: "Paz e instituições", 17: "Parcerias" };
const KIND: [string, string][] = [["project", "Projeto"], ["idea", "Ideia"], ["methodology", "Metodologia"], ["social_tech", "Tecnologia social"], ["academic", "Projeto acadêmico"]];
const STAGE: [string, string][] = [["idea", "Ideia"], ["proposal", "Proposta"], ["developing", "Em desenvolvimento"], ["running", "Em execução"], ["completed", "Realizado"]];
const VIEWS: [string, string][] = [["card", "Cartões"], ["list", "Lista"], ["map", "Mapa"], ["ods", "Por ODS"], ["case", "Cases"], ["funding", "Financiamento"], ["research", "Pesquisa"]];
const TRUST_TONE: Record<string, string> = { verified: "good", evidenced: "good", documented: "warn", self_declared: "muted", in_review: "warn", unverified: "muted" };
const LICENSE: [string, string][] = [["all_rights_reserved", "Todos os direitos reservados"], ["cc_by", "CC BY (atribuição)"], ["cc_by_sa", "CC BY-SA"], ["cc_by_nc", "CC BY-NC"],
  ["cc_by_nc_sa", "CC BY-NC-SA"], ["public_domain", "Domínio público"], ["custom", "Condições próprias"]];
const score = (v: number | null | undefined) => (v === null || v === undefined ? "sem dados" : `${Math.round(v)}/100`);

function TruthPills({ s }: { s: any }) {
  return (
    <span className="stack-row">
      <Pill tone={s.labels.proven ? "good" : s.kind === "idea" ? "warn" : "muted"}>{s.labels.primary}</Pill>
      <Pill tone={TRUST_TONE[s.trust_level] || "muted"}>{s.labels.trust}</Pill>
      {s.disputed && <Pill tone="bad">Autoria em disputa</Pill>}
      {s.is_demo && <Pill tone="warn">DEMO</Pill>}
    </span>
  );
}

function Scores({ s }: { s: any }) {
  return (
    <p className="muted small">
      Maturidade do cadastro: {score(s.scores.maturity)} · Evidência: {score(s.scores.evidence)} · Replicabilidade: {score(s.scores.replicability)}
    </p>
  );
}

function SolutionCard({ s, picked, onPick, onSave }: { s: any; picked: boolean; onPick: () => void; onSave: () => void }) {
  return (
    <article className="panel solution-card" aria-label={s.title}>
      <TruthPills s={s} />
      <h3><Link to={`/solucoes/${s.id}`}>{s.title}</Link></h3>
      <p className="muted small">{s.labels.kind}{s.uf ? ` · ${s.city ? s.city + "/" : ""}${s.uf}` : ""}{s.budget_cents != null ? ` · orçamento ${money(s.budget_cents)}` : ""}</p>
      <p>{s.summary.length > 220 ? s.summary.slice(0, 220) + "…" : s.summary}</p>
      {s.ods.length > 0 && <p className="small">ODS: {s.ods.map((o: number) => `${o} ${ODS_NAMES[o]}`).join(" · ")}</p>}
      {s.sharing_label && <p className="small">Compartilhamento: {s.sharing_label}</p>}
      {s.proponent && <p className="small muted">Proponente: {s.proponent.legal_nature_code ? `natureza declarada: ${s.proponent.legal_nature_code}` : "natureza não informada"}{(s.proponent.verified_qualifications || []).length ? ` · qualificações verificadas: ${s.proponent.verified_qualifications.length}` : " · sem qualificação verificada"}</p>}
      {s.funding_readiness && (
        <details className="small"><summary>Prontidão para financiamento: {s.funding_readiness.score == null ? "sem dados" : `${Math.round(s.funding_readiness.score)}/100`}{s.funding_readiness.ready ? " (critérios atendidos)" : ""}</summary>
          <ul>{(s.funding_readiness.criteria || []).map((c: any) => <li key={c.code}>{c.status === "met" ? "Atende" : "Falta"}: {c.label} — {c.detail}</li>)}</ul>
          <p className="muted">Indicador de preenchimento; não é aprovação nem garantia de recurso.</p></details>)}
      {s.demo_notice && <p className="small" role="note">{s.demo_notice}</p>}
      <Scores s={s} />
      {s.relevance && s.relevance.why.length > 0 && (
        <details><summary>Por que apareceu{s.relevance.score != null ? ` (relevância ${Math.round(s.relevance.score)}/100)` : ""}</summary>
          <ul>{s.relevance.why.map((w: string, i: number) => <li key={i}>{w}</li>)}</ul>
          {s.relevance.confidence != null && <p className="muted small">Confiança no cálculo: {pct(s.relevance.confidence)} (só entram sinais com dados).</p>}
        </details>)}
      <div className="stack-row">
        <label className="check"><input type="checkbox" checked={picked} onChange={onPick} /> Comparar</label>
        <Button variant="ghost" onClick={onSave}>Salvar</Button>
      </div>
    </article>
  );
}

const PERSONAS: [string, string, string][] = [
  ["Tenho um problema", "problem", "Ex.: jovens sem atividade no contraturno, em área rural"],
  ["Tenho dinheiro para investir", "invest", "Ex.: tenho R$ 250 mil para educação no Mato Grosso"],
  ["Tenho uma ideia", "idea", "Ex.: biblioteca móvel para comunidades ribeirinhas"],
  ["Tenho um projeto que funciona", "works", ""],
];

export function Library() {
  const { query } = useLocation();
  const { me } = useSession();
  const kind = me?.active_org?.kind;
  const [text, setText] = useState(query.get("q") || "");
  const f = useForm<any>({ kinds: [], stages: [], ods: [], ufs: [], trust_min: "", replicable: false, seeking_funding: false, proven: false, legal_natures: [], qualifications: [], modalities: [], funding_ready: false, sharing: [], min: "", max: "", sort: "relevance" });
  const [view, setView] = useState("card");
  const [offset, setOffset] = useState(0);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const [persona, setPersona] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);
  const { run } = useAction();
  const agg = useLoad<any>("/v1/solutions/aggregates");
  const recs = useLoad<any>("/v1/solutions/recommendations");

  const payload = useMemo(() => {
    const p: any = { text: text.trim() || null, limit: 12, offset, view, sort: f.v.sort };
    const kinds = view === "research" ? ["academic", "methodology", "social_tech"] : view === "case" ? ["project"] : f.v.kinds;
    if (kinds.length) p.kinds = kinds;
    const stages = view === "case" ? ["running", "completed"] : f.v.stages;
    if (stages.length) p.stages = stages;
    if (f.v.ods.length) p.ods = f.v.ods.map(Number);
    if (f.v.ufs.length) p.ufs = f.v.ufs;
    if (f.v.trust_min) p.trust_min = f.v.trust_min;
    if (f.v.replicable) p.replicable = true;
    if (f.v.seeking_funding || view === "funding") p.seeking_funding = true;
    if (f.v.proven) p.proven = true;
    if (f.v.legal_natures.length) p.legal_natures = f.v.legal_natures;
    if (f.v.qualifications.length) p.qualifications = f.v.qualifications;
    if (f.v.modalities.length) p.modalities = f.v.modalities;
    if (f.v.funding_ready) p.funding_ready = true;
    if (f.v.sharing.length) p.sharing = f.v.sharing;
    const min = parseFloat(String(f.v.min).replace(",", ".")), max = parseFloat(String(f.v.max).replace(",", "."));
    if (!isNaN(min)) p.budget_min_cents = Math.round(min * 100);
    if (!isNaN(max)) p.budget_max_cents = Math.round(max * 100);
    return p;
  }, [text, offset, view, f.v]);

  const search = async () => {
    setLoading(true); setErr(null);
    try { setRes(await api.post("/v1/solutions/search", payload)); } catch (e: any) { setErr(e.message || "Erro na busca"); } finally { setLoading(false); }
  };
  useEffect(() => { search(); /* eslint-disable-next-line */ }, [view, offset, f.v.kinds, f.v.stages, f.v.ods, f.v.ufs, f.v.trust_min, f.v.replicable, f.v.seeking_funding, f.v.proven, f.v.sort, f.v.legal_natures, f.v.qualifications, f.v.modalities, f.v.funding_ready, f.v.sharing]);
  const togglePick = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length >= 4 ? p : [...p, id]));
  const save = (id: string) => run(() => api.put(`/v1/solutions/${id}/save`, {}), "Salva na sua lista");
  const intent = res?.intent;
  const items: any[] = res?.items || [];

  const byOds = useMemo(() => {
    const g: Record<number, any[]> = {};
    items.forEach((s) => (s.ods.length ? s.ods : [0]).forEach((o: number) => (g[o] = g[o] || []).push(s)));
    return g;
  }, [items]);

  return (
    <>
      <PageHead title="Biblioteca de soluções" sub="Ideias, projetos, metodologias e cases de impacto — com a origem e o nível de verificação sempre à vista."
        actions={<><Link to="/solucoes/nova" className="btn btn-primary">Cadastrar solução</Link></>} />
      <Panel>
        <form role="search" className="form" onSubmit={(e: any) => { e.preventDefault(); setOffset(0); search(); }}>
          <Field label="O que você procura?" wide hint="Escreva do seu jeito: tema, público, lugar, orçamento. Ex.: “artes caps”, “educação rural”, “tenho R$ 250 mil para idosos em MT”.">
            <Input value={text} onChange={setText} maxLength={500} placeholder="Descreva a busca" aria-describedby="persona-help" />
          </Field>
          <div className="stack-row">
            <Button type="submit" variant="primary" busy={loading}>Buscar</Button>
            <Button variant="ghost" onClick={() => setShowFilters((v) => !v)} aria-expanded={showFilters}>Filtros</Button>
          </div>
        </form>
        <div className="chips" id="persona-help" role="group" aria-label="Pontos de partida">
          {PERSONAS.map(([l, k, ex]) => (
            <button key={k} type="button" className={`chip${persona === k ? " chip-on" : ""}`} aria-pressed={persona === k}
              onClick={() => { setPersona(k); if (k === "works") navigate("/solucoes/nova"); else if (k === "idea") { f.set("kinds")(["idea"]); setText(""); } else { setText(ex.replace("Ex.: ", "")); } }}>{l}</button>
          ))}
        </div>
        {persona && persona !== "works" && <p className="muted small">{PERSONAS.find((p) => p[1] === persona)?.[2]}</p>}
        {showFilters && (
          <div className="form" aria-label="Filtros">
            <Group label="Tipo"><Chips options={KIND} value={f.v.kinds} onChange={f.set("kinds")} /></Group>
            <Group label="Estágio"><Chips options={STAGE} value={f.v.stages} onChange={f.set("stages")} /></Group>
            <Group label="ODS"><Chips options={Object.entries(ODS_NAMES).map(([k, v]) => [k, `${k} ${v}`])} value={f.v.ods} onChange={f.set("ods")} /></Group>
            <Group label="UF"><Chips options={UFS.map((u) => [u, u])} value={f.v.ufs} onChange={f.set("ufs")} /></Group>
            <Group label="Natureza jurídica do proponente"><Chips options={[["association", "Associação"], ["foundation", "Fundação"], ["cooperative", "Cooperativa"], ["collective", "Coletivo"], ["academic_institution", "Instituição acadêmica"], ["company", "Empresa"], ["public_body", "Órgão público"]]} value={f.v.legal_natures} onChange={f.set("legal_natures")} /></Group>
            <Group label="Qualificações verificadas do proponente"><Chips options={[["osc", "OSC"], ["oscip", "OSCIP"], ["os", "OS"], ["cebas", "CEBAS"], ["utilidade_publica_federal", "Utilidade pública federal"]]} value={f.v.qualifications} onChange={f.set("qualifications")} /></Group>
            <Group label="Modalidade de recurso"><Chips options={[["donation", "Doação"], ["sponsorship", "Patrocínio"], ["partnership", "Parceria"], ["public_call", "Edital"], ["incentive_law", "Lei de incentivo"], ["amendment", "Emenda"]]} value={f.v.modalities} onChange={f.set("modalities")} /></Group>
            <Group label="Compartilhamento"><Chips options={[["public", "Pública"], ["shareable", "Compartilhável"], ["shareable_on_request", "Sob solicitação"], ["restricted_use", "Uso restrito"]]} value={f.v.sharing} onChange={f.set("sharing")} /></Group>
            <label className="check"><input type="checkbox" checked={f.v.funding_ready} onChange={(e: any) => f.set("funding_ready")(e.target.checked)} /> Só prontas para financiamento (critérios abaixo, sem garantia)</label>
            <Field label="Orçamento mínimo (R$)"><Input value={f.v.min} onChange={f.set("min")} inputMode="decimal" /></Field>
            <Field label="Orçamento máximo (R$)"><Input value={f.v.max} onChange={f.set("max")} inputMode="decimal" /></Field>
            <Field label="Verificação mínima"><Select value={f.v.trust_min} onChange={f.set("trust_min")} placeholder="Qualquer"
              options={[["documented", "Documentada"], ["evidenced", "Evidenciada"], ["verified", "Verificada"]]} /></Field>
            <Field label="Ordenar por"><Select value={f.v.sort} onChange={f.set("sort")} options={[["relevance", "Relevância"], ["recent", "Mais recentes"], ["evidence", "Mais evidência cadastrada"], ["budget", "Menor orçamento"]]} /></Field>
            <label className="check"><input type="checkbox" checked={f.v.replicable} onChange={(e: any) => f.set("replicable")(e.target.checked)} /> Só replicáveis</label>
            <label className="check"><input type="checkbox" checked={f.v.seeking_funding} onChange={(e: any) => f.set("seeking_funding")(e.target.checked)} /> Buscando financiamento</label>
            <label className="check"><input type="checkbox" checked={f.v.proven} onChange={(e: any) => f.set("proven")(e.target.checked)} /> Quero algo que já funcionou</label>
            <Button variant="primary" onClick={() => { setOffset(0); search(); }}>Aplicar</Button>
          </div>
        )}
      </Panel>

      <div role="tablist" aria-label="Modos de visualização" className="chips" style={{ margin: "12px 0" }}>
        {VIEWS.map(([k, l]) => <button key={k} role="tab" aria-selected={view === k} className={`chip${view === k ? " chip-on" : ""}`} onClick={() => { setView(k); setOffset(0); }}>{l}</button>)}
      </div>

      {intent && (intent.concepts.length > 0 || intent.territory.ufs.length > 0 || intent.budget || intent.ods.length > 0) && (
        <p className="muted small" aria-live="polite">Entendemos: {[
          ...intent.concepts.map((c: any) => c.how === "fuzzy" ? `“${c.matched}” como “${c.corrected_to}”` : c.label),
          ...intent.territory.ufs.map((u: string) => `território ${u}`), intent.budget ? `orçamento (${intent.budget.kind === "have" ? "disponível" : "faixa"})` : "",
          ...intent.ods.slice(0, 3).map((o: number) => `ODS ${o}`)].filter(Boolean).join(" · ")}. A IA não é necessária para esta interpretação.</p>
      )}

      <StateView loading={loading && !res} error={err} onRetry={search}>
        {view === "map" && (
          <Panel title="Mapa por UF" id="mapa-uf">
            <p className="muted small">Quantidade de soluções publicadas por UF (grade acessível; não usa mapas externos). Selecione uma UF para filtrar.</p>
            <div className="uf-grid" role="list">
              {UFS.map((u) => { const n = (agg.data?.by_uf || []).find((x: any) => x.uf === u)?.solutions || 0; const on = f.v.ufs.includes(u);
                return <button key={u} role="listitem" className={`chip${on ? " chip-on" : ""}`} aria-pressed={on} disabled={!n} onClick={() => f.set("ufs")(on ? f.v.ufs.filter((x: string) => x !== u) : [...f.v.ufs, u])}>{u}: {n}</button>; })}
            </div>
          </Panel>)}
        {view === "ods" && (
          <Panel title="Por ODS">
            <Bars rows={Object.entries(byOds).map(([o, l]) => ({ label: o === "0" ? "Sem ODS informado" : `ODS ${o} · ${ODS_NAMES[+o]}`, value: l.length }))} format={(v) => `${v} solução(ões)`} />
          </Panel>)}
        {items.length === 0 && res ? (
          <div className="state state-empty">
            <h2>Nenhuma solução encontrada</h2>
            <ul>{(res.empty?.suggestions || []).map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>
            <Link to="/solucoes/nova" className="btn btn-ghost">Cadastrar uma solução</Link>
          </div>
        ) : view === "list" || view === "research" ? (
          <ul className="rows" aria-label="Resultados">
            {items.map((s) => (
              <li key={s.id}><span><Link to={`/solucoes/${s.id}`}>{s.title}</Link> <span className="muted small">{s.labels.kind} · {s.uf || "—"} · fonte: {s.source_name || s.source_type}</span></span><TruthPills s={s} /></li>))}
          </ul>
        ) : view === "funding" ? (
          <ul className="rows" aria-label="Soluções buscando financiamento">
            {items.map((s) => (
              <li key={s.id}><span><Link to={`/solucoes/${s.id}`}>{s.title}</Link> <span className="muted small">precisa de {money(s.needed_cents)} · captado {money(s.raised_cents)} · {s.labels.primary}</span></span><TruthPills s={s} /></li>))}
          </ul>
        ) : view === "ods" ? (
          Object.entries(byOds).sort((a, b) => +a[0] - +b[0]).map(([o, l]) => (
            <Panel key={o} title={o === "0" ? "Sem ODS informado" : `ODS ${o} · ${ODS_NAMES[+o]}`}>
              <ul className="rows">{l.map((s) => <li key={s.id}><Link to={`/solucoes/${s.id}`}>{s.title}</Link><TruthPills s={s} /></li>)}</ul>
            </Panel>))
        ) : (
          <div className="grid-home">{items.map((s) => <SolutionCard key={s.id} s={s} picked={picked.includes(s.id)} onPick={() => togglePick(s.id)} onSave={() => save(s.id)} />)}</div>
        )}
        <Pager data={res} offset={offset} setOffset={setOffset} />
        {res?.capped && <p className="muted small">A busca considerou os {res.candidate_cap} candidatos mais relacionados; refine os filtros para ver outros.</p>}
      </StateView>

      {picked.length > 0 && (
        <div className="tray" role="region" aria-label="Comparador">
          <span>{picked.length} selecionada(s) {picked.length < 2 ? "— escolha ao menos 2" : ""}</span>
          <Button variant="primary" disabled={picked.length < 2} onClick={() => navigate(`/solucoes/comparar?ids=${picked.join(",")}`)}>Comparar</Button>
          <Button variant="ghost" onClick={() => setPicked([])}>Limpar</Button>
        </div>)}

      {recs.data && recs.data.items.length > 0 && (
        <Panel title="Recomendadas para você">
          <p className="muted small">Base: {recs.data.basis.join(", ")}. {recs.data.note}</p>
          <ul className="rows">{recs.data.items.slice(0, 5).map((s: any) => (
            <li key={s.id}><span><Link to={`/solucoes/${s.id}`}>{s.title}</Link> <span className="muted small">{(s.why || []).join(" · ")}</span></span><span className="muted">{Math.round(s.score)}/100</span></li>))}</ul>
        </Panel>)}
      {recs.data && recs.data.items.length === 0 && recs.data.message && (kind === "company" || kind === "individual" || kind === "government") && (
        <p className="muted small">{recs.data.message} <Link to="/solucoes/preferencias">Ajustar tese e personalização</Link></p>)}
      <Assistant />
    </>
  );
}

function Assistant() {
  const [q, setQ] = useState("");
  const [r, setR] = useState<any>(null);
  const { busy, run } = useAction();
  return (
    <Panel title="Copiloto da biblioteca" quiet>
      <p className="muted small">Responde somente com soluções realmente cadastradas. Não gera texto por modelo de linguagem.</p>
      <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/solutions/assistant", { text: q })).then(setR); }}>
        <Field label="Pergunte" wide><Input value={q} onChange={setQ} placeholder="Ex.: o que existe para saúde mental com arte?" /></Field>
        <Button type="submit" busy={busy} disabled={q.trim().length < 2}>Perguntar</Button>
      </form>
      {r && (<div aria-live="polite"><p>{r.message}</p>
        <ul>{r.suggestions.map((s: any) => <li key={s.id}><Link to={`/solucoes/${s.id}`}>{s.title}</Link> — {s.label}, {s.trust}</li>)}</ul>
        {r.suggestions.length === 0 && <ul>{r.next_steps.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>}
        <p className="muted small">{r.disclaimer}</p></div>)}
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ comparador
export function Compare() {
  const { query } = useLocation();
  const ids = (query.get("ids") || "").split(",").filter(Boolean);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const { busy, run } = useAction();
  const { me } = useSession();
  // v0.25.0: sem `?ids=` (quem abre a tela pelo endereço, ou volta para ela) a tela chamava a API
  // com lista vazia e mostrava "Dados inválidos". A API compara de 2 a 4 — com menos, a tela explica.
  const poucas = ids.length < 2;
  useEffect(() => { if (poucas) return; api.post("/v1/solutions/compare", { ids }).then(setRes).catch((e: any) => setErr(e.message)); /* eslint-disable-next-line */ }, [query.get("ids")]);
  const rows: [string, (c: any) => any][] = [
    ["Situação", (c) => c.labels.primary], ["Verificação", (c) => c.labels.trust], ["Tipo", (c) => c.labels.kind], ["Território", (c) => (c.uf ? `${c.city ? c.city + "/" : ""}${c.uf}` : "—")],
    ["Orçamento", (c) => money(c.budget_cents)], ["Necessidade de captação", (c) => (c.seeking_funding ? money(c.needed_cents) : "—")],
    ["ODS", (c) => c.ods.map((o: number) => `${o} ${ODS_NAMES[o]}`).join(", ") || "—"], ["Beneficiários", (c) => c.beneficiaries_count ?? "—"],
    ["Maturidade do cadastro", (c) => score(c.scores.maturity)], ["Evidência cadastrada", (c) => score(c.scores.evidence)], ["Replicabilidade", (c) => score(c.scores.replicability)],
    ["Licença", (c) => LICENSE.find((l) => l[0] === c.license)?.[1] || c.license], ["Adaptação autorizada", (c) => (c.allow_adaptation ? "Sim" : "Não")], ["Replicação autorizada", (c) => (c.allow_replication ? "Sim" : "Não")],
    ["Problema", (c) => c.problem || "—"], ["Abordagem", (c) => c.approach || "—"], ["Limitações declaradas", (c) => c.limitations || "—"],
  ];
  return (
    <>
      <PageHead title="Comparar soluções" sub="Lado a lado, com a mesma régua de verdade: o que é declarado e o que é verificado." back={<Link to="/solucoes" className="back">Biblioteca</Link>} />
      <StateView loading={!poucas && !res && !err} error={err}
                 empty={poucas && <><h2>Escolha de 2 a 4 soluções para comparar</h2>
                   <p>Na biblioteca, marque as soluções e use "Comparar".</p>
                   <Link to="/solucoes" className="btn btn-ink">Abrir a biblioteca</Link></>}>
        {res && (<>
          <div className="table-wrap"><table className="table" aria-label="Comparação de soluções">
            <thead><tr><th scope="col">Critério</th>{res.columns.map((c: any) => <th scope="col" key={c.id}><Link to={`/solucoes/${c.id}`}>{c.title}</Link></th>)}</tr></thead>
            <tbody>{rows.map(([l, fn]) => <tr key={l}><th scope="row">{l}</th>{res.columns.map((c: any) => <td key={c.id}>{String(fn(c))}</td>)}</tr>)}</tbody>
          </table></div>
          <p className="muted small">Menor orçamento: {res.columns.find((c: any) => c.id === res.highlights.lowest_budget)?.title || "—"} · Mais evidência cadastrada: {res.columns.find((c: any) => c.id === res.highlights.highest_evidence)?.title || "—"}. {res.note}</p>
          {me?.active_org?.kind !== "platform" && (
            <Panel title="Combinar estas soluções">
              <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/solutions/combine", { ids, title }), "Combinação analisada").then((r) => setRes((x: any) => ({ ...x, combination: r }))); }}>
                <Field label="Nome da combinação"><Input value={title} onChange={setTitle} /></Field>
                <Button type="submit" variant="primary" busy={busy} disabled={title.trim().length < 3}>Analisar combinação</Button>
              </form>
              {res.combination && <CombinationView c={res.combination} />}
            </Panel>)}
        </>)}
      </StateView>
    </>
  );
}

function CombinationView({ c }: { c: any }) {
  const L = ({ t, items }: { t: string; items: any[] }) => items.length ? <><h3>{t}</h3><ul>{items.map((x, i) => <li key={i}>{typeof x === "string" ? x : `${(x.titles || [x.title]).join(" + ")}: ${x.reason}`}</li>)}</ul></> : null;
  return (<div><p><Pill tone="warn">{c.status}</Pill></p>
    <L t="Complementaridades" items={c.complementary} /><L t="Sobreposições" items={c.overlaps} /><L t="Conflitos" items={c.conflicts} />
    <L t="Dependências" items={c.dependencies} /><L t="Oportunidades" items={c.opportunities} /><L t="Observações" items={c.notes} />
    <p className="muted small">{c.disclaimer}</p></div>);
}

// ------------------------------------------------------------------------------------------------ perfil
export function Profile({ id }: { id: string }) {
  const { data: s, error, loading, reload } = useLoad<any>(`/v1/solutions/${id}`);
  const { me } = useSession();
  const kind = me?.active_org?.kind;
  const { busy, run } = useAction();
  const [modal, setModal] = useState<string | null>(null);
  const similar = useLoad<any>(modal === "similar" ? `/v1/solutions/${id}/similar` : null, [modal]);
  const [adapt, setAdapt] = useState<any>(null);
  const af = useForm<any>({ uf: "", city: "", budget: "", months: "" });
  const rf = useForm<any>({ kind: "info", message: "" });
  const rep = useForm<any>({ uf: "", city: "", pub: false });
  const dispute = useForm<any>({ claim: "" });
  const [matchRes, setMatchRes] = useState<any>(null);
  const [pub, setPub] = useState(false);
  if (!s) return <StateView loading={loading} error={error} onRetry={reload} />;
  const own = s.is_owner;
  const mine = s.mine || {};
  const close = () => setModal(null);
  const rpv = s.replication_profile;
  return (
    <>
      <PageHead title={s.title} sub={<TruthPills s={s} />} back={<Link to="/solucoes" className="back">Biblioteca</Link>}
        actions={own ? <><Link to={`/solucoes/${id}/editar`} className="btn btn-ghost">Editar</Link>
          {s.visibility === "draft" && <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/solutions/${id}/publish`), "Publicada. Você responde pela autorização e pela titularidade declaradas.").then(reload)}>Publicar</Button>}
          {s.visibility === "published" && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/solutions/${id}/request-review`), "Pedido enviado à administração").then(reload)}>Pedir verificação</Button>}</> : undefined} />
      {s.access && s.access.level !== "full" && <p role="note" className="panel"><strong>Acesso limitado.</strong> {s.access.message}</p>}
      {s.visibility !== "published" && <p role="status"><Pill tone="warn">{s.visibility === "draft" ? "Rascunho — visível só para a sua organização" : s.visibility}</Pill></p>}
      {s.demo_notice && <p role="note"><strong>{s.demo_notice}</strong></p>}
      {s.disputed && <p role="alert">A autoria ou o conteúdo desta solução está em disputa; a administração fará a análise.</p>}
      <div className="grid-home">
        <Panel title="Resumo">
          <p>{s.summary}</p>
          <KeyValue items={[["Autor", `${s.author.name} (${s.author.kind})`], ["Território", s.uf ? `${s.city ? s.city + "/" : ""}${s.uf}` : "—"], ["Orçamento", money(s.budget_cents)],
            ["Necessidade de captação", s.seeking_funding ? money(s.needed_cents) : "Não busca financiamento"], ["Captado", money(s.raised_cents)], ["Duração", s.duration_months ? `${s.duration_months} meses` : "—"],
            ["Beneficiários", s.beneficiaries_count ?? "—"], ["ODS", s.ods.map((o: number) => `${o} ${ODS_NAMES[o]}`).join(", ") || "—"], ["ESG", s.esg.join(", ") || "—"],
            ["Licença", LICENSE.find((l) => l[0] === s.license)?.[1]], ["Replicação", s.allow_replication ? "Autorizada" : "Não autorizada"], ["Adaptação", s.allow_adaptation ? "Autorizada" : "Não autorizada"],
            ["Atribuição", s.attribution_required ? "Obrigatória" : "Não exigida"]]} />
        </Panel>
        <Panel title="Origem e verificação">
          <KeyValue items={[["Nível", `${s.labels.trust}`], ["Fonte", s.provenance.source_name || s.provenance.source_type], ["Data da fonte", date(s.provenance.source_date)], ["Verificada em", date(s.provenance.verified_at)],
            ["Nota da verificação", s.provenance.verification_note || "—"], ["Versão", `v${s.provenance.current_version}`], ["Atualizada em", date(s.provenance.updated_at)]]} />
          <p className="muted small">“Autodeclarado” significa que a informação vem do próprio autor e ainda não foi conferida pela plataforma. Só a administração altera este nível, com base em evidências aceitas.</p>
        </Panel>
        <Panel title="Pontuações explicadas">
          <p className="small"><strong>Maturidade do cadastro: {score(s.scores_detail.maturity.score)}</strong> — {s.scores_detail.maturity.basis}. {s.scores_detail.maturity.missing.length > 0 && `Faltam: ${s.scores_detail.maturity.missing.join(", ")}.`}</p>
          <p className="small"><strong>Evidência: {score(s.scores_detail.evidence.score)}</strong> — {(s.scores_detail.evidence.reasons || []).join("; ") || s.scores_detail.evidence.note}</p>
          <p className="small"><strong>Replicabilidade: {score(s.scores_detail.replicability.score)}</strong> — {s.scores_detail.replicability.score == null ? s.scores_detail.replicability.note : `${s.scores_detail.replicability.basis}. Confiança ${pct(s.scores_detail.replicability.confidence)}.`}</p>
          {s.scores_detail.replicability.negatives?.length > 0 && <p className="small">Pontos de atenção: {s.scores_detail.replicability.negatives.join("; ")}.</p>}
          <p className="muted small">Pontuações ajudam a comparar; não medem eficácia nem qualidade.</p>
        </Panel>
      </div>
      {(s.problem || s.approach || s.objectives) && (
        <Panel title="Descrição">
          {s.problem && <><h3>Problema</h3><p>{s.problem}</p></>}{s.objectives && <><h3>Objetivos</h3><p>{s.objectives}</p></>}{s.approach && <><h3>Solução / metodologia</h3><p>{s.approach}</p></>}
          {s.learnings && <><h3>Aprendizados</h3><p>{s.learnings}</p></>}{s.challenges && <><h3>Desafios</h3><p>{s.challenges}</p></>}{s.limitations && <><h3>Limitações</h3><p>{s.limitations}</p></>}
        </Panel>)}
      <Panel title="Resultados e evidências">
        {s.results.length === 0 ? <p className="muted">Nenhum resultado registrado.</p> : (
          <ul className="rows">{s.results.map((r: any) => <li key={r.id}><span>{r.indicator}: <strong>{r.value}{r.unit ? ` ${r.unit}` : ""}</strong>{r.baseline != null ? ` (linha de base ${r.baseline})` : ""}{r.period ? ` · ${r.period}` : ""}</span><Pill tone={r.status === "validated" ? "good" : "muted"}>{r.status_label}</Pill></li>)}</ul>)}
        {s.evidence.length === 0 ? <p className="muted">Nenhuma evidência anexada.</p> : (
          <ul className="rows">{s.evidence.map((e: any) => <li key={e.id}><span>{e.title} <span className="muted small">({e.kind}{e.url ? `, ${new URL(e.url).hostname}` : ""})</span></span><Pill tone={e.status === "accepted" ? "good" : e.status === "rejected" ? "bad" : "warn"}>{e.status_label}</Pill></li>)}</ul>)}
      </Panel>
      {rpv && (
        <Panel title="Perfil de replicação (declarado pelo autor)">
          <KeyValue items={[["Simplicidade (1–5)", rpv.simplicity ?? "—"], ["Custo", rpv.cost_level ?? "—"], ["Dependência de infraestrutura", rpv.infra_dependency ?? "—"], ["Dependência territorial", rpv.territorial_dependency ?? "—"],
            ["Especialistas", rpv.specialists_needed ?? "—"], ["Documentada", rpv.documented == null ? "—" : rpv.documented ? "Sim" : "Não"], ["Treinamento", rpv.training_available == null ? "—" : rpv.training_available ? "Sim" : "Não"],
            ["Adaptável em", (rpv.adaptable || []).join(", ") || "—"]]} />
        </Panel>)}
      {s.people.length > 0 && <Panel title="Autoria e equipe"><ul className="rows">{s.people.map((p: any, i: number) => <li key={i}><span>{p.name}{p.institution ? ` — ${p.institution}` : ""}</span><span className="muted">{p.role}</span></li>)}</ul></Panel>}
      {s.relationships.length > 0 && <Panel title="Relações"><ul className="rows">{s.relationships.map((r: any, i: number) => <li key={i}><Link to={`/solucoes/${r.id}`}>{r.title}</Link><span className="muted">{r.rel_type}</span></li>)}</ul></Panel>}

      {s.visibility === "published" && <Panel title="Rede da solução"><Button onClick={() => setModal("network")}>Ver rede de relações</Button> <span className="muted small">Autoria, território, ODS, temas e soluções relacionadas, em lista acessível.</span></Panel>}

      {!own && s.visibility === "published" && (
        <Panel title="O que você quer fazer?">
          <div className="stack-row" role="group" aria-label="Ações">
            <Button variant="primary" onClick={() => run(() => api.put(`/v1/solutions/${id}/save`, {}), "Salva").then(reload)}>{mine.saved ? "Salva ✓" : "Salvar"}</Button>
            <Button onClick={() => setModal("similar")}>Quero algo como este</Button>
            <Button onClick={() => setModal("adapt")}>Adaptar para meu território</Button>
            {(s.kind === "idea" || s.allow_adaptation) && kind !== "platform" && <Button onClick={() => run(() => api.post(`/v1/solutions/${id}/develop`), "Rascunho criado").then((r: any) => r && navigate(`/solucoes/${r.id}/editar`))}>Desenvolver esta ideia</Button>}
            {s.allow_replication && <Button onClick={() => setModal("replicate")}>Quero replicar</Button>}
            <Button onClick={() => setModal("request")}>Pedir informações ao autor</Button>
            {(kind === "company" || kind === "government" || kind === "individual") && <>
              <Button onClick={() => run(() => api.put(`/v1/solutions/${id}/intent`, { stage: "interested", public_identity: pub }), "Interesse registrado").then(reload)}>Tenho interesse em apoiar</Button>
              <label className="check"><input type="checkbox" checked={pub} onChange={(e: any) => setPub(e.target.checked)} /> Mostrar minha identidade ao autor</label>
              <Button variant="ghost" onClick={() => run(() => api.post(`/v1/solutions/${id}/match`)).then(setMatchRes)}>Aderência à minha tese</Button></>}
            <Button variant="ghost" onClick={() => setModal("dispute")}>Contestar autoria</Button>
            <Button variant="ghost" onClick={() => run(() => api.post("/v1/reports", { target_type: "solution", target_id: id, reason: "inappropriate" }), "Denúncia enviada à triagem")}>Denunciar</Button>
          </div>
          <p className="muted small">Ver esta página não registra interesse. A identidade do financiador é privada por padrão.{mine.intent ? ` Sua etapa atual: ${mine.intent.stage}.` : ""}</p>
          {matchRes && (<div aria-live="polite"><p><strong>Aderência: {matchRes.score == null ? "dados insuficientes" : `${Math.round(matchRes.score)}/100`}</strong> (confiança {pct(matchRes.confidence)}) — {matchRes.eligibility}</p>
            <ul>{(matchRes.why_match || []).map((w: any, i: number) => <li key={i}>{w.label}: {w.detail}</li>)}{(matchRes.risks || []).map((r: any, i: number) => <li key={"r" + i}>Risco: {r.label}</li>)}</ul><p className="muted small">{matchRes.disclaimer}</p></div>)}
        </Panel>)}
      {!own && (s.reviews.items.length > 0) && <Panel title="Avaliações de quem teve relação com a solução"><p className="muted small">{s.reviews.note} Média: {s.reviews.average}</p>
        <ul>{s.reviews.items.map((r: any, i: number) => <li key={i}>{r.rating}/5 {r.body}</li>)}</ul></Panel>}
      {s.stats && <Panel title="Interesse (organizações distintas)"><KeyValue items={[["Interessadas", s.stats.interested_orgs], ["Pediram informação", s.stats.requested_info_orgs], ["Em avaliação", s.stats.in_evaluation_orgs],
        ["Pediram adaptação", s.stats.adaptation_requests], ["Financiamento confirmado pelo autor", s.stats.funded_confirmed_orgs], ["Replicações concluídas e confirmadas", s.stats.replications.completed_confirmed], ["Salvamentos", s.stats.saves]]} /></Panel>}
      {own && <OwnerTools id={id} s={s} reload={reload} />}

      <Modal open={modal === "network"} title="Rede da solução" onClose={close}>{modal === "network" && <NetworkView id={id} />}</Modal>

      <Modal open={modal === "similar"} title="Quero algo como este" onClose={close}>
        <StateView loading={similar.loading} error={similar.error}>
          {(similar.data?.items || []).length === 0 ? <p className="muted">Não encontramos soluções parecidas. Tente “Adaptar para meu território” ou cadastre uma necessidade.</p> :
            <ul className="rows">{similar.data.items.map((x: any) => <li key={x.id}><span><Link to={`/solucoes/${x.id}`} onClick={close}>{x.title}</Link> <span className="muted small">{x.why.join(" · ")}{x.same_territory_as_me ? " · no seu território" : ""}</span></span><span>{Math.round(x.similarity)}%</span></li>)}</ul>}
          {similar.data && <p className="muted small">Critério: {similar.data.basis}.</p>}
        </StateView>
      </Modal>
      <Modal open={modal === "adapt"} title="Adaptar para meu território" onClose={close}>
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/solutions/${id}/adapt`, { uf: af.v.uf || undefined, city: af.v.city || undefined,
          budget_cents: af.v.budget ? Math.round(parseFloat(af.v.budget.replace(",", ".")) * 100) : undefined, months: af.v.months ? +af.v.months : undefined })).then(setAdapt); }}>
          <Field label="UF"><Select value={af.v.uf} onChange={af.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
          <Field label="Município"><Input value={af.v.city} onChange={af.set("city")} /></Field>
          <Field label="Orçamento disponível (R$)"><Input value={af.v.budget} onChange={af.set("budget")} inputMode="decimal" /></Field>
          <Field label="Prazo (meses)"><Input value={af.v.months} onChange={af.set("months")} inputMode="numeric" /></Field>
          <Button type="submit" variant="primary" busy={busy}>Simular adaptação</Button>
        </form>
        {adapt && (<div aria-live="polite"><p><Pill tone="warn">{adapt.label}</Pill></p>
          {adapt.status === "insufficient_data" ? <p>{adapt.message} Informe: {adapt.needed.join(", ")}.</p> : (<>
            {adapt.recommended_changes.length > 0 && <><h3>O que mudar</h3><ul>{adapt.recommended_changes.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></>}
            {adapt.risks.length > 0 && <><h3>Riscos</h3><ul>{adapt.risks.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></>}
            <h3>Próximos passos</h3><ul>{adapt.steps.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul>
            {adapt.conditions.length > 0 && <><h3>Condições</h3><ul>{adapt.conditions.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></>}
            <p className="muted small">{adapt.disclaimer}</p></>)}</div>)}
      </Modal>
      <Modal open={modal === "request"} title="Pedir ao autor" onClose={close}>
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/solutions/${id}/requests`, { kind: rf.v.kind, message: rf.v.message }), "Pedido enviado").then((r) => { if (r) { close(); reload(); } }); }}>
          <Field label="Tipo de pedido"><Select value={rf.v.kind} onChange={rf.set("kind")} options={[["info", "Mais informações"], ["contact", "Contato"], ["budget", "Orçamento"], ...(s.allow_adaptation ? [["adaptation", "Adaptação"]] : []), ...(s.allow_replication ? [["replication", "Replicação"]] : [])] as [string, string][]} /></Field>
          <Field label="Mensagem" wide><TextArea value={rf.v.message} onChange={rf.set("message")} rows={4} maxLength={3000} /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={rf.v.message.trim().length < 5}>Enviar pedido</Button>
        </form>
        <p className="muted small">O autor verá o nome da sua organização, pois este é um pedido direto.</p>
      </Modal>
      <Modal open={modal === "replicate"} title="Quero replicar" onClose={close}>
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/solutions/${id}/replications`, { target_uf: rep.v.uf, target_city: rep.v.city, public_identity: rep.v.pub }), "Interesse de replicação registrado").then((r) => r && close()); }}>
          <Field label="UF de destino"><Select value={rep.v.uf} onChange={rep.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
          <Field label="Município de destino"><Input value={rep.v.city} onChange={rep.set("city")} /></Field>
          <label className="check"><input type="checkbox" checked={rep.v.pub} onChange={(e: any) => rep.set("pub")(e.target.checked)} /> Mostrar minha identidade como replicadora</label>
          <Button type="submit" variant="primary" busy={busy} disabled={!rep.v.uf || rep.v.city.length < 2}>Registrar interesse</Button>
        </form>
        <p className="muted small">“Replicada” só aparece depois que a replicação é concluída e confirmada pelo autor.</p>
      </Modal>
      <Modal open={modal === "dispute"} title="Contestar autoria ou conteúdo" onClose={close}>
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/solutions/${id}/disputes`, { claim: dispute.v.claim }), "Contestação enviada").then((r) => { if (r) { close(); reload(); } }); }}>
          <Field label="O que está incorreto?" wide hint="Mínimo de 20 caracteres. A decisão é humana."><TextArea value={dispute.v.claim} onChange={dispute.set("claim")} rows={5} /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={dispute.v.claim.trim().length < 20}>Enviar contestação</Button>
        </form>
      </Modal>
    </>
  );
}

function OwnerTools({ id, s, reload }: { id: string; s: any; reload: () => void }) {
  const funnel = useLoad<any>(`/v1/solutions/${id}/funnel`);
  const intents = useLoad<any>(`/v1/solutions/${id}/intents`);
  const { busy, run } = useAction();
  const ev = useForm<any>({ kind: "report", title: "", url: "" });
  const rs = useForm<any>({ indicator: "", value: "", unit: "" });
  const rp = useForm<any>({ simplicity: "", cost_level: "", infra_dependency: "", territorial_dependency: "", specialists_needed: "", documented: "", training_available: "" });
  return (
    <>
      <Panel title="Funil de interesse (só você vê)">
        <StateView loading={funnel.loading} error={funnel.error}>
          <Bars rows={Object.entries(funnel.data?.funnel || {}).map(([k, v]) => ({ label: k, value: v as number }))} format={(v) => `${v} org.`} />
          <p className="muted small">{funnel.data?.note}</p>
        </StateView>
        {(intents.data?.identified || []).length > 0 && <ul className="rows">{intents.data.identified.map((i: any) => (
          <li key={i.id}><span>{i.org_name} <span className="muted small">{i.org_kind} · {i.org_uf || "—"}</span></span>
            <span className="stack-row"><Pill>{i.stage}</Pill>{i.request_accepted && !["completed"].includes(i.stage) && (
              <Select value="" onChange={(v: string) => v && run(() => api.post(`/v1/solution-intents/${i.id}/stage`, { to: v }), "Etapa confirmada").then(() => { intents.reload(); funnel.reload(); })}
                placeholder="Confirmar etapa…" options={[["negotiating", "Em negociação"], ["commitment_started", "Compromisso iniciado"], ["funded", "Financiada"], ["implementing", "Em implementação"], ["completed", "Concluída"]]} aria-label="Confirmar etapa" />)}</span></li>))}</ul>}
        <p className="muted small">{intents.data?.note}</p>
      </Panel>
      <Panel title="Evidências e resultados">
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/solutions/${id}/evidence`, { kind: ev.v.kind, title: ev.v.title, url: ev.v.url }), "Evidência enviada para revisão").then(reload); }}>
          <Field label="Tipo"><Select value={ev.v.kind} onChange={ev.set("kind")} options={[["report", "Relatório"], ["document", "Documento"], ["publication", "Publicação"], ["audit", "Auditoria"], ["photo", "Foto"], ["video", "Vídeo"], ["external_source", "Fonte externa"]]} /></Field>
          <Field label="Título"><Input value={ev.v.title} onChange={ev.set("title")} /></Field>
          <Field label="Endereço (https)"><Input value={ev.v.url} onChange={ev.set("url")} placeholder="https://" /></Field>
          <Button type="submit" busy={busy} disabled={ev.v.title.length < 3 || !ev.v.url.startsWith("https://")}>Anexar evidência</Button>
        </form>
        {s.kind !== "idea" && <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/solutions/${id}/results`, { indicator: rs.v.indicator, value: parseFloat(rs.v.value.replace(",", ".")), unit: rs.v.unit || null }), "Resultado registrado (reportado)").then(reload); }}>
          <Field label="Indicador"><Input value={rs.v.indicator} onChange={rs.set("indicator")} /></Field>
          <Field label="Valor"><Input value={rs.v.value} onChange={rs.set("value")} inputMode="decimal" /></Field>
          <Field label="Unidade"><Input value={rs.v.unit} onChange={rs.set("unit")} /></Field>
          <Button type="submit" busy={busy} disabled={rs.v.indicator.length < 2 || isNaN(parseFloat(String(rs.v.value).replace(",", ".")))}>Registrar resultado</Button>
        </form>}
        <p className="muted small">Evidências e resultados só ganham o selo “aceita/validado” pela administração.</p>
      </Panel>
      <Panel title="Perfil de replicação">
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); const v = rp.v; run(() => api.put(`/v1/solutions/${id}/replication-profile`, { simplicity: v.simplicity ? +v.simplicity : null, cost_level: v.cost_level || null,
          infra_dependency: v.infra_dependency || null, territorial_dependency: v.territorial_dependency || null, specialists_needed: v.specialists_needed || null,
          documented: v.documented === "" ? null : v.documented === "1", training_available: v.training_available === "" ? null : v.training_available === "1", adaptable: [] }), "Perfil salvo").then(reload); }}>
          <Field label="Simplicidade (1–5)"><Select value={rp.v.simplicity} onChange={rp.set("simplicity")} placeholder="—" options={[1, 2, 3, 4, 5].map((n) => [String(n), String(n)])} /></Field>
          <Field label="Custo"><Select value={rp.v.cost_level} onChange={rp.set("cost_level")} placeholder="—" options={[["low", "Baixo"], ["moderate", "Moderado"], ["high", "Alto"]]} /></Field>
          <Field label="Dependência de infraestrutura"><Select value={rp.v.infra_dependency} onChange={rp.set("infra_dependency")} placeholder="—" options={[["low", "Baixa"], ["medium", "Média"], ["high", "Alta"]]} /></Field>
          <Field label="Dependência territorial"><Select value={rp.v.territorial_dependency} onChange={rp.set("territorial_dependency")} placeholder="—" options={[["low", "Baixa"], ["medium", "Média"], ["high", "Alta"]]} /></Field>
          <Field label="Especialistas necessários"><Select value={rp.v.specialists_needed} onChange={rp.set("specialists_needed")} placeholder="—" options={[["none", "Nenhum"], ["some", "Alguns"], ["many", "Muitos"]]} /></Field>
          <Field label="Metodologia documentada"><Select value={rp.v.documented} onChange={rp.set("documented")} placeholder="—" options={[["1", "Sim"], ["0", "Não"]]} /></Field>
          <Field label="Há treinamento"><Select value={rp.v.training_available} onChange={rp.set("training_available")} placeholder="—" options={[["1", "Sim"], ["0", "Não"]]} /></Field>
          <Button type="submit" busy={busy}>Salvar perfil</Button>
        </form>
      </Panel>
    </>
  );
}
