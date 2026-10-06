// Central de Conhecimento (v0.12.0): ajuda, guias, biblioteca, FAQ, academia, eventos, suporte, parcerias, demonstração,
// solicitação de teste, boletim, "Comece aqui", pendências e preferências. Conteúdo vem sempre da API; nada é inventado aqui.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, qs } from "../api";
import { Link, navigate, useLocation } from "../router";
import { useSession } from "../session";
import { date, dateTime, label } from "../format";
import { Button, Field, Group, Input, KeyValue, PageHead, Panel, Pill, Pager, Select, StateView, TextArea, useAction, useForm, useLoad, useToast, Chips } from "../ui/kit";
import { JourneyTrail } from "../ui/trail";

// ----------------------------------------------------------------------------------------- moldura pública
export function PublicFrame({ children }: { children: ReactNode }) {
  return (
    <div className="pubhelp">
      <a className="skip" href="#conteudo">Pular para o conteúdo</a>
      <header className="pubhelp-bar">
        <Link to="/" className="brand"><span className="brand-mark" aria-hidden="true" />Impacto</Link>
        <nav aria-label="Central de ajuda">
          <Link to="/ajuda">Ajuda</Link>
          <Link to="/ajuda/academia">Academia</Link>
          <Link to="/ajuda/eventos">Eventos</Link>
          <Link to="/ajuda/demonstracao">Demonstração</Link>
          <Link to="/entrar">Entrar</Link>
        </nav>
      </header>
      <main id="conteudo" tabIndex={-1} className="pubhelp-main">{children}</main>
    </div>
  );
}

/** Páginas que exigem login: redireciona para a entrada preservando o destino. */
export function NeedLogin({ children }: { children: ReactNode }) {
  const { me, loading } = useSession();
  const { path } = useLocation();
  useEffect(() => {
    if (!loading && !me) navigate(`/entrar?proximo=${encodeURIComponent(path + location.search)}`, true);
  }, [loading, me, path]);
  if (loading || !me) return <StateView loading />;
  return <>{children}</>;
}

// ----------------------------------------------------------------------------------------- peças comuns
function Origin({ x }: { x: any }) {
  return (
    <span className="origin">
      {x.demo_label && <Pill tone="warn">{x.demo_label}</Pill>}
      {x.origin_label && !x.demo_label && <Pill tone="muted">{x.origin_label}</Pill>}
      {x.needs_review && <Pill tone="warn">Revisão necessária</Pill>}
    </span>
  );
}

function Paragraphs({ text }: { text?: string | null }) {
  if (!text) return null;
  return <>{text.split(/\n{2,}/).map((p, i) => <p key={i} className="prose">{p.split("\n").map((l, j) => <span key={j}>{j > 0 && <br />}{l}</span>)}</p>)}</>;
}

const TYPE_LABEL: Record<string, string> = { article: "Guia", faq: "FAQ", resource: "Biblioteca", course: "Curso", event: "Evento" };

function ResultList({ items }: { items: any[] }) {
  return (
    <ul className="hits">
      {items.map((i) => (
        <li key={`${i.type}-${i.id}`}>
          <Link to={i.link}><strong>{i.title}</strong></Link>
          <span className="hit-meta"><Pill tone="muted">{TYPE_LABEL[i.type] || i.type}</Pill> <Origin x={i} />{i.est_minutes ? ` ${i.est_minutes} min` : ""}</span>
          {i.summary && <p className="muted">{i.summary}</p>}
          {i.why?.length > 0 && <p className="fineprint">Por que apareceu: {i.why.join("; ")}</p>}
        </li>
      ))}
    </ul>
  );
}

function SearchBox({ initial = "", ctx }: { initial?: string; ctx?: string }) {
  const [q, setQ] = useState(initial);
  return (
    <form role="search" className="searchbox" onSubmit={(e: any) => { e.preventDefault(); if (q.trim()) navigate(`/ajuda/busca${qs({ q: q.trim(), ctx })}`); }}>
      <label className="sr-only" htmlFor="help-q">Buscar na Central de Conhecimento</label>
      <input id="help-q" className="input" value={q} onChange={(e: any) => setQ(e.target.value)} placeholder="Ex.: como enviar uma prestação de contas" maxLength={200} />
      <Button type="submit" variant="primary">Buscar</Button>
    </form>
  );
}

