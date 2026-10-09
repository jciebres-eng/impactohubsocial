// Central de IA (v0.28.0, ADR-347/350): saldo por lote, cotas, operações com preço e quem paga, pedidos de crédito por PIX,
// patrocínio, análises de originalidade/similaridade e a tela de confirmação ANTES de qualquer operação cobrada.
// O frontend nunca decide preço, saldo ou fonte: pede a prévia ao backend, mostra, e só então confirma.
import { useState } from "react";
import { api } from "../api";
import { date, dateTime, money } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useLoad } from "../ui/kit";
import { GlossaryTerm, ContextualHelp } from "../ui/help";

const CAT: Record<string, string> = { A: "Assistência leve", B: "Assistência contextual", C: "Análise avançada", D: "Originalidade e similaridade", E: "Lote", F: "Institucional" };
const FUND: Record<string, string> = { free: "gratuita", promotional: "cota gratuita", purchased: "créditos comprados", sponsorship: "patrocínio", cached: "já calculado" };
const STATE: Record<string, [string, string]> = {
  created: ["criada", "muted"], authorized: ["autorizada", "muted"], reserved: ["reservada", "muted"], running: ["em execução", "muted"],
  succeeded: ["concluída", "ok"], reconciled: ["concluída e conciliada", "ok"], failed: ["falhou (não cobrada)", "danger"],
  partial: ["parcial (não cobrada)", "warn"], cancelled: ["cancelada (não cobrada)", "muted"],
};
const ORDER: Record<string, [string, string]> = {
  created: ["piloto: aguardando a administração", "muted"], awaiting_payment: ["aguardando pagamento", "warn"], paid: ["pago", "ok"],
  credited: ["creditado", "ok"], expired: ["expirado", "muted"], cancelled: ["cancelado", "muted"], failed: ["falhou", "danger"],
};

function credits(n: number) { return `${n} crédito${n === 1 ? "" : "s"}`; }

// ------------------------------------------------------------------------------------------------ confirmação antes de executar
/** Botão que pede a PRÉVIA, mostra o que será feito, o custo, quem paga e o saldo, e só executa com a confirmação. */
export function OperationLauncher({ code, label, variant = "ink", units = 1, inputChars = 0, projectId, onConfirm, small }: {
  code: string; label: string; variant?: "primary" | "ink" | "ghost"; units?: number; inputChars?: number; projectId?: string;
  onConfirm: () => Promise<any>; small?: boolean;
}) {
  const [pv, setPv] = useState<any | null>(null);
  const [open, setOpen] = useState(false);
  const { run, busy } = useAction();
  async function abrir() {
    const r = await run(() => api.post("/v1/ai/preview", { operation_code: code, units, input_chars: inputChars, project_id: projectId || undefined }));
    if (r) { setPv(r); setOpen(true); }
  }
  const op = pv?.operation;
  return (
    <>
      <Button variant={variant} busy={busy} onClick={abrir} {...(small ? { className: "btn-sm" } : {})}>{label}</Button>
      <Modal open={open} title={op ? op.name : "Confirmar operação"} onClose={() => setOpen(false)}
        footer={pv?.allowed
          ? <><Button variant="ghost" onClick={() => setOpen(false)}>Cancelar</Button>
            <Button variant="primary" busy={busy} onClick={() => run(onConfirm).then(() => setOpen(false))}>Confirmar e executar</Button></>
          : <><Button variant="ghost" onClick={() => setOpen(false)}>Fechar</Button>
            <Button variant="ink" onClick={() => navigate("/ia")}>Ver créditos e patrocínios</Button></>}>
        {pv && (
          <div className="stack-lg">
            <p className="lead">{op.delivers}</p>
            <KeyValue items={[
              ["O que será feito", `${op.name} · ${CAT[op.category]} · faixa ${op.tier}`],
              ["Escopo", `${pv.units} ${pv.unit_label}${pv.units === 1 ? "" : "s"}${inputChars ? ` · ${inputChars.toLocaleString("pt-BR")} caracteres` : ""}`],
              ["Custo", pv.credits_required === 0 ? "sem custo" : `${credits(pv.credits_required)}${op.price_is_hypothesis ? " (preço de teste — hipótese)" : ""}`],
              ["Custo externo estimado", pv.cost_status === "local_no_cost" ? "nenhum: motor local, nada sai da instalação" : pv.cost_status === "no_price_table" ? "não disponível (sem preço vigente do provedor)" : money(Math.round(pv.estimated_cost_cents || 0))],
              ["Quem paga", pv.allowed ? pv.funding_label : "— nenhuma fonte disponível"],
              ["Saldo", `cota ${pv.balances.promotional.available} · comprados ${pv.balances.purchased.available}`],
              ["Critério de conclusão", op.completion_rule],
              ["Se falhar", "nada é cobrado"],
            ]} />
            {pv.message && <p className={pv.allowed ? "note" : "note warn"}>{pv.message}</p>}
            {!pv.allowed && pv.options && <ul className="rows">{pv.options.map((o: any) => <li key={o.kind}><span>{o.label}</span>{o.link && <Link to={o.link} className="btn btn-ghost btn-sm">Abrir</Link>}</li>)}</ul>}
            <p className="fineprint">O resultado não comprova plágio ou fraude; traz indícios por dimensão e exige revisão humana. Pagar não altera resultado, match, reputação nem elegibilidade.</p>
          </div>
        )}
      </Modal>
    </>
  );
}

