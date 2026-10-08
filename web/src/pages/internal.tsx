// Operação interna: controladoria, financeiro, contabilidade, tesouraria, operações, auditoria.
//
// O QUE ESTAS TELAS RESOLVEM
//
// A auditoria desta rodada encontrou 224 das 848 rotas sem tela nenhuma — entre elas a saúde do
// sistema, a receita apurada, as tarefas agendadas e o hub de integrações. Construído,
// funcionando, invisível. E não havia controladoria, contabilidade nem tesouraria da PRÓPRIA
// plataforma: o "financeiro" era um punhado de rotas soltas atrás de um booleano de administrador.
//
// A REGRA QUE GOVERNA O QUE ESTAS TELAS MOSTRAM (ADR-284)
//
// A plataforma CALCULA, INSTRUI e CONCILIA. Ela não guarda dinheiro de terceiro, não repassa e não
// executa pagamento. Toda tela daqui diz de quem é o dinheiro que está mostrando — porque a
// pergunta "esse saldo é de quem?" é a que separa um SaaS de uma instituição de pagamento.
//
// E TODO INDICADOR DIZ DE ONDE VEIO
//
// Indicador sem fonte responde `available: false` com o motivo, nunca zero. Zero parece medição.
import { useState } from "react";
import { api } from "../api";
import { date, dateTime, money } from "../format";
import { Link } from "../router";
import { Button, Field, Input, KeyValue, PageHead, Panel, Pill, Select, StateView, useAction, useLoad } from "../ui/kit";
import { useAccess } from "../access";

const hoje = () => new Date().toISOString().slice(0, 7);

// --------------------------------------------------------------------------------- indicador honesto
type Metric = { value?: number | null; source: string; calculation: string; period?: string | null; available?: boolean; unavailable_reason?: string; currency?: string; last_updated?: string | null };

function Indicator({ title, m, kind = "money" }: { title: string; m?: Metric; kind?: "money" | "count" | "percent" | "months" }) {
  if (!m) return null;
  const indisponivel = m.available === false;
  const texto = indisponivel ? "não medido"
    : kind === "money" ? money(m.value ?? 0, m.currency || "BRL")
    : kind === "percent" ? `${Math.round((m.value ?? 0) * 10) / 10}%`
    : kind === "months" ? `${Math.round((m.value ?? 0) * 10) / 10} meses`
    : String(m.value ?? 0);
  return (
    <div className={`metric${indisponivel ? " metric-void" : ""}`}>
      <span className="metric-label">{title}</span>
      <strong className="metric-value">{texto}</strong>
      {indisponivel
        ? <span className="metric-why">{m.unavailable_reason}</span>
        : <span className="metric-why">{m.source} · {m.calculation}{m.period ? ` · ${m.period}` : ""}</span>}
    </div>
  );
}

function Honesty({ note }: { note?: string }) {
  if (!note) return null;
  return <p className="note-honesty" role="note">{note}</p>;
}

// ------------------------------------------------------------------------------------- CONTROLADORIA

export function Controladoria() {
  const [period, setPeriod] = useState(hoje());
  const { data, error, loading, reload } = useLoad<any>(`/v1/controladoria/summary?period=${period}`, [period]);
  return (
    <>
      <PageHead title="Controladoria" sub="Receita, caixa, despesa e resultado da plataforma. Cada número diz de onde veio."
        actions={<Field label="Competência"><Input type="month" value={period} onChange={setPeriod} /></Field>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title="Camada econômica da operação (sem assinatura — ADR-341)">
              <div className="metrics">
                <Indicator title="Registrado (3,5%)" m={data.operation_layer?.platform_layer_registered} />
                <Indicator title="Devido" m={data.operation_layer?.platform_layer_due} />
                <Indicator title="Pago à plataforma" m={data.operation_layer?.platform_layer_paid} />
                <div className="metric"><span className="metric-label">Operações com camada registrada</span><strong className="metric-value">{data.operation_layer?.operations ?? 0}</strong><span className="metric-why">economic_events · platform_service_registered</span></div>
                <Indicator title="MRR" m={data.operation_layer?.mrr} />
              </div>
            </Panel>
            <Panel title="Competência" actions={<Link to="/contabilidade">Abrir contabilidade</Link>}>
              <div className="metrics">
                <Indicator title="Receita bruta" m={data.revenue?.gross_revenue} />
                <Indicator title="Deduções" m={data.revenue?.deductions} />
                <Indicator title="Receita líquida" m={data.revenue?.net_revenue} />
              </div>
            </Panel>
            <Panel title="Caixa e despesa" actions={<Link to="/financeiro">Abrir financeiro</Link>}>
              <div className="metrics">
                <Indicator title="Entradas" m={data.cash?.cash_in} />
                <Indicator title="Saídas" m={data.cash?.cash_out} />
                <Indicator title="Despesa total" m={data.expenses?.total} />
                <Indicator title="Custo de IA" m={data.expenses?.ai_cost} />
                <Indicator title="Resultado" m={data.result?.net_result} />
                <Indicator title="Queima mensal" m={data.result?.burn} />
                <Indicator title="Autonomia" m={data.result?.runway_months} kind="months" />
              </div>
            </Panel>
            <Panel title="Volume transacionado na rede (GMV)">
              <div className="metrics">
                <Indicator title="GMV" m={data.gmv?.gmv} />
                <Indicator title="Receita da plataforma sobre o GMV" m={data.gmv?.platform_revenue_on_gmv} />
              </div>
              {data.gmv?.warning && <p className="note-honesty">{data.gmv.warning}</p>}
            </Panel>
            <Panel title="Conversão">
              <div className="metrics">
                <Indicator title="Teste → pago" m={data.conversion?.free_to_paid} kind="percent" />
                <Indicator title="Churn" m={data.conversion?.churn} kind="percent" />
                <Indicator title="LTV" m={data.conversion?.ltv} />
                <Indicator title="CAC" m={data.conversion?.cac} />
              </div>
            </Panel>
            <Panel title="O que exige ação">
              <ul className="rows">
                <li><span>Aprovações pendentes</span><span className="stack-row"><strong>{data.pending_approvals}</strong><Link to="/aprovacoes">Abrir</Link></span></li>
                <li><span>Divergências na conciliação</span><span className="stack-row"><strong>{data.divergences}</strong><Link to="/controladoria/conciliacao">Conferir</Link></span></li>
                <li><span>Indicadores sem base de dados</span><span><strong>{data.unavailable_metrics ?? 0}</strong></span></li>
              </ul>
            </Panel>
            <Honesty note={data.honesty_note} />
          </div>
        )}
      </StateView>
    </>
  );
}