// ----------------------------------------------------------------------------------------- hub
export function HelpHome() {
  const { me } = useSession();
  const cats = useLoad("/v1/help/categories");
  const faqs = useLoad("/v1/help/faqs?limit=6");
  const evs = useLoad("/v1/help/events?limit=3");
  const recs = useLoad(me ? "/v1/help/recommendations" : null);
  return (
    <div className="stack-lg">
      <PageHead title="Como podemos ajudar?" sub="Guias, modelos, cursos, eventos e suporte em um só lugar." />
      <SearchBox />
      <AssistantPanel />
      {me && (
        <div className="stack-row">
          <Button variant="primary" onClick={() => navigate("/ajuda/comece-aqui")}>Comece aqui</Button>
          <Button variant="ghost" onClick={() => navigate("/ajuda/pendencias")}>O que falta para eu avançar?</Button>
          <Button variant="ghost" onClick={() => navigate("/ajuda/atividades")}>Minhas atividades</Button>
        </div>
      )}
      <Panel title="Assuntos">
        <StateView loading={cats.loading} error={cats.error} onRetry={cats.reload}>
          <ul className="cats">
            {(cats.data?.items || []).map((c: any) => (
              <li key={c.slug}>
                <Link to={`/ajuda/busca${qs({ category: c.slug })}`}><strong>{c.name}</strong></Link>
                <span className="muted">{c.description}</span>
                <span className="fineprint">{c.articles} guias · {c.resources} materiais · {c.faqs} perguntas</span>
              </li>
            ))}
          </ul>
        </StateView>
      </Panel>
      {me && recs.data?.items?.length > 0 && (
        <Panel title="Recomendado para você" quiet>
          <ul className="rows">{recs.data.items.map((r: any, i: number) => <li key={i}><Link to={r.link}>{r.title}</Link><span className="muted">{r.reason}</span></li>)}</ul>
        </Panel>
      )}
      <div className="grid-home">
        <Panel title="Perguntas frequentes" actions={<Link to="/ajuda/faq">Ver todas</Link>}>
          <StateView loading={faqs.loading} error={faqs.error} empty={faqs.data && !faqs.data.items.length && "Nenhuma pergunta publicada ainda."}>
            <ul className="rows">{(faqs.data?.items || []).map((f: any) => <li key={f.id}><Link to={`/ajuda/faq/${f.id}`}>{f.question}</Link></li>)}</ul>
          </StateView>
        </Panel>
        <Panel title="Próximos eventos" actions={<Link to="/ajuda/eventos">Agenda</Link>}>
          <StateView loading={evs.loading} error={evs.error} empty={evs.data && !evs.data.items.length && "Nenhum evento agendado."}>
            <ul className="rows">{(evs.data?.items || []).map((e: any) => <li key={e.id}><Link to={`/ajuda/eventos/${e.slug}`}>{e.title}</Link><span className="muted">{dateTime(e.starts_at)}</span></li>)}</ul>
          </StateView>
        </Panel>
        <Panel title="Fale com a gente">
          <div className="stack">
            <Link to="/ajuda/suporte/novo">Abrir um chamado</Link>
            <Link to="/ajuda/demonstracao">Agendar uma demonstração</Link>
            <Link to="/ajuda/parcerias">Propor uma parceria</Link>
            <Link to="/ajuda/boletim">Receber o boletim</Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function AssistantPanel({ ctx }: { ctx?: string }) {
  const [question, setQuestion] = useState("");
  const [out, setOut] = useState<any>(null);
  const { busy, run } = useAction();
  return (
    <Panel title="Assistente de ajuda" quiet>
      <p className="muted">Responde somente com o que está publicado na Central, mostra a fonte e diz quando não encontra. Não usa IA generativa.</p>
      <form className="searchbox" onSubmit={(e: any) => { e.preventDefault(); if (question.trim().length >= 3) run(() => api.post("/v1/help/assistant", { question: question.trim(), ctx })).then(setOut); }}>
        <label className="sr-only" htmlFor="help-ai">Pergunte ao assistente</label>
        <input id="help-ai" className="input" value={question} onChange={(e: any) => setQuestion(e.target.value)} placeholder="Pergunte algo sobre a plataforma" maxLength={300} />
        <Button type="submit" busy={busy}>Perguntar</Button>
      </form>
      {out && (
        <div className="answer" role="status">
          {out.answer ? <Paragraphs text={out.answer} /> : <p>{out.message}</p>}
          {out.sources?.length > 0 && (
            <p className="fineprint">Fontes: {out.sources.map((s: any, i: number) => <span key={i}><Link to={s.link}>{s.title}</Link>{s.demo ? " (exemplo)" : ""}{s.needs_review ? " (revisão pendente)" : ""}{i < out.sources.length - 1 ? "; " : ""}</span>)}</p>
          )}
          {out.notice && <p className="fineprint">{out.notice}</p>}
          <div className="stack-row">{(out.actions || []).map((a: any) => <Link key={a.link + a.label} to={a.link} className="btn btn-ghost">{a.label}</Link>)}</div>
        </div>
      )}
    </Panel>
  );
}

// ----------------------------------------------------------------------------------------- busca
export function HelpSearch() {
  const { query } = useLocation();
  const q = query.get("q") || "";
  const category = query.get("category") || "";
  const [type, setType] = useState("");
  const { data, loading, error, reload } = useLoad(`/v1/help/search${qs({ q, category, type, ctx: query.get("ctx") || "" })}`);
  const arts = useLoad(!q && category ? `/v1/help/articles${qs({ category })}` : null);
  return (
    <div className="stack-lg">
      <PageHead title={q ? `Resultados para “${q}”` : "Buscar na Central"} back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <SearchBox initial={q} ctx={query.get("ctx") || undefined} />
      <Select aria-label="Filtrar por tipo" value={type} onChange={setType} placeholder="Todos os tipos" options={[["article", "Guias"], ["faq", "FAQ"], ["resource", "Biblioteca"], ["course", "Cursos"], ["event", "Eventos"]]} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {data.topics?.length > 0 && <p className="muted">Assuntos reconhecidos: {data.topics.join(", ")}. A busca usa vocabulário de assuntos, sem inteligência artificial.</p>}
            {data.items.length ? <ResultList items={data.items} /> : (
              <div className="state state-empty">
                <p>{data.empty?.message || "Não encontramos conteúdo para esta busca."}</p>
                <ul>{(data.empty?.suggest || []).map((s: string) => <li key={s}>{s}</li>)}</ul>
                <Button variant="ink" onClick={() => navigate("/ajuda/suporte/novo")}>Abrir um chamado</Button>
              </div>
            )}
          </>
        )}
        {!q && category && arts.data && <ul className="rows">{arts.data.items.map((a: any) => <li key={a.slug}><Link to={a.link}>{a.title}</Link><Origin x={a} /></li>)}</ul>}
      </StateView>
    </div>
  );
}

// ----------------------------------------------------------------------------------------- ajuda contextual (widget reutilizável)
export function ContextHelp({ ctxKey }: { ctxKey: string }) {
  const [open, setOpen] = useState(false);
  const d = useLoad(open ? `/v1/help/context${qs({ key: ctxKey })}` : null);
  return (
    <span className="ctxhelp">
      <button type="button" className="btn btn-link" aria-expanded={open} onClick={() => setOpen(!open)}>Preciso de ajuda</button>
      {open && (
        <div className="panel ctxhelp-box" role="region" aria-label="Ajuda desta tela">
          <StateView loading={d.loading} error={d.error}>
            {d.data && !d.data.articles.length && !d.data.faqs.length && !d.data.resources.length && <p className="muted">Ainda não há ajuda cadastrada para esta tela.</p>}
            <ul className="rows">
              {d.data?.articles.map((a: any) => <li key={a.slug}><Link to={a.link}>{a.title}</Link><Origin x={a} /></li>)}
              {d.data?.faqs.map((f: any) => <li key={f.id}><Link to={f.link}>{f.title}</Link></li>)}
              {d.data?.resources.map((r: any) => <li key={r.slug}><Link to={r.link}>{r.title}</Link></li>)}
            </ul>
          </StateView>
          <Link to={`/ajuda/suporte/novo${qs({ page: ctxKey.split(".")[0], field: ctxKey })}`}>Abrir um chamado sobre esta tela</Link>
        </div>
      )}
    </span>
  );
}

// ----------------------------------------------------------------------------------------- guia / artigo
function Feedback({ type, id, initial }: { type: string; id: string; initial?: any }) {
  const { me } = useSession();
  const { run, busy } = useAction();
  const [sent, setSent] = useState<any>(initial ? { helpful: initial.helpful } : null);
  const [reason, setReason] = useState("");
  const [offer, setOffer] = useState(false);
  if (!me) return <p className="fineprint"><Link to="/entrar">Entre</Link> para avaliar este conteúdo.</p>;
  const send = (helpful: boolean, r?: string) => run(() => api.post("/v1/help/feedback", { target_type: type, target_id: id, helpful, reason: r || undefined }), "Obrigado pelo retorno").then((x) => { if (x) { setSent({ helpful }); setOffer(!!x.offer_support); } });
  return (
    <div className="feedback" role="group" aria-label="Este conteúdo ajudou?">
      <strong>Este conteúdo ajudou?</strong>
      <Button variant="ghost" busy={busy} onClick={() => send(true)} aria-pressed={sent?.helpful === true}>Ajudou</Button>
      <Button variant="ghost" busy={busy} onClick={() => setSent({ helpful: false, ask: true })} aria-pressed={sent?.helpful === false}>Não ajudou</Button>
      {sent?.ask && (
        <div className="stack-row">
          <Select aria-label="O que faltou?" value={reason} onChange={setReason} placeholder="O que faltou?" options={[["not_found", "Não encontrei o que procurava"], ["hard_to_understand", "Difícil de entender"], ["outdated", "Parece desatualizado"], ["need_support", "Preciso falar com alguém"], ["other", "Outro"]]} />
          <Button variant="ink" disabled={!reason} busy={busy} onClick={() => send(false, reason)}>Enviar</Button>
        </div>
      )}
      {offer && <Link to="/ajuda/suporte/novo">Abrir um chamado</Link>}
    </div>
  );
}

