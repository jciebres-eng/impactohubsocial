// Compras com cotações, modelos de contribuição, pagamentos (registro, não custódia), extratos e conciliação.
import { useState } from "react";
import { api } from "../api";
import { date, label, money, n, parseMoney } from "../format";
import { Link } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, KeyValue, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

export function Procurement({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/procurement`);
  const policy = useLoad<any>("/v1/procurement/policy");
  const f = useForm<any>({ description: "", estimated: "" });
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Compras e cotações" back={<Link to={`/projetos/${id}`} className="back">Projeto</Link>}
        sub={policy.data ? `Política: mínimo de ${policy.data.min_quotes} cotações${policy.data.quote_threshold_cents ? ` acima de ${money(policy.data.quote_threshold_cents)}` : ""}.` : undefined} />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Pedidos">
            {(data?.items || []).length === 0 ? <p className="muted">Nenhum pedido de compra.</p> : (
              <ul className="rows">{data.items.map((r: any) => <li key={r.id}><Link to={`/compras/${r.id}`}>{r.description}</Link><span>{money(r.estimated_cents)} · {r.quotes} cotação(ões) <Pill status={r.status} /></span></li>)}</ul>
            )}
          </Panel>
          <Panel title="Novo pedido de compra">
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); const c = parseMoney(f.v.estimated); if (c === null) return;
              run(() => api.post(`/v1/projects/${id}/procurement`, { description: f.v.description, estimated_cents: c }), "Pedido criado").then(reload); }}>
              <Field label="O que será comprado" wide><Input value={f.v.description} onChange={f.set("description")} /></Field>
              <Field label="Valor estimado (R$)"><Input value={f.v.estimated} onChange={f.set("estimated")} inputMode="decimal" /></Field>
              <Button type="submit" variant="primary" busy={busy} disabled={f.v.description.length < 3}>Criar pedido</Button>
            </form>
          </Panel>
        </div>
      </StateView>
    </>
  );
}

export function ProcurementDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/procurement/${id}`);
  const f = useForm<any>({ supplier_name: "", amount: "" });
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();
  const r = data?.request;
  const open = r && ["open", "exception_pending"].includes(r.status);
  const b = data?.benchmark;
  return (
    <>
      <PageHead title={r?.description || "Pedido de compra"} sub={r && <>Estimado {money(r.estimated_cents)} · <Pill status={r.status} /></>} back={r && <Link to={`/projetos/${r.project_id}/compras`} className="back">Compras</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title={`Cotações (${data.quotes.length} de ${data.required_quotes} exigidas)`}>
              {data.quotes.length === 0 ? <p className="muted">Nenhuma cotação ainda.</p> : (
                <table className="table"><thead><tr><th>Fornecedor</th><th>Valor</th><th>Observação automática</th><th></th></tr></thead>
                  <tbody>{data.quotes.map((q: any) => (
                    <tr key={q.id}><td>{q.supplier_name}</td><td>{money(q.amount_cents)}</td>
                      <td>{q.flag ? <Pill tone="warn">{q.flag}</Pill> : <span className="muted">—</span>}</td>
                      <td>{open && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/procurement/${id}/decide`, { quotation_id: q.id, decision_reason: reason || undefined, exception_reason: data.meets_policy ? undefined : reason || undefined }), "Decisão registrada").then(reload)}>Escolher</Button>}</td></tr>
                  ))}</tbody></table>
              )}
              {b && b.count >= 3 && <KeyValue items={[["Mediana", money(b.median_cents)], ["Menor", money(b.min_cents)], ["Maior", money(b.max_cents)]]} />}
              <p className="muted">Os avisos indicam preço possivelmente fora do padrão das cotações recebidas; são um sinal para justificar a escolha, não uma conclusão sobre o fornecedor.</p>
            </Panel>
            {open && (
              <>
                <Panel title="Justificativa">
                  <Field label="Motivo da escolha ou da exceção (obrigatório se faltar cotação ou o valor estiver fora do padrão)" wide><TextArea value={reason} onChange={setReason} rows={2} /></Field>
                </Panel>
                <Panel title="Nova cotação">
                  <form className="form" onSubmit={(e: any) => { e.preventDefault(); const c = parseMoney(f.v.amount); if (c === null) return;
                    run(() => api.post(`/v1/procurement/${id}/quotes`, { supplier_name: f.v.supplier_name, amount_cents: c }), "Cotação adicionada").then(() => { f.set("supplier_name")(""); f.set("amount")(""); reload(); }); }}>
                    <Field label="Fornecedor"><Input value={f.v.supplier_name} onChange={f.set("supplier_name")} /></Field>
                    <Field label="Valor (R$)"><Input value={f.v.amount} onChange={f.set("amount")} inputMode="decimal" /></Field>
                    <Button type="submit" variant="primary" busy={busy} disabled={f.v.supplier_name.length < 2}>Adicionar</Button>
                  </form>
                </Panel>
              </>
            )}
            {r.status === "exception_pending" && (
              <Panel title="Exceção aguardando segunda aprovação">
                <p>Outra pessoa da organização, diferente de quem decidiu, precisa aprovar.</p>
                <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/procurement/${id}/approve-exception`), "Exceção aprovada").then(reload)}>Aprovar exceção</Button>
              </Panel>
            )}
          </div>
        )}
      </StateView>
    </>
  );
}

