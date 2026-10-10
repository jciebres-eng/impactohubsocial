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
  open: "Aberto", allowed: "Liberado", rejected_case: "Recusado", active: "Ativa", pledged: "compromisso aberto", fulfilled: "cumprido",
};
const st = (s?: string) => (s ? D_STATUS[s] || s : "—");
const EVIDENCE: Record<string, string> = { declared: "declarado", documented: "com documento", validated: "validado", contested: "contestado" };

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
  const f = useForm<any>({ amount: "", method: "pix", contribution: "", donor_display: "", donor_email: "", public_anonymous: false, cover_costs: false });
  const contribution = d.costs_disclosure?.platform_contribution;
  const contribCents = contribution?.available ? (parseMoney(f.v.contribution) || 0) : 0;
  const [recurring, setRecurring] = useState<any>(null);
  const consentText = `Autorizo a cobrança mensal de ${f.v.amount ? "R$ " + f.v.amount : "o valor informado"} para "${c.title}" até eu cancelar, o que posso fazer a qualquer momento em Minhas doações.`;
  const { busy, run } = useAction();
  const [result, setResult] = useState<any>(null);
  const [pledge, setPledge] = useState("");
  const qrUrl = `/v1/public/donation-campaigns/${encodeURIComponent(slug)}/qr.svg`;
  const open = c.status === "published";
  const minCents = c.min_donation_cents || 100;

  async function donate(e: any) {
    e.preventDefault();
    const cents = parseMoney(f.v.amount);
    if (!cents || cents < minCents) { return; }
    await run(async () => {
      const out = await api.post(`/v1/public/donation-campaigns/${encodeURIComponent(slug)}/donate`, {
        amount_cents: cents, method: f.v.method,
        ...(contribCents > 0 ? { platform_contribution_cents: contribCents } : {}),
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
        <KeyValue items={[["Confirmado pelo provedor", money(d.totals?.gross_confirmed_cents)], ["Já liquidado ao beneficiário", money(d.totals?.settled_cents)],
                          ...(d.totals?.settled_partial_cents ? [["Liquidado em parte (restante pendente)", money(d.totals.settled_partial_cents)] as [string, any]] : []),
                          ["Estornado", money(d.totals?.reversed_cents)], ["Falta para a meta", c.target_cents ? money(Math.max(0, c.target_cents - (d.totals?.net_after_reversals_cents || 0))) : "—"],
                          ["Compromissos (não é dinheiro)", money(d.totals?.pledged_cents)], ["Recursos declarados fora da plataforma", money(d.totals?.external_declared_cents)]]} />
        {(c.starts_on || c.ends_on) && <p className="muted small">Período: {date(c.starts_on)} a {date(c.ends_on)}</p>}
        <p className="muted small">{d.totals?.counting_policy}. Última atualização financeira válida: {dateTime(d.last_financial_update_at) || "nenhuma ainda"}.{d.funding_source !== "private" ? ` Campanha com recurso ${d.funding_source === "public" ? "público" : "misto"}.` : ""}</p>
      </Panel>
      <Panel title="Doar">
        {!open && <p className="muted">Esta campanha não está recebendo doações no momento.</p>}
        {open && !result && (
          <form onSubmit={donate}>
            <Field label="Valor (R$)" hint={`Mínimo ${money(minCents)}.`}><Input value={f.v.amount} onChange={f.set("amount")} inputMode="decimal" placeholder="50,00" /></Field>
            <Field label="Forma de pagamento"><Select value={f.v.method} onChange={f.set("method")} options={[["pix", "Pix"], ["card", "Cartão"]]} /></Field>
            {contribution?.available && (
              <Field label="Contribuição para a plataforma (opcional)" hint={`${contribution.note} Até ${money(Math.min(contribution.max_cents, parseMoney(f.v.amount) || 0))}.`}>
                <Input value={f.v.contribution} onChange={f.set("contribution")} inputMode="decimal" placeholder="0,00" />
              </Field>
            )}
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
            {parseMoney(f.v.amount) ? (
              <KeyValue items={[["Doação para a campanha", money(parseMoney(f.v.amount))],
                                ...(contribCents > 0 ? [["Contribuição para a plataforma (separada)", money(contribCents)] as [string, any]] : []),
                                ["Total a pagar", money((parseMoney(f.v.amount) || 0) + contribCents)]]} />
            ) : null}
            <Button variant="primary" type="submit" busy={busy} disabled={!parseMoney(f.v.amount) || (parseMoney(f.v.amount) || 0) < minCents}>{f.v.method === "card" ? "Ir para o pagamento com cartão" : "Gerar Pix"}</Button>
          </form>
        )}
        {result && (
          <>
            <KeyValue items={[["Doação", <Link key="l" to={`/doacao/${result.id}`}>{result.id}</Link>], ["Valor", money(result.amount_cents)],
                              ["Situação", st(result.status)], ["Provedor", result.provider], ["Total a pagar", money(result.total_to_pay_cents)], ["Expira em", dateTime(result.expires_at)]]} />
            {result.pix_payload && <>
              <p><strong>Código Pix (sandbox, não pagável):</strong></p>
              <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{result.pix_payload}</pre>
            </>}
            {result.checkout_url && <p><strong>Pagamento com cartão (sandbox):</strong> o provedor abriria o checkout em <code>{result.checkout_url}</code>. Nenhum dado de cartão passa pela plataforma.</p>}
            <p className="muted small">A confirmação chega pelo provedor (webhook). Acompanhe em <Link to={`/doacao/${result.id}`}>/doacao/{result.id}</Link>.</p>
          </>
        )}
      </Panel>
      {open && d.recurring_available && (
        <Panel title="Doar todo mês" quiet>
          {!recurring ? (
            <>
              <p className="muted small">Autorizar não é pagar: cada mês o provedor tenta a cobrança e só o que ele confirmar vira doação. Você cancela quando quiser em Minhas doações.</p>
              <p className="small">{consentText}</p>
              <Button busy={busy} disabled={!parseMoney(f.v.amount) || (parseMoney(f.v.amount) || 0) < minCents}
                      onClick={() => run(async () => { setRecurring(await api.post(`/v1/public/donation-campaigns/${encodeURIComponent(slug)}/recurring`, { amount_cents: parseMoney(f.v.amount), method: "card", consent_text: consentText })); return "Autorização registrada. A primeira tentativa de cobrança acontece na próxima rodada."; })}>
                Autorizar doação mensal
              </Button>
            </>
          ) : <p>Autorização registrada: {money(recurring.amount_cents)} por mês. Situação: {st(recurring.status)}.</p>}
        </Panel>
      )}
      {open && (
        <Panel title="Compromisso de doação futura" quiet>
          <p className="muted small">Quem tem conta pode registrar um compromisso de doar depois. Não é doação nem dinheiro: aparece à parte e só vira arrecadação quando a doação for confirmada pelo provedor.</p>
          <Field label="Valor do compromisso (R$)"><Input value={pledge} onChange={setPledge} inputMode="decimal" /></Field>
          <Button busy={busy} disabled={!parseMoney(pledge)} onClick={() => run(async () => { await api.post(`/v1/public/donation-campaigns/${encodeURIComponent(slug)}/pledge`, { amount_cents: parseMoney(pledge) }); setPledge(""); return "Compromisso registrado (não é dinheiro recebido)."; })}>Registrar compromisso</Button>
        </Panel>
      )}
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
      {d.external_resources?.length > 0 && (
        <Panel title="Recursos declarados fora da plataforma (não conferidos pelo provedor)">
          <ul className="rows">{d.external_resources.map((x: any, i: number) => (
            <li key={i}><span>{EXT_KIND[x.kind] || x.kind} — {x.source_name} — {x.amount_cents ? money(x.amount_cents) : x.in_kind_description} em {date(x.received_on)}</span><Pill tone="muted">{FUNDING[x.funding_source] || x.funding_source}</Pill></li>
          ))}</ul>
        </Panel>
      )}
      {d.expenses?.length > 0 && (
        <Panel title="Prestação de contas (gastos declarados)">
          <ul className="rows">{d.expenses.map((x: any, i: number) => (
            <li key={i}><span>{x.budget_line} — {money(x.amount_cents)} em {date(x.spent_on)}</span><Pill tone={x.evidence_status === "validated" ? "ok" : "muted"}>{EVIDENCE[x.evidence_status] || x.evidence_status}</Pill></li>
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
      <PageHead title="Minhas doações" sub="Doações feitas com esta conta e autorizações de doação mensal." />
      <StateView loading={loading} error={error} onRetry={reload} empty={!data?.donations?.length}>
        <ul className="rows">{data?.donations?.map((x: any) => (
          <li key={x.id}><span><Link to={`/doacao/${x.id}`}>{x.title}</Link> — {money(x.amount_cents)} · {dateTime(x.created_at)}</span><Pill tone="muted">{st(x.status)}</Pill></li>
        ))}</ul>
        {data?.recurring?.length > 0 && (
          <Panel title="Doação mensal (autorizações)">
            <ul className="rows">{data.recurring.map((r: any) => (
              <li key={r.id}><span>{r.title} — {money(r.amount_cents)} por mês · autorizado em {date(r.consent_at)} · {r.attempts} tentativa(s), {r.confirmed_n} confirmada(s), {r.failed_n} falha(s) · recebido {money(r.received_cents)}</span>
                {["active", "paused"].includes(r.status) && <Button onClick={() => run(async () => { await api.post(`/v1/me/recurring-donations/${r.id}/cancel`, {}); reload(); return "Autorização cancelada: nenhuma nova cobrança."; })}>Cancelar</Button>}
                <Pill tone={r.status === "paused" ? "warn" : "muted"}>{r.status === "paused" ? "pausado (falhas seguidas)" : st(r.status)}</Pill></li>
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
const EMPTY_E = { kind: "offline_donation", funding_source: "private", source_name: "", instrument_ref: "", amount: "", in_kind_description: "", received_on: "", note: "" };
const EXT_KIND: Record<string, string> = { public_transfer: "Repasse público", grant: "Edital / fomento", offline_donation: "Doação fora da plataforma", sponsorship: "Patrocínio", in_kind: "Apoio não financeiro", own_funds: "Recursos próprios", other: "Outro" };
const FUNDING: Record<string, string> = { private: "privado", public: "público", mixed: "misto" };
const OBL_RULE: Record<string, string> = { "donation.platform_fee": "taxa de serviço", "donation.platform_contribution": "contribuição voluntária do doador", "donation.institutional_fee": "taxa institucional" };
const obligationRuleLabel = (k: string) => OBL_RULE[k] || k;
const OBL: Record<string, string> = { calculated: "calculada (não devida)", exempt: "isenta", due: "devida", invoiced: "faturada", charged: "cobrada", received: "recebida", settled: "liquidada", reversed: "estornada", overdue: "vencida", disputed: "em disputa", waived: "dispensada" };

export function CampaignAccountability({ campaign, onChange }: { campaign: any; onChange: (c: any) => void }) {
  const id = campaign.id;
  const { data, error, loading, reload } = useLoad<any>(`/v1/campaigns/${id}/accountability`, [id]);
  const { busy, run } = useAction();
  const fx = useForm<any>(EMPTY_X);
  const fu = useForm<any>(EMPTY_U);
  const fe = useForm<any>(EMPTY_E);
  const [modal, setModal] = useState<"" | "expense" | "update" | "external">("");
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
              <KeyValue items={[["Pendente (iniciado, não pago)", money(data.totals?.pending_cents)], ["Bruto confirmado", money(data.totals?.gross_confirmed_cents)],
                                ["Liquidado (disponível segundo o provedor)", money(data.totals?.settled_cents)], ["Em análise", money(data.totals?.under_review_cents)],
                                ["Estornado", money(data.totals?.reversed_cents)],
                                ["Tarifa do provedor", money(data.totals?.provider_fees_cents)], ["Taxa da plataforma (calculada, devida R$ 0,00)", money(data.totals?.platform_fee_accrued_cents)],
                                ["Líquido estimado ao beneficiário", money(data.totals?.beneficiary_net_estimated_cents)],
                                ["Gastos declarados / validados", `${money(data.expenses_declared_cents)} / ${money(data.expenses_validated_cents)}`],
                                ["Compromissos (não é dinheiro)", money(data.totals?.pledged_cents)], ["Recursos declarados fora da plataforma", money(data.totals?.external_declared_cents)]]} />
              <p className="muted small">{data.totals?.basis} · {data.totals?.counting_policy}</p>
              {data.open_risk_cases?.length > 0 && <p><Pill tone="warn">{data.open_risk_cases.length} caso(s) de risco aberto(s) em revisão humana</Pill></p>}
              {data.reconciliation_exceptions?.length > 0 && <p><Pill tone="warn">{data.reconciliation_exceptions.length} divergência(s) de conciliação em aberto</Pill></p>}
            </Panel>
            <Panel title="Recursos declarados fora da plataforma" actions={<Button onClick={() => setModal("external")}>Declarar recurso</Button>}>
              <p className="muted small">Entram na prestação de contas rotulados como declarados; nunca na barra nem no razão. Recurso público exige o instrumento.</p>
              <ul className="rows">{data.external_resources?.map((x: any) => (
                <li key={x.id}><span>{EXT_KIND[x.kind] || x.kind} — {x.source_name}{x.instrument_ref ? ` (${x.instrument_ref})` : ""} — {x.amount_cents ? money(x.amount_cents) : x.in_kind_description} em {date(x.received_on)}</span>
                  <Pill tone={x.funding_source === "public" ? "warn" : "muted"}>{FUNDING[x.funding_source] || x.funding_source}</Pill></li>
              ))}</ul>
            </Panel>
            {data.pledges?.length > 0 && (
              <Panel title="Compromissos de doação (não é dinheiro recebido)">
                <ul className="rows">{data.pledges.map((p: any) => (
                  <li key={p.id}><span>{p.pledger_display || "Compromisso"} — {money(p.amount_cents)}{p.expected_on ? ` até ${date(p.expected_on)}` : ""}</span><Pill tone={p.status === "fulfilled" ? "ok" : "muted"}>{st(p.status)}</Pill></li>
                ))}</ul>
              </Panel>
            )}
            {data.remuneration_obligations?.length > 0 && (
              <Panel title="Taxa de serviço desta campanha (obrigações)" quiet>
                <ul className="rows">{data.remuneration_obligations.map((o: any) => (
                  <li key={o.id}><span>{money(o.amount_cents)} sobre {money(o.basis_cents)}{o.funding_source !== "private" ? ` · recurso ${FUNDING[o.funding_source]}` : ""}</span><Pill tone={o.state === "due" || o.state === "overdue" ? "warn" : "muted"}>{OBL[o.state] || o.state}</Pill></li>
                ))}</ul>
                <p className="muted small">Ver <Link to="/remuneracao">Remuneração da plataforma</Link> para a política vigente, a franquia e os avisos. Nada aqui bloqueia a prestação de contas.</p>
              </Panel>
            )}
            <Panel title="Gastos declarados" actions={<Button onClick={() => setModal("expense")}>Declarar gasto</Button>}>
              <ul className="rows">{data.expenses?.map((x: any) => <li key={x.id}><span>{x.budget_line} — {money(x.amount_cents)} em {date(x.spent_on)}</span><Pill tone={x.evidence_status === "validated" ? "ok" : "muted"}>{EVIDENCE[x.evidence_status] || x.evidence_status}</Pill></li>)}</ul>
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
      <Modal open={modal === "external"} title="Declarar recurso recebido fora da plataforma" onClose={() => setModal("")}
             footer={<><Button onClick={() => setModal("")}>Cancelar</Button>
               <Button variant="primary" busy={busy} disabled={!fe.v.source_name || !fe.v.received_on || (fe.v.kind !== "in_kind" && !parseMoney(fe.v.amount)) || (fe.v.funding_source !== "private" && !fe.v.instrument_ref)}
                       onClick={() => run(async () => {
                         await api.post(`/v1/campaigns/${id}/external-resources`, {
                           kind: fe.v.kind, source_name: fe.v.source_name, funding_source: fe.v.funding_source, received_on: fe.v.received_on,
                           ...(fe.v.instrument_ref ? { instrument_ref: fe.v.instrument_ref } : {}),
                           ...(fe.v.kind === "in_kind" ? { in_kind_description: fe.v.in_kind_description } : { amount_cents: parseMoney(fe.v.amount) }),
                           ...(fe.v.note ? { note: fe.v.note } : {}),
                         });
                         setModal(""); fe.setV(EMPTY_E); reload(); return "Recurso declarado (não entra na barra).";
                       })}>Declarar</Button></>}>
        <Field label="Tipo"><Select value={fe.v.kind} onChange={fe.set("kind")} options={Object.entries(EXT_KIND)} /></Field>
        <Field label="Origem do recurso"><Select value={fe.v.funding_source} onChange={fe.set("funding_source")} options={Object.entries(FUNDING)} /></Field>
        <Field label="Fonte (quem pagou)"><Input value={fe.v.source_name} onChange={fe.set("source_name")} /></Field>
        <Field label="Instrumento" hint="Obrigatório para recurso público: termo, convênio, edital."><Input value={fe.v.instrument_ref} onChange={fe.set("instrument_ref")} /></Field>
        {fe.v.kind === "in_kind"
          ? <Field label="Descrição do apoio" wide><TextArea value={fe.v.in_kind_description} onChange={fe.set("in_kind_description")} rows={2} /></Field>
          : <Field label="Valor (R$)"><Input value={fe.v.amount} onChange={fe.set("amount")} inputMode="decimal" /></Field>}
        <Field label="Recebido em"><Input value={fe.v.received_on} onChange={fe.set("received_on")} type="date" /></Field>
        <Field label="Observação" wide><TextArea value={fe.v.note} onChange={fe.set("note")} rows={2} /></Field>
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
                actions={<Select aria-label="Filtrar por situação" value={status} onChange={setStatus} options={[["pending_review", "Em revisão"], ["approved", "Aprovadas"], ["published", "Publicadas"], ["rejected", "Recusadas"], ["under_review", "Em análise"]]} />} />
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

// ------------------------------------------------------------------ v0.34.0: remuneração da plataforma (organização)
export function OrgRemuneration() {
  const { data, error, loading, reload } = useLoad<any>("/v1/org/remuneration");
  const { busy, run } = useAction();
  const [reason, setReason] = useState<Record<string, string>>({});
  const pol = data?.policy || {};
  return (
    <>
      <PageHead title="Remuneração da plataforma" sub="Gratuito até gerar valor: a taxa é calculada e mostrada, mas só fica devida com regra ativa, franquia ultrapassada e aviso prévio. Nada aqui bloqueia a sua prestação de contas." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Política vigente (hipótese registrada)">
              <KeyValue items={[["Versão", `${pol.version} · ${pol.legal_status}`], ["Franquia (liquidado em 12 meses)", money(pol.allowance_settled_cents_12m)],
                                ["Liquidado ao seu favor nos últimos 12 meses", money(data.settled_12m_cents)], ["Franquia restante", money(data.allowance_remaining_cents)],
                                ["Aviso prévio mínimo", `${pol.notice_days} dias`], ["Mínimo para faturar", money(pol.min_invoice_cents)],
                                ["Teto das obrigações", `${bps(pol.max_fee_share_of_settled_bps)} do liquidado`], ["Recurso público", pol.public_funding_default === "exempt" ? "isento salvo instrumento autorizado" : pol.public_funding_default]]} />
              <p className="muted small">Nunca bloqueia: {(data.never_blocks || []).map((k: string) => NEVER_BLOCKS[k] || k).join(", ")}.</p>
            </Panel>
            <Panel title="Totais por estado (nunca somados num número só)">
              <KeyValue items={Object.entries(OBL).map(([k, v]) => [v, money(data.totals_by_state?.[k] || 0)] as [string, any])} />
            </Panel>
            <Panel title="Obrigações">
              {!data.obligations?.length && <p className="muted">Nenhuma obrigação registrada.</p>}
              <ul className="rows">{data.obligations?.map((o: any) => (
                <li key={o.id}>
                  <span>{money(o.amount_cents)} sobre {money(o.basis_cents)} · {obligationRuleLabel(o.rule_key)} · {dateTime(o.created_at)}{o.due_on ? ` · vence ${date(o.due_on)}` : ""}{o.received_cents ? ` · recebido ${money(o.received_cents)}` : ""}
                    {["due", "invoiced", "charged", "overdue", "received", "settled"].includes(o.state) && (
                      <> <Input value={reason[o.id] || ""} onChange={(v) => setReason({ ...reason, [o.id]: v })} placeholder="Motivo da contestação (mín. 10 caracteres)" />
                        <Button busy={busy} disabled={(reason[o.id] || "").length < 10} onClick={() => run(async () => { await api.post(`/v1/org/remuneration/${o.id}/dispute`, { reason: reason[o.id] }); reload(); return "Contestação registrada."; })}>Contestar</Button></>
                    )}
                  </span>
                  <Pill tone={o.state === "due" || o.state === "overdue" ? "warn" : o.state === "settled" ? "ok" : "muted"}>{OBL[o.state] || o.state}</Pill>
                </li>
              ))}</ul>
            </Panel>
            <Panel title="Avisos recebidos">
              {!data.notices?.length && <p className="muted">Nenhum aviso.</p>}
              <ul className="rows">{data.notices?.map((n: any) => (
                <li key={n.id}><span><strong>{dateTime(n.sent_at)}</strong> — {n.body}<br />
                  {n.acknowledged_at ? <Pill tone="ok">ciente em {dateTime(n.acknowledged_at)}</Pill> : <Button onClick={() => run(async () => { await api.post(`/v1/org/remuneration/notices/${n.id}/ack`, {}); reload(); return "Ciência registrada."; })}>Registrar ciência</Button>}</span></li>
              ))}</ul>
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------ v0.34.0: painel do financiador
export function OrgContributions() {
  const { data, error, loading, reload } = useLoad<any>("/v1/org/contributions");
  return (
    <>
      <PageHead title="Contribuições da organização" sub="Doações e compromissos feitos em nome da organização, com estado e comprovante. Resultados são os declarados pelas organizações apoiadas." />
      <StateView loading={loading} error={error} onRetry={reload} empty={!data?.donations?.length && !data?.pledges?.length}>
        {data && (
          <>
            <Panel title="Totais">
              <KeyValue items={[["Confirmado (líquido de estornos)", money(data.totals?.confirmed_cents)], ["Pendente (não é doação)", money(data.totals?.pending_cents)],
                                ["Estornado", money(data.totals?.reversed_cents)], ["Compromissos em aberto (não é dinheiro)", money(data.totals?.pledged_cents)],
                                ["Campanhas apoiadas", data.campaigns_supported?.length || 0]]} />
            </Panel>
            <Panel title="Doações">
              <ul className="rows">{data.donations?.map((d: any) => (
                <li key={d.id}><span><Link to={`/campanha/${d.slug}`}>{d.campaign_title}</Link> — {d.beneficiary} — {money(d.amount_cents)} · {dateTime(d.created_at)}{d.settled_at ? " · liquidada" : ""}{d.receipt_number ? ` · comprovante ${d.receipt_number}` : ""}{d.is_simulated ? " · simulada" : ""}</span>
                  <Pill tone={["confirmed", "reconciled"].includes(d.status) ? "ok" : "muted"}>{st(d.status)}</Pill></li>
              ))}</ul>
            </Panel>
            {data.pledges?.length > 0 && (
              <Panel title="Compromissos">
                <ul className="rows">{data.pledges.map((p: any) => <li key={p.id}><span>{p.campaign_title} — {money(p.amount_cents)}{p.expected_on ? ` até ${date(p.expected_on)}` : ""}</span><Pill tone="muted">{st(p.status)}</Pill></li>)}</ul>
              </Panel>
            )}
            <p className="muted small">{data.note}</p>
          </>
        )}
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------ v0.34.0: administração — obrigações e conciliação
export function AdminRemuneration() {
  const [state, setState] = useState("");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/remuneration${state ? `?state=${state}` : ""}`, [state]);
  const { busy, run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const [sel, setSel] = useState<string[]>([]);
  const rev = data?.revenue;
  const act = (path: string, body: any, msg: string) => run(async () => { await api.post(path, body); reload(); return msg; });
  return (
    <>
      <PageHead title="Remuneração: previsto × devido × recebido" sub="Nenhum destes números é receita reconhecida: só 'liquidada' é dinheiro conciliado na conta da plataforma."
                actions={<Select aria-label="Filtrar por estado" value={state} onChange={setState} options={[["", "Todos"], ...Object.entries(OBL)]} />} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Visão de receita (por estado)">
              <KeyValue items={[["Calculada, não devida", money(rev?.calculated_not_due_cents)], ["Devida / faturada / cobrada / vencida", money(rev?.due_cents)],
                                ["Recebida", money(rev?.received_cents)], ["Liquidada (conciliada)", money(rev?.settled_cents)]]} />
              <p className="muted small">{rev?.note}</p>
            </Panel>
            <Panel title="Obrigações" actions={<Button variant="primary" busy={busy} disabled={!sel.length} onClick={() => act("/v1/admin/remuneration/invoice", { obligation_ids: sel }, "Fatura própria emitida.")}>Faturar selecionadas ({sel.length})</Button>}>
              <ul className="rows">{data.items?.map((o: any) => (
                <li key={o.id}>
                  <span>
                    {o.state === "due" && <input type="checkbox" aria-label="Selecionar para faturar" checked={sel.includes(o.id)} onChange={(e) => setSel(e.target.checked ? [...sel, o.id] : sel.filter((x) => x !== o.id))} />}
                    {" "}{o.org_name} — {money(o.amount_cents)} sobre {money(o.basis_cents)} · {obligationRuleLabel(o.rule_key)} · {FUNDING[o.funding_source]}{o.public_fee_authorized ? " (autorizado)" : ""}{o.trigger_code ? ` · gatilho ${o.trigger_code}` : ""}{o.due_on ? ` · vence ${date(o.due_on)}` : ""}
                    {" "}<Input value={note[o.id] || ""} onChange={(v) => setNote({ ...note, [o.id]: v })} placeholder="Justificativa / referência" />
                    {" "}<Button busy={busy} onClick={() => act(`/v1/admin/remuneration/orgs/${o.org_id}/evaluate`, {}, "Política aplicada à organização.")}>Avaliar política</Button>
                    {o.state === "invoiced" && <> <Button busy={busy} onClick={() => act(`/v1/admin/remuneration/${o.id}/charged`, {}, "Marcada como cobrada.")}>Cobrada</Button></>}
                    {["invoiced", "charged", "overdue", "disputed"].includes(o.state) && <> <Button busy={busy} disabled={(note[o.id] || "").length < 3} onClick={() => act(`/v1/admin/remuneration/${o.id}/receipt`, { received_cents: o.amount_cents - (o.received_cents || 0), reference: note[o.id] }, "Recebimento registrado.")}>Recebida (restante)</Button></>}
                    {o.state === "received" && <> <Button busy={busy} disabled={(note[o.id] || "").length < 3} onClick={() => act(`/v1/admin/remuneration/${o.id}/settle`, { note: note[o.id] }, "Liquidada.")}>Liquidar</Button></>}
                    {["received", "settled"].includes(o.state) && <> <Button busy={busy} disabled={(note[o.id] || "").length < 10} onClick={() => act(`/v1/admin/remuneration/${o.id}/refund`, { refunded_cents: o.received_cents, reference: note[o.id].slice(0, 120), note: note[o.id] }, "Reembolso integral registrado: obrigação estornada.")}>Reembolsar integral</Button></>}
                    {o.state === "disputed" && <> <Button busy={busy} disabled={(note[o.id] || "").length < 10} onClick={() => act(`/v1/admin/remuneration/${o.id}/decide`, { outcome: "uphold", note: note[o.id] }, "Disputa decidida: mantida.")}>Manter</Button> <Button busy={busy} disabled={(note[o.id] || "").length < 10} onClick={() => act(`/v1/admin/remuneration/${o.id}/decide`, { outcome: "waive", note: note[o.id] }, "Disputa decidida: dispensada.")}>Dispensar</Button></>}
                    {["calculated", "exempt", "due", "invoiced", "charged", "overdue"].includes(o.state) && <> <Button busy={busy} disabled={(note[o.id] || "").length < 10} onClick={() => act(`/v1/admin/remuneration/${o.id}/waive`, { reason: note[o.id] }, "Obrigação dispensada.")}>Dispensar</Button></>}
                    {o.funding_source !== "private" && !o.public_fee_authorized && <> <Button busy={busy} disabled={(note[o.id] || "").length < 10} onClick={() => act(`/v1/admin/remuneration/${o.id}/authorize-public`, { instrument_ref: note[o.id].slice(0, 300), note: note[o.id] }, "Instrumento e autorização registrados.")}>Autorizar por instrumento</Button></>}
                  </span>
                  <Pill tone={o.state === "due" || o.state === "overdue" ? "warn" : o.state === "settled" ? "ok" : "muted"}>{OBL[o.state] || o.state}</Pill>
                </li>
              ))}</ul>
              <p className="muted small"><Button busy={busy} onClick={() => act("/v1/admin/remuneration/mark-overdue", {}, "Vencidas marcadas.")}>Marcar vencidas</Button> · Liquidar, decidir disputa, dispensar e autorizar recurso público exigem <code>finance.approve</code> (segregação).</p>
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

export function AdminReconciliation() {
  const [status, setStatus] = useState("open");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/reconciliation/exceptions?status=${status}`, [status]);
  const { busy, run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const [camp, setCamp] = useState("");
  return (
    <>
      <PageHead title="Conciliação: fila de exceções" sub="Webhook recebido não é conciliação. Só a doação cujo evento assinado bate com o snapshot do provedor vira conciliada; o resto vira exceção tipada, com responsável e histórico."
                actions={<Select aria-label="Filtrar por situação" value={status} onChange={setStatus} options={[["open", "Abertas"], ["assigned", "Assumidas"], ["resolved", "Resolvidas"], ["dismissed", "Descartadas"]]} />} />
      <Panel title="Executar conciliação de uma campanha">
        <Field label="Identificador da campanha"><Input value={camp} onChange={setCamp} /></Field>
        <Button variant="primary" busy={busy} disabled={!camp} onClick={() => run(async () => { const r = await api.post(`/v1/admin/reconciliation/campaigns/${camp}/run`, {}); reload(); return `Conferidas ${r.checked}, conciliadas ${r.reconciled}, exceções abertas ${r.opened}.`; })}>Executar (snapshot do provedor)</Button>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={!data?.items?.length}>
        <ul className="rows">{data?.items?.map((e: any) => (
          <li key={e.id}>
            <span><strong>{RECON_KIND[e.kind] || e.kind}</strong> · {e.campaign_title || e.campaign_id} · {e.provider_ref || "—"}{e.expected_cents != null ? ` · esperado ${money(e.expected_cents)}` : ""}{e.observed_cents != null ? ` · observado ${money(e.observed_cents)}` : ""} · {dateTime(e.created_at)}
              <br /><small>{e.detail}</small>
              {["open", "assigned"].includes(e.status) && (
                <> <Input value={note[e.id] || ""} onChange={(v) => setNote({ ...note, [e.id]: v })} placeholder="Resolução (mín. 10 caracteres)" />
                  {e.status === "open" && <Button busy={busy} onClick={() => run(async () => { await api.post(`/v1/admin/reconciliation/exceptions/${e.id}/assign`, {}); reload(); return "Assumida."; })}>Assumir</Button>}
                  {" "}<Button busy={busy} disabled={(note[e.id] || "").length < 10} onClick={() => run(async () => { await api.post(`/v1/admin/reconciliation/exceptions/${e.id}/resolve`, { outcome: "resolved", note: note[e.id] }); reload(); return "Resolvida."; })}>Resolver</Button>
                  {" "}<Button busy={busy} disabled={(note[e.id] || "").length < 10} onClick={() => run(async () => { await api.post(`/v1/admin/reconciliation/exceptions/${e.id}/resolve`, { outcome: "dismissed", note: note[e.id] }); reload(); return "Descartada."; })}>Descartar</Button></>
              )}
              {e.resolution_note && <><br /><small>Resolução: {e.resolution_note}</small></>}
            </span>
            <Pill tone={e.priority === "high" ? "warn" : "muted"}>{e.priority} · {e.status}</Pill>
          </li>
        ))}</ul>
      </StateView>
    </>
  );
}
const NEVER_BLOCKS: Record<string, string> = { accountability: "prestação de contas", exports: "exportações", public_page: "página pública", evidence: "evidências", reports: "relatórios" };
const RECON_KIND: Record<string, string> = { provider_only: "Só no provedor", system_only: "Só no sistema", amount_mismatch: "Valor divergente", fee_mismatch: "Tarifa divergente", reversal_missing: "Estorno sem reversão", duplicate_entry: "Lançamento duplicado", fee_miscalculated: "Taxa calculada errada", settlement_partial: "Liquidação parcial/atrasada", unreconciled_overdue: "Sem conciliação no prazo", settlement_failed: "Falha de liquidação", event_processing_failed: "Evento não aplicado (reprocessa)" };
