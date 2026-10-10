// Doações (v0.33.0) — campanha pública com QR, doação em sandbox, prestação de contas,
// revisão e casos de risco. Nada aqui movimenta dinheiro real: o provedor é o sandbox
// interno até que um provedor brasileiro seja contratado (ADR-372..376).
import { useEffect, useState } from "react";
import { api, describeError } from "../api";
import { centsToInput, date, dateTime, money, parseMoney } from "../format";
import { Link, useLocation } from "../router";
import { Button, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

const bps = (v?: number | null) => (v === null || v === undefined ? "—" : `${(v / 100).toFixed(2).replace(".", ",")}%`);

const D_STATUS: Record<string, string> = {
  draft: "Rascunho", pending_review: "Em revisão", approved: "Aprovada", published: "Publicada", paused: "Pausada",
  target_reached: "Meta atingida", ended: "Encerrada", under_review: "Em análise", rejected: "Recusada", cancelled: "Cancelada",
  refunding: "Em estorno", closed: "Fechada",
  pending: "Aguardando pagamento", confirmed: "Confirmada", reconciled: "Conciliada", refund_pending: "Estorno em curso",
  refunded: "Estornada", chargeback: "Contestada", expired: "Expirada", failed: "Falhou",
  open: "Aberto", allowed: "Liberado", rejected_case: "Recusado",
};
const st = (s?: string) => (s ? D_STATUS[s] || s : "—");

function Progress({ totals, target }: { totals: any; target?: number | null }) {
  const raised = totals?.net_after_reversals_cents ?? 0;
  const pct = target ? Math.min(100, Math.round((raised / target) * 100)) : 0;
  return (
    <>
      <p><strong>{money(raised)}</strong>{target ? <> de {money(target)} ({pct}%)</> : null}
        {" "}· {totals?.confirmed_donations ?? 0} doação(ões) confirmada(s)</p>
      {target ? (
        <div className="bar" role="img" aria-label={`${pct}% da meta`}><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
      ) : null}
      <p className="muted small">{totals?.label}</p>
    </>
  );
}

// ------------------------------------------------------------------ página pública (doação)
export function PublicDonationCampaign({ data, slug }: { data: any; slug: string }) {
  const d = data;
  const c = d.campaign;
  const f = useForm<any>({ amount: "", donor_display: "", donor_email: "", public_anonymous: false, cover_costs: false });
  const { busy, run } = useAction();
  const [result, setResult] = useState<any>(null);
  const qrUrl = `/v1/public/donation-campaigns/${encodeURIComponent(slug)}/qr.svg`;
  const open = c.status === "published";
  const minCents = c.min_donation_cents || 100;

  async function donate(e: any) {
    e.preventDefault();
    const cents = parseMoney(f.v.amount);
    if (!cents || cents < minCents) { return; }
    await run(async () => {
      const out = await api.post(`/v1/public/donation-campaigns/${encodeURIComponent(slug)}/donate`, {
        amount_cents: cents, method: "pix",
        ...(f.v.donor_display ? { donor_display: f.v.donor_display } : {}),
        ...(f.v.donor_email ? { donor_email: f.v.donor_email } : {}),
        public_anonymous: !!f.v.public_anonymous, cover_costs: !!f.v.cover_costs,
        idempotency_key: `web-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
      });
      setResult(out);
      return out.notice || "Cobrança criada.";
    });
  }

  return (
    <>
      <h1>{c.title}</h1>
      <p>{c.summary}</p>
      <p className="muted small">
        Beneficiário: {d.beneficiary.name}{d.beneficiary.city ? ` — ${d.beneficiary.city}/${d.beneficiary.uf}` : ""}
        {" "}<Pill tone={d.beneficiary.verified ? "ok" : "warn"}>{d.beneficiary.verified ? "cadastro verificado" : "verificação pendente"}</Pill>
        {" "}<Pill tone="muted">{st(c.status)}</Pill>
        {d.payment_mode === "sandbox" && <> <Pill tone="warn">ambiente de teste: pagamentos não são reais</Pill></>}
      </p>
      <Panel title="Arrecadação">
        <Progress totals={d.totals} target={c.target_cents} />
        {(c.starts_on || c.ends_on) && <p className="muted small">Período: {date(c.starts_on)} a {date(c.ends_on)}</p>}
      </Panel>
      <Panel title="Doar por Pix">
        {!open && <p className="muted">Esta campanha não está recebendo doações no momento.</p>}
        {open && !result && (
          <form onSubmit={donate}>
            <Field label="Valor (R$)" hint={`Mínimo ${money(minCents)}.`}><Input value={f.v.amount} onChange={f.set("amount")} inputMode="decimal" placeholder="50,00" /></Field>
            <Field label="Seu nome (opcional)"><Input value={f.v.donor_display} onChange={f.set("donor_display")} /></Field>
            <Field label="E-mail para o comprovante (opcional)" hint="Guardado cifrado; nunca aparece em público."><Input value={f.v.donor_email} onChange={f.set("donor_email")} type="email" /></Field>
            <Field label="Aparecer na lista pública?"><Select value={f.v.public_anonymous ? "1" : "0"} onChange={(v) => f.set("public_anonymous")(v === "1")} options={[["0", "Sim, com meu nome"], ["1", "Não, como anônimo"]]} /></Field>
            <Field label="Cobrir custos de transação" hint="Desmarcado por padrão. Só muda algo quando houver provedor real com tarifa.">
              <Select value={f.v.cover_costs ? "1" : "0"} onChange={(v) => f.set("cover_costs")(v === "1")} options={[["0", "Não"], ["1", "Sim"]]} />
            </Field>
            <p className="muted small">
              Antes de pagar: taxa de serviço da plataforma {bps(d.costs_disclosure.platform_fee_bps)}
              {d.costs_disclosure.platform_fee_active ? " (ativa)" : " (hipótese, INATIVA: nada é cobrado)"};
              {" "}fundo de apoio ao beneficiário até {bps(d.costs_disclosure.beneficiary_fund_max_bps)} (inativo);
              {" "}provedor: {d.costs_disclosure.provider} — {d.costs_disclosure.provider_fee_note}.
            </p>
            <Button variant="primary" type="submit" busy={busy} disabled={!parseMoney(f.v.amount) || (parseMoney(f.v.amount) || 0) < minCents}>Gerar Pix</Button>
          </form>
        )}
        {result && (
          <>
            <KeyValue items={[["Doação", <Link key="l" to={`/doacao/${result.id}`}>{result.id}</Link>], ["Valor", money(result.amount_cents)],
                              ["Situação", st(result.status)], ["Provedor", result.provider], ["Total a pagar", money(result.total_to_pay_cents)], ["Expira em", dateTime(result.expires_at)]]} />
            <p><strong>Código Pix (sandbox, não pagável):</strong></p>
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{result.pix_payload}</pre>
            <p className="muted small">A confirmação chega pelo provedor (webhook). Acompanhe em <Link to={`/doacao/${result.id}`}>/doacao/{result.id}</Link>.</p>
          </>
        )}
      </Panel>
      <Panel title="QR da campanha">
        <img src={qrUrl} alt={`QR que leva a ${d.canonical_url || `/campanha/${slug}`}`} width={180} height={180} />
        <p className="muted small">O QR aponta para esta página (versão {c.qr_version}); nunca para uma chave Pix fixa. Confira o endereço antes de doar.</p>
      </Panel>
      {c.purpose && <Panel title="Para que serve"><p style={{ whiteSpace: "pre-wrap" }}>{c.purpose}</p></Panel>}
      {c.story && <Panel title="A história"><p style={{ whiteSpace: "pre-wrap" }}>{c.story}</p></Panel>}
      {(c.contingency_policy || c.refund_policy) && (
        <Panel title="Regras da campanha">
          {c.contingency_policy && <p><strong>Se a meta não for atingida:</strong> {c.contingency_policy}</p>}
          {c.refund_policy && <p><strong>Estornos:</strong> {c.refund_policy}</p>}
        </Panel>
      )}
      {d.updates?.length > 0 && (
        <Panel title="Atualizações">
          <ul className="rows">{d.updates.map((u: any) => <li key={u.id}><span><strong>{u.title}</strong> — {u.body}</span><Pill tone="muted">{date(u.created_at)}</Pill></li>)}</ul>
        </Panel>
      )}
      {d.expenses?.length > 0 && (
        <Panel title="Prestação de contas (gastos declarados)">
          <ul className="rows">{d.expenses.map((x: any, i: number) => (
            <li key={i}><span>{x.budget_line} — {money(x.amount_cents)} em {date(x.spent_on)}</span><Pill tone={x.evidence_status === "verified" ? "ok" : "muted"}>{x.evidence_status}</Pill></li>
          ))}</ul>
        </Panel>
      )}
      {d.backers?.length > 0 && (
        <Panel title="Quem já apoiou">
          <ul className="rows">{d.backers.map((b: any, i: number) => <li key={i}><span>{b.name}</span><Pill tone="muted">{money(b.amount_cents)}</Pill></li>)}</ul>
        </Panel>
      )}
      <Panel title="O que esta campanha NÃO é" quiet>
        <ul>{d.what_this_is_not?.map((t: string, i: number) => <li key={i}>{t}</li>)}</ul>
        <p className="muted small">{d.costs_disclosure.note}</p>
      </Panel>
    </>
  );
}

// ------------------------------------------------------------------ situação pública de uma doação
export function DonationStatus() {
  const { path } = useLocation();
  const id = path.replace(/^\/doacao\/?/, "");
  const { data, error, loading, reload } = useLoad<any>(`/v1/public/donations/${encodeURIComponent(id)}`, [id]);
  const [receipt, setReceipt] = useState<any>(null);
  const [rErr, setRErr] = useState<string | null>(null);
  useEffect(() => {
    if (!data?.receipt) return;
    api.get(`/v1/public/donations/${encodeURIComponent(id)}/receipt`).then(setReceipt).catch((e) => setRErr(describeError(e)));
  }, [data, id]);
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <h1>Doação</h1>
          <KeyValue items={[["Campanha", <Link key="c" to={`/campanha/${data.slug}`}>{data.campaign_title}</Link>], ["Valor", money(data.amount_cents)],
                            ["Situação", <Pill key="s" tone={data.status === "confirmed" || data.status === "reconciled" ? "ok" : "muted"}>{st(data.status)}</Pill>],
                            ["Provedor", `${data.provider}${data.is_simulated ? " (simulado)" : ""}`], ["Criada em", dateTime(data.created_at)],
                            ["Confirmada em", dateTime(data.confirmed_at)]]} />
          <p className="muted small">{data.notice}</p>
          {receipt && (
            <Panel title={`Comprovante ${receipt.number}`}>
              <KeyValue items={[["Emitente", receipt.issuer], ["Valor", money(receipt.amount_cents)], ["Emitido em", dateTime(receipt.issued_at)],
                                ["Situação", receipt.status === "voided" ? "anulado (doação estornada)" : st(receipt.status)], ["Integridade (SHA-256)", receipt.content_sha256]]} />
              <p className="muted small">{receipt.what_this_is}</p>
            </Panel>
          )}
          {rErr && <p className="muted small">{rErr}</p>}
        </>
      )}
    </StateView>
  );
}

// ------------------------------------------------------------------ minhas doações (usuário logado)
export function MyDonations() {
  const { data, error, loading, reload } = useLoad<any>("/v1/me/donations");
  const { run } = useAction();
  return (
    <>
      <PageHead title="Minhas doações" sub="Doações feitas com este e-mail e acordos recorrentes (recorrência ainda desligada)." />
      <StateView loading={loading} error={error} onRetry={reload} empty={!data?.donations?.length}>
        <ul className="rows">{data?.donations?.map((x: any) => (
          <li key={x.id}><span><Link to={`/doacao/${x.id}`}>{x.title}</Link> — {money(x.amount_cents)} · {dateTime(x.created_at)}</span><Pill tone="muted">{st(x.status)}</Pill></li>
        ))}</ul>
        {data?.recurring?.length > 0 && (
          <Panel title="Acordos recorrentes">
            <ul className="rows">{data.recurring.map((r: any) => (
              <li key={r.id}><span>{r.title} — {money(r.amount_cents)} ({r.cadence})</span>
                {r.status === "active" && <Button onClick={() => run(async () => { await api.post(`/v1/me/recurring-donations/${r.id}/cancel`, {}); reload(); return "Acordo cancelado."; })}>Cancelar</Button>}
                <Pill tone="muted">{st(r.status)}</Pill></li>
            ))}</ul>
          </Panel>
        )}
        {data?.recurring_note && <p className="muted small">{data.recurring_note}</p>}
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------ gestão da campanha (organização)
const EMPTY_X = { budget_line: "", amount: "", spent_on: "", note: "" };
const EMPTY_U = { title: "", body: "", is_public: true };

export function CampaignAccountability({ campaign, onChange }: { campaign: any; onChange: (c: any) => void }) {
  const id = campaign.id;
  const { data, error, loading, reload } = useLoad<any>(`/v1/campaigns/${id}/accountability`, [id]);
  const { busy, run } = useAction();
  const fx = useForm<any>(EMPTY_X);
  const fu = useForm<any>(EMPTY_U);
  const [modal, setModal] = useState<"" | "expense" | "update">("");
  const act = (what: string, msg: string) => run(async () => { const out = await api.post(`/v1/campaigns/${id}/${what}`, {}); onChange({ ...campaign, ...out }); reload(); return msg; });
  const s = campaign.status;
  return (
    <>
      <Panel title="Fluxo de publicação" actions={<>
        {["draft", "rejected"].includes(s) && <Button variant="primary" busy={busy} onClick={() => act("submit", "Enviada para revisão.")}>Enviar para revisão</Button>}
        {s === "approved" && <Button variant="primary" busy={busy} onClick={() => act("publish", "Campanha publicada.")}>Publicar</Button>}
        {["published", "paused"].includes(s) && <Button busy={busy} onClick={() => act("rotate-qr", "QR renovado: o anterior deixa de valer.")}>Renovar QR</Button>}
      </>}>
        <KeyValue items={[["Situação", st(s)], ["Endereço público", <Link key="l" to={`/campanha/${campaign.slug}`}>/campanha/{campaign.slug}</Link>],
                          ["Versão do QR", campaign.qr_version ?? 1], ["Nota da revisão", campaign.review_note || "—"]]} />
        <p className="muted small">Publicar exige: termos aceitos ao enviar, revisão por outra pessoa e cadastro do beneficiário verificado pela plataforma.</p>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Arrecadação (saldo contábil, não custódia)">
              <Progress totals={data.totals} target={campaign.target_cents} />
              <KeyValue items={[["Bruto confirmado", money(data.totals?.gross_confirmed_cents)], ["Estornado", money(data.totals?.reversed_cents)],
                                ["Tarifa do provedor", money(data.totals?.provider_fees_cents)], ["Taxa da plataforma (calculada, devida R$ 0,00)", money(data.totals?.platform_fee_accrued_cents)],
                                ["Líquido estimado ao beneficiário", money(data.totals?.beneficiary_net_estimated_cents)],
                                ["Gastos declarados / validados", `${money(data.expenses_declared_cents)} / ${money(data.expenses_validated_cents)}`]]} />
              <p className="muted small">{data.totals?.basis}</p>
              {data.open_risk_cases?.length > 0 && <p><Pill tone="warn">{data.open_risk_cases.length} caso(s) de risco aberto(s) em revisão humana</Pill></p>}
            </Panel>
            <Panel title="Gastos declarados" actions={<Button onClick={() => setModal("expense")}>Declarar gasto</Button>}>
              <ul className="rows">{data.expenses?.map((x: any) => <li key={x.id}><span>{x.budget_line} — {money(x.amount_cents)} em {date(x.spent_on)}</span><Pill tone="muted">{x.evidence_status}</Pill></li>)}</ul>
            </Panel>
            <Panel title="Atualizações" actions={<Button onClick={() => setModal("update")}>Publicar atualização</Button>}>
              <ul className="rows">{data.updates?.map((u: any) => <li key={u.id}><span><strong>{u.title}</strong> — {u.body}</span><Pill tone="muted">{u.is_public ? "pública" : "interna"}</Pill></li>)}</ul>
            </Panel>
          </>
        )}
      </StateView>
      <Modal open={modal === "expense"} title="Declarar gasto" onClose={() => setModal("")}
             footer={<><Button onClick={() => setModal("")}>Cancelar</Button>
               <Button variant="primary" busy={busy} disabled={!fx.v.budget_line || !parseMoney(fx.v.amount) || !fx.v.spent_on}
                       onClick={() => run(async () => {
                         await api.post(`/v1/campaigns/${id}/expenses`, { description: fx.v.note || fx.v.budget_line, budget_line: fx.v.budget_line, amount_cents: parseMoney(fx.v.amount), spent_on: fx.v.spent_on });
                         setModal(""); fx.setV(EMPTY_X); reload(); return "Gasto declarado.";
                       })}>Salvar</Button></>}>
        <Field label="Linha do orçamento"><Input value={fx.v.budget_line} onChange={fx.set("budget_line")} /></Field>
        <Field label="Valor (R$)"><Input value={fx.v.amount} onChange={fx.set("amount")} inputMode="decimal" /></Field>
        <Field label="Data"><Input value={fx.v.spent_on} onChange={fx.set("spent_on")} type="date" /></Field>
        <Field label="Descrição" wide><TextArea value={fx.v.note} onChange={fx.set("note")} rows={2} /></Field>
      </Modal>
      <Modal open={modal === "update"} title="Publicar atualização" onClose={() => setModal("")}
             footer={<><Button onClick={() => setModal("")}>Cancelar</Button>
               <Button variant="primary" busy={busy} disabled={!fu.v.title || fu.v.body.length < 10}
                       onClick={() => run(async () => {
                         await api.post(`/v1/campaigns/${id}/updates`, { title: fu.v.title, body: fu.v.body, is_public: !!fu.v.is_public });
                         setModal(""); fu.setV(EMPTY_U); reload(); return "Atualização publicada.";
                       })}>Publicar</Button></>}>
        <Field label="Título"><Input value={fu.v.title} onChange={fu.set("title")} /></Field>
        <Field label="Texto" wide><TextArea value={fu.v.body} onChange={fu.set("body")} rows={4} /></Field>
        <Field label="Visibilidade"><Select value={fu.v.is_public ? "1" : "0"} onChange={(v) => fu.set("is_public")(v === "1")} options={[["1", "Pública"], ["0", "Interna"]]} /></Field>
      </Modal>
    </>
  );
}

// ------------------------------------------------------------------ administração: revisão de campanhas e verificação de beneficiários
export function DonationReview() {
  const [status, setStatus] = useState("pending_review");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/donation-campaigns?status=${status}`, [status]);
  const { busy, run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const decide = (id: string, decision: string) => run(async () => {
    await api.post(`/v1/admin/donation-campaigns/${id}/review`, { approve: decision === "approve", note: note[id] || "" });
    reload(); return decision === "approve" ? "Campanha aprovada." : "Campanha recusada.";
  });
  const suspend = (id: string, reinstate: boolean) => run(async () => {
    await api.post(`/v1/admin/donation-campaigns/${id}/suspend`, { note: note[id] || "", reinstate });
    reload(); return reinstate ? "Campanha de volta ao ar." : "Campanha fora do ar, em análise.";
  });
  const verify = (orgId: string, status2: string) => run(async () => {
    await api.post(`/v1/admin/beneficiaries/${orgId}/verification`, { status: status2, note: note[orgId] || "" });
    reload(); return "Verificação do beneficiário registrada.";
  });
  return (
    <>
      <PageHead title="Revisão de campanhas de doação" sub="Quatro olhos: quem criou não aprova. Publicar ainda exige beneficiário verificado."
                actions={<Select value={status} onChange={setStatus} options={[["pending_review", "Em revisão"], ["approved", "Aprovadas"], ["published", "Publicadas"], ["rejected", "Recusadas"], ["under_review", "Em análise"]]} />} />
      <StateView loading={loading} error={error} onRetry={reload} empty={!data?.items?.length}>
        {data?.items?.map((c: any) => (
          <Panel key={c.id} title={`${c.title} — ${c.org}`}>
            <KeyValue items={[["Situação", st(c.status)], ["Meta", money(c.target_cents)], ["Beneficiário verificado", c.beneficiary_verified ? "sim" : "não"],
                              ["Termos aceitos em", dateTime(c.accepted_terms_at)], ["Finalidade", c.purpose || "—"], ["Criada por", c.created_by || "—"]]} />
            <Field label="Justificativa (mínimo 10 caracteres)" wide><Input value={note[c.id] || ""} onChange={(v) => setNote({ ...note, [c.id]: v })} /></Field>
            <p>
              {c.status === "pending_review" && <><Button variant="primary" busy={busy} disabled={(note[c.id] || "").length < 10} onClick={() => decide(c.id, "approve")}>Aprovar</Button>{" "}
                <Button busy={busy} disabled={(note[c.id] || "").length < 10} onClick={() => decide(c.id, "reject")}>Recusar</Button>{" "}</>}
              {["published", "paused", "target_reached"].includes(c.status) && <><Button busy={busy} disabled={(note[c.id] || "").length < 10} onClick={() => suspend(c.id, false)}>Tirar do ar (em análise)</Button>{" "}</>}
              {c.status === "under_review" && <><Button variant="primary" busy={busy} disabled={(note[c.id] || "").length < 10} onClick={() => suspend(c.id, true)}>Devolver ao ar</Button>{" "}</>}
              {!c.beneficiary_verified && <Button busy={busy} disabled={(note[c.id] || "").length < 10} onClick={() => { note[c.beneficiary_org_id] = note[c.id]; verify(c.beneficiary_org_id, "verified"); }}>Registrar beneficiário como verificado</Button>}
            </p>
          </Panel>
        ))}
      </StateView>
    </>
  );
}

export function DonationRiskCases() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/donation-risk-cases?status=open");
  const { busy, run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const decide = (id: string, decision: string) => run(async () => {
    await api.post(`/v1/admin/donation-risk-cases/${id}/decide`, { action: decision, note: note[id] || "" });
    reload(); return "Decisão registrada.";
  });
  return (
    <>
      <PageHead title="Casos de risco em doações" sub="Regras proporcionais ao sandbox. Reter repasse (payout hold) não existe: a plataforma não tem custódia." />
      <StateView loading={loading} error={error} onRetry={reload} empty={!data?.items?.length}>
        {data?.note && <p className="muted small">{data.note}</p>}
        {data?.items?.map((r: any) => (
          <Panel key={r.id} title={`${(r.reason_codes || []).join(", ")} — ${money(r.amount_cents)}`}>
            <KeyValue items={[["Doação", <Link key="d" to={`/doacao/${r.donation_id}`}>{r.donation_id}</Link>], ["Campanha", r.campaign_title], ["Nível / ação sugerida", `${r.level} / ${r.action}`], ["Versão das regras", r.rule_version],
                              ["Situação da doação", st(r.donation_status)], ["Aberto em", dateTime(r.created_at)], ["Explicação", r.explanation || "—"]]} />
            <Field label="Justificativa (mínimo 10 caracteres)" wide><Input value={note[r.id] || ""} onChange={(v) => setNote({ ...note, [r.id]: v })} /></Field>
            <p><Button variant="primary" busy={busy} disabled={(note[r.id] || "").length < 10} onClick={() => decide(r.id, "allow")}>Liberar</Button>{" "}
              <Button busy={busy} disabled={(note[r.id] || "").length < 10} onClick={() => decide(r.id, "reject")}>Recusar (cancela a doação)</Button></p>
          </Panel>
        ))}
      </StateView>
    </>
  );
}

export const donationFormDefaults = {
  kind: "donation", target: "", starts_on: "", ends_on: "", purpose: "", contingency_policy: "", refund_policy: "", min_donation: centsToInput(500),
};
export { st as donationStatusLabel };
