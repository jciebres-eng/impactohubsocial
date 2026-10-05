// Rede e mensagens, oportunidades profissionais, necessidades do projeto, conquistas objetivas.
import { useState } from "react";
import { api } from "../api";
import { dateTime, label, MATCH_STATE } from "../format";
import { Link } from "../router";
import { Button, Field, Input, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad, useTaxonomy } from "../ui/kit";

export function Messages({ cid }: { cid?: string }) {
  const convs = useLoad<any>("/v1/messages/conversations");
  const thread = useLoad<any>(cid ? `/v1/messages/conversations/${cid}` : null, [cid]);
  const [body, setBody] = useState("");
  const { busy, run } = useAction();
  const current = convs.data?.items?.find((c: any) => c.id === cid);
  return (
    <>
      <PageHead title="Mensagens" sub="Conversas só entre organizações que já têm relação na plataforma." />
      <div className="grid-home">
        <Panel title="Conversas">
          <StateView loading={convs.loading} error={convs.error} onRetry={convs.reload}>
            {(convs.data?.items || []).length === 0 ? <p className="muted">Sem conversas. Elas começam a partir de uma candidatura, aporte ou oferta aceita.</p> :
              <ul className="rows">{convs.data.items.map((c: any) => <li key={c.id}><Link to={`/mensagens/${c.id}`}>{c.with_name}</Link>{c.unread > 0 && <Pill tone="warn">{c.unread} nova(s)</Pill>}</li>)}</ul>}
          </StateView>
        </Panel>
        {cid && current && (
          <Panel title={current.with_name}>
            <StateView loading={thread.loading} error={thread.error} onRetry={thread.reload}>
              <ul className="rows" aria-live="polite">{(thread.data?.items || []).slice().reverse().map((m: any) => (
                <li key={m.id}><span><strong>{m.mine ? "Você" : m.sender}:</strong> {m.removed ? <em className="muted">mensagem removida pela moderação</em> : m.body}</span>
                  <span className="muted">{dateTime(m.created_at)}</span></li>))}</ul>
            </StateView>
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/messages/${current.with_org_id}`, { body }), "Mensagem enviada").then(() => { setBody(""); thread.reload(); convs.reload(); }); }}>
              <Field label="Nova mensagem" wide><TextArea value={body} onChange={setBody} rows={3} maxLength={4000} /></Field>
              <div className="stack-row">
                <Button type="submit" variant="primary" busy={busy} disabled={!body.trim()}>Enviar</Button>
                <Button variant="ghost" onClick={() => run(() => api.post(`/v1/network/block/${current.with_org_id}`), "Organização bloqueada").then(convs.reload)}>Bloquear</Button>
              </div>
            </form>
          </Panel>
        )}
      </div>
    </>
  );
}

export function ProjectNeeds({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/needs`);
  const tax = useTaxonomy();
  const f = useForm<any>({ category: "", title: "", description: "" });
  const { busy, run } = useAction();
  const cats: [string, string][] = Object.entries(tax?.professional_categories || {}) as [string, string][];
  return (
    <>
      <PageHead title="Apoio profissional" sub="Publique o que o projeto precisa; profissionais compatíveis podem se oferecer." back={<Link to={`/projetos/${id}`} className="back">Projeto</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Necessidades">
            {(data?.items || []).length === 0 ? <p className="muted">Nenhuma necessidade publicada.</p> : (
              <ul className="rows">{data.items.map((x: any) => <li key={x.id}><span><Link to={`/necessidades/${x.id}`}>{x.title}</Link> <span className="muted">{x.category} · {x.offers} oferta(s)</span></span><Pill status={x.status} /></li>)}</ul>
            )}
          </Panel>
          <Panel title="Nova necessidade">
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${id}/needs`, { category: f.v.category, title: f.v.title, description: f.v.description || null }), "Necessidade publicada").then(reload); }}>
              <Field label="Categoria profissional">{cats.length ? <Select value={f.v.category} onChange={f.set("category")} placeholder="Escolha…" options={cats} /> : <Input value={f.v.category} onChange={f.set("category")} placeholder="ex.: contador" />}</Field>
              <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
              <Field label="Detalhes" wide><TextArea value={f.v.description} onChange={f.set("description")} rows={3} /></Field>
              <Button type="submit" variant="primary" busy={busy} disabled={!f.v.category || f.v.title.length < 3}>Publicar</Button>
            </form>
          </Panel>
        </div>
      </StateView>
    </>
  );
}

function MatchBadge({ m }: { m: any }) {
  const s = MATCH_STATE[m.recommended_state] || { label: m.recommended_state, tone: "muted" };
  return (
    <div>
      <Pill tone={s.tone}>{s.label}</Pill> {m.score !== null && m.score !== undefined && <span className="muted">compatibilidade {Math.round(m.score)} · confiança {Math.round(m.confidence)}%</span>}
      {m.requirements?.length > 0 && <ul>{m.requirements.map((r: any) => <li key={r.code}>{r.label}</li>)}</ul>}
    </div>
  );
}

export function NeedDetail({ id }: { id: string }) {
  const offers = useLoad<any>(`/v1/needs/${id}/offers`);
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Ofertas recebidas" />
      <StateView loading={offers.loading} error={offers.error} onRetry={offers.reload}>
        {(offers.data?.items || []).length === 0 ? <p className="muted">Ainda sem ofertas.</p> : (
          <div className="stack-lg">{offers.data.items.map((o: any) => (
            <Panel key={o.id} title={o.name}>
              <p>{o.message}</p>
              <MatchBadge m={o.match} />
              <div className="stack-row"><Pill status={o.status} />
                {o.status === "pending" && <>
                  <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/offers/${o.id}/decide`, { decision: "accepted" }), "Oferta aceita").then(offers.reload)}>Aceitar</Button>
                  <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/offers/${o.id}/decide`, { decision: "declined" }), "Oferta recusada").then(offers.reload)}>Recusar</Button></>}
              </div>
            </Panel>))}</div>
        )}
      </StateView>
    </>
  );
}

export function Opportunities() {
  const { data, error, loading, reload } = useLoad<any>("/v1/professional/opportunities");
  const mine = useLoad<any>("/v1/professional/offers");
  const [msg, setMsg] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Oportunidades profissionais" sub="Ordenadas por elegibilidade e compatibilidade. Plano pago não altera a ordem nem a elegibilidade." />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          {(data?.items || []).length === 0 ? <p className="muted">Nenhuma necessidade compatível com seu perfil. Complete categorias, credenciais e território no perfil.</p> :
            data.items.map((o: any) => (
              <Panel key={o.id} title={o.title}>
                <p className="muted">{o.osc_name} · {o.project_title} · {o.territory}</p>
                {o.description && <p>{o.description}</p>}
                <MatchBadge m={o.match} />
                {o.already_offered ? <Pill tone="good">Oferta enviada</Pill> : (
                  <div className="stack-row"><Input value={msg} onChange={setMsg} placeholder="Mensagem opcional" aria-label="Mensagem da oferta" />
                    <Button variant="primary" busy={busy} disabled={o.match.eligibility === "blocked"} onClick={() => run(() => api.post(`/v1/needs/${o.id}/offers`, { message: msg || null }), "Oferta enviada").then(() => { setMsg(""); reload(); mine.reload(); })}>Oferecer ajuda</Button></div>
                )}
              </Panel>))}
          <Panel title="Minhas ofertas">
            {(mine.data?.items || []).length === 0 ? <p className="muted">Nenhuma oferta enviada.</p> :
              <ul className="rows">{mine.data.items.map((x: any) => <li key={x.id}><span>{x.title}</span><Pill status={x.status} /></li>)}</ul>}
          </Panel>
        </div>
      </StateView>
    </>
  );
}

export function Badges() {
  const { data, error, loading, reload } = useLoad<any>("/v1/badges");
  return (
    <>
      <PageHead title="Conquistas" sub="Critérios objetivos de boa prática. Não há ranking nem comparação entre organizações." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && <div className="stack-lg">
          <ul className="rows">{data.items.map((b: any) => <li key={b.code}><span><strong>{b.label}</strong><div className="muted">{b.how}{b.progress ? ` · ${b.progress}` : ""}</div></span>
            <Pill tone={b.earned ? "good" : "muted"}>{b.earned ? "Conquistada" : "Em andamento"}</Pill></li>)}</ul>
          <p className="muted">{data.note}</p></div>}
      </StateView>
    </>
  );
}

export { label };
