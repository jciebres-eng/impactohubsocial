// CMS e operação da Central de Conhecimento (v0.12.0) — editorial com quatro olhos, suporte com SLA, parcerias, testes, analytics.
import { useState } from "react";
import type { ReactNode } from "react";
import { api, qs } from "../api";
import { Link, navigate, useLocation } from "../router";
import { date, dateTime, label } from "../format";
import { Bars, Button, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Pager, Select, StateView, TextArea, useAction, useForm, useLoad, Chips } from "../ui/kit";

const TABS: [string, string][] = [["/admin/central", "Visão geral"], ["/admin/central/artigos", "Guias"], ["/admin/central/recursos", "Biblioteca"], ["/admin/central/faqs", "FAQ"],
  ["/admin/central/cursos", "Cursos"], ["/admin/central/eventos", "Eventos"], ["/admin/central/suporte", "Suporte"], ["/admin/central/parcerias", "Parcerias"],
  ["/admin/central/testes", "Testes e demonstrações"], ["/admin/central/analytics", "Indicadores"], ["/admin/central/equipe", "Equipe editorial"]];

function Frame({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  const { path } = useLocation();
  return (
    <div className="stack-lg">
      <PageHead title={title} actions={actions} />
      <nav className="tabs" aria-label="Central de Conhecimento — administração">
        {TABS.map(([to, l]) => <Link key={to} to={to} className={`tab${path === to ? " on" : ""}`} aria-current={path === to ? "page" : undefined}>{l}</Link>)}
      </nav>
      {children}
    </div>
  );
}

const STATUS_NEXT: Record<string, [string, string][]> = {
  draft: [["review", "Enviar para revisão"]], review: [["approved", "Aprovar"], ["draft", "Devolver"]], approved: [["published", "Publicar"], ["draft", "Devolver"]],
  published: [["archived", "Arquivar"]], archived: [["draft", "Reabrir"]],
};

/** Botões de transição editorial. Aprovar/publicar exige outra pessoa com papel de revisão: o servidor decide. */
function Transitions({ type, id, status, onDone }: { type: string; id: string; status: string; onDone: () => void }) {
  const { run, busy } = useAction();
  const path = { article_version: "article-versions", resource: "resources", faq: "faqs", course: "courses", event: "events", path: "paths" }[type];
  return (
    <span className="row-actions">
      {(STATUS_NEXT[status] || []).map(([to, l]) => (
        <Button key={to} variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/admin/content/${path}/${id}/transition`, { to }), `${l}: ok`).then(onDone)}>{l}</Button>
      ))}
    </span>
  );
}

// ----------------------------------------------------------------------------------------- visão geral e fila de revisão
export function Overview() {
  const { data, loading, error, reload } = useLoad("/v1/admin/content/overview");
  const { run } = useAction();
  const sum = (rows: any[]) => (rows || []).map((r) => `${label(r.status)}: ${r.n}`).join(" · ") || "—";
  return (
    <Frame title="Central de Conhecimento">
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Conteúdo por estado">
              <KeyValue items={[["Versões de guias", sum(data.by_status.article_versions)], ["Biblioteca", sum(data.by_status.resources)], ["FAQ", sum(data.by_status.faqs)], ["Cursos", sum(data.by_status.courses)], ["Eventos", sum(data.by_status.events)]]} />
            </Panel>
            <Panel title="Aguardando revisão">
              {data.waiting_review.length === 0 ? <p className="muted">Nada na fila.</p> : (
                <ul className="rows">{data.waiting_review.map((w: any) => (
                  <li key={w.id}><div><strong>{w.title}</strong><p className="muted">{label(w.type)} · {dateTime(w.created_at)}</p></div><Transitions type={w.type} id={w.id} status="review" onDone={reload} /></li>
                ))}</ul>
              )}
              <p className="fineprint">Quem escreveu não pode aprovar o próprio conteúdo (quatro olhos, garantido no banco de dados).</p>
            </Panel>
            <Panel title="Revisão em atraso ou vencida">
              <KeyValue items={[["Guias", String(data.stale.articles)], ["Biblioteca", String(data.stale.resources)], ["FAQ", String(data.stale.faqs)], ["Cursos", String(data.stale.courses)]]} />
              <ul className="rows">{(data.stale.oldest || []).map((x: any) => (
                <li key={x.id}><span>{x.title}</span><span className="row-actions"><span className="muted">última revisão {date(x.last_reviewed)}</span>
                  <Button variant="ghost" onClick={() => run(() => api.post(`/v1/admin/content/${x.type}/${x.id}/reviewed`, {}), "Marcado como revisado").then(reload)}>Marcar revisado</Button></span></li>
              ))}</ul>
              {!data.stale.total && <p className="muted">Nada vencido.</p>}
            </Panel>
            {data.low_resolution_faqs?.length > 0 && (
              <Panel title="FAQs que pouco ajudam"><ul className="rows">{data.low_resolution_faqs.map((f: any) => <li key={f.id}><span>{f.question}</span><span className="muted">{f.helpful_yes} úteis / {f.helpful_no} não úteis</span></li>)}</ul></Panel>
            )}
          </>
        )}
      </StateView>
    </Frame>
  );
}

// ----------------------------------------------------------------------------------------- guias
export function Articles() {
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useLoad(`/v1/admin/content/articles${qs({ q, offset })}`);
  return (
    <Frame title="Guias e artigos" actions={<Button variant="primary" onClick={() => navigate("/admin/central/artigos/novo")}>Novo guia</Button>}>
      <Input aria-label="Buscar por endereço" placeholder="Buscar" value={q} onChange={(v: string) => { setQ(v); setOffset(0); }} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhum guia."}>
        <ul className="rows">{(data?.items || []).map((a: any) => (
          <li key={a.id}><div><Link to={`/admin/central/artigos/${a.slug}`}><strong>{a.title}</strong></Link><p className="muted">/{a.slug} · {label(a.visibility)}{a.demo ? " · EXEMPLO" : ""}</p></div>
            <span className="row-actions">{a.live && <Pill tone="good">No ar</Pill>}<Pill status={a.latest_status} /></span></li>
        ))}</ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </Frame>
  );
}

const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export function ArticleEditor({ slug }: { slug?: string }) {
  const isNew = !slug || slug === "novo";
  const cur = useLoad(isNew ? null : `/v1/admin/content/articles/${slug}`);
  const f = useForm({ slug: "", kind: "guide", title: "", summary: "", body: "", visibility: "authenticated", origin: "official", audience: [] as string[], tags: "", ctx_keys: "", steps: "", checklist: "", demo: false,
    regulatory: false, regulatory_source: "", regulatory_date: "", valid_until: "", change_note: "" });
  const { run, busy } = useAction();
  const [loaded, setLoaded] = useState<string | null>(null);
  const v0 = cur.data?.versions?.[0];
  if (v0 && loaded !== v0.id) {
    setLoaded(v0.id);
    f.setV({ ...f.v, slug: cur.data.slug, kind: cur.data.kind, title: v0.title, summary: v0.summary || "", body: v0.body, visibility: cur.data.visibility, origin: cur.data.origin, audience: cur.data.audience || [],
      tags: (cur.data.tags || []).join(", "), ctx_keys: (cur.data.ctx_keys || []).join(", "), steps: (v0.steps || []).map((s: any) => `${s.title} | ${s.text || ""}`).join("\n"),
      checklist: (v0.checklist || []).join("\n"), demo: cur.data.demo, regulatory: v0.regulatory, regulatory_source: v0.regulatory_source || "", regulatory_date: v0.regulatory_date || "", valid_until: v0.valid_until || "", change_note: "" });
  }
  const content = () => ({
    title: f.v.title, summary: f.v.summary || null, body: f.v.body,
    steps: f.v.steps.split("\n").filter((l) => l.trim()).map((l) => { const [t, ...r] = l.split("|"); return { title: t.trim(), text: r.join("|").trim() }; }),
    checklist: f.v.checklist.split("\n").map((l) => l.trim()).filter(Boolean), common_mistakes: [], refs: [],
    regulatory: f.v.regulatory, regulatory_source: f.v.regulatory_source || null, regulatory_date: f.v.regulatory_date || null, valid_until: f.v.valid_until || null, change_note: f.v.change_note || null,
  });
  const save = async () => {
    if (isNew) {
      const x = await run(() => api.post("/v1/admin/content/articles", { slug: f.v.slug, kind: f.v.kind, visibility: f.v.visibility, origin: f.v.origin, audience: f.v.audience, tags: csv(f.v.tags), ctx_keys: csv(f.v.ctx_keys), demo: f.v.demo, ...content() }), "Rascunho criado");
      if (x) navigate(`/admin/central/artigos/${f.v.slug}`);
    } else if (v0?.status === "draft") {
      await run(() => api.put(`/v1/admin/content/article-versions/${v0.id}`, content()), "Rascunho salvo");
      cur.reload();
    } else {
      await run(() => api.post(`/v1/admin/content/articles/${slug}/versions`, { ...content(), change_note: f.v.change_note || "Nova versão" }), "Nova versão criada");
      cur.reload();
    }
  };
  return (
    <Frame title={isNew ? "Novo guia" : f.v.title || "Guia"}>
      <StateView loading={cur.loading} error={cur.error} onRetry={cur.reload}>
        {v0 && (
          <Panel title={`Versão ${v0.version}`} actions={<Transitions type="article_version" id={v0.id} status={v0.status} onDone={cur.reload} />}>
            <p className="muted">Estado: <Pill status={v0.status} />{v0.status !== "draft" && " — versões fora de rascunho são imutáveis; salvar cria uma nova versão."}</p>
          </Panel>
        )}
        <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); save(); }}>
          {isNew && <Field label="Endereço (slug)" hint="minúsculas e hífens"><Input value={f.v.slug} onChange={f.set("slug")} required /></Field>}
          <Field label="Tipo"><Select value={f.v.kind} onChange={f.set("kind")} options={[["start", "Comece aqui"], ["how_it_works", "Como funciona"], ["guide", "Guia"], ["article", "Artigo"], ["policy", "Política"], ["glossary", "Glossário"], ["procedure", "Procedimento"]]} /></Field>
          <Field label="Quem pode ver"><Select value={f.v.visibility} onChange={f.set("visibility")} options={[["public", "Público"], ["authenticated", "Quem entrou"], ["audience", "Só o público indicado"]]} /></Field>
          <Field label="Origem"><Select value={f.v.origin} onChange={f.set("origin")} options={[["official", "Oficial"], ["educational", "Educativo"], ["third_party", "Terceiros"]]} /></Field>
          <Field label="Título" wide><Input value={f.v.title} onChange={f.set("title")} required /></Field>
          <Field label="Resumo" wide><TextArea rows={2} value={f.v.summary} onChange={f.set("summary")} maxLength={600} /></Field>
          <Field label="Texto" wide><TextArea rows={10} value={f.v.body} onChange={f.set("body")} required /></Field>
          <Field label="Passos (um por linha: título | texto)" wide><TextArea rows={4} value={f.v.steps} onChange={f.set("steps")} /></Field>
          <Field label="Checklist (um item por linha)" wide><TextArea rows={4} value={f.v.checklist} onChange={f.set("checklist")} /></Field>
          <Field label="Público (OSC, empresa…)" wide>
            <Chips value={f.v.audience} onChange={f.set("audience")} options={[["osc", "OSC"], ["company", "Empresa"], ["individual", "Apoiador"], ["provider", "Profissional"], ["government", "Governo"]]} />
          </Field>
          <Field label="Etiquetas (vírgula)"><Input value={f.v.tags} onChange={f.set("tags")} /></Field>
          <Field label="Telas com ajuda contextual (vírgula)" hint="ex.: project.budget"><Input value={f.v.ctx_keys} onChange={f.set("ctx_keys")} /></Field>
          <label className="check field-wide"><input type="checkbox" checked={f.v.demo} onChange={(e: any) => f.set("demo")(e.target.checked)} /> Conteúdo de exemplo (aparece com selo “Exemplo”)</label>
          <label className="check field-wide"><input type="checkbox" checked={f.v.regulatory} onChange={(e: any) => f.set("regulatory")(e.target.checked)} /> Conteúdo regulatório (exige fonte oficial e data)</label>
          {f.v.regulatory && (
            <>
              <Field label="Fonte oficial" wide><Input value={f.v.regulatory_source} onChange={f.set("regulatory_source")} /></Field>
              <Field label="Data da fonte"><Input type="date" value={f.v.regulatory_date} onChange={f.set("regulatory_date")} /></Field>
              <Field label="Válido até"><Input type="date" value={f.v.valid_until} onChange={f.set("valid_until")} /></Field>
            </>
          )}
          {!isNew && v0?.status !== "draft" && <Field label="O que mudou" wide><Input value={f.v.change_note} onChange={f.set("change_note")} required minLength={3} /></Field>}
          <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>{isNew ? "Criar rascunho" : v0?.status === "draft" ? "Salvar rascunho" : "Criar nova versão"}</Button></div>
        </form>
        {!isNew && cur.data && <History type="article_version" id={v0?.id} />}
      </StateView>
    </Frame>
  );
}

function History({ type, id }: { type: string; id?: string }) {
  const h = useLoad(id ? `/v1/admin/content/history/${type}/${id}` : null);
  if (!h.data?.items?.length) return null;
  return <Panel title="Histórico" quiet><ul className="rows">{h.data.items.map((x: any, i: number) => <li key={i}><span>{label(x.from_status)} → {label(x.to_status)}</span><span className="muted">{dateTime(x.at || x.created_at)} {x.note || ""}</span></li>)}</ul></Panel>;
}

// ----------------------------------------------------------------------------------------- recursos, FAQs, cursos (listas + criação)
function SimpleList({ title, path, type, row, create }: { title: string; path: string; type: string; row: (x: any) => ReactNode; create?: ReactNode }) {
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useLoad(`${path}${qs({ offset })}`);
  return (
    <Frame title={title}>
      {create}
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nada cadastrado."}>
        <ul className="rows">{(data?.items || []).map((x: any) => (
          <li key={x.id}><div>{row(x)}</div><span className="row-actions"><Pill status={x.status} /><Transitions type={type} id={x.id} status={x.status} onDone={reload} /></span></li>
        ))}</ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </Frame>
  );
}

function CreateJson({ title, path, example, onDone }: { title: string; path: string; example: object; onDone?: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(JSON.stringify(example, null, 2));
  const { run, busy } = useAction();
  return (
    <>
      <div><Button variant="primary" onClick={() => setOpen(true)}>{title}</Button></div>
      <Modal open={open} title={title} onClose={() => setOpen(false)} footer={<Button variant="primary" busy={busy} onClick={() => {
        let body: any;
        try { body = JSON.parse(text); } catch { return run(async () => { throw new Error("JSON inválido"); }); }
        run(() => api.post(path, body), "Criado como rascunho").then((x) => { if (x) { setOpen(false); onDone?.(); location.reload(); } });
      }}>Criar rascunho</Button>}>
        <p className="fineprint">Editor avançado: o servidor valida todos os campos e recusa o que estiver inválido. O conteúdo nasce em rascunho e segue o fluxo de revisão.</p>
        <TextArea rows={18} value={text} onChange={setText} spellCheck={false} />
      </Modal>
    </>
  );
}

export function Resources() {
  return (
    <SimpleList title="Biblioteca" path="/v1/admin/content/resources" type="resource"
      row={(x) => <><strong>{x.title}</strong><p className="muted">{label(x.kind)} · v{x.version}{x.demo ? " · EXEMPLO" : ""}</p></>}
      create={<CreateJson title="Novo material" path="/v1/admin/content/resources" example={{ slug: "meu-material", kind: "checklist", title: "Título do material", summary: "", visibility: "authenticated", origin: "official", checklist_items: ["Primeiro item"], demo: false }} />} />
  );
}

export function Faqs() {
  return (
    <SimpleList title="Perguntas frequentes" path="/v1/admin/content/faqs" type="faq"
      row={(x) => <><strong>{x.question}</strong><p className="muted">{x.helpful_yes ?? 0} úteis · {x.helpful_no ?? 0} não úteis{x.demo ? " · EXEMPLO" : ""}</p></>}
      create={<CreateJson title="Nova pergunta" path="/v1/admin/content/faqs" example={{ question: "Pergunta?", answer: "Resposta.", visibility: "public", origin: "official", demo: false }} />} />
  );
}

export function Courses() {
  return (
    <SimpleList title="Cursos" path="/v1/admin/content/courses" type="course"
      row={(x) => <><strong>{x.title}</strong><p className="muted">{label(x.level)}{x.demo ? " · EXEMPLO" : ""} · v{x.version}</p></>}
      create={<CreateJson title="Novo curso" path="/v1/admin/content/courses" example={{ slug: "meu-curso", title: "Título", level: "beginner", pass_score: 70, cert_enabled: false, visibility: "authenticated", modules: [{ title: "Módulo 1", lessons: [{ title: "Aula 1", kind: "text", body: "Texto da aula." }] }] }} />} />
  );
}

// ----------------------------------------------------------------------------------------- eventos
export function EventsAdmin() {
  const list = useLoad("/v1/help/events?when=all&limit=50");
  const [sel, setSel] = useState<any>(null);
  const regs = useLoad(sel ? `/v1/admin/content/events/${sel.id}/registrations` : null);
  const { run } = useAction();
  const draft = useLoad("/v1/admin/content/overview");
  return (
    <Frame title="Eventos">
      <CreateJson title="Novo evento" path="/v1/admin/content/events" example={{ slug: "meu-evento", kind: "webinar", title: "Título", description: "", starts_at: new Date(Date.now() + 14 * 864e5).toISOString(), duration_min: 60, modality: "online", capacity: 100, visibility: "public", demo: false }} />
      <StateView loading={list.loading} error={list.error} onRetry={list.reload} empty={list.data && !list.data.items.length && "Nenhum evento publicado. Rascunhos aparecem na fila de revisão da visão geral."}>
        <ul className="rows">{(list.data?.items || []).map((e: any) => (
          <li key={e.id}><div><strong>{e.title}</strong><p className="muted">{dateTime(e.starts_at)} · {e.seats_taken ?? 0} inscritas{e.capacity ? ` de ${e.capacity}` : ""}</p></div>
            <span className="row-actions"><Pill status={e.status} /><Button variant="ghost" onClick={() => setSel(e)}>Inscritas</Button>
              {e.status === "published" && <Button variant="ghost" onClick={() => run(() => api.patch(`/v1/admin/content/events/${e.id}`, { status: "completed" }), "Evento concluído").then(list.reload)}>Concluir</Button>}
              {e.status === "published" && <Button variant="danger" onClick={() => run(() => api.patch(`/v1/admin/content/events/${e.id}`, { status: "cancelled" }), "Evento cancelado").then(list.reload)}>Cancelar</Button>}</span></li>
        ))}</ul>
      </StateView>
      {draft.data && <p className="fineprint">Rascunhos e revisão: {(draft.data.by_status.events || []).map((r: any) => `${label(r.status)} ${r.n}`).join(", ") || "nenhum"}.</p>}
      <Modal open={!!sel} title={`Inscritas — ${sel?.title || ""}`} onClose={() => setSel(null)}>
        <StateView loading={regs.loading} error={regs.error} empty={regs.data && !regs.data.items.length && "Ninguém inscrito."}>
          <ul className="rows">{(regs.data?.items || []).map((r: any) => (
            <li key={r.user_id}><span>{r.full_name}{r.org ? ` · ${r.org}` : ""}</span>
              <span className="row-actions"><Pill status={r.status} />{r.attended ? <Pill tone="good">Presente</Pill> : <Button variant="ghost" onClick={() => run(() => api.post(`/v1/admin/content/events/${sel.id}/attendance`, { user_ids: [r.user_id] }), "Presença registrada").then(regs.reload)}>Marcar presença</Button>}</span></li>
          ))}</ul>
        </StateView>
      </Modal>
    </Frame>
  );
}

// ----------------------------------------------------------------------------------------- suporte
export function SupportQueue() {
  const [status, setStatus] = useState("active");
  const [overdue, setOverdue] = useState(false);
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useLoad(`/v1/admin/support/tickets${qs({ status, overdue, offset })}`);
  const sla = useLoad("/v1/admin/support/sla");
  return (
    <Frame title="Fila de suporte">
      <div className="stack-row">
        <Select aria-label="Estado" value={status} onChange={setStatus} options={[["active", "Em aberto"], ["open", "Novos"], ["in_progress", "Em atendimento"], ["waiting_user", "Aguardando a pessoa"], ["resolved", "Resolvidos"], ["closed", "Encerrados"]]} />
        <label className="check"><input type="checkbox" checked={overdue} onChange={(e: any) => setOverdue(e.target.checked)} /> Só atrasados</label>
      </div>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhum chamado."}>
        <ul className="rows">{(data?.items || []).map((t: any) => (
          <li key={t.id}><div><Link to={`/admin/central/suporte/${t.id}`}><strong>#{t.number} {t.subject}</strong></Link><p className="muted">{t.requester} · {label(t.category)} · resolução até {dateTime(t.resolution_due)}</p></div>
            <span className="row-actions">{t.overdue && <Pill tone="bad">Atrasado</Pill>}{t.escalated_at && <Pill tone="warn">Escalado</Pill>}<Pill tone={t.priority === "critical" || t.priority === "high" ? "warn" : "muted"}>{t.priority}</Pill></span></li>
        ))}</ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      {sla.data && <Panel title="Metas de atendimento (SLA)" quiet><ul className="rows">{(sla.data.items || sla.data).map((s: any) => <li key={s.priority}><span>{s.priority}</span><span className="muted">1ª resposta {s.first_response_minutes} min · resolução {s.resolution_minutes} min · escala em {s.escalate_after_minutes} min</span></li>)}</ul><p className="fineprint">Valores iniciais são hipótese de trabalho; ajuste conforme a capacidade real da equipe.</p></Panel>}
    </Frame>
  );
}

export function SupportTicket({ id }: { id: string }) {
  const { data: t, loading, error, reload } = useLoad(`/v1/admin/support/tickets/${id}`);
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const { run, busy } = useAction();
  const upd = (patch: object, ok: string) => run(() => api.patch(`/v1/admin/support/tickets/${id}`, patch), ok).then(reload);
  return (
    <Frame title={t ? `#${t.number} ${t.subject}` : "Chamado"}>
      <StateView loading={loading} error={error} onRetry={reload}>
        {t && (
          <>
            <KeyValue items={[["Solicitante", t.requester], ["Categoria", label(t.category)], ["Contexto", Object.entries(t.context || {}).map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"], ["Recorrente", t.recurring ? "Sim" : "Não"],
              ["1ª resposta até", dateTime(t.first_response_due)], ["Resolução até", dateTime(t.resolution_due)], ["Atraso", t.sla.resolution_overdue ? "Resolução atrasada" : t.sla.first_response_overdue ? "Primeira resposta atrasada" : "Dentro da meta"]]} />
            <div className="stack-row">
              <Select aria-label="Estado" value={t.status} onChange={(v) => upd({ status: v }, "Estado atualizado")} options={[["open", "Aberto"], ["in_progress", "Em atendimento"], ["waiting_user", "Aguardando a pessoa"], ["waiting_internal", "Análise interna"], ["resolved", "Resolvido"], ["closed", "Encerrado"]]} />
              <Select aria-label="Prioridade" value={t.priority} onChange={(v) => upd({ priority: v }, "Prioridade atualizada")} options={[["low", "Baixa"], ["normal", "Normal"], ["high", "Alta"], ["critical", "Crítica"]]} />
              <Button variant="ghost" onClick={() => upd({ assign: true }, "Chamado assumido")}>Assumir</Button>
            </div>
            <Panel title="Conversa">
              <ul className="thread">{t.messages.map((m: any) => <li key={m.id} className={m.internal ? "internal" : m.author_kind === "staff" ? "from-staff" : ""}><strong>{m.internal ? "Nota interna" : m.author_kind === "staff" ? "Atendimento" : t.requester}</strong> <span className="fineprint">{dateTime(m.created_at)}</span><p className="prose">{m.body}</p></li>)}</ul>
            </Panel>
            <form className="stack" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/admin/support/tickets/${id}/messages`, { body, internal }), "Enviado").then(() => { setBody(""); reload(); }); }}>
              <Field label="Responder"><TextArea rows={4} value={body} onChange={setBody} /></Field>
              <label className="check"><input type="checkbox" checked={internal} onChange={(e: any) => setInternal(e.target.checked)} /> Nota interna (a pessoa não vê)</label>
              <div className="form-actions"><Button type="submit" variant="primary" busy={busy} disabled={!body.trim()}>Enviar</Button></div>
            </form>
          </>
        )}
      </StateView>
    </Frame>
  );
}

// ----------------------------------------------------------------------------------------- parcerias (CRM)
const STAGES: [string, string][] = [["received", "Recebida"], ["qualification", "Qualificação"], ["contact", "Contato"], ["meeting", "Reunião"], ["proposal", "Proposta"], ["negotiation", "Negociação"], ["approved", "Aprovada"], ["active", "Ativa"], ["rejected", "Recusada"], ["archived", "Arquivada"]];
export function Partnerships() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, loading, error, reload } = useLoad(`/v1/admin/hub/partnerships${qs({ status, offset })}`);
  const [sel, setSel] = useState<string | null>(null);
  const one = useLoad(sel ? `/v1/admin/hub/partnerships/${sel}` : null);
  const [note, setNote] = useState("");
  const { run } = useAction();
  return (
    <Frame title="Parcerias">
      <Select aria-label="Etapa" value={status} onChange={(v) => { setStatus(v); setOffset(0); }} placeholder="Todas as etapas" options={STAGES} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhuma proposta."}>
        <ul className="rows">{(data?.items || []).map((p: any) => <li key={p.id}><div><strong>{p.org_name}</strong><p className="muted">{p.contact_name} · {label(p.kind)} · {dateTime(p.created_at)}</p></div><span className="row-actions"><Pill tone="muted">{STAGES.find((s) => s[0] === p.status)?.[1] || p.status}</Pill><Button variant="ghost" onClick={() => setSel(p.id)}>Abrir</Button></span></li>)}</ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={!!sel} title={one.data?.org_name || "Proposta"} onClose={() => setSel(null)}>
        <StateView loading={one.loading} error={one.error}>
          {one.data && (
            <div className="stack-lg">
              <KeyValue items={[["Contato", `${one.data.contact_name} <${one.data.contact_email}>`], ["Objetivo", one.data.objective], ["Proposta", one.data.proposal || "—"], ["Território", one.data.territory || "—"], ["Oferece", one.data.resources_offered || "—"], ["Espera", one.data.counterpart || "—"], ["Consentimento", `${dateTime(one.data.consent_at)} (${one.data.consent_version})`]]} />
              <Select aria-label="Mover para" value={one.data.status} onChange={(v) => run(() => api.post(`/v1/admin/hub/partnerships/${sel}/move`, { to: v }), "Etapa atualizada").then(() => { one.reload(); reload(); })} options={STAGES} />
              <ul className="rows">{one.data.activities.map((a: any, i: number) => <li key={i}><span>{a.kind}{a.to_status ? `: ${label(a.from_status)} → ${label(a.to_status)}` : ""} {a.body || ""}</span><span className="muted">{dateTime(a.created_at)}</span></li>)}</ul>
              <div className="stack-row"><Input aria-label="Nota" placeholder="Registrar nota" value={note} onChange={setNote} /><Button variant="ink" disabled={!note.trim()} onClick={() => run(() => api.post(`/v1/admin/hub/partnerships/${sel}/notes`, { body: note }), "Nota registrada").then(() => { setNote(""); one.reload(); })}>Salvar nota</Button></div>
            </div>
          )}
        </StateView>
      </Modal>
    </Frame>
  );
}

// ----------------------------------------------------------------------------------------- testes e demonstrações
export function Trials() {
  const dash = useLoad("/v1/admin/hub/trials");
  const reqs = useLoad("/v1/admin/hub/trial-requests?status=requested");
  const demos = useLoad("/v1/admin/hub/demo-requests");
  const [dec, setDec] = useState<{ id: string; approve: boolean } | null>(null);
  const [reason, setReason] = useState("");
  const { run, busy } = useAction();
  return (
    <Frame title="Testes e demonstrações">
      <Panel title="Pedidos de teste aguardando decisão">
        <StateView loading={reqs.loading} error={reqs.error} empty={reqs.data && !reqs.data.items.length && "Nenhum pedido pendente."}>
          <ul className="rows">{(reqs.data?.items || []).map((r: any) => (
            <li key={r.id}><div><strong>{r.legal_name}</strong><p className="muted">{r.users_count} pessoas · {r.period_days} dias · {r.purpose}</p></div>
              <span className="row-actions"><Button variant="primary" onClick={() => setDec({ id: r.id, approve: true })}>Aprovar</Button><Button variant="danger" onClick={() => setDec({ id: r.id, approve: false })}>Recusar</Button></span></li>
          ))}</ul>
        </StateView>
      </Panel>
      <Panel title="Painel de testes">
        <StateView loading={dash.loading} error={dash.error}>
          {dash.data && <KeyValue items={[["Ativos", String(dash.data.active)], ["Convertidos", String(dash.data.converted)], ["Encerrados", String(dash.data.ended)], ["Pedidos", (dash.data.requests || []).map((r: any) => `${label(r.status)} ${r.n}`).join(", ") || "—"]]} />}
          <ul className="rows">{(dash.data?.usage || []).map((u: any) => <li key={u.org_id}><span>{u.legal_name}</span><span className="muted">até {date(u.trial_end)} · {u.projects} projetos · {u.documents} documentos · {u.applications} candidaturas</span></li>)}</ul>
          <p className="fineprint">{dash.data?.note}</p>
        </StateView>
      </Panel>
      <Panel title="Demonstrações">
        <StateView loading={demos.loading} error={demos.error} empty={demos.data && !demos.data.items.length && "Nenhum pedido."}>
          <ul className="rows">{(demos.data?.items || []).map((d: any) => <DemoRow key={d.id} d={d} onDone={demos.reload} />)}</ul>
        </StateView>
      </Panel>
      <Modal open={!!dec} title={dec?.approve ? "Aprovar teste" : "Recusar teste"} onClose={() => setDec(null)} footer={<Button variant="primary" busy={busy} disabled={reason.trim().length < 5} onClick={() => run(() => api.post(`/v1/admin/hub/trial-requests/${dec!.id}/decide`, { approve: dec!.approve, reason }), "Decisão registrada").then(() => { setDec(null); setReason(""); reqs.reload(); dash.reload(); })}>Confirmar</Button>}>
        <Field label="Motivo (obrigatório, fica no registro)"><TextArea rows={3} value={reason} onChange={setReason} /></Field>
      </Modal>
    </Frame>
  );
}

function DemoRow({ d, onDone }: { d: any; onDone: () => void }) {
  const [when, setWhen] = useState("");
  const [url, setUrl] = useState("");
  const { run } = useAction();
  return (
    <li>
      <div><strong>{d.org_name}</strong><p className="muted">{d.contact_name} · {label(d.audience_kind)} · {label(d.status)}{d.scheduled_at ? ` · ${dateTime(d.scheduled_at)}` : ""}</p></div>
      {d.status === "requested" && (
        <span className="row-actions">
          <Input aria-label="Data e hora" type="datetime-local" value={when} onChange={setWhen} />
          <Input aria-label="Link da reunião" placeholder="https://" value={url} onChange={setUrl} />
          <Button variant="ink" disabled={!when} onClick={() => run(() => api.post(`/v1/admin/hub/demo-requests/${d.id}/handle`, { status: "scheduled", scheduled_at: new Date(when).toISOString(), meeting_url: url || undefined }), "Agendada e e-mail enviado").then(onDone)}>Agendar</Button>
        </span>
      )}
      {d.status === "scheduled" && <span className="row-actions"><Button variant="ghost" onClick={() => run(() => api.post(`/v1/admin/hub/demo-requests/${d.id}/handle`, { status: "done" }), "Concluída").then(onDone)}>Concluir</Button></span>}
    </li>
  );
}

// ----------------------------------------------------------------------------------------- indicadores
export function Analytics() {
  const { data: a, loading, error, reload } = useLoad("/v1/admin/hub/analytics");
  const news = useLoad("/v1/admin/hub/newsletter");
  const { run, busy } = useAction();
  const bars = (rows: any[] | undefined, k: string, v = "n") => <Bars rows={(rows || []).map((r) => ({ label: String(r[k]), value: Number(r[v]) }))} format={(x) => String(x)} />;
  return (
    <Frame title="Indicadores da Central">
      <StateView loading={loading} error={error} onRetry={reload}>
        {a && (
          <>
            <p className="fineprint">{a.privacy_note} Janela: {a.period_days} dias.</p>
            <div className="grid-home">
              <Panel title="Buscas"><KeyValue items={[["Total", String(a.searches)], ["Sem resultado", String(a.searches_without_result)], ["Assistente: respondidas", String(a.assistant?.answered ?? 0)], ["Assistente: sem base", String(a.assistant?.no_basis ?? 0)], ["Chamados abertos pela ajuda", String(a.tickets_from_help)]]} /></Panel>
              <Panel title="Assuntos mais buscados">{bars(a.top_topics, "topic")}</Panel>
              <Panel title="Lacunas (buscas sem resposta)">{bars(a.gap_topics, "topic")}</Panel>
              <Panel title="Guias mais vistos">{bars((a.top_articles || []).map((x: any) => ({ ...x, n: x.view_count })), "title")}</Panel>
              <Panel title="Telas com mais pedidos de ajuda">{bars(a.context_help, "ctx_key")}</Panel>
              <Panel title="Suporte"><KeyValue items={[["Abertos", String(a.tickets?.open ?? 0)], ["Atrasados", String(a.tickets?.overdue ?? 0)], ["1ª resposta média (h)", String(a.tickets?.avg_first_response_h ?? "—")], ["Satisfação média", String(a.tickets?.avg_satisfaction ?? "—")]]} /></Panel>
              <Panel title="Academia"><KeyValue items={[["Matrículas", String(a.academy?.enrollments ?? 0)], ["Conclusões", String(a.academy?.completions ?? 0)], ["Certificados", String(a.academy?.certificates ?? 0)]]} /></Panel>
              <Panel title="Parcerias por etapa">{bars(a.partnerships, "status")}</Panel>
            </div>
            {a.recurring_tickets?.length > 0 && <Panel title="Assuntos recorrentes em chamados (candidatos a novo guia)"><ul className="rows">{a.recurring_tickets.map((r: any, i: number) => <li key={i}><span>{label(r.category)} · {r.page}</span><span className="muted">{r.tickets} chamados</span></li>)}</ul></Panel>}
          </>
        )}
      </StateView>
      <Panel title="Boletim">
        {news.data && <KeyValue items={news.data.by_status.map((r: any) => [`${label(r.status)} (${label(r.frequency)})`, String(r.n)] as [string, string])} />}
        <Button variant="ghost" busy={busy} onClick={() => run(() => api.post("/v1/admin/hub/newsletter/dispatch"), "Envio disparado")}>Enviar agora aos inscritos devidos</Button>
      </Panel>
    </Frame>
  );
}

// ----------------------------------------------------------------------------------------- equipe editorial
export function StaffRoles() {
  const { data, loading, error, reload } = useLoad("/v1/admin/staff-roles");
  const f = useForm({ email: "", role: "editor" });
  const { run, busy } = useAction();
  return (
    <Frame title="Equipe editorial">
      <p className="muted">Editor escreve; revisor aprova e publica (outra pessoa); suporte atende chamados. Só administradores da plataforma concedem papéis.</p>
      <form className="stack-row" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/admin/staff-roles", f.v), "Papel concedido").then(() => { f.set("email")(""); reload(); }); }}>
        <Input aria-label="E-mail" type="email" placeholder="E-mail da pessoa" value={f.v.email} onChange={f.set("email")} required />
        <Select aria-label="Papel" value={f.v.role} onChange={f.set("role")} options={[["editor", "Editor"], ["reviewer", "Revisor"], ["support", "Suporte"]]} />
        <Button type="submit" variant="primary" busy={busy}>Conceder</Button>
      </form>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length && "Nenhum papel concedido."}>
        <ul className="rows">{(data?.items || []).map((r: any) => (
          <li key={r.user_id + r.role}><span>{r.full_name} · {r.email}</span><span className="row-actions"><Pill tone="muted">{label(r.role)}</Pill><Button variant="danger" onClick={() => run(() => api.del(`/v1/admin/staff-roles/${r.user_id}/${r.role}`), "Papel removido").then(reload)}>Remover</Button></span></li>
        ))}</ul>
      </StateView>
    </Frame>
  );
}