export function Conciliacao() {
  const { data, error, loading, reload } = useLoad<any>("/v1/controladoria/reconciliation?days=30");
  const blocos: [string, string, string][] = [
    ["overdue_instructions", "Instruções vencidas", "Emitidas, com vencimento passado e sem registro de execução."],
    ["executed_without_evidence", "Executadas sem evidência", "Não deveria existir: a restrição da tabela exige evidência. Se aparecer, há caminho novo gravando sem ela."],
    ["paid_expenses_without_entry", "Despesa paga sem lançamento", "Saiu caixa e a competência não registrou."],
    ["unbalanced_batches", "Lotes que não fecham", "Débito diferente de crédito. Impede o fechamento da competência."],
  ];
  return (
    <>
      <PageHead title="Conciliação" sub="O que foi esperado contra o que aconteceu. Esta tela APONTA; ela não corrige nada sozinha." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel quiet>
              <div className="metrics">
                <div className="metric"><span className="metric-label">Divergências</span><strong className="metric-value">{data.divergences}</strong>
                  <span className="metric-why">últimos {data.window_days} dias</span></div>
              </div>
            </Panel>
            {blocos.map(([chave, titulo, explicacao]) => (
              <Panel key={chave} title={`${titulo} (${(data[chave] || []).length})`}>
                <p className="muted">{explicacao}</p>
                {(data[chave] || []).length === 0 ? <p className="muted">Nada aqui.</p> : (
                  <table className="table"><tbody>
                    {(data[chave] || []).map((r: any, i: number) => (
                      <tr key={i}>{Object.entries(r).map(([k, v]) => (
                        <td key={k}>{k.endsWith("_cents") ? money(v as number) : k.endsWith("_on") || k.endsWith("_at") ? dateTime(String(v)) : String(v ?? "—")}</td>
                      ))}</tr>
                    ))}
                  </tbody></table>
                )}
              </Panel>
            ))}
            {data.charges && (
              <Panel title="Cobrança">
                <p className="muted">Nenhum provedor de pagamento está em produção; estas são as cobranças registradas pela plataforma.</p>
                <pre className="code-block">{JSON.stringify(data.charges, null, 2)}</pre>
              </Panel>
            )}
          </div>
        )}
      </StateView>
    </>
  );
}

// ---------------------------------------------------------------------------------------- APROVAÇÕES