// ------------------------------------------------------------------------------------------------ painel no projeto
export function SimilarityPanel({ projectId, isOwner }: { projectId: string; isOwner: boolean }) {
  const { me } = useSession();
  const kind = me?.active_org?.kind || "";
  const [outro, setOutro] = useState("");
  const list = useLoad<any>("/v1/similarity/analyses?limit=5", [projectId]);
  const mine = (list.data?.items || []).filter((a: any) => a.subject_project_id === projectId);
  async function analisar(kindOp: string, compared: string[] = []) {
    const r = await api.post(`/v1/projects/${projectId}/similarity`, { kind: kindOp, compared_project_ids: compared });
    navigate(`/ia/analises/${r.id}`);
    return r;
  }
  return (
    <Panel title={<><GlossaryTerm id="originalidade">Originalidade</GlossaryTerm>, <GlossaryTerm id="similaridade">similaridade</GlossaryTerm> e <GlossaryTerm id="complementaridade">complementaridade</GlossaryTerm></>}>
      <p className="muted small">Oito dimensões separadas (texto, escopo, público, território, período, orçamento, financiamento, indicadores). Similaridade textual ≠ escopo ≠ território ≠ duplicidade financeira ≠ plágio ≠ fraude. Nada aqui bloqueia financiamento, altera reputação ou posição no match.</p>
      <div className="stack-row wrap">
        <OperationLauncher code="similarity.single" label="O que este projeto traz de novo" variant="primary" projectId={projectId} onConfirm={() => analisar("single")} />
        <OperationLauncher code="similarity.complementarity" label="Com quem posso colaborar" projectId={projectId} onConfirm={() => analisar("complementarity")} />
      </div>
      <div className="stack-row wrap">
        <Input aria-label="Identificador do outro projeto" placeholder="Identificador do outro projeto (visível a você)" value={outro} onChange={setOutro} />
        <OperationLauncher code="similarity.pair" label="Comparar com este projeto" projectId={projectId} onConfirm={() => analisar("pair", [outro.trim()])} />
        {["company", "government"].includes(kind) && (
          <OperationLauncher code="similarity.expense_overlap" label="Sobreposição de despesas" variant="ghost" projectId={projectId} onConfirm={() => analisar("expense_overlap", [outro.trim()])} />
        )}
      </div>
      {mine.length > 0 && (
        <ul className="rows">{mine.map((a: any) => (
          <li key={a.id}><span>{KIND_LABEL[a.kind] || a.kind} · confiança {CONF[a.confidence] || a.confidence} · {dateTime(a.created_at)}</span>
            <Link to={`/ia/analises/${a.id}`} className="btn btn-ghost btn-sm">Abrir</Link></li>
        ))}</ul>
      )}
      {!isOwner && <p className="fineprint">Você só compara projetos que enxerga: os seus e os publicados. Rascunhos de outras organizações entram apenas como contagem agregada.</p>}
    </Panel>
  );
}

const KIND_LABEL: Record<string, string> = { single: "Originalidade", pair: "Comparação de dois projetos", set: "Comparação com conjunto", complementarity: "Complementaridade", expense_overlap: "Sobreposição de despesas" };
const CONF: Record<string, string> = { low: "baixa", medium: "média", high: "alta" };
const LEVEL: Record<string, [string, string]> = { low: ["baixa", "ok"], medium: ["média", "warn"], high: ["alta", "danger"] };
const DIM_LABEL: Record<string, string> = { text: "Texto", scope: "Escopo", audience: "Público", territory: "Território", time: "Período", budget: "Orçamento", funding: "Financiamento", indicators: "Indicadores" };
const QUALITY: Record<string, string> = { good: "dado bom", fair: "dado parcial", poor: "dado insuficiente" };

