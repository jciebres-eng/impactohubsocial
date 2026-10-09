import { useEffect, useState } from "react";
import { api, describeError } from "../api";
import { date, dateTime, money } from "../format";
import { Link, useLocation } from "../router";
import { Button, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";
import { ContextualHelp } from "../ui/help";

const Q_STATUS: [string, string][] = [["draft", "Rascunho"], ["open", "Aberta"], ["paused", "Pausada"], ["closed", "Fechada"]];
const C_STATUS: [string, string][] = [["draft", "Rascunho"], ["published", "Publicada"], ["closed", "Fechada"]];
const EMPTY_Q = { project_id: "", label: "", description: "", quota: "", total: "", min: "1", max: "", deadline: "" };

function QuotaProgress({ q }: { q: any }) {
  const pct = q.total_quotas ? Math.round((q.taken / q.total_quotas) * 100) : 0;
  return (
    <>
      <p><strong>{q.remaining_quotas}</strong> de {q.total_quotas} cota(s) ainda disponível(is) — {money(q.quota_cents)} cada
        {" "}(meta {money(q.goal_cents)}).</p>
      <div className="bar" role="img" aria-label={`${pct}% das cotas reservadas`}>
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <p className="muted small">{q.taken} reservada(s) · {q.confirmed} confirmada(s) · {money(q.raised_cents)} recebido(s)
        {q.deadline ? ` · prazo ${date(q.deadline)}` : ""}</p>
    </>
  );
}

export function Quotas() {
  const { data, error, loading, reload } = useLoad<any>("/v1/funding-quotas");
  const f = useForm<any>(EMPTY_Q);
  const { busy, run } = useAction();
  const [creating, setCreating] = useState(false);

  async function create(e: any) {
    e.preventDefault();
    await run(async () => {
      await api.post("/v1/funding-quotas", {
        project_id: f.v.project_id, label: f.v.label,
        ...(f.v.description ? { description: f.v.description } : {}),
        quota_cents: Math.round(parseFloat(String(f.v.quota).replace(",", ".")) * 100),
        total_quotas: parseInt(f.v.total, 10), min_per_backer: parseInt(f.v.min || "1", 10),
        ...(f.v.max ? { max_per_backer: parseInt(f.v.max, 10) } : {}),
        ...(f.v.deadline ? { deadline: f.v.deadline } : {}),
      });
      setCreating(false); f.setV(EMPTY_Q); reload();
      return "Cotas criadas em rascunho. Abra quando estiver pronta para receber apoio.";
    });
  }

  return (
    <>
      <PageHead title={<>Financiamento em cotas <ContextualHelp id="nao_custodial" /></>} sub="Divida o custo do projeto em cotas e mostre publicamente quantas faltam. A plataforma instrui e concilia; nunca guarda o dinheiro."
                actions={<Button variant="primary" onClick={() => setCreating(true)}>Criar cotas</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.map((q: any) => (
          <Panel key={q.id} title={q.label} actions={
            <Select aria-label="Situação da cota" value={q.status} options={Q_STATUS}
                    onChange={(v) => run(async () => { await api.patch(`/v1/funding-quotas/${q.id}`, { status: v }); reload(); return "Situação atualizada."; })} />}>
            {q.description && <p>{q.description}</p>}
            <QuotaProgress q={q} />
            <p><Link to={`/cotas/${q.id}/apoios`}>Ver apoios</Link></p>
          </Panel>
        ))}
      </StateView>
      <Modal open={creating} title="Criar cotas de financiamento" onClose={() => setCreating(false)}
             footer={<><Button onClick={() => setCreating(false)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={create}
                       disabled={!f.v.project_id || !f.v.label || !f.v.quota || !f.v.total}>Criar</Button></>}>
        <p className="muted small">O valor da cota é definido pela sua organização. A plataforma não sugere nem calcula preço.</p>
        <Field label="Projeto (identificador)"><Input value={f.v.project_id} onChange={f.set("project_id")} placeholder="UUID do projeto" /></Field>
        <Field label="Nome da cota"><Input value={f.v.label} onChange={f.set("label")} placeholder="Ex.: Cota de apoio mensal" /></Field>
        <Field label="Descrição" wide><TextArea value={f.v.description} onChange={f.set("description")} rows={2} /></Field>
        <Field label="Valor de cada cota (R$)"><Input value={f.v.quota} onChange={f.set("quota")} placeholder="250,00" /></Field>
        <Field label="Quantas cotas no total"><Input value={f.v.total} onChange={f.set("total")} inputMode="numeric" /></Field>
        <Field label="Mínimo por apoiador"><Input value={f.v.min} onChange={f.set("min")} inputMode="numeric" /></Field>
        <Field label="Máximo por apoiador" hint="Em branco = sem limite"><Input value={f.v.max} onChange={f.set("max")} inputMode="numeric" /></Field>
        <Field label="Prazo"><Input type="date" value={f.v.deadline} onChange={f.set("deadline")} /></Field>
      </Modal>
    </>
  );
}

export function QuotaPledges({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/funding-quotas/${id}/pledges`, [id]);
  return (
    <>
      <PageHead title="Apoios recebidos" back="/cotas" />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <ul className="rows">{data.items.map((p: any) => (
            <li key={p.id}>
              <span>{p.backer_name || "Apoiador"}<br />
                <span className="muted small">{p.quantity} cota(s) · {money(p.amount_cents)} · {dateTime(p.created_at)}</span></span>
              <Pill tone={p.status === "confirmed" ? "good" : p.status === "pledged" ? "warn" : "muted"}>{p.status}</Pill>
            </li>
          ))}</ul>
        )}
        <p className="muted small">A confirmação do recebimento é registrada pela equipe da plataforma — uma reserva não se
          confirma sozinha.</p>
      </StateView>
    </>
  );
}

const EMPTY_C = { project_id: "", slug: "", title: "", summary: "", story: "", show_backers: false };

export function Campaigns() {
  const { data, error, loading, reload } = useLoad<any>("/v1/funding-quotas");
  const f = useForm<any>(EMPTY_C);
  const { busy, run } = useAction();
  const [creating, setCreating] = useState(false);
  const [campaign, setCampaign] = useState<any>(null);

  useEffect(() => { api.get("/v1/campaigns").then((r) => setCampaign(r.items?.[0] || null)).catch(() => setCampaign(null)); }, []);

  async function create(e: any) {
    e.preventDefault();
    await run(async () => {
      const out = await api.post("/v1/campaigns", {
        project_id: f.v.project_id, slug: f.v.slug, title: f.v.title, summary: f.v.summary,
        ...(f.v.story ? { story: f.v.story } : {}), show_backers: !!f.v.show_backers,
      });
      setCreating(false); f.setV(EMPTY_C); setCampaign({ ...out, status: "draft" });
      return "Campanha criada em rascunho.";
    });
  }

  return (
    <>
      <PageHead title="Campanha de divulgação" sub="Dá publicidade ao projeto e mostra quantas cotas faltam."
                actions={<Button variant="primary" onClick={() => setCreating(true)}>Criar campanha</Button>} />
      {campaign?.id && (
        <Panel title={campaign.title || "Campanha"} actions={
          <Select aria-label="Situação da campanha" value={campaign.status || "draft"} options={C_STATUS}
                  onChange={(v) => run(async () => {
                    await api.patch(`/v1/campaigns/${campaign.id}`, { status: v });
                    setCampaign({ ...campaign, status: v });
                    return v === "published" ? "Campanha publicada." : "Situação atualizada.";
                  })} />}>
          <KeyValue items={[["Endereço público", <Link key="l" to={`/campanha/${campaign.slug}`}>/campanha/{campaign.slug}</Link>],
                            ["Situação", campaign.status || "draft"]]} />
        </Panel>
      )}
      <StateView loading={loading} error={error} onRetry={reload}>
        {data?.items?.map((q: any) => <Panel key={q.id} title={q.label}><QuotaProgress q={q} /></Panel>)}
      </StateView>
      <Modal open={creating} title="Criar campanha" onClose={() => setCreating(false)}
             footer={<><Button onClick={() => setCreating(false)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={create}
                       disabled={!f.v.project_id || !f.v.slug || !f.v.title || f.v.summary.length < 20}>Criar</Button></>}>
        <Field label="Projeto (identificador)"><Input value={f.v.project_id} onChange={f.set("project_id")} /></Field>
        <Field label="Endereço público" hint="Só letras minúsculas, números e hífen."><Input value={f.v.slug} onChange={f.set("slug")} placeholder="nossa-campanha-2026" /></Field>
        <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Resumo" wide hint="Entre 20 e 600 caracteres."><TextArea value={f.v.summary} onChange={f.set("summary")} rows={3} /></Field>
        <Field label="História do projeto" wide><TextArea value={f.v.story} onChange={f.set("story")} rows={6} /></Field>
        <Field label="Mostrar apoiadores publicamente">
          <Select value={f.v.show_backers ? "1" : "0"} onChange={(v) => f.set("show_backers")(v === "1")}
                  options={[["0", "Não"], ["1", "Sim"]]} />
        </Field>
      </Modal>
    </>
  );
}

// ------------------------------------------------------------------ página pública da campanha
export function PublicCampaign() {
  const { path } = useLocation();
  const slug = path.replace(/^\/campanha\/?/, "");
  const [state, setState] = useState<{ data?: any; error?: string; loading: boolean }>({ loading: true });
  useEffect(() => {
    api.get(`/v1/public/campaigns/${encodeURIComponent(slug)}`)
      .then((data) => setState({ data, loading: false }))
      .catch((e) => setState({ error: describeError(e), loading: false }));
  }, [slug]);
  const d = state.data;
  return (
    <StateView loading={state.loading} error={state.error}>
      {d && (
        <>
          <h1>{d.campaign.title}</h1>
          <p>{d.campaign.summary}</p>
          <p className="muted small">{d.organization.name}{d.organization.city ? ` — ${d.organization.city}/${d.organization.uf}` : ""}
            {" · "}projeto: {d.campaign.project_title}</p>
          {d.impact_tags?.length > 0 && (
            <p>{d.impact_tags.map((t: any) => (
              <span key={`${t.taxonomy}-${t.code}`} className="pill"
                    style={t.color_hex ? { background: t.color_hex, color: "#fff" } : undefined}>{t.name || t.code}</span>
            ))}</p>
          )}
          <Panel title={`Faltam ${d.remaining_quotas} cota(s)`}>
            {d.quotas.map((q: any) => (
              <div key={q.id}>
                <h3>{q.label}</h3>
                {q.description && <p>{q.description}</p>}
                <QuotaProgress q={q} />
              </div>
            ))}
          </Panel>
          {d.campaign.story && <Panel title="A história do projeto"><p style={{ whiteSpace: "pre-wrap" }}>{d.campaign.story}</p></Panel>}
          {d.backers?.length > 0 && (
            <Panel title="Quem já apoiou">
              <ul className="rows">{d.backers.map((b: any, i: number) => (
                <li key={i}><span>{b.name}</span><Pill tone="muted">{b.quantity} cota(s)</Pill></li>
              ))}</ul>
            </Panel>
          )}
          <p className="muted small">{d.note}</p>
        </>
      )}
    </StateView>
  );
}