export function Aprovacoes() {
  const { data, error, loading, reload } = useLoad<any>("/v1/aprovacoes");
  const { has } = useAccess();
  const { busy, run } = useAction();
  const [nota, setNota] = useState("");
  return (
    <>
      <PageHead title="Aprovações" sub="A alçada é dado no banco, não constante no código: mudar faixa é decisão de governança." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title={`Pendentes (${data.items.length})`}>
              {data.items.length === 0 ? <p className="muted">Nada aguardando decisão.</p> : (
                <ul className="rows">
                  {data.items.map((p: any) => {
                    // A faixa e o que falta vêm RESOLVIDOS do servidor (`permissions_available`,
                    // `remaining`). Esta tela recalculava `approval_rule_for()` em JavaScript —
                    // segunda implementação da mesma regra, com desempate diferente do SQL.
                    const faltam = Number(p.remaining ?? 0);
                    const usadas: string[] = p.permissions_used || [];
                    const disponiveis: string[] = (p.permissions_available || []).filter((x: string) => has(x));
                    return (
                      <li key={p.id}>
                        <span>
                          <strong>{money(p.amount_cents, p.currency)}</strong> · {p.summary}
                          <div className="muted">{p.operation} · pedido por {p.requested_by} · {dateTime(p.created_at)}</div>
                          <div className="muted">faltam {faltam} de {p.approvals_needed}
                            {usadas.length > 0 && <> · já usadas: {usadas.join(", ")}</>}</div>
                        </span>
                        <span className="stack-row">
                          {disponiveis.length === 0
                            ? <Pill tone="muted">Nenhuma permissão sua serve aqui</Pill>
                            : disponiveis.map((perm) => (
                              <Button key={perm} variant="ink" busy={busy}
                                onClick={() => run(() => api.post(`/v1/aprovacoes/${p.id}/decide`, { approve: true, permission_used: perm, note: nota || undefined }), "Aprovado").then(reload)}>
                                Aprovar como {perm}
                              </Button>
                            ))}
                          {disponiveis.length > 0 && (
                            <Button variant="danger" busy={busy} disabled={nota.length < 5}
                              onClick={() => run(() => api.post(`/v1/aprovacoes/${p.id}/decide`, { approve: false, permission_used: disponiveis[0], note: nota }), "Recusado").then(reload)}>
                              Recusar
                            </Button>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
              <Field label="Justificativa (obrigatória para recusar, mín. 5 caracteres)" wide><Input value={nota} onChange={setNota} /></Field>
            </Panel>
            <Panel title="Faixas de alçada vigentes">
              <table className="table">
                <thead><tr><th>Operação</th><th>De</th><th>Até</th><th>Assinaturas</th><th>Permissões aceitas</th></tr></thead>
                <tbody>{(data.bands || []).map((b: any, i: number) => (
                  <tr key={i}><td>{b.operation}</td><td>{money(b.min_cents)}</td><td>{b.max_cents === null ? "sem limite" : money(b.max_cents)}</td>
                    <td>{b.approvals_needed}</td><td>{(b.required_permissions || []).join(", ")}</td></tr>
                ))}</tbody>
              </table>
              <p className="note-honesty">Quem pede não aprova, e faixa de duas assinaturas não se satisfaz com a mesma permissão duas vezes — as duas regras são gatilho no banco, não conferência de tela.</p>
            </Panel>
            <Honesty note={data.note} />
          </div>
        )}
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------------------------------ FINANCEIRO

export function Financeiro() {
  const [period, setPeriod] = useState(hoje());
  const { data, error, loading, reload } = useLoad<any>(`/v1/financeiro/summary?period=${period}`, [period]);
  return (
    <>
      <PageHead title="Financeiro" sub="Recebíveis, pagáveis e instruções em aberto."
        actions={<Field label="Competência"><Input type="month" value={period} onChange={setPeriod} /></Field>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel quiet>
              <div className="metrics">
                <div className="metric"><span className="metric-label">A receber (faturas abertas)</span><strong className="metric-value">{money(data.receivable.cents)}</strong><span className="metric-why">{data.receivable.count} fatura(s)</span></div>
                <div className="metric"><span className="metric-label">A pagar (aprovado ou agendado)</span><strong className="metric-value">{money(data.payable.cents)}</strong><span className="metric-why">{data.payable.count} despesa(s)</span></div>
                <div className={`metric${data.overdue.count ? " metric-alert" : ""}`}><span className="metric-label">Vencido</span><strong className="metric-value">{money(data.overdue.cents)}</strong><span className="metric-why">{data.overdue.count} despesa(s)</span></div>
              </div>
            </Panel>
            <Panel title="Caixa da competência">
              <div className="metrics">
                <Indicator title="Entradas" m={data.cash?.cash_in} />
                <Indicator title="Saídas" m={data.cash?.cash_out} />
                <Indicator title="Resultado de caixa" m={data.cash?.net_cash} />
              </div>
            </Panel>
            <Panel title="Despesa por centro de custo" actions={<Link to="/financeiro/despesas">Ver despesas</Link>}>
              {(data.expenses?.by_cost_center || []).length === 0 ? <p className="muted">Nenhuma despesa registrada nesta competência.</p> : (
                <table className="table"><thead><tr><th>Centro de custo</th><th>Valor</th></tr></thead>
                  <tbody>{data.expenses.by_cost_center.map((r: any) => <tr key={r.cost_center}><td>{r.name || r.cost_center}</td><td>{money(r.cents)}</td></tr>)}</tbody></table>
              )}
            </Panel>
            <Panel title={`Instruções em aberto (${(data.open_instructions || []).length})`} actions={<Link to="/financeiro/instrucoes">Gerenciar</Link>}>
              {(data.open_instructions || []).length === 0 ? <p className="muted">Nenhuma instrução em aberto.</p> : (
                <table className="table"><thead><tr><th>Beneficiário</th><th>Tipo</th><th>Valor</th><th>Vencimento</th><th>Situação</th></tr></thead>
                  <tbody>{data.open_instructions.map((i: any) => <tr key={i.id}><td>{i.payee_name}</td><td>{i.kind}</td><td>{money(i.amount_cents)}</td><td>{date(i.due_on)}</td><td><Pill status={i.state} /></td></tr>)}</tbody></table>
              )}
            </Panel>
            <Honesty note={data.note} />
          </div>
        )}
      </StateView>
    </>
  );
}

const CENTROS: [string, string][] = [["TECH", "Engenharia"], ["CLOUD", "Infraestrutura"], ["AI", "Modelos de IA"], ["PRODUCT", "Produto"], ["MARKETING", "Marketing"], ["SALES", "Comercial"], ["SUPPORT", "Suporte"], ["LEGAL", "Jurídico"], ["FINANCE", "Financeiro"], ["ADMIN", "Administrativo"], ["MARKETPLACE", "Marketplace"]];

export function Despesas() {
  const [period, setPeriod] = useState(hoje());
  const { data, error, loading, reload } = useLoad<any>(`/v1/financeiro/expenses?period=${period}`, [period]);
  const plano = useLoad<any>("/v1/contabilidade/chart");
  const { busy, run } = useAction();
  const [f, setF] = useState({ account_code: "5.1.1", cost_center: "CLOUD", description: "", valor: "", due_on: "", supplier_name: "" });
  const contas = (plano.data?.accounts || []).filter((a: any) => a.analytical && a.nature === "expense").map((a: any) => [a.code, `${a.code} — ${a.name}`] as [string, string]);
  const centavos = Math.round(parseFloat((f.valor || "0").replace(/\./g, "").replace(",", ".")) * 100);
  return (
    <>
      <PageHead title="Despesas da plataforma" sub="Custo próprio, por conta e centro de custo. Quem registra não aprova — é restrição de banco, não de tela."
        actions={<Field label="Competência"><Input type="month" value={period} onChange={setPeriod} /></Field>} back={<Link to="/financeiro">Financeiro</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="Registrar despesa">
            <div className="form-grid">
              <Field label="Conta"><Select value={f.account_code} onChange={(v) => setF({ ...f, account_code: v })} options={contas} /></Field>
              <Field label="Centro de custo"><Select value={f.cost_center} onChange={(v) => setF({ ...f, cost_center: v })} options={CENTROS} /></Field>
              <Field label="Descrição" wide><Input value={f.description} onChange={(v) => setF({ ...f, description: v })} /></Field>
              <Field label="Fornecedor"><Input value={f.supplier_name} onChange={(v) => setF({ ...f, supplier_name: v })} /></Field>
              <Field label="Valor (R$)"><Input value={f.valor} onChange={(v) => setF({ ...f, valor: v })} inputMode="decimal" /></Field>
              <Field label="Vencimento"><Input type="date" value={f.due_on} onChange={(v) => setF({ ...f, due_on: v })} /></Field>
            </div>
            <Button variant="ink" busy={busy} disabled={!(f.description.length > 2 && centavos > 0)}
              onClick={() => run(() => api.post("/v1/financeiro/expenses", {
                period: `${period}-01`, account_code: f.account_code, cost_center: f.cost_center,
                description: f.description, amount_cents: centavos,
                supplier_name: f.supplier_name || undefined, due_on: f.due_on || undefined,
              }), "Despesa registrada e enviada para aprovação").then(() => { setF({ ...f, description: "", valor: "", supplier_name: "" }); reload(); })}>
              Registrar e pedir aprovação
            </Button>
            <p className="note-honesty">Registrar não aprova e não paga: abre um pedido na faixa do valor, que outra pessoa decide em /aprovacoes.</p>
          </Panel>
          <Panel title={`Competência ${period}`}>
            {(data?.items || []).length === 0 ? <p className="muted">Nenhuma despesa nesta competência.</p> : (
              <table className="table">
                <thead><tr><th>Conta</th><th>Centro</th><th>Descrição</th><th>Valor</th><th>Vencimento</th><th>Situação</th><th>Registrou</th><th>Aprovou</th></tr></thead>
                <tbody>{data.items.map((e: any) => (
                  <tr key={e.id}><td>{e.account_code}<div className="muted">{e.account_name}</div></td><td>{e.cost_center}</td><td>{e.description}</td>
                    <td>{money(e.amount_cents)}</td><td>{date(e.due_on)}</td><td><Pill status={e.status} /></td>
                    <td className="muted">{e.created_by}</td><td className="muted">{e.approved_by || "—"}</td></tr>
                ))}</tbody>
              </table>
            )}
          </Panel>
        </div>
      </StateView>
    </>
  );
}

const TIPOS: [string, string][] = [["supplier", "Fornecedor"], ["reimbursement", "Reembolso"], ["tax", "Tributo"], ["payroll", "Folha"], ["marketplace_fee", "Taxa de marketplace"], ["refund", "Devolução"], ["other", "Outro"]];

export function Instrucoes() {
  const { data, error, loading, reload } = useLoad<any>("/v1/financeiro/instructions");
  const { has } = useAccess();
  const { busy, run } = useAction();
  const [f, setF] = useState({ kind: "supplier", payee_name: "", valor: "", due_on: "", reference: "" });
  const [evidencias, setEvidencias] = useState<Record<string, string>>({});
  const centavos = Math.round(parseFloat((f.valor || "0").replace(/\./g, "").replace(",", ".")) * 100);
  return (
    <>
      <PageHead title="Instruções de pagamento" sub="Instrução é DOCUMENTO: valor, beneficiário e vencimento. Quem paga é quem tem o dinheiro — a plataforma nunca executa a transferência."
        back={<Link to="/financeiro">Financeiro</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        <div className="stack-lg">
          <Panel title="O que esta tela faz e o que ela não faz">
            <ul className="bullets">
              <li><strong>Faz:</strong> registra a instrução, abre a aprovação na faixa do valor, congela valor e beneficiário na emissão e guarda a evidência de que alguém pagou.</li>
              <li><strong>Não faz:</strong> não movimenta conta, não gera PIX, não repassa e não guarda saldo de terceiro. A plataforma não é instituição de pagamento (ADR-284).</li>
            </ul>
          </Panel>
          {has("instruction.create") && (
            <Panel title="Nova instrução">
              <div className="form-grid">
                <Field label="Tipo"><Select value={f.kind} onChange={(v) => setF({ ...f, kind: v })} options={TIPOS} /></Field>
                <Field label="Beneficiário"><Input value={f.payee_name} onChange={(v) => setF({ ...f, payee_name: v })} /></Field>
                <Field label="Valor (R$)"><Input value={f.valor} onChange={(v) => setF({ ...f, valor: v })} inputMode="decimal" /></Field>
                <Field label="Vencimento"><Input type="date" value={f.due_on} onChange={(v) => setF({ ...f, due_on: v })} /></Field>
                <Field label="Referência (nota, contrato, guia)" wide><Input value={f.reference} onChange={(v) => setF({ ...f, reference: v })} /></Field>
              </div>
              <Button variant="ink" busy={busy} disabled={!(f.payee_name.length > 1 && centavos > 0 && f.due_on && f.reference.length > 2)}
                onClick={() => run(() => api.post("/v1/financeiro/instructions", {
                  kind: f.kind, payee_name: f.payee_name, amount_cents: centavos,
                  due_on: f.due_on, reference: f.reference,
                }), "Instrução criada e enviada para aprovação").then(() => { setF({ ...f, payee_name: "", valor: "", reference: "" }); reload(); })}>
                Criar instrução
              </Button>
            </Panel>
          )}
          <Panel title={`Em aberto (${(data?.open || []).length})`}>
            {(data?.open || []).length === 0 ? <p className="muted">Nenhuma instrução em aberto.</p> : (
              <ul className="rows">{data.open.map((i: any) => (
                <li key={i.id}>
                  <span><strong>{money(i.amount_cents)}</strong> · {i.payee_name}
                    <div className="muted">{i.kind} · vence {date(i.due_on)}</div></span>
                  <span className="stack-row">
                    <Pill status={i.state} />
                    {/* Só `approved`: `issue_instruction()` chama `require_approved()` e recusa
                        qualquer outro estado com 409. O botão era oferecido em `pending_approval`
                        e `draft` — botão que o servidor recusa por construção. */}
                    {has("instruction.approve") && i.state === "approved" && (
                      <Button variant="ink" busy={busy}
                        onClick={() => run(() => api.post(`/v1/financeiro/instructions/${i.id}/issue`, {}), "Instrução emitida").then(reload)}>Emitir</Button>
                    )}
                    {has("instruction.approve") && i.state === "issued" && (
                      <>
                        <Input value={evidencias[i.id] || ""} onChange={(v) => setEvidencias({ ...evidencias, [i.id]: v })} placeholder="comprovante (arquivo ou referência)" />
                        <Button variant="ghost" busy={busy} disabled={(evidencias[i.id] || "").length < 3}
                          onClick={() => run(() => api.post(`/v1/financeiro/instructions/${i.id}/executed`, { evidence_doc: evidencias[i.id] }), "Execução registrada").then(reload)}>
                          Registrar execução
                        </Button>
                      </>
                    )}
                  </span>
                </li>
              ))}</ul>
            )}
            <p className="note-honesty">A evidência é obrigatória por restrição de tabela: marcar como executada sem ela seria a plataforma afirmando um pagamento que ela não viu.</p>
          </Panel>
        </div>
      </StateView>
    </>
  );
}

// ---------------------------------------------------------------------------------- CONTABILIDADE

export function Contabilidade() {
  const [period, setPeriod] = useState(hoje());
  const { data, error, loading, reload } = useLoad<any>(`/v1/contabilidade/summary?period=${period}`, [period]);
  const { has } = useAccess();
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Contabilidade" sub="Competência, não caixa. Os dois números são diferentes de propósito."
        actions={<Field label="Competência"><Input type="month" value={period} onChange={setPeriod} /></Field>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel quiet>
              <div className="metrics">
                <div className="metric"><span className="metric-label">Situação da competência</span><strong className="metric-value"><Pill status={data.status} /></strong>
                  <span className="metric-why">{data.closed_at ? `fechada em ${dateTime(data.closed_at)}` : "aberta para lançamento"}</span></div>
                <div className="metric"><span className="metric-label">Débitos</span><strong className="metric-value">{money(data.totals.debit_cents)}</strong></div>
                <div className="metric"><span className="metric-label">Créditos</span><strong className="metric-value">{money(data.totals.credit_cents)}</strong></div>
                <div className={`metric${data.totals.balanced ? "" : " metric-alert"}`}><span className="metric-label">Fecha?</span>
                  <strong className="metric-value">{data.totals.balanced ? "sim" : "não"}</strong>
                  <span className="metric-why">{data.totals.balanced ? "débitos iguais a créditos" : "há lote desequilibrado nesta competência"}</span></div>
              </div>
            </Panel>
            <Panel title="Balancete" actions={<Link to="/contabilidade/plano-de-contas">Plano de contas</Link>}>
              {data.trial_balance.length === 0 ? <p className="muted">Nenhum lançamento nesta competência.</p> : (
                <table className="table"><thead><tr><th>Conta</th><th>Natureza</th><th>Débito</th><th>Crédito</th><th>Saldo</th></tr></thead>
                  <tbody>{data.trial_balance.map((r: any) => (
                    <tr key={r.account_code}><td>{r.account_code}<div className="muted">{r.name}</div></td><td>{r.nature}</td>
                      <td>{money(r.debit_cents)}</td><td>{money(r.credit_cents)}</td><td>{money(r.balance_cents)}</td></tr>
                  ))}</tbody></table>
              )}
              {data.balance_note && <p className="note-honesty">{data.balance_note}</p>}
            </Panel>
            {data.unbalanced_batches.length > 0 && (
              <Panel title={`Lotes que não fecham (${data.unbalanced_batches.length})`}>
                <p className="muted">Impedem o fechamento. Fechar um mês que não fecha é publicar um número errado com carimbo de definitivo.</p>
                <ul className="bullets">{data.unbalanced_batches.map((b: string) => <li key={b}><code>{b}</code></li>)}</ul>
              </Panel>
            )}
            {has("accounting.close") && data.status === "open" && (
              <Panel title="Fechar competência">
                <p className="muted">Irreversível. O lançamento de ajuste passa a ir para a competência seguinte.</p>
                <Button variant="danger" busy={busy} disabled={!data.totals.balanced || data.unbalanced_batches.length > 0}
                  onClick={() => run(() => api.post("/v1/contabilidade/close", { period: `${period}-01`, note: `Fechamento de ${period}` }), "Competência fechada").then(reload)}>
                  Fechar {period}
                </Button>
              </Panel>
            )}
            <Honesty note={data.note} />
          </div>
        )}
      </StateView>
    </>
  );
}

export function PlanoDeContas() {
  const { data, error, loading, reload } = useLoad<any>("/v1/contabilidade/chart");
  const NATUREZA: Record<string, string> = { asset: "Ativo", liability: "Passivo", equity: "Patrimônio líquido", revenue: "Receita", expense: "Despesa" };
  return (
    <>
      <PageHead title="Plano de contas" sub="Contas sintéticas agrupam; só as analíticas recebem lançamento." back={<Link to="/contabilidade">Contabilidade</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title={`Contas (${data.accounts.length})`}>
              <table className="table"><thead><tr><th>Código</th><th>Nome</th><th>Natureza</th><th>Tipo</th></tr></thead>
                <tbody>{data.accounts.map((a: any) => (
                  <tr key={a.code}><td style={{ paddingLeft: `${(a.code.split(".").length - 1) * 16}px` }}><code>{a.code}</code></td>
                    <td>{a.name}</td><td>{NATUREZA[a.nature] || a.nature}</td>
                    <td>{a.analytical ? <Pill tone="good">analítica</Pill> : <Pill tone="muted">sintética</Pill>}</td></tr>
                ))}</tbody></table>
            </Panel>
            <Panel title={`Centros de custo (${data.cost_centers.length})`}>
              <table className="table"><thead><tr><th>Código</th><th>Nome</th><th>Responsável</th></tr></thead>
                <tbody>{data.cost_centers.map((c: any) => <tr key={c.code}><td><code>{c.code}</code></td><td>{c.name}</td><td className="muted">{c.owner_role || "—"}</td></tr>)}</tbody></table>
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}

// -------------------------------------------------------------------------------------- TESOURARIA

export function Tesouraria() {
  const { data, error, loading, reload } = useLoad<any>("/v1/tesouraria/summary");
  return (
    <>
      <PageHead title="Tesouraria" sub="Caixa e patrimônio da plataforma." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel quiet>
              <div className="metrics">
                <div className="metric"><span className="metric-label">Disponível</span><strong className="metric-value">{money(data.available_cents)}</strong><span className="metric-why">conta 1.1.1</span></div>
                <div className="metric"><span className="metric-label">Aplicado</span><strong className="metric-value">{money(data.invested_cents)}</strong><span className="metric-why">conta 1.1.2</span></div>
                <div className="metric"><span className="metric-label">A receber</span><strong className="metric-value">{money(data.receivable_cents)}</strong><span className="metric-why">faturas abertas</span></div>
                <div className="metric"><span className="metric-label">A pagar</span><strong className="metric-value">{money(data.payable_cents)}</strong><span className="metric-why">despesas aprovadas ou agendadas</span></div>
                <div className="metric"><span className="metric-label">Posição líquida</span><strong className="metric-value">{money(data.net_position_cents)}</strong></div>
              </div>
            </Panel>
            <Panel title="De quem é este dinheiro">
              <p>{data.scope_note}</p>
              <ul className="bullets">
                <li>Não há carteira, saldo de cliente, repasse nem custódia nesta plataforma — nem tabela que os comportasse.</li>
                <li>Doação, patrocínio e pagamento de serviço acontecem FORA da plataforma, entre as partes; aqui ficam o registro, o contrato, a instrução e a evidência.</li>
                <li>A plataforma fatura o que é dela: a taxa de serviço contratada na operação financiada (3,5%), uso e contratos avulsos. Não existe assinatura.</li>
              </ul>
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}

// ----------------------------------------------------------------------------------- ADMINISTRATIVO

export function Orcamento() {
  const ano = new Date().getFullYear();
  const [year, setYear] = useState(String(ano));
  const { data, error, loading, reload } = useLoad<any>(`/v1/administrativo/orcamento?year=${year}`, [year]);
  return (
    <>
      <PageHead title="Orçamento" sub="Orçado contra realizado, por conta e centro de custo."
        actions={<Field label="Exercício"><Select value={year} onChange={setYear} options={[String(ano - 1), String(ano), String(ano + 1)].map((y) => [y, y] as [string, string])} /></Field>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            {!data.approved_budget ? (
              <Panel title={`Exercício ${data.year}`}>
                <p className="muted">{data.note}</p>
              </Panel>
            ) : (
              <>
                {data.alerts.length > 0 && (
                  <Panel title={`Linhas com 80% ou mais consumido (${data.alerts.length})`}>
                    <ul className="rows">{data.alerts.map((a: any, i: number) => (
                      <li key={i}><span>{a.account_name} · {a.cost_center} · mês {a.month}</span>
                        <span className="stack-row"><Pill tone={a.used_percent >= 100 ? "bad" : "warn"}>{Math.round(a.used_percent)}%</Pill></span></li>
                    ))}</ul>
                  </Panel>
                )}
                <Panel title={`Orçamento aprovado v${data.approved_budget.version}`}>
                  <table className="table">
                    <thead><tr><th>Mês</th><th>Conta</th><th>Centro</th><th>Orçado</th><th>Realizado</th><th>Desvio</th><th>%</th></tr></thead>
                    <tbody>{data.items.map((i: any, k: number) => (
                      <tr key={k}><td>{i.month}</td><td>{i.account_code}<div className="muted">{i.account_name}</div></td><td>{i.cost_center}</td>
                        <td>{money(i.budgeted_cents)}</td><td>{money(i.actual_cents)}</td>
                        <td className={Number(i.variance_cents) < 0 ? "neg" : ""}>{money(i.variance_cents)}</td>
                        <td>{i.used_percent === null ? "—" : `${Math.round(i.used_percent)}%`}</td></tr>
                    ))}</tbody>
                  </table>
                </Panel>
              </>
            )}
          </div>
        )}
      </StateView>
    </>
  );
}

// ---------------------------------------------------------------------------------------- OPERAÇÕES

const ESTADO: Record<string, [string, string]> = { ok: ["Em ordem", "good"], warn: ["Atenção", "warn"], fail: ["Falhando", "bad"], unknown: ["Sem registro", "muted"] };

export function Operacoes() {
  const { data, error, loading, reload } = useLoad<any>("/v1/operacoes/health");
  return (
    <>
      <PageHead title="Saúde do sistema" sub="Banco, migrações, tarefas, backup, cobrança e integrações, numa tela."
        actions={<Link to="/operacoes/alertas">Central de alertas</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title="Serviços">
              <ul className="rows">{data.services.map((s: any) => { const [t, tone] = ESTADO[s.state] || [s.state, "muted"]; return (
                <li key={s.name}><span><strong>{s.name}</strong><div className="muted">{s.detail}</div></span><Pill tone={tone}>{t}</Pill></li>
              ); })}</ul>
            </Panel>
            <Panel title={`Tarefas agendadas (${(data.jobs || []).length})`}>
              {(data.jobs || []).length === 0 ? <p className="muted">Nenhuma tarefa com execução registrada.</p> : (
                <table className="table"><thead><tr><th>Tarefa</th><th>Situação</th><th>Início</th><th>Fim</th></tr></thead>
                  <tbody>{data.jobs.map((j: any) => <tr key={j.job}><td>{j.job}</td><td><Pill status={j.status} /></td><td>{dateTime(j.started_at)}</td><td>{dateTime(j.finished_at)}</td></tr>)}</tbody></table>
              )}
            </Panel>
            <Panel title={`Execuções com duração e erro (${(data.ops_runs || []).length})`}>
              {(data.ops_runs || []).length === 0 ? <p className="muted">Nenhuma execução registrada.</p> : (
                <table className="table"><thead><tr><th>Tarefa</th><th>Situação</th><th>Duração</th><th>Erro</th><th>Fim</th></tr></thead>
                  <tbody>{data.ops_runs.map((r: any, i: number) => <tr key={i}><td>{r.job}</td><td><Pill status={r.status} /></td>
                    <td>{r.duration_ms === null ? "—" : `${r.duration_ms} ms`}</td><td className="muted">{r.error || "—"}</td><td>{dateTime(r.finished_at)}</td></tr>)}</tbody></table>
              )}
            </Panel>
            <Panel title={`Integrações (${(data.integrations || []).length})`}>
              <table className="table"><thead><tr><th>Chave</th><th>Nome</th><th>Categoria</th><th>Maturidade</th><th>Ativa</th></tr></thead>
                <tbody>{(data.integrations || []).map((i: any) => <tr key={i.key}><td><code>{i.key}</code></td><td>{i.name}</td><td>{i.category}</td>
                  <td><Pill tone={i.maturity === "production" ? "good" : i.maturity === "sandbox" ? "warn" : "muted"}>{i.maturity}</Pill></td>
                  <td>{i.active ? "sim" : "não"}</td></tr>)}</tbody></table>
            </Panel>
            <Honesty note={data.note} />
          </div>
        )}
      </StateView>
    </>
  );
}

const PRIORIDADE: Record<string, string> = { CRITICAL: "bad", HIGH: "bad", MEDIUM: "warn", LOW: "muted", INFO: "muted" };

export function Alertas() {
  const { data, error, loading, reload } = useLoad<any>("/v1/operacoes/alerts");
  return (
    <>
      <PageHead title="Central de alertas" sub="O que exige ação agora, por prioridade." back={<Link to="/operacoes">Saúde do sistema</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel quiet>
              <div className="metrics">{Object.entries(data.by_priority as Record<string, number>).map(([p, n]) => (
                <div key={p} className={`metric${n > 0 && (p === "CRITICAL" || p === "HIGH") ? " metric-alert" : ""}`}>
                  <span className="metric-label">{p}</span><strong className="metric-value">{n}</strong></div>
              ))}</div>
            </Panel>
            <Panel title={`Alertas (${data.items.length})`}>
              {data.items.length === 0 ? <p className="muted">Nada exigindo ação.</p> : (
                <ul className="rows">{data.items.map((a: any, i: number) => (
                  <li key={i}><span><strong>{a.message}</strong>
                    <div className="muted">{a.kind} · {a.object_type}{a.object_id ? ` · ${a.object_id}` : ""}{a.at ? ` · ${dateTime(a.at)}` : ""}</div></span>
                    <Pill tone={PRIORIDADE[a.priority] || "muted"}>{a.priority}</Pill></li>
                ))}</ul>
              )}
            </Panel>
            <Honesty note={data.note} />
          </div>
        )}
      </StateView>
    </>
  );
}

// ---------------------------------------------------------------------------------------- AUDITORIA

export function AcessoPrivilegiado() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/privileged-access");
  return (
    <>
      <PageHead title="Acesso privilegiado" sub="Quem entrou com papel interno, quando, em qual rota e com qual permissão. Responde “quem olhou”, não só “quem mudou”." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title="Últimos 30 dias por permissão">
              {(data.last_30_days || []).length === 0 ? <p className="muted">Nenhum acesso privilegiado nos últimos 30 dias.</p> : (
                <table className="table"><thead><tr><th>Permissão</th><th>Acessos</th><th>Pessoas</th></tr></thead>
                  <tbody>{data.last_30_days.map((r: any) => <tr key={r.permission}><td><code>{r.permission}</code></td><td>{r.acessos}</td><td>{r.pessoas}</td></tr>)}</tbody></table>
              )}
            </Panel>
            <Panel title={`Trilha (${(data.items || []).length} mais recentes)`}>
              {(data.items || []).length === 0 ? <p className="muted">Trilha vazia.</p> : (
                <table className="table"><thead><tr><th>Quando</th><th>Quem</th><th>Papéis</th><th>Permissão</th><th>Rota</th></tr></thead>
                  <tbody>{data.items.map((r: any) => <tr key={r.id}><td>{dateTime(r.at)}</td><td>{r.email || "—"}</td>
                    <td className="muted">{(r.roles_used || []).join(", ")}</td><td><code>{r.permission || "—"}</code></td>
                    <td className="muted">{r.method} {r.path}</td></tr>)}</tbody></table>
              )}
            </Panel>
            <p className="note-honesty">Esta trilha é append-only: o gatilho do banco recusa alteração e remoção, inclusive para o papel proprietário.</p>
          </div>
        )}
      </StateView>
    </>
  );
}

export function MatrizPermissoes() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/permissions");
  return (
    <>
      <PageHead title="Matriz de permissões" sub="Papel interno → permissão, como está no banco. Esta tela lê a fonte, não uma cópia." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title="Pessoas da equipe interna">
              <table className="table"><thead><tr><th>Pessoa</th><th>Papéis</th></tr></thead>
                <tbody>{(data.staff || []).map((s: any) => <tr key={s.email}><td>{s.email}</td><td>{(s.roles || []).join(", ")}</td></tr>)}</tbody></table>
            </Panel>
            {Object.entries(data.matrix as Record<string, any[]>).map(([papel, perms]) => (
              <Panel key={papel} title={`${papel} (${perms.length})`}>
                <table className="table"><thead><tr><th>Permissão</th><th>Por quê</th></tr></thead>
                  <tbody>{perms.map((p: any) => <tr key={p.permission}><td><code>{p.permission}</code></td><td className="muted">{p.note}</td></tr>)}</tbody></table>
              </Panel>
            ))}
            <Panel title="Permissões declaradas em rota">
              <p className="muted">{(data.declared_on_routes || []).length} permissões aparecem como exigência de alguma rota.</p>
              <p className="code-block">{(data.declared_on_routes || []).join("  ")}</p>
            </Panel>
            <p className="note-honesty">{data.super_admin_note}</p>
          </div>
        )}
      </StateView>
    </>
  );
}

export function Integracoes() {
  const { data, error, loading, reload } = useLoad<any>("/v1/operacoes/health");
  return (
    <>
      <PageHead title="Integrações" sub="Provedores declarados, com a maturidade real de cada um." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <Panel title={`Provedores (${(data.integrations || []).length})`}>
            <table className="table"><thead><tr><th>Chave</th><th>Nome</th><th>Categoria</th><th>Maturidade</th><th>Ativa</th></tr></thead>
              <tbody>{(data.integrations || []).map((i: any) => <tr key={i.key}><td><code>{i.key}</code></td><td>{i.name}</td><td>{i.category}</td>
                <td><Pill tone={i.maturity === "production" ? "good" : i.maturity === "sandbox" ? "warn" : "muted"}>{i.maturity}</Pill></td>
                <td>{i.active ? "sim" : "não"}</td></tr>)}</tbody></table>
            <p className="note-honesty">`scaffolded` significa contrato e adaptador escritos, sem provedor ligado. Nenhum provedor de pagamento está em produção.</p>
          </Panel>
        )}
      </StateView>
    </>
  );
}