function Dimensions({ cmp }: { cmp: any }) {
  const r = cmp.readings;
  return (
    <div className="stack-lg">
      <div className="stack-row wrap">
        <Pill tone={LEVEL[r.textual_similarity][1]}>texto: {LEVEL[r.textual_similarity][0]}</Pill>
        <Pill tone={LEVEL[r.scope_similarity][1]}>escopo: {LEVEL[r.scope_similarity][0]}</Pill>
        <Pill tone={LEVEL[r.territorial_overlap][1]}>território: {LEVEL[r.territorial_overlap][0]}</Pill>
        <Pill tone={LEVEL[r.temporal_overlap][1]}>período: {LEVEL[r.temporal_overlap][0]}</Pill>
        {r.possible_textual_reproduction && <Pill tone="danger">indício de reprodução textual — revisão humana</Pill>}
        {r.possible_expense_duplication && <Pill tone="danger">indício de sobreposição de despesa — revisão humana</Pill>}
        {r.complementarity && <Pill tone="ok">complementaridade possível</Pill>}
        {r.same_funding_source && <Pill tone="muted">fonte de financiamento em comum</Pill>}
      </div>
      <table className="table">
        <thead><tr><th>Dimensão</th><th>Score</th><th>Fatores</th><th>Dado</th></tr></thead>
        <tbody>{Object.entries(cmp.dimensions).map(([k, d]: any) => (
          <tr key={k}>
            <td>{DIM_LABEL[k] || k}</td>
            <td>{d.score === null || d.score === undefined ? "—" : <><span className="bar" style={{ width: `${Math.round(d.score * 100)}px` }} aria-hidden="true" /> {Math.round(d.score * 100)}%</>}</td>
            <td><ul className="plain small">{d.factors.map((f: string, i: number) => <li key={i}>{f}</li>)}{d.limitation && <li className="muted">{d.limitation}</li>}</ul></td>
            <td className="small muted">{QUALITY[d.data_quality] || d.data_quality}</td>
          </tr>
        ))}</tbody>
      </table>
      <Panel title="O que fazer" quiet>
        <ul className="rows">{cmp.recommendations.map((x: any) => <li key={x.action}><span><strong>{x.label}</strong><br /><span className="muted small">{x.why}</span></span></li>)}</ul>
      </Panel>
      {cmp.limitations?.length > 0 && <p className="muted small">Limitações: {cmp.limitations.join("; ")}.</p>}
      <p className="fineprint">{cmp.disclaimer}</p>
    </div>
  );
}