export function Article({ slug }: { slug: string }) {
  const { me } = useSession();
  const { data: a, loading, error, reload } = useLoad(`/v1/help/articles/${encodeURIComponent(slug)}`);
  const [checked, setChecked] = useState<number[]>([]);
  const toast = useToast();
  useEffect(() => { if (a) setChecked(a.checklist_progress || []); }, [a]);
  useEffect(() => {
    if (!a) return;
    document.title = `${a.title} — Central de Conhecimento`;
    const robots = document.createElement("meta");
    robots.name = "robots";
    robots.content = a.seo?.index ? "index,follow" : "noindex,nofollow";
    const ld = document.createElement("script");
    ld.type = "application/ld+json";
    if (a.seo?.index && a.structured_data) ld.textContent = JSON.stringify(a.structured_data);
    document.head.append(robots, ld);
    return () => { robots.remove(); ld.remove(); };
  }, [a]);
  const toggle = (i: number) => {
    const next = checked.includes(i) ? checked.filter((x) => x !== i) : [...checked, i];
    setChecked(next);
    if (me) api.put("/v1/help/checklists", { scope: `article:${slug}`, checked: next }).catch(() => toast("Não foi possível salvar o progresso", "err"));
  };
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {a && (
        <article className="stack-lg article">
          <PageHead title={a.title} sub={a.summary} back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
          <div className="stack-row"><Origin x={a} /><span className="muted">{a.category_name}{a.est_minutes ? ` · ${a.est_minutes} min de leitura` : ""}</span></div>
          {a.review_notice && <div className="banner" role="status">{a.review_notice}</div>}
          {a.regulatory && a.regulatory_source && <p className="fineprint">Fonte oficial: {a.regulatory_source}{a.regulatory_date ? ` (${date(a.regulatory_date)})` : ""}{a.valid_until ? ` · válido até ${date(a.valid_until)}` : ""}</p>}
          <Paragraphs text={a.body} />
          {a.steps?.length > 0 && (
            <Panel title="Passo a passo">
              <ol className="steps">{a.steps.map((s: any, i: number) => <li key={i}><strong>{s.title}</strong>{s.text && <p>{s.text}</p>}</li>)}</ol>
            </Panel>
          )}
          {a.required_docs?.length > 0 && <Panel title="Documentos necessários"><ul>{a.required_docs.map((d: string) => <li key={d}>{d}</li>)}</ul></Panel>}
          {a.checklist?.length > 0 && (
            <Panel title="Checklist" actions={me ? <span className="muted">{checked.length}/{a.checklist.length}</span> : undefined}>
              <ul className="checklist">
                {a.checklist.map((t: string, i: number) => (
                  <li key={i}><label><input type="checkbox" checked={checked.includes(i)} onChange={() => toggle(i)} /> {t}</label></li>
                ))}
              </ul>
              {!me && <p className="fineprint"><Link to="/entrar">Entre</Link> para salvar seu progresso.</p>}
            </Panel>
          )}
          {a.common_mistakes?.length > 0 && <Panel title="Erros comuns"><ul>{a.common_mistakes.map((m: string) => <li key={m}>{m}</li>)}</ul></Panel>}
          {a.action_link && me && <div><Link to={a.action_link} className="btn btn-primary">{a.action_label || "Fazer agora"}</Link></div>}
          {a.resources?.length > 0 && <Panel title="Modelos e materiais"><ul className="rows">{a.resources.map((r: any) => <li key={r.slug}><Link to={r.link}>{r.title}</Link><Origin x={r} /></li>)}</ul></Panel>}
          {a.courses?.length > 0 && <Panel title="Cursos relacionados"><ul className="rows">{a.courses.map((c: any) => <li key={c.slug}><Link to={`/ajuda/academia/${c.slug}`}>{c.title}</Link></li>)}</ul></Panel>}
          {a.related?.length > 0 && <Panel title="Veja também"><ul className="rows">{a.related.map((r: any) => <li key={r.slug}><Link to={`/ajuda/${r.slug}`}>{r.title}</Link></li>)}</ul></Panel>}
          {a.refs?.length > 0 && <Panel title="Referências"><ul>{a.refs.map((r: any, i: number) => <li key={i}><a href={r.url} rel="noopener noreferrer" target="_blank">{r.label}</a>{r.source_date ? ` (${date(r.source_date)})` : ""}</li>)}</ul></Panel>}
          <Feedback type="article" id={a.id} initial={a.my_feedback} />
          <p className="fineprint">Versão {a.version}{a.published_at ? ` · publicada em ${date(a.published_at)}` : ""}{a.last_reviewed_at ? ` · revisada em ${date(a.last_reviewed_at)}` : ""}</p>
          <Link to={`/ajuda/suporte/novo${qs({ article: slug })}`}>Ainda com dúvida? Abra um chamado</Link>
        </article>
      )}
    </StateView>
  );
}

// ----------------------------------------------------------------------------------------- FAQ
export function Faq({ focus }: { focus?: string }) {
  const [category, setCategory] = useState("");
  const cats = useLoad("/v1/help/categories");
  const { data, loading, error, reload } = useLoad(`/v1/help/faqs${qs({ category, limit: 50 })}`);
  return (
    <div className="stack-lg">
      <PageHead title="Perguntas frequentes" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <Select aria-label="Filtrar por assunto" value={category} onChange={setCategory} placeholder="Todos os assuntos" options={(cats.data?.items || []).filter((c: any) => c.faqs > 0).map((c: any) => [c.slug, c.name] as [string, string])} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhuma pergunta publicada neste assunto."}>
        <div className="faqs">{(data?.items || []).map((f: any) => <FaqItem key={f.id} f={f} open={f.id === focus} />)}</div>
      </StateView>
    </div>
  );
}
function FaqItem({ f, open }: { f: any; open?: boolean }) {
  return (
    <details open={open} id={f.id}>
      <summary>{f.question} <Origin x={f} /></summary>
      <Paragraphs text={f.answer} />
      {f.related_article && <p><Link to={`/ajuda/${f.related_article}`}>Ler o guia completo</Link></p>}
      <Feedback type="faq" id={f.id} />
    </details>
  );
}

// ----------------------------------------------------------------------------------------- biblioteca
export function Library() {
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useLoad(`/v1/help/resources${qs({ kind, q, offset })}`);
  return (
    <div className="stack-lg">
      <PageHead title="Biblioteca de documentos e modelos" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <div className="stack-row">
        <Input aria-label="Buscar na biblioteca" placeholder="Buscar" value={q} onChange={(v: string) => { setQ(v); setOffset(0); }} />
        <Select aria-label="Tipo" value={kind} onChange={(v) => { setKind(v); setOffset(0); }} placeholder="Todos os tipos"
          options={[["template", "Modelos"], ["checklist", "Checklists"], ["document", "Documentos"], ["video", "Vídeos"], ["report", "Relatórios"], ["bulletin", "Boletins"], ["spreadsheet", "Planilhas"]]} />
      </div>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhum material publicado com estes filtros."}>
        <ul className="hits">
          {(data?.items || []).map((r: any) => (
            <li key={r.id}>
              <Link to={r.link}><strong>{r.title}</strong></Link>
              <span className="hit-meta"><Pill tone="muted">{label(r.kind)}</Pill> <Origin x={r} />{r.fillable ? " · modelo preenchível" : ""}</span>
              {r.summary && <p className="muted">{r.summary}</p>}
            </li>
          ))}
        </ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </div>
  );
}