export function Payments() {
  const { me } = useSession();
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/payments?offset=${offset}`);
  return (
    <>
      <PageHead title="Pagamentos" sub="Registro e confirmação entre as partes. A plataforma não movimenta nem guarda dinheiro." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (data.items.length === 0 ? <div className="state state-empty"><p>Nenhum pagamento registrado. Eles surgem a partir de aportes registrados.</p></div> : (
          <>
            <table className="table"><thead><tr><th>Projeto</th><th>Valor</th><th>Estado</th><th>Conciliação</th><th></th></tr></thead>
              <tbody>{data.items.map((p: any) => <tr key={p.id}><td>{p.project_title}</td><td>{money(p.amount_cents)}</td><td><Pill status={p.state} /></td><td>{label(p.reconciliation_status)}</td>
                <td><Link to={`/pagamentos/${p.id}`}>Abrir</Link></td></tr>)}</tbody></table>
            <Pager data={data} offset={offset} setOffset={setOffset} />
          </>
        ))}
      </StateView>
      {me?.active_org?.kind === "osc" && <p><Link to="/extratos">Importar extrato e conciliar</Link></p>}
    </>
  );
}

const STATE_LABEL: Record<string, string> = { created: "Registrado", awaiting_confirmation: "Aguardando confirmação", confirmed: "Recebimento confirmado", failed: "Não recebido", disputed: "Em disputa",
  cancelled: "Cancelado", partially_refunded: "Parcialmente estornado", refunded: "Estornado" };

export function PaymentDetail({ id }: { id: string }) {
  const { me } = useSession();
  const { data, error, loading, reload } = useLoad<any>(`/v1/payments/${id}`);
  const [note, setNote] = useState("");
  const rf = useForm<any>({ amount: "", reason: "" });
  const { busy, run } = useAction();
  const kind = me?.active_org?.kind;
  const move = (to: string, ok: string) => run(() => api.post(`/v1/payments/${id}/transition`, { to, note: note || undefined }), ok).then(reload);
  const isOsc = kind === "osc";
  return (
    <>
      <PageHead title="Pagamento" sub={data && <>{money(data.amount_cents)} · {STATE_LABEL[data.state] || data.state}</>} back={<Link to="/pagamentos" className="back">Pagamentos</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title="Ações">
              <Field label="Observação (obrigatória para “não recebido” e “disputa”)" wide><Input value={note} onChange={setNote} /></Field>
              <div className="stack-row">
                {!isOsc && data.state === "created" && <Button variant="primary" busy={busy} onClick={() => move("awaiting_confirmation", "Envio informado à OSC")}>Informar que enviei</Button>}
                {isOsc && data.state === "awaiting_confirmation" && <>
                  <Button variant="primary" busy={busy} onClick={() => move("confirmed", "Recebimento confirmado")}>Confirmar recebimento</Button>
                  <Button variant="ghost" busy={busy} onClick={() => move("failed", "Marcado como não recebido")}>Não recebi</Button>
                  <Button variant="danger" busy={busy} onClick={() => move("disputed", "Disputa aberta")}>Abrir disputa</Button></>}
                {["created", "awaiting_confirmation"].includes(data.state) && <Button variant="ghost" busy={busy} onClick={() => move("cancelled", "Pagamento cancelado")}>Cancelar</Button>}
              </div>
            </Panel>
            <Panel title="Histórico">
              <ol className="rows">{data.events.map((e: any, i: number) => <li key={i}><span>{STATE_LABEL[e.to_state] || e.to_state}{e.note ? ` — ${e.note}` : ""}</span><span className="muted">{e.actor} · {date(e.at)}</span></li>)}</ol>
            </Panel>
            {["confirmed", "partially_refunded"].includes(data.state) && (
              <Panel title="Estorno">
                <p className="muted">O estorno exige aprovação da outra parte e é concluído pela OSC. Estornado até agora: {money(data.refunded_cents)}.</p>
                <form className="form" onSubmit={(e: any) => { e.preventDefault(); const c = parseMoney(rf.v.amount); if (c === null) return;
                  run(() => api.post(`/v1/payments/${id}/refunds`, { amount_cents: c, reason: rf.v.reason }), "Estorno solicitado").then(reload); }}>
                  <Field label="Valor (R$)"><Input value={rf.v.amount} onChange={rf.set("amount")} inputMode="decimal" /></Field>
                  <Field label="Motivo" wide><Input value={rf.v.reason} onChange={rf.set("reason")} /></Field>
                  <Button type="submit" variant="ghost" busy={busy} disabled={rf.v.reason.length < 5}>Solicitar estorno</Button>
                </form>
              </Panel>
            )}
            {data.refunds.length > 0 && (
              <Panel title="Pedidos de estorno">
                <ul className="rows">{data.refunds.map((r: any) => (
                  <li key={r.id}><span>{money(r.amount_cents)} — {r.reason}</span>
                    <span className="stack-row"><Pill status={r.status} />
                      {r.status === "requested" && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/refunds/${r.id}/decide`, { decision: "approved" }), "Estorno aprovado").then(reload)}>Aprovar</Button>}
                      {r.status === "approved" && isOsc && <Button variant="ink" busy={busy} onClick={() => run(() => api.post(`/v1/refunds/${r.id}/decide`, { decision: "completed" }), "Estorno concluído").then(reload)}>Concluir</Button>}
                    </span></li>
                ))}</ul>
              </Panel>
            )}
          </div>
        )}
      </StateView>
    </>
  );
}

