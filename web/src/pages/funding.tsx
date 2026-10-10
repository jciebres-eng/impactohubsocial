import { useEffect, useState } from "react";
import { api, describeError } from "../api";
import { date, dateTime, money } from "../format";
import { Link, useLocation } from "../router";
import { Button, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";
import { ContextualHelp } from "../ui/help";
import { CampaignAccountability, PublicDonationCampaign, donationStatusLabel } from "./donations";
import { parseMoney } from "../format";

const Q_STATUS: [string, string][] = [["draft", "Rascunho"], ["open", "Aberta"], ["paused", "Pausada"], ["closed", "Fechada"]];
const C_STATUS: [string, string][] = [["published", "Publicada"], ["paused", "Pausada"]];
const KIND_LABEL: Record<string, string> = { project_crowdfunding: "Vaquinha de projeto", emergency: "Emergência", institutional_fund: "Fundo institucional", recurring: "Apoio recorrente", organization: "Organização" };
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

const EMPTY_C = { project_id: "", slug: "", title: "", summary: "", story: "", show_backers: false, kind: "project_crowdfunding", target: "", starts_on: "", ends_on: "",
  purpose: "", contingency_policy: "", refund_policy: "", min_donation: "5,00" };

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
        ...(f.v.project_id ? { project_id: f.v.project_id } : {}), slug: f.v.slug, title: f.v.title, summary: f.v.summary,
        ...(f.v.story ? { story: f.v.story } : {}), show_backers: !!f.v.show_backers, kind: f.v.kind,
        ...(parseMoney(f.v.target) ? { target_cents: parseMoney(f.v.target) } : {}),
        ...(f.v.starts_on ? { starts_on: f.v.starts_on } : {}), ...(f.v.ends_on ? { ends_on: f.v.ends_on } : {}),
        ...(f.v.purpose ? { purpose: f.v.purpose } : {}), ...(f.v.contingency_policy ? { contingency_policy: f.v.contingency_policy } : {}),
        ...(f.v.refund_policy ? { refund_policy: f.v.refund_policy } : {}),
        ...(parseMoney(f.v.min_donation) ? { min_donation_cents: parseMoney(f.v.min_donation) } : {}),
      });
      setCreating(false); f.setV(EMPTY_C); setCampaign({ ...out, status: "draft", slug: f.v.slug, title: f.v.title, kind: f.v.kind, target_cents: parseMoney(f.v.target), qr_version: 1 });
      return "Campanha criada em rascunho.";
    });
  }

  return (
    <>
      <PageHead title="Campanha" sub="Doações confirmadas pelo provedor de pagamento, QR da página e prestação de contas. A plataforma não guarda dinheiro."
                actions={<Button variant="primary" onClick={() => setCreating(true)}>Criar campanha</Button>} />
      {campaign?.id && (
        <>
          <Panel title={campaign.title || "Campanha"} actions={
            ["published", "paused"].includes(campaign.status) && (
              <Select aria-label="Pausar ou retomar" value={campaign.status} options={C_STATUS}
                      onChange={(v) => run(async () => {
                        await api.patch(`/v1/campaigns/${campaign.id}`, { status: v });
                        setCampaign({ ...campaign, status: v });
                        return "Situação atualizada.";
                      })} />)}>
            <KeyValue items={[["Tipo", KIND_LABEL[campaign.kind] || campaign.kind || "—"], ["Situação", donationStatusLabel(campaign.status || "draft")]]} />
          </Panel>
          <CampaignAccountability campaign={campaign} onChange={setCampaign} />
        </>
      )}
      <StateView loading={loading} error={error} onRetry={reload}>
        {data?.items?.map((q: any) => <Panel key={q.id} title={q.label}><QuotaProgress q={q} /></Panel>)}
      </StateView>
      <Modal open={creating} title="Criar campanha" onClose={() => setCreating(false)}
             footer={<><Button onClick={() => setCreating(false)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={create}
                       disabled={(["project_crowdfunding", "emergency"].includes(f.v.kind) && !f.v.project_id) || !f.v.slug || !f.v.title || f.v.summary.length < 20}>Criar</Button></>}>
        <Field label="Tipo"><Select value={f.v.kind} onChange={f.set("kind")} options={Object.entries(KIND_LABEL)} /></Field>
        <Field label="Projeto (identificador)" hint="Obrigatório para vaquinha de projeto e emergência."><Input value={f.v.project_id} onChange={f.set("project_id")} /></Field>
        <Field label="Endereço público" hint="Só letras minúsculas, números e hífen."><Input value={f.v.slug} onChange={f.set("slug")} placeholder="nossa-campanha-2026" /></Field>
        <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Resumo" wide hint="Entre 20 e 600 caracteres."><TextArea value={f.v.summary} onChange={f.set("summary")} rows={3} /></Field>
        <Field label="História do projeto" wide><TextArea value={f.v.story} onChange={f.set("story")} rows={6} /></Field>
        <>
            <Field label="Meta (R$)" hint="Opcional. A barra pública usa só pagamentos confirmados."><Input value={f.v.target} onChange={f.set("target")} inputMode="decimal" /></Field>
            <Field label="Doação mínima (R$)"><Input value={f.v.min_donation} onChange={f.set("min_donation")} inputMode="decimal" /></Field>
            <Field label="Início"><Input value={f.v.starts_on} onChange={f.set("starts_on")} type="date" /></Field>
            <Field label="Fim"><Input value={f.v.ends_on} onChange={f.set("ends_on")} type="date" /></Field>
            <Field label="Para que serve o dinheiro" wide hint="Obrigatório para enviar à revisão."><TextArea value={f.v.purpose} onChange={f.set("purpose")} rows={3} /></Field>
            <Field label="Se a meta não for atingida" wide hint="Obrigatório para enviar à revisão."><TextArea value={f.v.contingency_policy} onChange={f.set("contingency_policy")} rows={2} /></Field>
            <Field label="Política de estorno" wide hint="Obrigatório para enviar à revisão."><TextArea value={f.v.refund_policy} onChange={f.set("refund_policy")} rows={2} /></Field>
        </>
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
  const cleanSlug = slug.split("?")[0];
  useEffect(() => {
    // Campanha de doação (v0.33.0) primeiro; se não houver, a página legada de cotas.
    api.get(`/v1/public/donation-campaigns/${encodeURIComponent(cleanSlug)}`)
      .then(async (data) => {
        // Campanha de projeto: as cotas do projeto continuam na página (endpoint legado), se existirem.
        const legacy = await api.get(`/v1/public/campaigns/${encodeURIComponent(cleanSlug)}`).catch(() => null);
        setState({ data: { donation: data, legacy }, loading: false });
      })
      .catch(() => api.get(`/v1/public/campaigns/${encodeURIComponent(cleanSlug)}`)
        .then((data) => setState({ data, loading: false }))
        .catch((e) => setState({ error: describeError(e), loading: false })));
  }, [cleanSlug]);
  const d = state.data;
  return (
    <StateView loading={state.loading} error={state.error}>
      {d?.donation && (
        <>
          <PublicDonationCampaign data={d.donation} slug={cleanSlug} />
          {d.legacy?.quotas?.length > 0 && (
            <Panel title={`Faltam ${d.legacy.remaining_quotas} cota(s)`}>
              {d.legacy.quotas.map((q: any) => (
                <div key={q.id}>
                  <h3>{q.label}</h3>
                  {q.description && <p>{q.description}</p>}
                  <QuotaProgress q={q} />
                </div>
              ))}
            </Panel>
          )}
        </>
      )}
      {d && !d.donation && (
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