export function Resource({ slug }: { slug: string }) {
  const { me } = useSession();
  const { data: r, loading, error, reload } = useLoad(`/v1/help/resources/${encodeURIComponent(slug)}`);
  const { run, busy } = useAction();
  const f = useForm<Record<string, string>>({});
  const [checked, setChecked] = useState<number[]>([]);
  const download = () => run(() => api.post(`/v1/help/resources/${r.id}/download-url`)).then((x) => { if (x?.url) window.open(x.url, "_blank", "noopener"); });
  const use = () => run(() => api.post(`/v1/help/resources/${r.id}/use-template`, { values: f.v })).then((x) => { if (x?.draft_id) navigate(`/rascunhos/${x.draft_id}`); }, );
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {r && (
        <div className="stack-lg">
          <PageHead title={r.title} sub={r.summary} back={<Link to="/ajuda/biblioteca">← Biblioteca</Link>} />
          <div className="stack-row"><Pill tone="muted">{label(r.kind)}</Pill><Origin x={r} /><span className="muted">Versão {r.version}</span></div>
          {r.review_notice && <div className="banner" role="status">{r.review_notice}</div>}
          {r.regulatory && r.regulatory_source && <p className="fineprint">Fonte oficial: {r.regulatory_source}{r.regulatory_date ? ` (${date(r.regulatory_date)})` : ""}</p>}
          {(r.has_file || r.url) && (me ? <div><Button variant="primary" busy={busy} onClick={download}>Baixar</Button></div> : <p><Link to="/entrar">Entre</Link> para baixar.</p>)}
          {r.checklist_items?.length > 0 && (
            <Panel title="Checklist">
              <ul className="checklist">{r.checklist_items.map((t: string, i: number) => (
                <li key={i}><label><input type="checkbox" checked={checked.includes(i)} onChange={() => { const n = checked.includes(i) ? checked.filter((x) => x !== i) : [...checked, i]; setChecked(n); if (me) api.put("/v1/help/checklists", { scope: `resource:${slug}`, checked: n }).catch(() => {}); }} /> {t}</label></li>
              ))}</ul>
            </Panel>
          )}
          {r.template_schema && (
            <Panel title="Preencher modelo">
              {me ? (
                <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); use(); }}>
                  {r.template_schema.fields.map((fl: any) => (
                    <Field key={fl.key} label={fl.label + (fl.required ? " *" : "")} hint={fl.help} wide={fl.type === "textarea"}>
                      {fl.type === "textarea" ? <TextArea value={f.v[fl.key]} onChange={f.set(fl.key)} /> : <Input type={fl.type === "number" ? "number" : fl.type === "date" ? "date" : "text"} value={f.v[fl.key]} onChange={f.set(fl.key)} />}
                    </Field>
                  ))}
                  <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>Criar rascunho a partir do modelo</Button></div>
                </form>
              ) : <p><Link to="/entrar">Entre</Link> para preencher o modelo.</p>}
            </Panel>
          )}
          {r.versions?.length > 1 && <Panel title="Versões" quiet><ul className="rows">{r.versions.map((v: any) => <li key={v.version}>Versão {v.version} <Pill status={v.status === "superseded" ? "superseded" : "published"} /><span className="muted">{date(v.published_at)} {v.change_note || ""}</span></li>)}</ul></Panel>}
          <Feedback type="resource" id={r.id} />
        </div>
      )}
    </StateView>
  );
}

// ----------------------------------------------------------------------------------------- academia
export function Academy() {
  const { data, loading, error, reload } = useLoad("/v1/help/courses");
  return (
    <div className="stack-lg">
      <PageHead title="Academia" sub="Cursos curtos com quiz. Os certificados são de conclusão da plataforma, não oficiais." back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhum curso publicado ainda."}>
        <ul className="hits">
          {(data?.items || []).map((c: any) => (
            <li key={c.slug}><Link to={`/ajuda/academia/${c.slug}`}><strong>{c.title}</strong></Link>
              <span className="hit-meta"><Origin x={c} /> {label(c.level)} · {c.lessons} aulas{c.hours ? ` · ${c.hours} h` : ""}</span>
              {c.summary && <p className="muted">{c.summary}</p>}</li>
          ))}
        </ul>
        {data?.paths?.length > 0 && (
          <Panel title="Trilhas de aprendizagem">
            <ul className="rows">{data.paths.map((p: any) => <li key={p.slug}><div><strong>{p.title}</strong><p className="muted">{p.description}</p><ol>{(p.items || []).map((i: any, k: number) => <li key={k}>{i.type === "course" ? <Link to={`/ajuda/academia/${i.slug}`}>{i.title || i.slug}</Link> : <Link to={`/ajuda/${i.slug}`}>{i.title || i.slug}</Link>}</li>)}</ol></div></li>)}</ul>
          </Panel>
        )}
      </StateView>
    </div>
  );
}

export function Course({ slug }: { slug: string }) {
  const { me } = useSession();
  const { data: k, loading, error, reload } = useLoad(`/v1/help/courses/${encodeURIComponent(slug)}`);
  const { run, busy } = useAction();
  const first = k?.modules?.[0]?.lessons?.[0];
  const next = k?.modules?.flatMap((m: any) => m.lessons).find((l: any) => !l.completed) || first;
  const enroll = () => run(() => api.post(`/v1/help/courses/${slug}/enroll`), "Matrícula feita").then(async (x) => { if (x) { await reload(); } });
  const cert = () => run(() => api.post(`/v1/help/courses/${slug}/certificate`)).then((x) => { if (x?.code) navigate(`/ajuda/certificado/${x.code}`); });
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {k && (
        <div className="stack-lg">
          <PageHead title={k.title} sub={k.summary} back={<Link to="/ajuda/academia">← Academia</Link>} />
          <div className="stack-row"><Origin x={k} /><span className="muted">{label(k.level)}{k.hours ? ` · ${k.hours} h` : ""} · nota mínima do quiz {k.pass_score}%</span></div>
          {k.certificate_note && <p className="fineprint">{k.certificate_note}</p>}
          {me ? (
            <div className="stack-row">
              {!k.enrollment ? <Button variant="primary" busy={busy} onClick={enroll}>Começar curso</Button>
                : next && <Button variant="primary" onClick={() => navigate(`/ajuda/academia/aula/${next.id}`)}>{k.lessons_done ? "Continuar" : "Começar"}</Button>}
              {k.cert_enabled && k.lessons_total > 0 && k.lessons_done === k.lessons_total && <Button variant="ink" busy={busy} onClick={cert}>Emitir certificado</Button>}
              <span className="muted" role="status">{k.lessons_done}/{k.lessons_total} aulas ({k.percent}%)</span>
            </div>
          ) : <p><Link to="/entrar">Entre</Link> para fazer o curso e acompanhar seu progresso.</p>}
          {k.modules.map((m: any) => (
            <Panel key={m.id} title={m.title}>
              {m.description && <p className="muted">{m.description}</p>}
              <ul className="rows">{m.lessons.map((l: any) => (
                <li key={l.id}>{me ? <Link to={`/ajuda/academia/aula/${l.id}`}>{l.title}</Link> : l.title}
                  <span className="muted">{label(l.kind)}{l.minutes ? ` · ${l.minutes} min` : ""} {l.completed && <Pill tone="good">Concluída</Pill>}</span></li>
              ))}</ul>
            </Panel>
          ))}
        </div>
      )}
    </StateView>
  );
}