export function Statements() {
  const { data, error, loading, reload } = useLoad<any>("/v1/statements/lines");
  const [csv, setCsv] = useState("");
  const { busy, run } = useAction();
  async function pick(e: any) { const file = e.target.files?.[0]; if (file) setCsv(await file.text()); }
  return (
    <>
      <PageHead title="Extrato e conciliação" sub="Importe um CSV (data;valor;descrição;referência). A conciliação sugere correspondências; você confirma." />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Importar extrato">
            <input type="file" accept=".csv,text/csv" onChange={pick} aria-label="Arquivo CSV do extrato" />
            <Button variant="primary" busy={busy} disabled={!csv} onClick={() => run(() => api.post("/v1/statements", { filename: "extrato.csv", csv }), "Extrato importado").then(() => { setCsv(""); reload(); })}>Importar</Button>
          </Panel>
          <Panel title={`Linhas (${data?.summary?.lines ?? 0}, ${data?.summary?.matched ?? 0} conciliadas)`}>
            {(data?.items || []).length === 0 ? <p className="muted">Nenhuma linha importada.</p> : (
              <table className="table"><thead><tr><th>Data</th><th>Descrição</th><th>Valor</th><th>Situação</th></tr></thead>
                <tbody>{data.items.map((l: any) => <tr key={l.id}><td>{date(l.booked_on)}</td><td>{l.description}</td><td>{money(l.amount_cents)}</td><td><Pill status={l.matched_payment_id ? "confirmed" : "pending"}>{l.matched_payment_id ? "Conciliada" : "Sem correspondência"}</Pill></td></tr>)}</tbody></table>
            )}
          </Panel>
        </div>
      </StateView>
    </>
  );
}

export function ContributionModels({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/contribution-models`);
  const proj = useLoad<any>(`/v1/projects/${id}`);
  const f = useForm<any>({ kind: "donation", title: "", legal_structure: "", refundable: false, refund_policy: "" });
  const { busy, run } = useAction();
  const owner = proj.data?.is_owner;
  return (
    <>
      <PageHead title="Modelos de contribuição" back={<Link to={`/projetos/${id}`} className="back">Projeto</Link>}
        sub="Cada modelo precisa de aprovação jurídica da plataforma antes de ser oferecido a financiadores." />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Modelos">
            {(data?.items || []).length === 0 ? <p className="muted">Nenhum modelo{owner ? "" : " aprovado"}.</p> : (
              <ul className="rows">{data.items.map((m: any) => <li key={m.id}><span>{m.title} <span className="muted">({label(m.kind)})</span></span>
                <span className="stack-row"><Pill status={m.status} />{owner && m.status === "draft" && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/contribution-models/${m.id}/submit`), "Enviado à análise jurídica").then(reload)}>Enviar para análise</Button>}</span></li>)}</ul>
            )}
          </Panel>
          {owner && (
            <Panel title="Novo modelo">
              <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/projects/${id}/contribution-models`, { kind: f.v.kind, title: f.v.title, legal_structure: f.v.legal_structure || null,
                refundable: f.v.refundable, refund_policy: f.v.refund_policy || null }), "Modelo criado").then(reload); }}>
                <Field label="Tipo"><Select value={f.v.kind} onChange={f.set("kind")} options={[["donation", "Doação"], ["sponsorship", "Patrocínio"], ["quota", "Cotas (exige estrutura jurídica)"], ["fund_transfer", "Repasse"]]} /></Field>
                <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
                <Field label="Estrutura jurídica prevista" wide><Input value={f.v.legal_structure} onChange={f.set("legal_structure")} /></Field>
                <Button type="submit" variant="primary" busy={busy} disabled={f.v.title.length < 3}>Criar rascunho</Button>
              </form>
            </Panel>
          )}
        </div>
      </StateView>
    </>
  );
}

export { n, TextArea };