export function SimilarityAnalysis({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/similarity/analyses/${id}`, [id]);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const { run, busy } = useAction();
  const res = data?.result;
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <PageHead title={KIND_LABEL[data.kind] || data.kind} back={<Link to={`/projetos/${data.subject_project_id}`} className="back">Projeto</Link>}
            sub={<>confiança {CONF[data.confidence]} · {data.engine_version} · {dateTime(data.created_at)} · {data.cached ? "resultado já calculado" : "calculado agora"}{data.execution?.funding_source ? ` · pago por: ${FUND[data.execution.funding_source] || data.execution.funding_source}` : ""}</>}
            actions={<Button variant="ghost" onClick={() => setOpen(true)}>Contestar ou corrigir</Button>} />
          <Panel title="Leia antes" quiet>
            <p className="note">{res.disclaimer}</p>
            {res.hidden_overlap_count > 0 && <p className="note warn">{res.hidden_overlap_note}</p>}
          </Panel>
          {data.kind === "single" && (
            <>
              <Panel title="O que este projeto traz de novo">
                <p className="lead">{res.originality_note?.[res.originality_reading]}</p>
                {res.novel_terms?.length > 0 && <p className="small">Termos do seu escopo que os projetos próximos não usam: {res.novel_terms.join(", ")}.</p>}
                <p className="muted small">{res.candidates_compared} projeto(s) visível(is) comparado(s); {res.shown?.length || 0} mostrado(s).</p>
              </Panel>
              {res.shown?.map((p: any) => (
                <Panel key={p.project_id} title={<><Link to={`/projetos/${p.project_id}`}>{p.title}</Link> <span className="muted small">· {p.org_name}</span></>}>
                  <Dimensions cmp={p.comparison} />
                </Panel>
              ))}
            </>
          )}
          {data.kind === "complementarity" && (
            <Panel title="Com quem colaborar">
              <p className="muted small">{res.note}</p>
              {(res.complementarity || []).length === 0 && <p className="muted">Nenhum projeto visível com causa em comum e território ou abordagem diferentes.</p>}
              {(res.complementarity || []).map((p: any) => (
                <Panel key={p.project_id} title={<><Link to={`/projetos/${p.project_id}`}>{p.title}</Link> <span className="muted small">· {p.org_name}</span></>} quiet>
                  <Dimensions cmp={p.comparison} />
                </Panel>
              ))}
            </Panel>
          )}
          {(data.kind === "pair" || data.kind === "expense_overlap") && (
            <>
              {res.expense_overlap && (
                <Panel title="Integridade do financiamento" actions={<Pill tone={res.expense_overlap.possible_duplication ? "danger" : "ok"}>{res.expense_overlap.possible_duplication ? "indício — revisão humana" : "sem indício"}</Pill>}>
                  <p className="lead">{res.expense_overlap.statement}</p>
                  {res.expense_overlap.shared_items?.length > 0 && <p className="small">Itens iguais: {res.expense_overlap.shared_items.join("; ")}.</p>}
                </Panel>
              )}
              <Panel title={<><Link to={`/projetos/${res.pair.project_id}`}>{res.pair.title}</Link> <span className="muted small">· {res.pair.org_name}</span></>}>
                <Dimensions cmp={res.comparison} />
              </Panel>
            </>
          )}
          {data.kind === "set" && res.set?.map((p: any) => (
            <Panel key={p.project_id} title={<><Link to={`/projetos/${p.project_id}`}>{p.title}</Link> <span className="muted small">· {p.org_name}</span></>}>
              <Dimensions cmp={p.comparison} />
            </Panel>
          ))}
          {data.disputes?.length > 0 && (
            <Panel title="Contestações">
              <ul className="rows">{data.disputes.map((d: any) => <li key={d.id}><span>{d.reason}<br /><span className="muted small">{d.reviewer_note || "aguardando revisão humana"}</span></span><Pill tone={d.status === "open" ? "warn" : "ok"}>{DISPUTE[d.status] || d.status}</Pill></li>)}</ul>
            </Panel>
          )}
          <Modal open={open} title="Contestar ou corrigir" onClose={() => setOpen(false)}
            footer={<Button variant="primary" busy={busy} disabled={reason.trim().length < 20} onClick={() => run(() => api.post(`/v1/similarity/analyses/${id}/dispute`, { reason }), "Contestação registrada; vai para revisão humana").then(() => { setOpen(false); setReason(""); reload(); })}>Enviar</Button>}>
            <Field label="O que está errado ou incompleto (mínimo 20 caracteres)"><TextArea rows={4} value={reason} onChange={setReason} /></Field>
            <p className="fineprint">A análise não produz efeito algum em financiamento, reputação ou match — contestar serve para corrigir o registro e orientar a revisão humana.</p>
          </Modal>
        </>
      )}
    </StateView>
  );
}
const DISPUTE: Record<string, string> = { open: "aberta", reviewed_upheld: "revisada: mantida", reviewed_corrected: "revisada: corrigida", withdrawn: "retirada" };

// ------------------------------------------------------------------------------------------------ central
export function AiCenter() {
  const { me } = useSession();
  const kind = me?.active_org?.kind || "";
  const role = me?.active_org?.role || "";
  const c = useLoad<any>("/v1/ai/center");
  const { run, busy } = useAction();
  const [orderOpen, setOrderOpen] = useState(false);
  const [pack, setPack] = useState("");
  const [terms, setTerms] = useState(false);
  const d = c.data;
  const canBuy = ["admin", "owner"].includes(role);
  return (
    <>
      <PageHead title="Central de IA" sub="Cada operação mostra o custo e quem paga antes de executar. Cadastro, projeto e seus dados nunca dependem de crédito." />
      <StateView loading={c.loading} error={c.error} onRetry={c.reload}>
        {d && (
          <>
            {d.quotas_granted_now?.length > 0 && <p className="note">Cota concedida agora: {d.quotas_granted_now.map((g: any) => `${g.policy} (+${g.credits})`).join(", ")}.</p>}
            <div className="metrics">
              <div className="metric"><span className="metric-label">Cota gratuita disponível <ContextualHelp id="creditos_de_ia" /></span><p className="metric-value">{d.balances.promotional.available}</p><p className="small">de {d.balances.promotional.balance} ({d.balances.promotional.reserved} reservados)</p></div>
              <div className="metric"><span className="metric-label">Créditos comprados</span><p className="metric-value">{d.balances.purchased.available}</p><p className="small">de {d.balances.purchased.balance} ({d.balances.purchased.reserved} reservados)</p></div>
              <div className="metric"><span className="metric-label">Patrocínios disponíveis</span><p className="metric-value">{d.sponsorships.length}</p><p className="small">{d.sponsorships.reduce((s: number, x: any) => s + (x.budget_credits - x.used), 0)} créditos restantes no total</p></div>
              <div className="metric"><span className="metric-label">Este mês</span><p className="metric-value">{d.this_month.executions}</p><p className="small">{d.this_month.credits} créditos · {d.this_month.sponsored} patrocinada(s) · {d.this_month.failed_or_partial} não cobrada(s)</p></div>
            </div>

            <Panel title="Operações disponíveis" actions={d.sale.mode === "pilot" ? <Pill tone="warn">fase piloto: preços são hipóteses de teste</Pill> : <Pill tone="ok">preços vigentes</Pill>}>
              <table className="table">
                <thead><tr><th>Operação</th><th>Categoria</th><th>Custo</th><th>Cota gratuita</th><th>Patrocinável</th><th>Situação</th></tr></thead>
                <tbody>{d.operations.map((o: any) => (
                  <tr key={o.code} className={o.available_to_me ? "" : "muted"}>
                    <td><strong>{o.name_pt}</strong><br /><span className="small muted">{o.delivers_pt}</span></td>
                    <td>{CAT[o.category]} <span className="small muted">· faixa {o.tier}{o.provider_mode === "local" ? " · local" : ""}</span></td>
                    <td>{o.credits_base === 0 && o.credits_per_unit === 0 ? "sem custo" : `${o.credits_base}${o.credits_per_unit ? ` + ${o.credits_per_unit}/${o.unit_label_pt}` : ""} créditos`}{o.price_is_hypothesis && <span className="small muted"> (teste)</span>}</td>
                    <td>{o.free_quota_eligible ? "sim" : "não"}</td>
                    <td>{o.sponsor_eligible ? "sim" : "não"}</td>
                    <td>{o.status === "planned" ? <Pill tone="muted">planejada — não implementada</Pill> : o.available_to_me ? <Pill tone="ok">disponível</Pill> : <Pill tone="muted">não para {kind}</Pill>}</td>
                  </tr>
                ))}</tbody>
              </table>
              <p className="fineprint">A análise de originalidade e as comparações ficam na ficha de cada projeto. Resumo, estruturação e rascunhos ficam onde sempre estiveram (projetos e documentos).</p>
            </Panel>

            <Panel title="Comprar créditos" actions={canBuy && d.packs.length > 0 && <Button variant="primary" onClick={() => { setPack(d.packs[0].code); setOrderOpen(true); }}>Fazer pedido</Button>}>
              {d.sale.mode === "pilot" && <p className="note warn">Fase piloto: a venda de créditos ainda não está liberada ({d.sale.why_pilot}). Um pedido registra o interesse sem pagamento; a administração pode aprová-lo como concessão de teste.</p>}
              <ul className="rows">{d.packs.map((p: any) => <li key={p.code}><span><strong>{p.name_pt}</strong> · {money(p.price_cents)} · validade {p.validity_days} dias<br /><span className="small muted">{p.note}</span></span><Pill tone={p.status === "active" ? "ok" : "warn"}>{p.status === "active" ? "vigente" : "hipótese"}</Pill></li>)}</ul>
              {d.orders.length > 0 && <ul className="rows">{d.orders.map((o: any) => <li key={o.id}><span>{o.credits} créditos · {money(o.amount_cents)} · {o.mode === "pilot" ? "piloto" : "real"} · {dateTime(o.created_at)}</span><Pill tone={ORDER[o.state]?.[1] || "muted"}>{ORDER[o.state]?.[0] || o.state}</Pill>{["created", "awaiting_payment"].includes(o.state) && canBuy && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/ai/credit-orders/${o.id}/cancel`), "Pedido cancelado").then(c.reload)}>Cancelar</Button>}</li>)}</ul>}
              <p className="fineprint">{d.terms}</p>
            </Panel>

            <Panel title={<>Patrocínio de uso <ContextualHelp id="creditos_de_ia" /></>}>
              {d.sponsorships.length === 0 && d.my_sponsorships.length === 0 && <p className="muted">Nenhum patrocínio ativo para a sua organização.</p>}
              {d.sponsorships.length > 0 && <ul className="rows">{d.sponsorships.map((s: any) => <li key={s.id}><span><strong>{s.name_pt}</strong> · {s.sponsor_name}<br /><span className="small muted">{s.budget_credits - s.used} de {s.budget_credits} créditos restantes · até {date(s.ends_on)} · {s.operations?.includes("*") ? "todas as operações patrocináveis" : s.operations?.join(", ")}</span></span><Pill tone="ok">disponível para você</Pill></li>)}</ul>}
              {d.my_sponsorships.length > 0 && <ul className="rows">{d.my_sponsorships.map((s: any) => <li key={s.id}><span><strong>{s.name_pt}</strong> (meu patrocínio)<br /><span className="small muted">{s.used} de {s.budget_credits} usados · até {date(s.ends_on)}</span></span><Link to={`/ia/patrocinios/${s.id}`} className="btn btn-ghost btn-sm">Prestação de contas</Link></li>)}</ul>}
              {["company", "government", "osc"].includes(kind) && canBuy && <SponsorshipForm onDone={c.reload} />}
            </Panel>

            <Panel title="Histórico de execuções">
              {d.recent_executions.length === 0 && <p className="muted">Nenhuma execução ainda.</p>}
              <ul className="rows">{d.recent_executions.map((e: any) => (
                <li key={e.id}><span>{e.operation_code} · {CAT[e.category]} · {dateTime(e.created_at)}<br /><span className="small muted">{credits(e.charged_credits)} cobrados de {e.estimated_credits} estimados · pago por: {FUND[e.funding_source] || e.funding_source} · custo externo: {e.cost_status === "local_no_cost" ? "nenhum (local)" : e.cost_status === "measured" ? money(Math.round(e.actual_cost_cents || 0)) : e.cost_status}</span></span>
                  <span className="row-actions"><Pill tone={STATE[e.state]?.[1] || "muted"}>{STATE[e.state]?.[0] || e.state}</Pill>{e.result_type === "similarity_analysis" && e.result_id && <Link to={`/ia/analises/${e.result_id}`} className="btn btn-ghost btn-sm">Abrir</Link>}</span></li>
              ))}</ul>
            </Panel>

            <Panel title="Extrato de créditos">
              <ul className="rows">{d.ledger.map((l: any) => <li key={l.id}><span>{l.note || l.reason} · {l.bucket === "purchased" ? "comprado" : "promocional"}{l.expires_at ? ` · válido até ${date(l.expires_at)}` : ""}<br /><span className="small muted">{dateTime(l.created_at)}</span></span><strong className={l.delta > 0 ? "ok" : ""}>{l.delta > 0 ? "+" : ""}{l.delta}</strong></li>)}</ul>
              <p className="fineprint">Saldo é a soma do extrato; nunca uma coluna que alguém edita. Reservas de execuções em andamento são descontadas do disponível e só viram consumo quando a operação conclui.</p>
            </Panel>

            <Panel title="Regras de uso" quiet>
              <ul className="plain">{d.rules.map((r: string, i: number) => <li key={i}>{r}</li>)}</ul>
              <p className="small"><Link to="/ia/orcamento">Orçamento em dinheiro, política de risco e uso do provedor externo</Link></p>
            </Panel>

            <Modal open={orderOpen} title="Pedido de créditos" onClose={() => setOrderOpen(false)}
              footer={<Button variant="primary" busy={busy} disabled={!terms || !pack} onClick={() => run(() => api.post("/v1/ai/credit-orders", { pack_code: pack, accept_terms: terms }), d.sale.mode === "pilot" ? "Pedido registrado em modo piloto (sem pagamento)" : "Pedido criado; aguardando confirmação do pagamento").then(() => { setOrderOpen(false); setTerms(false); c.reload(); })}>Confirmar pedido</Button>}>
              <Field label="Pacote"><Select aria-label="Pacote" value={pack} onChange={setPack} options={d.packs.map((p: any) => [p.code, `${p.name_pt} — ${money(p.price_cents)}`])} /></Field>
              <p className="small">{d.sale.mode === "pilot" ? "Nenhum pagamento é devido nesta fase. Seus créditos só aparecem se a administração aprovar o pedido como concessão de teste." : "Após confirmar, você recebe a instrução de PIX. Os créditos são liberados quando o pagamento é confirmado pelo provedor — a página de retorno não confirma nada."}</p>
              <label className="check"><input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} /> Li e aceito os termos de crédito</label>
              <p className="fineprint">{d.terms}</p>
            </Modal>
          </>
        )}
      </StateView>
    </>
  );
}