export function Lesson({ id }: { id: string }) {
  const { data: l, loading, error, reload } = useLoad(`/v1/help/lessons/${id}`);
  const { run, busy } = useAction();
  const [answers, setAnswers] = useState<number[]>([]);
  const [res, setRes] = useState<any>(null);
  const course = useLoad(l ? `/v1/help/courses/${l.course_slug}` : null);
  useEffect(() => { setAnswers([]); setRes(null); }, [id]);
  const flat: any[] = course.data?.modules?.flatMap((m: any) => m.lessons) || [];
  const idx = flat.findIndex((x) => x.id === id);
  const nextLesson = idx >= 0 ? flat[idx + 1] : null;
  const complete = () => run(() => api.post(`/v1/help/lessons/${id}/complete`, l.kind === "quiz" ? { answers } : {})).then((x) => {
    if (!x) return;
    setRes(x);
    if (l.kind !== "quiz" || x.passed) course.reload();
  });
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {l && (
        <div className="stack-lg">
          <PageHead title={l.title} back={<Link to={`/ajuda/academia/${l.course_slug}`}>← {l.course_title}</Link>} />
          {l.video_url && <p><a href={l.video_url} target="_blank" rel="noopener noreferrer">Abrir o vídeo</a>{l.captions_url && <> · <a href={l.captions_url} target="_blank" rel="noopener noreferrer">Legendas</a></>}</p>}
          <Paragraphs text={l.body} />
          {l.transcript && <details><summary>Transcrição</summary><Paragraphs text={l.transcript} /></details>}
          {l.materials?.length > 0 && <Panel title="Materiais"><ul>{l.materials.map((m: any, i: number) => <li key={i}>{m.url ? <a href={m.url} target="_blank" rel="noopener noreferrer">{m.title || m.url}</a> : m.title}</li>)}</ul></Panel>}
          {l.kind === "quiz" && (
            <Panel title="Quiz">
              {l.quiz.map((q: any, qi: number) => (
                <fieldset key={qi} className="quiz-q">
                  <legend>{qi + 1}. {q.q}</legend>
                  {q.options.map((o: string, oi: number) => (
                    <label key={oi} className="radio"><input type="radio" name={`q${qi}`} checked={answers[qi] === oi} onChange={() => { const a = [...answers]; a[qi] = oi; setAnswers(a); }} /> {o}</label>
                  ))}
                </fieldset>
              ))}
            </Panel>
          )}
          {res && l.kind === "quiz" && <div className={`banner${res.passed ? "" : " banner-bad"}`} role="status">{res.passed ? `Aprovada: ${res.score}% (mínimo ${res.required}%).` : `Nota ${res.score}% — mínimo ${res.required}%. Revise o conteúdo e tente de novo.`}</div>}
          <div className="stack-row">
            <Button variant="primary" busy={busy} disabled={l.kind === "quiz" && answers.filter((a) => a !== undefined).length < l.quiz.length} onClick={complete}>{l.kind === "quiz" ? "Enviar respostas" : "Concluir aula"}</Button>
            {nextLesson && (!l.kind || l.kind !== "quiz" ? res : res?.passed) && <Button variant="ink" onClick={() => navigate(`/ajuda/academia/aula/${nextLesson.id}`)}>Próxima aula</Button>}
          </div>
          <Feedback type="lesson" id={id} />
        </div>
      )}
    </StateView>
  );
}

export function Certificate({ code }: { code: string }) {
  const { data, loading, error } = useLoad(`/v1/help/certificates/${encodeURIComponent(code)}`);
  return (
    <div className="stack-lg">
      <PageHead title="Verificação de certificado" back={<Link to="/ajuda/academia">← Academia</Link>} />
      <StateView loading={loading} error={error}>
        {data && (
          <Panel title={data.valid ? "Certificado válido" : "Certificado revogado"}>
            <KeyValue items={[["Código", data.code], ["Curso", data.course_title], ["Titular", data.holder_name], ["Carga horária", data.hours ? `${data.hours} h` : "—"], ["Emitido em", date(data.issued_at)]]} />
            <p className="fineprint">{data.notice}</p>
            <Button variant="ghost" onClick={() => window.print()}>Imprimir</Button>
          </Panel>
        )}
      </StateView>
    </div>
  );
}

// ----------------------------------------------------------------------------------------- eventos
export function Events() {
  const [when, setWhen] = useState("upcoming");
  const { data, loading, error, reload } = useLoad(`/v1/help/events${qs({ when })}`);
  return (
    <div className="stack-lg">
      <PageHead title="Eventos" sub="Webinars, oficinas e treinamentos." back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <Select aria-label="Período" value={when} onChange={setWhen} options={[["upcoming", "Próximos"], ["past", "Realizados"]]} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhum evento neste período."}>
        <ul className="hits">{(data?.items || []).map((e: any) => (
          <li key={e.id}><Link to={`/ajuda/eventos/${e.slug}`}><strong>{e.title}</strong></Link>
            <span className="hit-meta">{e.demo_label && <Pill tone="warn">{e.demo_label}</Pill>} {dateTime(e.starts_at)} · {label(e.modality)}{e.seats_left !== null ? ` · ${e.full ? "lotado (lista de espera)" : `${e.seats_left} vagas`}` : ""}{e.has_recording ? " · com gravação" : ""}</span></li>
        ))}</ul>
      </StateView>
    </div>
  );
}