// ----------------------------------------------------------------------------- PERÍODOS GRATUITOS

const ORIGEM: [string, string][] = [["PROMOTION", "Promoção (FULL FREE)"], ["GRANT", "Concessão"], ["PARTNERSHIP", "Parceria"], ["MANUAL_EXCEPTION", "Exceção manual"]];

export function PeriodosGratuitos() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/free-periods");
  const { has } = useAccess();
  const { busy, run } = useAction();
  const [f, setF] = useState({ org_id: "", source: "GRANT", months: "12", reason: "", plan_key: "" });
  const [motivos, setMotivos] = useState<Record<string, string>>({});
  return (
    <>
      <PageHead title="Períodos gratuitos" sub="Quem está sem pagar, por qual motivo, concedido por quem e até quando."
        back={<Link to="/financeiro">Financeiro</Link>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="stack-lg">
            <Panel title="Por origem e situação">
              {(data.summary || []).length === 0 ? <p className="muted">Nenhum período gratuito concedido.</p> : (
                <table className="table"><thead><tr><th>Origem</th><th>Situação</th><th>Total</th><th>Próximo fim</th></tr></thead>
                  <tbody>{data.summary.map((r: any, i: number) => <tr key={i}><td>{r.source}</td><td><Pill status={r.status} /></td>
                    <td>{r.total}</td><td>{date(r.proximo_fim)}</td></tr>)}</tbody></table>
              )}
            </Panel>
            {has("free_period.write") && (
              <Panel title="Conceder período gratuito">
                <p className="muted">O motivo é obrigatório: cortesia sem motivo registrado é indistinguível de erro de operação quando alguém for auditar.</p>
                <div className="form-grid">
                  <Field label="ID da organização"><Input value={f.org_id} onChange={(v) => setF({ ...f, org_id: v })} /></Field>
                  <Field label="Origem"><Select value={f.source} onChange={(v) => setF({ ...f, source: v })} options={ORIGEM} /></Field>
                  <Field label="Meses"><Input value={f.months} onChange={(v) => setF({ ...f, months: v })} inputMode="numeric" /></Field>
                  <Field label="Plano (opcional)"><Input value={f.plan_key} onChange={(v) => setF({ ...f, plan_key: v })} /></Field>
                  <Field label="Motivo" wide><Input value={f.reason} onChange={(v) => setF({ ...f, reason: v })} /></Field>
                </div>
                <Button variant="ink" busy={busy} disabled={!(f.org_id.length > 10 && f.reason.length > 2 && Number(f.months) >= 1)}
                  onClick={() => run(() => api.post("/v1/admin/free-periods", {
                    org_id: f.org_id, source: f.source, months: Number(f.months),
                    reason: f.reason, plan_key: f.plan_key || undefined,
                  }), "Período gratuito concedido").then(() => { setF({ ...f, org_id: "", reason: "" }); reload(); })}>
                  Conceder
                </Button>
              </Panel>
            )}
            <Panel title={`Concedidos (${(data.items || []).length})`}>
              {(data.items || []).length === 0 ? <p className="muted">Nenhum registro.</p> : (
                <table className="table">
                  <thead><tr><th>Organização</th><th>Origem</th><th>Meses</th><th>Início</th><th>Fim</th><th>Situação</th><th>Motivo</th>{has("free_period.write") && <th></th>}</tr></thead>
                  <tbody>{data.items.map((p: any) => (
                    <tr key={p.id}><td>{p.legal_name}</td><td>{p.source}</td><td>{p.months}</td><td>{date(p.started_at)}</td><td>{date(p.ends_at)}</td>
                      <td><Pill status={p.status} /></td><td className="muted">{p.reason}</td>
                      {has("free_period.write") && (
                        <td>{p.status === "active" && (
                          <span className="stack-row">
                            <Input value={motivos[p.id] || ""} onChange={(v) => setMotivos({ ...motivos, [p.id]: v })} placeholder="motivo do cancelamento" />
                            <Button variant="danger" busy={busy} disabled={(motivos[p.id] || "").length < 3}
                              onClick={() => run(() => api.post(`/v1/admin/free-periods/${p.id}/cancel`, { reason: motivos[p.id] }), "Período cancelado").then(reload)}>
                              Cancelar
                            </Button>
                          </span>
                        )}</td>
                      )}</tr>
                  ))}</tbody>
                </table>
              )}
              <p className="note-honesty">Cancelar não apaga: o registro permanece com motivo e autor, porque é ele que explica por que a organização parou de ser gratuita.</p>
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------------------------- TORRE MASTER (v0.27.0)
/** A visão do proprietário: GMV × camada da plataforma, sem saldo inventado. Banco "NÃO CONECTADO" é dito em letras. */
export function TorreMaster() {
  const { data, error, loading, reload } = useLoad<any>("/v1/control-tower/master");
  const d = data;
  const pct = (bps: number) => `${(bps / 100).toFixed(2).replace(".", ",")}%`;
  return (
    <>
      <PageHead title="Torre financeira (master)" sub="O que passa pelo ecossistema e o que fica com a plataforma, em blocos separados que nunca se somam. Nenhum número aqui é saldo: a plataforma não custodia." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {d && (
          <div className="stack-lg">
            <ul className="bullets">{d.honesty.map((h: string) => <li key={h}>{h}</li>)}</ul>
            <Panel title="Assinatura">
              <p><strong>Não existe.</strong> {d.subscription.note}</p>
            </Panel>
            <div className="split">
              <Panel title="GMV — o que passa pelo ecossistema (não é receita)">
                <KeyValue items={[
                  ["Acordos de financiamento vigentes", String(d.gmv.funding_agreements_active)],
                  ["Valor contratado (bruto)", money(d.gmv.gross_contracted_cents)],
                  ["Recursos de projeto instruídos", money(d.gmv.project_funds_instructed_cents)],
                  ["Recursos de projeto confirmados", money(d.gmv.project_funds_confirmed_cents)],
                  ["Operações quitadas", String(d.gmv.operations_settled)],
                  ["Aportes registrados / confirmados", `${money(d.gmv.commitments_registered_cents)} / ${money(d.gmv.commitments_confirmed_cents)}`],
                ]} />
                <Honesty note={d.gmv.warning} />
              </Panel>
              <Panel title={`Camada da plataforma — ${d.platform_layer.pricing.rules.find((r: any) => r.key === "funding.platform_service") ? pct(d.platform_layer.pricing.rules.find((r: any) => r.key === "funding.platform_service").bps) : "—"} (versão ${d.platform_layer.pricing.pricing_version})`}>
                <div className="metrics">
                  <Indicator title="Registrado" m={d.platform_layer.registered} />
                  <Indicator title="Devido" m={d.platform_layer.due} />
                  <Indicator title="Pago" m={d.platform_layer.paid} />
                  <div className="metric"><span className="metric-label">Operações</span><strong className="metric-value">{d.platform_layer.operations}</strong><span className="metric-why">acordos com camada registrada</span></div>
                </div>
                <p className="muted small">Regra comercial <code className="small">{d.platform_layer.rule.key}</code>: <Pill tone={d.platform_layer.rule.active ? "good" : "warn"}>{d.platform_layer.rule.active ? "ativa" : `inativa · ${d.platform_layer.rule.legal_status}`}</Pill> <Link to={d.links.rules}>abrir regras</Link></p>
                <Honesty note={d.platform_layer.note} />
                {d.platform_layer.by_month.length > 0 && (
                  <table className="table"><thead><tr><th>Mês</th><th>GMV confirmado</th><th>Registrado</th><th>Devido</th><th>Pago</th></tr></thead>
                    <tbody>{d.platform_layer.by_month.map((m: any) => <tr key={m.month}><td>{m.month}</td><td>{money(m.gmv_confirmed_cents)}</td><td>{money(m.registered_cents)}</td><td>{money(m.due_cents)}</td><td>{money(m.paid_cents)}</td></tr>)}</tbody></table>
                )}
              </Panel>
            </div>
            <div className="split">
              <Panel title="Participação de autoria — 1,5% (não é receita da plataforma)">
                <div className="metrics">
                  <Indicator title="Na matriz" m={d.participation.accrued} />
                  <Indicator title="Paga ao proponente" m={d.participation.paid} />
                </div>
                <ul className="rows">{d.participation.participations.map((p: any) => <li key={p.status}><span>{p.status}</span><strong>{p.n}</strong></li>)}</ul>
                <Honesty note={d.participation.note} />
              </Panel>
              <Panel title="Captura de valor">
                <KeyValue items={[
                  ["Eventos de valor registrados", String(d.value_capture.value_events)],
                  ["Organizações com eventos", String(d.value_capture.organizations_with_value_events)],
                  ["Value Capture Ratio", d.value_capture.value_capture_ratio == null ? d.value_capture.value_capture_ratio_status : `${(d.value_capture.value_capture_ratio * 100).toFixed(2)}%`],
                  ["Fórmula", d.value_capture.formula],
                ]} />
                <Honesty note={d.value_capture.note} />
              </Panel>
            </div>
            <div className="split">
              <Panel title="Marketplace — sem percentual">
                <KeyValue items={[["Anúncios", `${d.marketplace.listings} (${d.marketplace.listings_active} publicados)`], ["Comissão", `nenhuma · ${d.marketplace.take_rate.status || "—"}`], ["Receita", money(d.marketplace.revenue_cents)]]} />
                <Honesty note={d.marketplace.note} />
              </Panel>
              <Panel title="IA e API — uso medido, receita zero">
                <KeyValue items={[
                  ["Chamadas de IA (30 dias)", String(d.usage.ai_calls_30d)],
                  ["Custo estimado de IA (30 dias)", d.usage.ai_cost_cents_estimate_30d == null ? "sem tabela de preço" : money(Math.round(d.usage.ai_cost_cents_estimate_30d))],
                  ["Chamadas sem tabela de preço", String(d.usage.ai_calls_without_price_table)],
                  ["Credenciais de integração", String(d.usage.api_credentials)],
                  ["Webhooks ativos / entregas (30 dias)", `${d.usage.webhook_subscriptions_active} / ${d.usage.webhook_deliveries_30d}`],
                  ["Receita por uso", money(d.usage.revenue_cents)],
                ]} />
                <Honesty note={d.usage.note} />
              </Panel>
            </div>
            <div className="split">
              <Panel title="Contratos avulsos e parcelados (enterprise, governo)">
                <KeyValue items={[
                  ["Contratos com cobrança autorizada", `${d.contracts.authorized} · ${money(d.contracts.authorized_value_cents)}`],
                  ["Aceites de acesso gratuito", String(d.contracts.free_access_acceptances)],
                  ["Propostas em aberto", String(d.contracts.open_offers)],
                  ["Licenças vigentes", String(d.contracts.licenses_active)],
                ]} />
                <Honesty note={d.contracts.note} />
              </Panel>
              <Panel title="A receber — cobranças próprias">
                <KeyValue items={[
                  ["Cobranças abertas (reais / simuladas)", `${money(d.receivables.charges_open_real_cents)} / ${money(d.receivables.charges_open_simulated_cents)}`],
                  ["Cobranças pagas (reais / simuladas)", `${money(d.receivables.charges_paid_real_cents)} / ${money(d.receivables.charges_paid_simulated_cents)}`],
                  ["Faturas abertas", `${d.receivables.invoices_open} · ${money(d.receivables.invoices_open_cents)}`],
                  ["Linha da plataforma aguardando regra", `${d.receivables.platform_fee_instructions_awaiting_rule} · ${money(d.receivables.platform_fee_awaiting_rule_cents)}`],
                  ["Linha da plataforma instruída / confirmada", `${money(d.receivables.platform_fee_open_cents)} / ${money(d.receivables.platform_fee_confirmed_cents)}`],
                  ["Provedor de pagamento", d.receivables.payment_provider.configured ? d.receivables.payment_provider.provider : `${d.receivables.payment_provider.provider} (simulado)`],
                ]} />
                <Honesty note={d.receivables.note} />
              </Panel>
            </div>
            <Panel title="Banco">
              <p className="big-figure">{d.bank.status}</p>
              <Honesty note={d.bank.note} />
            </Panel>
            <Panel title="Regras de monetização">
              <ul className="rows">{d.rules.map((r: any) => <li key={r.key}><span>{r.label_pt}<br /><code className="small">{r.key}</code></span><span><Pill tone={r.active ? "good" : r.legal_status === "refused" ? "bad" : "warn"}>{r.active ? "ativa" : r.legal_status}</Pill></span></li>)}</ul>
              <p className="muted small">Simulação de 24 meses (hipóteses declaradas): <code className="small">{d.links.model}</code></p>
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}