function SponsorshipForm({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", budget_credits: "", ends_on: "", eligible_kinds: "osc", eligible_uf: "", operations: "*", per_org_limit: "", accountability: "" });
  const { run, busy } = useAction();
  const set = (k: string) => (v: string) => setF({ ...f, [k]: v });
  return (
    <>
      <Button variant="ink" onClick={() => setOpen(true)}>Patrocinar uso de IA</Button>
      <Modal open={open} title="Novo patrocínio" onClose={() => setOpen(false)}
        footer={<Button variant="primary" busy={busy} disabled={!f.name || !f.budget_credits || !f.ends_on || f.accountability.length < 10}
          onClick={() => run(() => api.post("/v1/ai/sponsorships", {
            name: f.name, budget_credits: parseInt(f.budget_credits, 10), ends_on: f.ends_on, eligible_kinds: [f.eligible_kinds],
            eligible_uf: f.eligible_uf || null, operations: f.operations === "*" ? ["*"] : f.operations.split(",").map((s) => s.trim()).filter(Boolean),
            per_org_limit: f.per_org_limit ? parseInt(f.per_org_limit, 10) : null, accountability: f.accountability,
          }), "Patrocínio criado: créditos comprometidos do seu saldo").then(() => { setOpen(false); onDone(); })}>Criar patrocínio</Button>}>
        <p className="small">O patrocínio compromete créditos do SEU saldo agora. Organizações elegíveis usam as operações sem pagar; você vê a prestação de contas agregada (operações e créditos), nunca o conteúdo dos projetos. Esgotado, o patrocínio para — o beneficiário nunca é cobrado em silêncio.</p>
        <Field label="Nome"><Input value={f.name} onChange={set("name")} /></Field>
        <Field label="Orçamento (créditos)"><Input type="number" value={f.budget_credits} onChange={set("budget_credits")} /></Field>
        <Field label="Válido até"><Input type="date" value={f.ends_on} onChange={set("ends_on")} /></Field>
        <Field label="Tipo de organização elegível"><Select aria-label="Tipo elegível" value={f.eligible_kinds} onChange={set("eligible_kinds")} options={[["osc", "OSC"], ["individual", "Apoiador"], ["provider", "Profissional"]]} /></Field>
        <Field label="UF (opcional)"><Input value={f.eligible_uf} onChange={set("eligible_uf")} placeholder="MT" /></Field>
        <Field label="Operações (códigos separados por vírgula, ou * para todas)"><Input value={f.operations} onChange={set("operations")} /></Field>
        <Field label="Limite por organização (créditos, opcional)"><Input type="number" value={f.per_org_limit} onChange={set("per_org_limit")} /></Field>
        <Field label="Prestação de contas (o que você espera receber)"><TextArea rows={3} value={f.accountability} onChange={set("accountability")} /></Field>
      </Modal>
    </>
  );
}

export function SponsorshipReport({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/ai/sponsorships/${id}`, [id]);
  const { run, busy } = useAction();
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <PageHead title={data.name_pt} back={<Link to="/ia" className="back">Central de IA</Link>} sub={<>{data.used} de {data.budget_credits} créditos usados · {data.remaining} restantes · {date(data.starts_on)} a {date(data.ends_on)} · <Pill tone={data.status === "active" ? "ok" : "muted"}>{data.status}</Pill></>}
            actions={data.status !== "closed" && <Button variant="ghost" busy={busy} onClick={() => run(() => api.post(`/v1/ai/sponsorships/${id}/close`), "Patrocínio encerrado; crédito não usado devolvido").then(reload)}>Encerrar e devolver o não usado</Button>} />
          <Panel title="Por operação"><ul className="rows">{data.by_operation.map((o: any) => <li key={o.operation_code}><span>{o.operation_code}</span><span className="muted">{o.executions} execução(ões) · {o.credits} créditos · {o.not_charged} não cobrada(s)</span></li>)}</ul>{data.by_operation.length === 0 && <p className="muted">Nenhuma operação custeada ainda.</p>}</Panel>
          <Panel title="Por organização beneficiada"><ul className="rows">{data.by_organization.map((o: any) => <li key={o.org_name}><span>{o.org_name}</span><span className="muted">{o.executions} execução(ões) · {o.credits} créditos</span></li>)}</ul></Panel>
          <Panel title="Regras do patrocínio" quiet><KeyValue items={[["Tipos elegíveis", data.eligible_kinds.join(", ")], ["UF", data.eligible_uf || "qualquer"], ["Operações", data.operations.join(", ")], ["Limite por organização", data.per_org_limit ?? "sem limite"], ["Limite por projeto", data.per_project_limit ?? "sem limite"], ["Prestação de contas", data.accountability_pt]]} /><p className="fineprint">{data.note}</p></Panel>
        </>
      )}
    </StateView>
  );
}

// ------------------------------------------------------------------------------------------------ administração
export function AdminAiFinance() {
  const fin = useLoad<any>("/v1/admin/ai/finance");
  const orders = useLoad<any>("/v1/admin/ai/credit-orders");
  const disputes = useLoad<any>("/v1/admin/ai/disputes");
  const { run, busy } = useAction();
  const [ref, setRef] = useState("");
  const [note, setNote] = useState("");
  const [sel, setSel] = useState<any | null>(null);
  const [rev, setRev] = useState<any | null>(null);
  const [revNote, setRevNote] = useState("");
  const d = fin.data;
  const reloadAll = () => { fin.reload(); orders.reload(); disputes.reload(); };
  return (
    <>
      <PageHead title="IA: custos, créditos e sustentabilidade" sub="Só números medidos. Onde não há medição, o campo diz NÃO MEDIDO." />
      <StateView loading={fin.loading} error={fin.error} onRetry={fin.reload}>
        {d && (
          <>
            {d.alerts.length > 0 && <Panel title="Alertas" quiet><ul className="plain">{d.alerts.map((a: string, i: number) => <li key={i} className="warn">{a}</li>)}</ul></Panel>}
            <div className="metrics">
              <div className="metric"><span className="metric-label">Venda de créditos</span><p className="metric-value">{d.sale.mode === "pilot" ? "piloto" : "real"}</p><p className="small">{d.sale.why_pilot || "regra ativa e provedor real"}</p></div>
              <div className="metric"><span className="metric-label">Recebido (pedidos reais)</span><p className="metric-value">{money(d.revenue.received_cents)}</p><p className="small">reconhecido: {d.revenue.recognized_cents === null ? "NÃO MEDIDO" : money(Math.round(d.revenue.recognized_cents))}</p></div>
              <div className="metric"><span className="metric-label">Custo externo medido</span><p className="metric-value">{money(Math.round(d.costs.external_measured_cents))}</p><p className="small">infra, tarifa, imposto: NÃO MEDIDOS</p></div>
              <div className="metric"><span className="metric-label">Margem de contribuição</span><p className="metric-value">{d.contribution_margin.cents === null ? "—" : money(Math.round(d.contribution_margin.cents))}</p><p className="small">{d.contribution_margin.status}</p></div>
            </div>
            <Panel title="Créditos">
              <KeyValue items={[["Vendidos", d.credits.sold], ["Concedidos (gratuidade)", d.credits.granted], ["Consumidos (comprados)", d.credits.consumed_purchased], ["Consumidos (promocionais)", d.credits.consumed_promotional], ["Comprometidos em patrocínios", d.credits.committed_to_sponsorships], ["Comprados não consumidos (obrigação)", d.credits.outstanding_purchased], ["Promocionais não consumidos (custo futuro)", d.credits.outstanding_promotional]]} />
              <p className="fineprint">{d.revenue.note}</p>
            </Panel>
            <Panel title="Por operação">
              <table className="table"><thead><tr><th>Operação</th><th>Execuções</th><th>Concluídas</th><th>Falha/parcial/cancel.</th><th>Créditos</th><th>Gratuitas · patroc. · compradas · cache</th><th>Custo medido</th><th>Latência p50/p95</th></tr></thead>
                <tbody>{d.by_operation.map((o: any) => <tr key={o.operation_code}><td>{o.operation_code} <span className="small muted">{CAT[o.category]}</span></td><td>{o.executions}</td><td>{o.succeeded}</td><td>{o.failed}/{o.partial}/{o.cancelled}</td><td>{o.credits_charged}</td><td>{o.free_quota_uses} · {o.sponsored_uses} · {o.purchased_uses} · {o.cached_uses}</td><td>{o.cost_measured_cents === null ? (o.unpriced ? `${o.unpriced} sem preço` : "local") : money(Math.round(o.cost_measured_cents))}</td><td>{o.latency_p50_ms ?? "—"} / {o.latency_p95_ms ?? "—"} ms</td></tr>)}</tbody></table>
            </Panel>
            <Panel title="Pedidos de crédito">
              <StateView loading={orders.loading} error={orders.error}>
                <ul className="rows">{(orders.data?.items || []).map((o: any) => (
                  <li key={o.id}><span><strong>{o.org_name}</strong> · {o.credits} créditos · {money(o.amount_cents)} · {o.mode === "pilot" ? "piloto" : "real"} · {dateTime(o.created_at)}{o.paid_reference ? ` · ref. ${o.paid_reference}` : ""}</span>
                    <span className="row-actions"><Pill tone={ORDER[o.state]?.[1] || "muted"}>{ORDER[o.state]?.[0] || o.state}</Pill>
                      {o.mode === "pilot" && o.state === "created" && <Button variant="ink" onClick={() => setSel(o)}>Aprovar como concessão de piloto</Button>}
                      {o.mode === "real" && o.state === "awaiting_payment" && <Button variant="ink" onClick={() => setSel(o)}>Conciliar pagamento</Button>}</span></li>
                ))}</ul>
              </StateView>
            </Panel>
            <Panel title="Contestações de similaridade (revisão humana)">
              <StateView loading={disputes.loading} error={disputes.error}>
                <ul className="rows">{(disputes.data?.items || []).map((x: any) => (
                  <li key={x.id}><span><strong>{x.org_name}</strong> · {dateTime(x.created_at)}<br /><span className="small">{x.reason}</span>{x.reviewer_note && <><br /><span className="small muted">{x.reviewer_note}</span></>}</span>
                    <span className="row-actions"><Pill tone={x.status === "open" ? "warn" : "ok"}>{DISPUTE[x.status] || x.status}</Pill>{x.status === "open" && <Button variant="ink" onClick={() => setRev(x)}>Revisar</Button>}</span></li>
                ))}</ul>
              </StateView>
            </Panel>
            <Panel title="Catálogo, cotas e pacotes" quiet>
              <ul className="rows">{d.quota_policies.map((q: any) => <li key={q.key}><span>{q.label_pt} · {q.credits} créditos · {q.period === "once" ? "uma vez" : "mensal"}</span><span className="muted">{q.grants} concessão(ões) · {q.credits_granted} créditos</span></li>)}</ul>
              <ul className="rows">{d.packs.map((p: any) => <li key={p.code}><span>{p.code} · {p.credits} créditos · {money(p.price_cents)}</span><Pill tone={p.status === "active" ? "ok" : "warn"}>{p.status}</Pill></li>)}</ul>
              <p className="fineprint">Preços de operação e de pacote mudam por versão nova (POST /v1/admin/ai/operations e /credit-packs, permissão finance.approve), nunca por edição: execuções antigas guardam a versão que as autorizou.</p>
              <ul className="plain">{d.honesty.map((h: string, i: number) => <li key={i} className="small muted">{h}</li>)}</ul>
            </Panel>
            <Modal open={!!sel} title={sel?.mode === "pilot" ? "Aprovar pedido piloto" : "Conciliar pagamento recebido"} onClose={() => setSel(null)}
              footer={<Button variant="primary" busy={busy} disabled={sel?.mode === "real" ? ref.length < 6 || note.length < 5 : note.length < 5}
                onClick={() => run(() => sel.mode === "pilot" ? api.post(`/v1/admin/ai/credit-orders/${sel.id}/approve-pilot`, { note }) : api.post(`/v1/admin/ai/credit-orders/${sel.id}/confirm`, { reference: ref, note }), sel.mode === "pilot" ? "Concessão de piloto registrada (crédito promocional)" : "Pagamento conciliado; compra creditada").then(() => { setSel(null); setRef(""); setNote(""); reloadAll(); })}>Confirmar</Button>}>
              {sel?.mode === "real" && <Field label="Referência do extrato (obrigatória)"><Input value={ref} onChange={setRef} /></Field>}
              <Field label="Nota"><TextArea rows={2} value={note} onChange={setNote} /></Field>
              <p className="fineprint">{sel?.mode === "pilot" ? "Pedido piloto vira crédito PROMOCIONAL: nunca compra, nunca receita." : "Conciliação manual exige referência; cobrança simulada nunca credita compra."}</p>
            </Modal>
            <Modal open={!!rev} title="Revisão humana da contestação" onClose={() => setRev(null)}
              footer={<><Button variant="ghost" busy={busy} disabled={revNote.length < 10} onClick={() => run(() => api.post(`/v1/admin/ai/disputes/${rev.id}/review`, { outcome: "reviewed_upheld", reviewer_note: revNote }), "Análise mantida").then(() => { setRev(null); setRevNote(""); reloadAll(); })}>Manter análise</Button>
                <Button variant="primary" busy={busy} disabled={revNote.length < 10} onClick={() => run(() => api.post(`/v1/admin/ai/disputes/${rev.id}/review`, { outcome: "reviewed_corrected", reviewer_note: revNote }), "Análise corrigida").then(() => { setRev(null); setRevNote(""); reloadAll(); })}>Corrigir</Button></>}>
              <p className="small">{rev?.reason}</p>
              <Field label="Nota da revisão (mínimo 10 caracteres)"><TextArea rows={3} value={revNote} onChange={setRevNote} /></Field>
            </Modal>
          </>
        )}
      </StateView>
    </>
  );
}