export function EventPage({ slug }: { slug: string }) {
  const { me } = useSession();
  const { data: e, loading, error, reload } = useLoad(`/v1/help/events/${encodeURIComponent(slug)}`);
  const { run, busy } = useAction();
  const [score, setScore] = useState("");
  const mine = e?.my_registration;
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {e && (
        <div className="stack-lg">
          <PageHead title={e.title} sub={`${dateTime(e.starts_at)} · ${e.duration_min} min · ${label(e.modality)}`} back={<Link to="/ajuda/eventos">← Eventos</Link>} />
          {e.demo_label && <Pill tone="warn">{e.demo_label}</Pill>}
          <Paragraphs text={e.description} />
          <KeyValue items={[["Palestrante", e.speaker || "—"], ["Local", e.location || "Online"], ["Vagas", e.seats_left === null ? "Sem limite" : e.full ? "Lotado — lista de espera" : `${e.seats_left} restantes`], ["Situação", label(e.status)]]} />
          {e.status === "cancelled" && <div className="banner" role="status">Evento cancelado.</div>}
          {e.status === "published" && e.registration_open && (
            me ? (mine && mine.status !== "cancelled" ? (
              <div className="stack-row">
                <Pill tone={mine.status === "registered" ? "good" : "warn"}>{mine.status === "registered" ? "Inscrição confirmada" : "Na lista de espera"}</Pill>
                <Button variant="ghost" busy={busy} onClick={() => run(() => api.del(`/v1/help/events/${e.id}/register`), "Inscrição cancelada").then(reload)}>Cancelar inscrição</Button>
              </div>
            ) : <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/help/events/${e.id}/register`), e.full ? "Você entrou na lista de espera" : "Inscrição confirmada").then(reload)}>{e.full ? "Entrar na lista de espera" : "Inscrever-me"}</Button>)
              : <p><Link to="/entrar">Entre</Link> para se inscrever.</p>
          )}
          {e.join_url && <p><a className="btn btn-ink" href={e.join_url} target="_blank" rel="noopener noreferrer">Acessar o evento</a></p>}
          {e.status === "completed" && (
            <Panel title="Depois do evento">
              {e.summary && <Paragraphs text={e.summary} />}
              {e.recording_url && <p><a href={e.recording_url} target="_blank" rel="noopener noreferrer">Assistir à gravação</a></p>}
              {mine?.attended && !mine.satisfaction && (
                <div className="stack-row">
                  <Select aria-label="Nota do evento" value={score} onChange={setScore} placeholder="Sua nota" options={[["5", "5 — excelente"], ["4", "4"], ["3", "3"], ["2", "2"], ["1", "1"]]} />
                  <Button variant="ink" disabled={!score} busy={busy} onClick={() => run(() => api.post(`/v1/help/events/${e.id}/rate`, { satisfaction: Number(score) }), "Obrigado pela avaliação").then(reload)}>Avaliar</Button>
                </div>
              )}
            </Panel>
          )}
        </div>
      )}
    </StateView>
  );
}

// ----------------------------------------------------------------------------------------- suporte
const PRIO: Record<string, string> = { low: "Baixa", normal: "Normal", high: "Alta", critical: "Crítica" };
const TICKET_STATUS: Record<string, string> = { open: "Aberto", in_progress: "Em atendimento", waiting_user: "Aguardando você", waiting_internal: "Em análise interna", resolved: "Resolvido", closed: "Encerrado" };
const TICKET_CATEGORIES: [string, string][] = [["question", "Dúvida"], ["bug", "Erro na plataforma"], ["technical", "Problema técnico"], ["document", "Documentos"], ["payment", "Pagamentos"], ["compliance", "Compliance"], ["project", "Projetos"], ["funding", "Captação e editais"], ["report", "Relatórios"], ["account", "Conta e acesso"], ["other", "Outro"]];

export function Tickets() {
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useLoad(`/v1/support/tickets${qs({ offset })}`);
  return (
    <div className="stack-lg">
      <PageHead title="Meus chamados" back={<Link to="/ajuda">← Central de Conhecimento</Link>} actions={<Button variant="primary" onClick={() => navigate("/ajuda/suporte/novo")}>Novo chamado</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Você ainda não abriu chamados."}>
        <ul className="rows">{(data?.items || []).map((t: any) => (
          <li key={t.id}><div><Link to={`/ajuda/suporte/${t.id}`}><strong>#{t.number} {t.subject}</strong></Link><p className="muted">Atualizado em {dateTime(t.updated_at)}</p></div><Pill tone={t.status === "resolved" || t.status === "closed" ? "good" : t.status === "waiting_user" ? "warn" : "muted"}>{TICKET_STATUS[t.status] || t.status}</Pill></li>
        ))}</ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </div>
  );
}

export function NewTicket() {
  const { query } = useLocation();
  const f = useForm({ category: "question", subject: "", message: "" });
  const { run, busy } = useAction();
  const ctxPage = query.get("page"), ctxField = query.get("field"), ctxArticle = query.get("article");
  const submit = () => run(() => api.post("/v1/support/tickets", {
    ...f.v, context: { ...(ctxPage ? { page: ctxPage } : {}), ...(ctxField ? { field: ctxField } : {}), ...(ctxArticle ? { article: ctxArticle } : {}), app: "web" },
  }), "Chamado aberto").then((x) => { if (x?.id) navigate(`/ajuda/suporte/${x.id}`); });
  const hint = useLoad(f.v.subject.trim().length >= 6 ? `/v1/help/search${qs({ q: f.v.subject, limit: 3 })}` : null, [f.v.subject]);
  return (
    <div className="stack-lg">
      <PageHead title="Abrir um chamado" sub="Antes de enviar, veja se algum conteúdo já responde." back={<Link to="/ajuda/suporte">← Meus chamados</Link>} />
      <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); submit(); }}>
        <Field label="Assunto geral"><Select value={f.v.category} onChange={f.set("category")} options={TICKET_CATEGORIES} /></Field>
        <Field label="Resumo" wide><Input value={f.v.subject} onChange={f.set("subject")} maxLength={200} required /></Field>
        {hint.data?.items?.length > 0 && <div className="field field-wide"><p className="muted">Pode ajudar:</p><ResultList items={hint.data.items.slice(0, 3)} /></div>}
        <Field label="Descreva o que aconteceu" hint="Não envie senhas nem dados bancários." wide><TextArea rows={6} value={f.v.message} onChange={f.set("message")} maxLength={8000} required /></Field>
        {(ctxPage || ctxField || ctxArticle) && <p className="fineprint field-wide">Contexto anexado: {[ctxPage, ctxField, ctxArticle].filter(Boolean).join(" · ")}</p>}
        <div className="form-actions"><Button type="submit" variant="primary" busy={busy} disabled={f.v.subject.trim().length < 3 || f.v.message.trim().length < 5}>Enviar chamado</Button></div>
      </form>
    </div>
  );
}

export function Ticket({ id }: { id: string }) {
  const { data: t, loading, error, reload } = useLoad(`/v1/support/tickets/${id}`);
  const [body, setBody] = useState("");
  const { run, busy } = useAction();
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {t && (
        <div className="stack-lg">
          <PageHead title={`#${t.number} ${t.subject}`} back={<Link to="/ajuda/suporte">← Meus chamados</Link>} />
          <div className="stack-row"><Pill tone="muted">{TICKET_STATUS[t.status] || t.status}</Pill><span className="muted">Prioridade {PRIO[t.priority]} · aberto em {dateTime(t.created_at)}</span></div>
          {t.first_response_due && !t.first_response_at && <p className="fineprint">Primeira resposta prevista até {dateTime(t.first_response_due)} (meta interna, não é garantia contratual).</p>}
          <Panel title="Conversa">
            <ul className="thread">{t.messages.filter((m: any) => !m.internal).map((m: any) => (
              <li key={m.id} className={m.author_kind === "staff" ? "from-staff" : ""}><strong>{m.author_kind === "staff" ? "Atendimento" : "Você"}</strong> <span className="fineprint">{dateTime(m.created_at)}</span><Paragraphs text={m.body} /></li>
            ))}</ul>
          </Panel>
          {t.status !== "closed" && (
            <form className="stack" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/support/tickets/${id}/messages`, { body }), "Resposta enviada").then(() => { setBody(""); reload(); }); }}>
              <Field label="Responder"><TextArea rows={4} value={body} onChange={setBody} maxLength={8000} /></Field>
              <div className="form-actions"><Button type="submit" variant="primary" busy={busy} disabled={!body.trim()}>Enviar</Button></div>
            </form>
          )}
          {t.status === "resolved" && (
            <div className="stack-row">
              {!t.satisfaction && [1, 2, 3, 4, 5].map((n) => <Button key={n} variant="ghost" aria-label={`Nota ${n}`} onClick={() => run(() => api.post(`/v1/support/tickets/${id}/rate`, { score: n }), "Obrigado pela avaliação").then(reload)}>{n}</Button>)}
              <Button variant="ink" onClick={() => run(() => api.post(`/v1/support/tickets/${id}/close`), "Chamado encerrado").then(reload)}>Encerrar chamado</Button>
            </div>
          )}
        </div>
      )}
    </StateView>
  );
}

// ----------------------------------------------------------------------------------------- captação (público)
function Honeypot({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return <div className="hp" aria-hidden="true"><label>Não preencha este campo<input tabIndex={-1} autoComplete="off" value={value} onChange={(e: any) => onChange(e.target.value)} /></label></div>;
}
function Consent({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check field-wide">
      <input type="checkbox" checked={checked} onChange={(e: any) => onChange(e.target.checked)} />
      Concordo com o uso destes dados para responder a esta solicitação, conforme a <Link to="/legal/privacidade">Política de privacidade</Link>.
    </label>
  );
}

export function PartnershipForm() {
  const f = useForm({ org_name: "", contact_name: "", contact_email: "", contact_phone: "", kind: "institutional", objective: "", proposal: "", territory: "", resources_offered: "", counterpart: "", consent: false, website: "" });
  const { run, busy } = useAction();
  const [done, setDone] = useState(false);
  if (done) return <div className="state state-empty"><h1>Recebemos sua proposta</h1><p>Nossa equipe analisa as propostas e responde pelo e-mail informado. Isso não cria compromisso nem parceria automática.</p><Link to="/ajuda">Voltar à Central</Link></div>;
  const clean = () => Object.fromEntries(Object.entries(f.v).filter(([, v]) => v !== ""));
  return (
    <div className="stack-lg">
      <PageHead title="Propor uma parceria" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/help/partnerships", clean())).then((x) => x && setDone(true)); }}>
        <Field label="Organização"><Input value={f.v.org_name} onChange={f.set("org_name")} required maxLength={200} /></Field>
        <Field label="Seu nome"><Input value={f.v.contact_name} onChange={f.set("contact_name")} required maxLength={200} /></Field>
        <Field label="E-mail"><Input type="email" value={f.v.contact_email} onChange={f.set("contact_email")} required /></Field>
        <Field label="Telefone (opcional)"><Input value={f.v.contact_phone} onChange={f.set("contact_phone")} maxLength={40} /></Field>
        <Field label="Tipo de parceria"><Select value={f.v.kind} onChange={f.set("kind")} options={[["institutional", "Institucional"], ["academic", "Acadêmica"], ["government", "Governamental"], ["business", "Empresarial"], ["technology", "Tecnologia"], ["osc", "Organização da sociedade civil"], ["media", "Comunicação"], ["research", "Pesquisa"], ["other", "Outra"]]} /></Field>
        <Field label="Território de atuação (opcional)"><Input value={f.v.territory} onChange={f.set("territory")} maxLength={300} /></Field>
        <Field label="Objetivo" wide><TextArea value={f.v.objective} onChange={f.set("objective")} required minLength={10} maxLength={3000} /></Field>
        <Field label="Proposta (opcional)" wide><TextArea value={f.v.proposal} onChange={f.set("proposal")} maxLength={6000} /></Field>
        <Field label="O que você oferece (opcional)" wide><TextArea rows={3} value={f.v.resources_offered} onChange={f.set("resources_offered")} maxLength={2000} /></Field>
        <Field label="O que espera em troca (opcional)" wide><TextArea rows={3} value={f.v.counterpart} onChange={f.set("counterpart")} maxLength={2000} /></Field>
        <Consent checked={f.v.consent} onChange={f.set("consent")} />
        <Honeypot value={f.v.website} onChange={f.set("website")} />
        <div className="form-actions"><Button type="submit" variant="primary" busy={busy} disabled={!f.v.consent}>Enviar proposta</Button></div>
      </form>
    </div>
  );
}

export function DemoForm() {
  const f = useForm({ org_name: "", contact_name: "", contact_email: "", contact_phone: "", audience_kind: "osc", org_size: "", interest: "", notes: "", slot: "", consent: false, website: "" });
  const { run, busy } = useAction();
  const [done, setDone] = useState(false);
  if (done) return <div className="state state-empty"><h1>Pedido recebido</h1><p>Entraremos em contato por e-mail para confirmar o horário. Ainda não há horário reservado.</p><Link to="/ajuda">Voltar à Central</Link></div>;
  const body = () => { const { slot, ...rest } = f.v; const o: any = Object.fromEntries(Object.entries(rest).filter(([, v]) => v !== "")); if (slot) o.preferred_slots = [new Date(slot).toISOString()]; return o; };
  return (
    <div className="stack-lg">
      <PageHead title="Agendar uma demonstração" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/help/demo-requests", body())).then((x) => x && setDone(true)); }}>
        <Field label="Organização"><Input value={f.v.org_name} onChange={f.set("org_name")} required maxLength={200} /></Field>
        <Field label="Seu nome"><Input value={f.v.contact_name} onChange={f.set("contact_name")} required maxLength={200} /></Field>
        <Field label="E-mail"><Input type="email" value={f.v.contact_email} onChange={f.set("contact_email")} required /></Field>
        <Field label="Telefone (opcional)"><Input value={f.v.contact_phone} onChange={f.set("contact_phone")} maxLength={40} /></Field>
        <Field label="Você é"><Select value={f.v.audience_kind} onChange={f.set("audience_kind")} options={[["osc", "Organização da sociedade civil"], ["company", "Empresa"], ["individual", "Apoiador individual"], ["provider", "Profissional parceiro"], ["government", "Governo"], ["other", "Outro"]]} /></Field>
        <Field label="Tamanho da organização"><Select value={f.v.org_size} onChange={f.set("org_size")} placeholder="Não informar" options={[["1-10", "1 a 10 pessoas"], ["11-50", "11 a 50"], ["51-200", "51 a 200"], ["200+", "Mais de 200"]]} /></Field>
        <Field label="Horário preferido (opcional)"><Input type="datetime-local" value={f.v.slot} onChange={f.set("slot")} /></Field>
        <Field label="O que você quer ver?" wide><TextArea rows={3} value={f.v.interest} onChange={f.set("interest")} maxLength={1000} /></Field>
        <Consent checked={f.v.consent} onChange={f.set("consent")} />
        <Honeypot value={f.v.website} onChange={f.set("website")} />
        <div className="form-actions"><Button type="submit" variant="primary" busy={busy} disabled={!f.v.consent}>Pedir demonstração</Button></div>
      </form>
    </div>
  );
}

export function TrialRequest() {
  const { me } = useSession();
  const list = useLoad("/v1/help/trial-requests");
  const f = useForm({ users_count: "1", purpose: "", responsible: me?.user.full_name || "", period_days: "14" });
  const { run, busy } = useAction();
  const pending = (list.data?.items || []).some((r: any) => r.status === "requested");
  return (
    <div className="stack-lg">
      <PageHead title="Solicitar período de teste" sub="A equipe analisa cada pedido. O teste só começa depois da aprovação." back={<Link to="/conta/plano">← Plano</Link>} />
      <StateView loading={list.loading} error={list.error} onRetry={list.reload}>
        {(list.data?.items || []).length > 0 && (
          <Panel title="Seus pedidos"><ul className="rows">{list.data.items.map((r: any) => <li key={r.id}><span>{dateTime(r.created_at)} · {r.period_days} dias</span><span><Pill status={r.status} />{r.decision_reason && <span className="muted"> {r.decision_reason}</span>}</span></li>)}</ul></Panel>
        )}
        {pending ? <p className="muted">Há um pedido em análise.</p> : (
          <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/help/trial-requests", { ...f.v, users_count: Number(f.v.users_count), period_days: Number(f.v.period_days) }), "Pedido enviado").then(list.reload); }}>
            <Field label="Responsável"><Input value={f.v.responsible} onChange={f.set("responsible")} required /></Field>
            <Field label="Pessoas que usarão"><Input type="number" min={1} value={f.v.users_count} onChange={f.set("users_count")} required /></Field>
            <Field label="Duração desejada (dias)"><Input type="number" min={7} max={60} value={f.v.period_days} onChange={f.set("period_days")} /></Field>
            <Field label="Para que você quer testar?" wide><TextArea value={f.v.purpose} onChange={f.set("purpose")} minLength={10} maxLength={2000} required /></Field>
            <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>Enviar pedido</Button></div>
          </form>
        )}
      </StateView>
    </div>
  );
}

// ----------------------------------------------------------------------------------------- boletim
export function Newsletter() {
  const f = useForm({ email: "", frequency: "monthly", consent: false, website: "" });
  const [topics, setTopics] = useState<string[]>(["platform"]);
  const { run, busy } = useAction();
  const [done, setDone] = useState(false);
  if (done) return <div className="state state-empty"><h1>Falta só confirmar</h1><p>Enviamos um e-mail com um link de confirmação. Sem a confirmação, você não recebe o boletim.</p></div>;
  return (
    <div className="stack-lg">
      <PageHead title="Receber o boletim" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/help/newsletter", { ...f.v, topics })).then((x) => x && setDone(true)); }}>
        <Field label="E-mail"><Input type="email" value={f.v.email} onChange={f.set("email")} required /></Field>
        <Field label="Frequência"><Select value={f.v.frequency} onChange={f.set("frequency")} options={[["monthly", "Mensal"], ["weekly", "Semanal"]]} /></Field>
        <Group label="Assuntos"><Chips value={topics} onChange={setTopics} options={[["platform", "Plataforma"], ["opportunities", "Oportunidades"], ["events", "Eventos"], ["legislation", "Legislação"], ["technology", "Tecnologia"], ["esg", "ESG"], ["ods", "ODS"]]} /></Group>
        <Consent checked={f.v.consent} onChange={f.set("consent")} />
        <Honeypot value={f.v.website} onChange={f.set("website")} />
        <div className="form-actions"><Button type="submit" variant="primary" busy={busy} disabled={!f.v.consent || !topics.length}>Inscrever-me</Button></div>
      </form>
    </div>
  );
}

export function NewsletterToken({ mode }: { mode: "confirm" | "unsubscribe" }) {
  const { query } = useLocation();
  const token = query.get("token") || "";
  const { busy, run } = useAction();
  const [ok, setOk] = useState<boolean | null>(null);
  return (
    <div className="state state-empty">
      <h1>{mode === "confirm" ? "Confirmar inscrição" : "Cancelar inscrição"}</h1>
      {ok === null ? (
        token ? <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/help/newsletter/${mode}`, { token })).then((x) => setOk(!!x))}>{mode === "confirm" ? "Confirmar" : "Cancelar inscrição"}</Button>
          : <p>Link inválido. Use o link do e-mail.</p>
      ) : <p role="status">{ok ? (mode === "confirm" ? "Inscrição confirmada." : "Inscrição cancelada. Você não receberá mais o boletim.") : "Não foi possível concluir. O link pode ter expirado."}</p>}
    </div>
  );
}

// ----------------------------------------------------------------------------------------- jornada, pendências, atividades, preferências
export function Start() {
  const { data, loading, error, reload } = useLoad("/v1/help/start");
  return (
    <div className="stack-lg">
      <PageHead title="Comece aqui" sub="Seu caminho na plataforma, marcado por dados reais (não por autodeclaração)." back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.steps.length && "Ainda não há jornada cadastrada para este tipo de organização."}>
        {data && (
          <>
            {/* A mesma jornada que já vinha do servidor, agora desenhada como Trilha. A lista
                ordenada continua abaixo porque é ela que leva à ação: a trilha diz ONDE a pessoa
                está, a lista diz o que fazer. */}
            <JourneyTrail steps={data.steps} />
            <div className="meter" role="progressbar" aria-valuenow={data.percent} aria-valuemin={0} aria-valuemax={100} aria-label="Progresso da jornada"><span style={{ width: `${data.percent}%` }} /></div>
            <p className="muted">{data.done} de {data.total} etapas · {data.percent}%</p>
            <ol className="steps">{data.steps.map((s: any) => (
              <li key={s.key} className={s.done ? "done" : ""}>
                <strong>{s.title}</strong> {s.done ? <Pill tone="good">Concluída</Pill> : s.minutes ? <span className="muted">{s.minutes} min</span> : null}
                {!s.done && <div className="stack-row"><Link to={s.link} className="btn btn-ghost">Ir para a etapa</Link>{s.guide && <Link to={`/ajuda/${s.guide}`}>Ver o guia</Link>}</div>}
              </li>
            ))}</ol>
            {data.status !== "approved" && <p className="fineprint">Jornada em validação editorial ({data.config}).</p>}
          </>
        )}
      </StateView>
    </div>
  );
}

export function Pending() {
  const { data, loading, error, reload } = useLoad("/v1/help/pending");
  return (
    <div className="stack-lg">
      <PageHead title="O que falta para eu avançar?" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nada pendente por enquanto."}>
        <ul className="rows">{(data?.items || []).map((i: any, k: number) => (
          <li key={k}><div><Link to={i.link}><strong>{i.title}</strong></Link><p className="muted">{i.why}</p></div><span className="row-actions"><Pill tone={i.severity === "high" ? "bad" : i.severity === "medium" ? "warn" : "muted"}>{i.severity === "high" ? "Importante" : i.severity === "medium" ? "Em breve" : "Sugestão"}</Pill>{i.guide && <Link to={`/ajuda/${i.guide}`}>Guia</Link>}</span></li>
        ))}</ul>
      </StateView>
    </div>
  );
}

export function Activities() {
  const { data, loading, error, reload } = useLoad("/v1/help/activities");
  const sec = (title: string, items: any[] | undefined, row: (x: any, i: number) => ReactNode) => items && items.length > 0 && <Panel title={title}><ul className="rows">{items.map(row)}</ul></Panel>;
  return (
    <div className="stack-lg">
      <PageHead title="Minhas atividades" back={<Link to="/ajuda">← Central de Conhecimento</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {sec("Chamados", data.tickets, (t) => <li key={t.id}><Link to={`/ajuda/suporte/${t.id}`}>#{t.number} {t.subject}</Link><Pill tone="muted">{TICKET_STATUS[t.status] || t.status}</Pill></li>)}
            {sec("Cursos", data.courses, (c) => <li key={c.slug}><Link to={`/ajuda/academia/${c.slug}`}>{c.title}</Link><span className="muted">{c.completed_at ? "Concluído" : `${c.lessons_done} aulas feitas`}</span></li>)}
            {sec("Eventos", data.events, (e) => <li key={e.slug}><Link to={`/ajuda/eventos/${e.slug}`}>{e.title}</Link><span className="muted">{dateTime(e.starts_at)} · {e.status === "waitlist" ? "lista de espera" : "inscrita"}</span></li>)}
            {sec("Certificados", data.certificates, (c) => <li key={c.code}><Link to={`/ajuda/certificado/${c.code}`}>{c.course_title}</Link><span className="muted">{c.revoked_at ? "Revogado" : date(c.issued_at)}</span></li>)}
            {sec("Pedidos de teste", data.trial_requests, (r) => <li key={r.id}><span>{dateTime(r.created_at)}</span><Pill status={r.status} /></li>)}
            {sec("Propostas de parceria", data.partnership_requests, (r) => <li key={r.id}><span>{r.org_name}</span><Pill tone="muted">{label(r.status)}</Pill></li>)}
            {sec("Demonstrações", data.demo_requests, (r) => <li key={r.id}><span>{r.scheduled_at ? dateTime(r.scheduled_at) : "Aguardando horário"}</span><Pill tone="muted">{label(r.status)}</Pill></li>)}
          </>
        )}
      </StateView>
    </div>
  );
}

const PREF_LABEL: Record<string, string> = { billing: "Cobrança e plano", content: "Conteúdo da Central", events: "Eventos", support: "Chamados", partnerships: "Parcerias", opportunities: "Oportunidades", network: "Rede e relações", proposal: "Propostas", message: "Recados", funding: "Apoio e captação", report: "Relatórios de impacto", project: "Projetos e etapas", document: "Documentos", account: "Conta e moderação" };
export function Prefs() {
  const { data, loading, error, reload } = useLoad("/v1/notifications/prefs");
  const [items, setItems] = useState<any[]>([]);
  const { run, busy } = useAction();
  useEffect(() => { if (data) setItems(data.items); }, [data]);
  const tog = (grp: string, k: "in_app" | "email") => setItems(items.map((i) => (i.grp === grp ? { ...i, [k]: !i[k] } : i)));
  return (
    <div className="stack-lg">
      <PageHead title="Preferências de notificação" back={<Link to="/conta">← Minha conta</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        <table className="table">
          <thead><tr><th>Assunto</th><th>No aplicativo</th><th>Por e-mail</th></tr></thead>
          <tbody>{items.map((i) => (
            <tr key={i.grp}><th scope="row">{PREF_LABEL[i.grp] || i.grp}</th>
              <td><input type="checkbox" aria-label={`${PREF_LABEL[i.grp]}: no aplicativo`} checked={i.in_app} onChange={() => tog(i.grp, "in_app")} /></td>
              <td><input type="checkbox" aria-label={`${PREF_LABEL[i.grp]}: por e-mail`} checked={i.email} onChange={() => tog(i.grp, "email")} /></td></tr>
          ))}</tbody>
        </table>
        <div className="form-actions"><Button variant="primary" busy={busy} onClick={() => run(() => api.put("/v1/notifications/prefs", { items: items.map(({ grp, in_app, email }) => ({ grp, in_app, email })) }), "Preferências salvas").then(reload)}>Salvar</Button></div>
      </StateView>
    </div>
  );
}
