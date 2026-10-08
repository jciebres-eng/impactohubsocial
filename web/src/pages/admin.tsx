import React, { useState } from "react";
import { api } from "../api";
import { date, dateTime, label, money } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Bars, Button, Field, Input, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

function AdminGate({ children }: { children: any }) {
  const { me } = useSession();
  if (me && !me.user.mfa_verified) return (
    <div className="state state-empty">
      <h1>Ative a verificação em duas etapas</h1>
      <p>A área administrativa exige MFA ativo e verificado nesta sessão.</p>
      <Button variant="primary" onClick={() => navigate("/conta")}>Configurar agora</Button>
    </div>
  );
  return children;
}

export function Overview() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/overview");
  return (
    <AdminGate>
      <PageHead title="Administração" sub="Filas de trabalho e saúde da operação." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="grid-home">
            <Panel title="Filas">
              <ul className="rows">
                <li><Link to="/admin/compliance">Análises de compliance</Link><strong>{data.queues.compliance_open}</strong></li>
                <li><Link to="/admin/credenciais">Credenciais a verificar</Link><strong>{data.queues.credentials_pending}</strong></li>
                <li><Link to="/admin/denuncias">Denúncias abertas</Link><strong>{data.queues.reports_open}</strong></li>
                <li><Link to="/admin/fiscal">Regras fiscais em revisão</Link><strong>{data.queues.fiscal_pending}</strong></li>
                <li><span>Arquivos aguardando antivírus</span><strong>{data.queues.documents_pending_scan}</strong></li>
              </ul>
            </Panel>
            <Panel title="Usuários">
              <ul className="rows"><li><span>Total</span><strong>{data.users.total}</strong></li><li><span>Ativos em 30 dias</span><strong>{data.users.active_30d}</strong></li>
                <li><span>Com MFA</span><strong>{data.users.with_mfa}</strong></li></ul>
            </Panel>
            <Panel title="Recursos registrados">
              <ul className="rows"><li><span>Comprometido</span><strong>{money(data.funding.committed_cents)}</strong></li><li><span>Confirmado pelas OSCs</span><strong>{money(data.funding.confirmed_cents)}</strong></li></ul>
            </Panel>
            <Panel title="Organizações"><Bars rows={data.organizations.map((o: any) => ({ label: `${o.kind} · ${label(o.compliance_status)}`, value: o.n }))} format={String} /></Panel>
            <Panel title="Candidaturas"><Bars rows={data.applications.map((o: any) => ({ label: `${o.origin} · ${label(o.status)}`, value: o.n }))} format={String} /></Panel>
          </div>
        )}
      </StateView>
    </AdminGate>
  );
}

export function ComplianceQueue() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/compliance-reviews");
  const [sel, setSel] = useState<any>(null);
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  const decide = (decision: string) => run(() => api.post(`/v1/admin/compliance-reviews/${sel.id}/decide`, { decision, note: note || null }), "Decisão registrada").then((r) => { if (r) { setSel(null); setNote(""); reload(); } });
  return (
    <AdminGate>
      <PageHead title="Compliance" sub="Verificações automáticas + decisão humana registrada em auditoria." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma análise pendente."}>
        <table className="table"><thead><tr><th>Organização</th><th>Tipo</th><th>CNPJ</th><th>Risco</th><th>Desde</th><th /></tr></thead>
          <tbody>{data?.items.map((r: any) => (
            <tr key={r.id}><td>{r.legal_name}</td><td>{r.kind}</td><td>{r.cnpj}</td><td><Pill tone={r.risk_level === "high" ? "bad" : r.risk_level === "medium" ? "warn" : "good"}>{r.risk_level}</Pill></td>
              <td>{date(r.created_at)}</td><td><Button variant="ink" onClick={() => setSel(r)}>Analisar</Button></td></tr>
          ))}</tbody></table>
      </StateView>
      <Modal open={!!sel} title={sel?.legal_name || ""} onClose={() => setSel(null)} footer={<>
        <Button variant="ghost" busy={busy} onClick={() => decide("info_requested")}>Pedir informações</Button>
        <Button variant="danger" busy={busy} onClick={() => decide("rejected")}>Reprovar</Button>
        <Button variant="primary" busy={busy} onClick={() => decide("approved")}>Aprovar</Button></>}>
        <ul className="rows">{(sel?.checks || []).map((c: any) => <li key={c.type}><span>{c.type}<br /><span className="muted">{JSON.stringify(c.details)}</span></span><Pill status={c.status} /></li>)}</ul>
        <Field label="Justificativa (enviada à organização)"><TextArea rows={3} value={note} onChange={setNote} /></Field>
      </Modal>
    </AdminGate>
  );
}

export function Credentials() {
  const [status, setStatus] = useState("document_submitted");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/credentials?status=${status}`, [status]);
  const { run } = useAction();
  const verify = (id: string, st: string) => {
    const note = prompt("Registre a fonte consultada (ex.: cadastro público do conselho) e a data:");
    if (note) run(() => api.post(`/v1/admin/credentials/${id}/verify`, { status: st, note }), "Credencial atualizada").then(reload);
  };
  return (
    <AdminGate>
      <PageHead title="Credenciais profissionais" />
      <div className="filters"><Field label="Situação"><Select value={status} onChange={setStatus} options={[["document_submitted", "Com comprovante"], ["self_declared", "Autodeclaradas"], ["verified", "Verificadas"], ["rejected", "Rejeitadas"]]} /></Field></div>
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nada nesta fila."}>
        <table className="table"><thead><tr><th>Profissional</th><th>Registro</th><th>Validade</th><th>Comprovante</th><th /></tr></thead>
          <tbody>{data?.items.map((c: any) => (
            <tr key={c.id}><td>{c.holder_name}<br /><span className="muted">{c.legal_name}</span></td><td>{c.council}/{c.uf} {c.number}</td><td>{date(c.valid_until)}</td>
              <td>{c.document_id ? "anexado" : "—"}</td>
              <td className="row-actions"><Button variant="link" onClick={() => verify(c.id, "verified")}>Verificar</Button><Button variant="link" onClick={() => verify(c.id, "rejected")}>Rejeitar</Button></td></tr>
          ))}</tbody></table>
      </StateView>
    </AdminGate>
  );
}

export function CuratedCalls() {
  const sources = useLoad<any>("/v1/admin/call-sources");
  const f = useForm({ title: "", funder_name: "", url: "", sphere: "federal", instrument: "edital", closes_at: "", summary: "" });
  const s = useForm({ name: "", kind: "json_feed", url: "", sphere: "federal", terms_note: "" });
  const { busy, run } = useAction();
  return (
    <AdminGate>
      <PageHead title="Editais curados e fontes" sub="Toda oportunidade externa precisa de link para a fonte oficial. Importação automática só após verificar os termos de uso da fonte." />
      <div className="split">
        <Panel title="Cadastrar edital externo">
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/admin/calls", { ...f.v, status: "open", managed_on_platform: false, closes_at: f.v.closes_at ? f.v.closes_at + "T23:59:00-03:00" : null, summary: f.v.summary || null }), "Edital cadastrado").then((r: any) => r && navigate(`/oportunidades/${r.id}`)); }}>
            <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
            <Field label="Financiador / órgão"><Input value={f.v.funder_name} onChange={f.set("funder_name")} /></Field>
            <Field label="Link oficial"><Input value={f.v.url} onChange={f.set("url")} placeholder="https://" /></Field>
            <Field label="Esfera"><Select value={f.v.sphere} onChange={f.set("sphere")} options={[["federal", "Federal"], ["state", "Estadual"], ["municipal", "Municipal"], ["local", "Local"], ["international", "Internacional"], ["private", "Privado"]]} /></Field>
            <Field label="Encerramento"><Input type="date" value={f.v.closes_at} onChange={f.set("closes_at")} /></Field>
            <Field label="Resumo"><TextArea rows={3} value={f.v.summary} onChange={f.set("summary")} /></Field>
            <Button type="submit" variant="primary" busy={busy}>Cadastrar</Button>
          </form>
        </Panel>
        <Panel title="Fontes de importação">
          <ul className="rows">{sources.data?.items.map((x: any) => (
            <li key={x.id}><span><strong>{x.name}</strong> · {x.kind}<br /><span className="muted">{x.url} · última execução {dateTime(x.last_run_at)} {x.last_error && `· ${x.last_error}`}</span></span>
              <Button variant="link" onClick={() => run(() => api.post(`/v1/admin/call-sources/${x.id}/run`), "Importação executada").then(sources.reload)}>Importar agora</Button></li>
          ))}</ul>
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/admin/call-sources", { ...s.v, active: true }), "Fonte cadastrada").then(sources.reload); }}>
            <Field label="Nome"><Input value={s.v.name} onChange={s.set("name")} /></Field>
            <Field label="Formato"><Select value={s.v.kind} onChange={s.set("kind")} options={[["json_feed", "JSON"], ["csv_feed", "CSV"], ["rss", "RSS"]]} /></Field>
            <Field label="URL (https)"><Input value={s.v.url} onChange={s.set("url")} /></Field>
            <Field label="Esfera"><Select value={s.v.sphere} onChange={s.set("sphere")} options={[["federal", "Federal"], ["state", "Estadual"], ["municipal", "Municipal"], ["international", "Internacional"], ["private", "Privado"]]} /></Field>
            <Field label="Verificação dos termos de uso" hint="Quem verificou, quando e o que a licença permite"><TextArea rows={2} value={s.v.terms_note} onChange={s.set("terms_note")} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Cadastrar fonte</Button>
          </form>
        </Panel>
      </div>
    </AdminGate>
  );
}

export function FiscalRules() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/fiscal-rules");
  const { run } = useAction();
  const act = (id: string, action: string) => run(() => api.post(`/v1/admin/fiscal-rules/${id}/action`, { action, source_consulted_on: action === "submit" ? new Date().toISOString().slice(0, 10) : null }), "Regra atualizada").then(reload);
  return (
    <AdminGate>
      <PageHead title="Regras fiscais" sub="Rascunho → revisão → aprovação por DOIS revisores distintos. Só regras aprovadas e vigentes aparecem para empresas." />
      <StateView loading={loading} error={error} onRetry={reload}>
        <table className="table"><thead><tr><th>Regra</th><th>Fonte</th><th>Limite</th><th>Situação</th><th /></tr></thead>
          <tbody>{data?.items.map((r: any) => (
            <tr key={r.id}><td>{r.name}<br /><span className="muted">{r.code} v{r.version}</span></td>
              <td><a href={r.source_url} target="_blank" rel="noopener noreferrer">{r.source_citation}</a><br /><span className="muted">consultada {date(r.source_consulted_on)}</span></td>
              <td>{r.limit_pct === null ? "não validado" : `${r.limit_pct}%`}</td><td><Pill status={r.status} />{r.approved_by_1 && r.status === "pending_review" && <span className="muted"> 1 de 2 aprovações</span>}</td>
              <td className="row-actions">
                {r.status === "draft" && <Button variant="link" onClick={() => act(r.id, "submit")}>Enviar à revisão</Button>}
                {r.status === "pending_review" && <><Button variant="link" onClick={() => act(r.id, "approve")}>Aprovar</Button><Button variant="link" onClick={() => act(r.id, "return_to_draft")}>Devolver</Button></>}
                {r.status === "approved" && <Button variant="link" onClick={() => act(r.id, "retire")}>Retirar</Button>}
              </td></tr>
          ))}</tbody></table>
      </StateView>
    </AdminGate>
  );
}

export function Vouchers() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/voucher-batches");
  const f = useForm({ campaign: "", type: "grant_plan", plan_key: "osc_premium", feature_key: "", duration_days: "90", quantity: "10", max_redemptions: "1", scope_roles: "osc" });
  const [codes, setCodes] = useState<string[] | null>(null);
  const { busy, run } = useAction();
  return (
    <AdminGate>
      <PageHead title="Vouchers" sub="Códigos guardados apenas como hash. Cada lote só vale após aprovação de um segundo administrador." />
      <div className="split">
        <Panel title="Novo lote">
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/admin/voucher-batches", { campaign: f.v.campaign, type: f.v.type, plan_key: f.v.type === "grant_feature" ? null : f.v.plan_key,
            feature_key: f.v.type === "grant_feature" ? f.v.feature_key : null, duration_days: f.v.duration_days ? Number(f.v.duration_days) : null,
            quantity: Number(f.v.quantity), max_redemptions: Number(f.v.max_redemptions), scope_roles: f.v.scope_roles ? [f.v.scope_roles] : [] }), "Lote criado").then((r: any) => { if (r) { setCodes(r.codes); reload(); } }); }}>
            <Field label="Campanha"><Input value={f.v.campaign} onChange={f.set("campaign")} /></Field>
            {/* v0.27.0 (ADR-341): vouchers de desconto foram aposentados — não há assinatura para descontar. */}
            <Field label="Tipo"><Select value={f.v.type} onChange={f.set("type")} options={[["grant_plan", "Concessão de pacote"], ["grant_feature", "Liberar recurso"], ["free_period", "Período de concessão"]]} /></Field>
            {f.v.type !== "grant_feature" ? <Field label="Plano"><Select value={f.v.plan_key} onChange={f.set("plan_key")} options={[["osc_premium", "OSC Premium"], ["osc_plus", "OSC Plus"], ["company_premium", "Empresa Premium"], ["company_plus", "Empresa Plus"], ["provider_premium", "Profissional Plus"]]} /></Field>
              : <Field label="Recurso"><Input value={f.v.feature_key} onChange={f.set("feature_key")} placeholder="alerts.saved_search" /></Field>}
            <Field label="Duração da concessão (dias; vazio = permanente)"><Input inputMode="numeric" value={f.v.duration_days} onChange={f.set("duration_days")} /></Field>
            <Field label="Quantidade de códigos"><Input inputMode="numeric" value={f.v.quantity} onChange={f.set("quantity")} /></Field>
            <Field label="Usos por código"><Input inputMode="numeric" value={f.v.max_redemptions} onChange={f.set("max_redemptions")} /></Field>
            <Field label="Restrito a"><Select value={f.v.scope_roles} onChange={f.set("scope_roles")} placeholder="Qualquer tipo" options={[["osc", "OSC"], ["company", "Empresa"], ["provider", "Profissional"]]} /></Field>
            <Button type="submit" variant="primary" busy={busy}>Gerar códigos</Button>
          </form>
        </Panel>
        <Panel title="Lotes">
          <StateView loading={loading} error={error} onRetry={reload}>
            <ul className="rows">{data?.items.map((b: any) => (
              <li key={b.id}><span><strong>{b.campaign}</strong> · {b.codes} código(s) · {b.redemptions} resgate(s)<br /><span className="muted">criado por {b.created_by} em {date(b.created_at)}</span></span>
                <span className="row-actions"><Pill status={b.status} />
                  {b.status === "pending_approval" && <Button variant="link" onClick={() => run(() => api.post(`/v1/admin/voucher-batches/${b.id}/action`, { action: "approve" }), "Lote aprovado").then(reload)}>Aprovar</Button>}
                  {b.status === "active" && <Button variant="link" onClick={() => confirm("Revogar o lote?") && run(() => api.post(`/v1/admin/voucher-batches/${b.id}/action`, { action: "revoke" }), "Lote revogado").then(reload)}>Revogar</Button>}</span></li>
            ))}</ul>
          </StateView>
        </Panel>
      </div>
      <Modal open={!!codes} title="Códigos gerados" onClose={() => setCodes(null)}>
        <p><strong>Copie agora.</strong> Os códigos não podem ser exibidos novamente.</p>
        <textarea className="input" rows={10} readOnly value={(codes || []).join("\n")} />
      </Modal>
    </AdminGate>
  );
}

export function Users() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/users?offset=${offset}${query ? `&q=${encodeURIComponent(query)}` : ""}`, [query, offset]);
  const { run } = useAction();
  return (
    <AdminGate>
      <PageHead title="Usuários" />
      <form className="filters" onSubmit={(e: any) => { e.preventDefault(); setOffset(0); setQuery(q); }}><Field label="Buscar"><Input value={q} onChange={setQ} placeholder="nome ou e-mail" /></Field><Button type="submit" variant="ink">Buscar</Button></form>
      <StateView loading={loading} error={error} onRetry={reload}>
        <table className="table"><thead><tr><th>Usuário</th><th>Situação</th><th>MFA</th><th>Último acesso</th><th /></tr></thead>
          <tbody>{data?.items.map((u: any) => (
            <tr key={u.id}><td>{u.full_name}<br /><span className="muted">{u.email}{u.is_platform_admin && " · admin"}</span></td><td><Pill status={u.status} /></td><td>{u.mfa ? "sim" : "não"}</td><td>{dateTime(u.last_login_at)}</td>
              <td>{u.status === "active" ? <Button variant="link" onClick={() => { const reason = prompt("Motivo da desativação:"); if (reason) run(() => api.post(`/v1/admin/users/${u.id}/status`, { status: "disabled", reason }), "Usuário desativado").then(reload); }}>Desativar</Button>
                : u.status === "disabled" && <Button variant="link" onClick={() => run(() => api.post(`/v1/admin/users/${u.id}/status`, { status: "active", reason: "Reativação" }), "Usuário reativado").then(reload)}>Reativar</Button>}</td></tr>
          ))}</tbody></table>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </AdminGate>
  );
}

export function Orgs() {
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/organizations?offset=${offset}${kind ? `&kind=${kind}` : ""}`, [kind, offset]);
  const [grant, setGrant] = useState<any>(null);
  const g = useForm({ plan_key: "osc_premium", days: "90", reason: "" });
  const { busy, run } = useAction();
  return (
    <AdminGate>
      <PageHead title="Organizações" />
      <div className="filters"><Field label="Tipo"><Select value={kind} onChange={setKind} placeholder="Todos" options={[["osc", "OSC"], ["company", "Empresa"], ["provider", "Profissional"], ["government", "Governo"]]} /></Field></div>
      <StateView loading={loading} error={error} onRetry={reload}>
        <table className="table"><thead><tr><th>Organização</th><th>Tipo</th><th>Compliance</th><th>Situação</th><th>Membros</th><th /></tr></thead>
          <tbody>{data?.items.map((o: any) => (
            <tr key={o.id}><td>{o.legal_name}<br /><span className="muted">{o.cnpj} · {o.uf}</span></td><td>{o.kind}</td><td><Pill status={o.compliance_status} /></td><td><Pill status={o.status} /></td><td>{o.members}</td>
              <td className="row-actions">
                <Button variant="link" onClick={() => run(() => api.post(`/v1/admin/organizations/${o.id}/compliance-checks`), "Verificações executadas")}>Rodar verificações</Button>
                <Button variant="link" onClick={() => setGrant(o)}>Conceder plano</Button>
                {o.status === "active" ? <Button variant="link" onClick={() => { const reason = prompt("Motivo da suspensão:"); if (reason) run(() => api.post(`/v1/admin/organizations/${o.id}/status`, { status: "suspended", reason }), "Organização suspensa").then(reload); }}>Suspender</Button>
                  : <Button variant="link" onClick={() => run(() => api.post(`/v1/admin/organizations/${o.id}/status`, { status: "active", reason: "Reativação" }), "Reativada").then(reload)}>Reativar</Button>}
              </td></tr>
          ))}</tbody></table>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={!!grant} title={`Conceder plano a ${grant?.legal_name || ""}`} onClose={() => setGrant(null)} footer={
        <Button variant="primary" busy={busy} onClick={() => run(() => api.post(`/v1/admin/organizations/${grant.id}/grants`, { plan_key: g.v.plan_key, days: Number(g.v.days), reason: g.v.reason }), "Concessão registrada").then((r) => r && setGrant(null))}>Conceder</Button>}>
        <Field label="Plano"><Input value={g.v.plan_key} onChange={g.set("plan_key")} /></Field>
        <Field label="Dias"><Input inputMode="numeric" value={g.v.days} onChange={g.set("days")} /></Field>
        <Field label="Justificativa (auditada)"><TextArea rows={2} value={g.v.reason} onChange={g.set("reason")} /></Field>
      </Modal>
    </AdminGate>
  );
}

/** Apuração de denúncia com os quatro níveis separados.
 *
 * A tela anterior oferecia três botões — Triar, Providência, Arquivar — e pedia um texto por
 * `prompt()`. "Providência" não dizia se a denúncia procedia, e não havia como registrar que a
 * análise concluiu pela IMPROCEDÊNCIA: arquivar e absolver eram o mesmo botão. Para quem foi
 * denunciado, essa diferença é a única que importa.
 */
export function Reports() {
  const [status, setStatus] = useState("reported");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/reports/queue?status=${status}`, [status]);
  const voc = useLoad<any>("/v1/reports/vocabulary");
  const { run } = useAction();
  const [aberta, setAberta] = useState<string | null>(null);

  const acao = (id: string, path: string, corpo: any, msg: string) =>
    run(() => api.post(`/v1/admin/reports/${id}/${path}`, corpo), msg).then(() => { setAberta(null); reload(); });

  return (
    <AdminGate>
      <PageHead title="Denúncias" sub="Denúncia não é suspeita, suspeita não é infração, e infração apurada aqui não é decisão judicial." />
      {voc.data && (
        <Panel title="O que cada nível significa" quiet>
          <dl className="empty-facts">
            {voc.data.levels.map((n: any) => (<React.Fragment key={n.key}><dt>{n.label}</dt><dd>{n.means} — <em>{n.effects}</em></dd></React.Fragment>))}
          </dl>
        </Panel>
      )}
      <div className="filters"><Field label="Situação"><Select value={status} onChange={setStatus}
        options={(voc.data?.statuses || []).map((s: any) => [s.key, s.label])} /></Field></div>
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma denúncia nesta situação."}>
        <p className="muted">{data?.note}</p>
        <table className="table"><thead><tr><th>Alvo</th><th>Categoria</th><th>Detalhes</th><th>Situação</th><th>Manifestações</th><th /></tr></thead>
          <tbody>{data?.items.map((r: any) => (
            <tr key={r.id}>
              <td>{r.target_type}<br /><code className="hash">{r.target_id.slice(0, 8)}</code></td>
              <td>{r.category || r.reason}</td>
              <td>{r.details}</td>
              <td><Pill tone={r.finding === "substantiated" ? "bad" : r.finding === "unsubstantiated" ? "good" : "warn"}>{r.status_label}</Pill>
                {r.finding_label && <><br /><span className="small">{r.finding_label}</span></>}
                {r.legal_referral && <><br /><Pill tone="warn">encaminhado a autoridade</Pill></>}</td>
              <td>{r.responses}</td>
              <td className="row-actions">
                {r.status === "reported" && <Button variant="link" onClick={() => acao(r.id, "review", {}, "Em análise")}>Analisar</Button>}
                {(r.status === "reported" || r.status === "under_review") && <Button variant="link" onClick={() => setAberta(aberta === r.id + ":ask" ? null : r.id + ":ask")}>Pedir manifestação</Button>}
                {(r.status === "under_review" || r.status === "information_requested" || r.status === "appealed") && <Button variant="link" onClick={() => setAberta(aberta === r.id + ":end" ? null : r.id + ":end")}>Concluir</Button>}
                {["reported", "under_review", "information_requested"].includes(r.status) && <Button variant="link" onClick={() => setAberta(aberta === r.id + ":dis" ? null : r.id + ":dis")}>Arquivar</Button>}
              </td>
            </tr>
          ))}</tbody></table>
        {aberta && <ReportAction token={aberta} onDo={acao} onCancel={() => setAberta(null)} />}
      </StateView>
    </AdminGate>
  );
}

/** Formulário da ação escolhida. Toda conclusão exige fundamentação escrita — não há botão sozinho. */
function ReportAction({ token, onDo, onCancel }: { token: string; onDo: (id: string, p: string, b: any, m: string) => void; onCancel: () => void }) {
  const [id, tipo] = token.split(":");
  const f = useForm({ texto: "", finding: "substantiated", referral: false, referralNote: "" });
  const curto = f.v.texto.trim().length < 20;
  return (
    <Panel title={tipo === "ask" ? "Pedir manifestação a quem foi denunciado" : tipo === "end" ? "Concluir a análise" : "Arquivar sem análise de mérito"}>
      {tipo === "end" && (
        <Field label="Conclusão">
          <Select value={f.v.finding} onChange={f.set("finding")} options={[["substantiated", "Procede — autoriza medida"], ["unsubstantiated", "Não procede — é uma absolvição"]]} />
        </Field>
      )}
      {tipo === "dis" && <p className="muted">Arquivar NÃO é concluir pela improcedência. Se a análise concluiu que não procede, use “Concluir”.</p>}
      <Field label={tipo === "ask" ? "O que está sendo pedido" : "Fundamentação"} hint="Mínimo de 20 caracteres">
        <TextArea rows={3} value={f.v.texto} onChange={f.set("texto")} />
      </Field>
      {tipo === "end" && (
        <>
          <label className="check"><input type="checkbox" checked={f.v.referral} onChange={(e: any) => f.set("referral")(e.target.checked)} />
            <span>Encaminhar a autoridade competente (a plataforma não declara crime nem tipifica conduta)</span></label>
          {f.v.referral && <Field label="Por que encaminhar" hint="Mínimo de 20 caracteres"><TextArea rows={2} value={f.v.referralNote} onChange={f.set("referralNote")} /></Field>}
        </>
      )}
      <div className="panel-actions">
        <Button variant="primary" disabled={curto} onClick={() => {
          if (tipo === "ask") onDo(id, "request-response", { question: f.v.texto }, "Manifestação pedida");
          else if (tipo === "dis") onDo(id, "dismiss", { rationale: f.v.texto }, "Arquivada");
          else onDo(id, "conclude", { finding: f.v.finding, rationale: f.v.texto, legal_referral: f.v.referral, legal_referral_note: f.v.referral ? f.v.referralNote : null }, "Concluída");
        }}>Registrar</Button>
        <Button variant="ghost" onClick={onCancel}>Cancelar</Button>
      </div>
    </Panel>
  );
}

export function Audit() {
  const [action, setAction] = useState("");
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/audit?offset=${offset}${query ? `&action=${encodeURIComponent(query)}` : ""}`, [query, offset]);
  const verify = useLoad<any>("/v1/admin/audit/verify");
  return (
    <AdminGate>
      <PageHead title="Auditoria" actions={verify.data && (verify.data.valid ? <Pill tone="good">Cadeia da plataforma íntegra · {verify.data.entries}</Pill> : <Pill tone="bad">Inconsistência no registro {verify.data.first_broken_seq}</Pill>)} />
      <form className="filters" onSubmit={(e: any) => { e.preventDefault(); setOffset(0); setQuery(action); }}><Field label="Ação começa com"><Input value={action} onChange={setAction} placeholder="auth., billing., compliance." /></Field><Button type="submit" variant="ink">Filtrar</Button></form>
      <StateView loading={loading} error={error} onRetry={reload}>
        <table className="table"><thead><tr><th>Quando</th><th>Ação</th><th>Objeto</th><th>IP</th><th>Hash</th></tr></thead>
          <tbody>{data?.items.map((e: any) => (
            <tr key={e.id}><td>{dateTime(e.at)}</td><td>{e.action}</td><td>{e.object_type} {e.object_id?.slice(0, 8)}</td><td>{e.ip}</td><td><code className="hash">{e.event_hash?.slice(0, 10)}</code></td></tr>
          ))}</tbody></table>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </AdminGate>
  );
}


const AGR_KIND: [string, string][] = [["convention", "Convênio"], ["partner", "Parceria"], ["gov", "Instituição pública (GOV)"]];

/** Convênios, parcerias e contratos institucionais: licença e/ou desconto por código; ativação por um segundo administrador. */
export function Agreements() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/agreements");
  const f = useForm({ name: "", kind: "convention", plan_key: "osc_premium", seats: "10", grant_days: "", email_domains: "", contract_ref: "" });
  const [code, setCode] = useState<string | null>(null);
  const { busy, run } = useAction();
  const act = (id: string, action: string, ok: string) => run(() => api.post(`/v1/admin/agreements/${id}/action`, { action }), ok).then(reload);
  return (
    <AdminGate>
      <PageHead title="Convênios e contratos" sub="O código é exibido uma única vez e guardado apenas como hash. O domínio de e-mail só restringe quem pode entrar; o código continua obrigatório. A ativação exige um segundo administrador." />
      <div className="split">
        <Panel title="Novo convênio">
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/admin/agreements", { name: f.v.name, kind: f.v.kind, plan_key: f.v.plan_key || null, seats: Number(f.v.seats), grant_days: f.v.grant_days ? Number(f.v.grant_days) : null,
            email_domains: f.v.email_domains.split(/[\s,;]+/).filter(Boolean), contract_ref: f.v.contract_ref || null }), "Convênio criado (rascunho)").then((r: any) => { if (r) { setCode(r.code); reload(); } }); }}>
            <Field label="Nome"><Input value={f.v.name} onChange={f.set("name")} /></Field>
            <Field label="Tipo"><Select value={f.v.kind} onChange={f.set("kind")} options={AGR_KIND} /></Field>
            <Field label="Pacote concedido"><Select value={f.v.plan_key} onChange={f.set("plan_key")} options={[["osc_premium", "OSC Premium"], ["osc_plus", "OSC Plus"], ["company_premium", "Empresa Premium"], ["company_plus", "Empresa Plus"], ["gov_institutional", "GOV institucional"]]} /></Field>
            <Field label="Vagas (organizações)"><Input inputMode="numeric" value={f.v.seats} onChange={f.set("seats")} /></Field>
            <Field label="Dias de licença (vazio = até o fim do convênio)"><Input inputMode="numeric" value={f.v.grant_days} onChange={f.set("grant_days")} /></Field>
            <Field label="Domínios de e-mail permitidos (opcional)"><Input value={f.v.email_domains} onChange={f.set("email_domains")} placeholder="exemplo.org.br" /></Field>
            <Field label="Referência do contrato"><Input value={f.v.contract_ref} onChange={f.set("contract_ref")} /></Field>
            <Button type="submit" variant="primary" busy={busy}>Criar convênio</Button>
          </form>
        </Panel>
        <Panel title="Convênios">
          <StateView loading={loading} error={error} onRetry={reload}>
            <ul className="rows">{data?.items.map((a: any) => (
              <li key={a.id}><span><strong>{a.name}</strong> · {label(a.kind)} · {a.seats_used}/{a.seats} vagas<br /><span className="muted">{a.plan_key} · código …{a.code_hint}</span></span>
                <span className="row-actions"><Pill status={a.status} />
                  {a.status === "draft" && <Button variant="link" onClick={() => act(a.id, "activate", "Convênio ativado")}>Ativar (2º admin)</Button>}
                  {a.status === "active" && <Button variant="link" onClick={() => confirm("Suspender novos ingressos?") && act(a.id, "suspend", "Convênio suspenso")}>Suspender</Button>}
                  {a.status !== "ended" && <Button variant="link" onClick={() => confirm("Encerrar o convênio? As licenças dos membros são revogadas.") && act(a.id, "end", "Convênio encerrado")}>Encerrar</Button>}</span></li>
            ))}{data?.items.length === 0 && <li className="muted">Nenhum convênio.</li>}</ul>
          </StateView>
        </Panel>
      </div>
      <Modal open={!!code} title="Código do convênio" onClose={() => setCode(null)}>
        <p>Guarde agora: o código não será exibido novamente.</p>
        <p><code>{code}</code></p>
      </Modal>
    </AdminGate>
  );
}

/** Acesso de uma organização: licenças (concessão e revogação com motivo), licença sob contrato e histórico. Toda intervenção exige motivo e é auditada.
 * v0.27.0 (ADR-341): o período de teste saiu com a assinatura. */
export function OrgBilling() {
  const [orgId, setOrgId] = useState("");
  const [data, setData] = useState<any>(null);
  const f = useForm({ plan_key: "osc_premium", days: "30", source: "license", reason: "", months: "12", reference: "" });
  const { busy, run } = useAction();
  const load = (id = orgId) => run(() => api.get(`/v1/admin/billing/organizations/${id}`)).then((r: any) => r && setData(r));
  return (
    <AdminGate>
      <PageHead title="Acesso por organização" sub="Intervenções de suporte: concessão, revogação e licença sob contrato. Sempre com motivo; ficam na trilha de auditoria. Não existe assinatura." />
      <Panel>
        <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); load(); }}>
          <Field label="ID da organização"><Input value={orgId} onChange={setOrgId} /></Field>
          <Button type="submit" variant="ink" busy={busy}>Consultar</Button>
        </form>
      </Panel>
      {data && <>
        <Panel title="Situação">
          <KV d={data} />
        </Panel>
        <div className="split">
          <Panel title="Conceder licença">
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/admin/organizations/${orgId}/grants`, { plan_key: f.v.plan_key, days: f.v.days ? Number(f.v.days) : null, source: f.v.source, reason: f.v.reason }), "Licença concedida").then(() => load()); }}>
              <Field label="Plano"><Select value={f.v.plan_key} onChange={f.set("plan_key")} options={[["osc_premium", "OSC Premium"], ["osc_plus", "OSC Plus"], ["company_premium", "Empresa Premium"], ["company_plus", "Empresa Plus"], ["gov_institutional", "GOV institucional"]]} /></Field>
              <Field label="Origem"><Select value={f.v.source} onChange={f.set("source")} options={[["license", "Licença"], ["partner", "Parceria"], ["convention", "Convênio"], ["gov", "GOV"], ["promotion", "Promoção"], ["admin", "Administrativa"]]} /></Field>
              <Field label="Dias (vazio = permanente)"><Input inputMode="numeric" value={f.v.days} onChange={f.set("days")} /></Field>
              <Field label="Motivo"><Input value={f.v.reason} onChange={f.set("reason")} /></Field>
              <Button type="submit" variant="primary" busy={busy}>Conceder</Button>
            </form>
          </Panel>
          <Panel title="Licença sob contrato (Enterprise/Governo)">
            <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post(`/v1/admin/organizations/${orgId}/license`, { plan_key: f.v.plan_key, months: Number(f.v.months), reference: f.v.reference }), "Licença concedida").then(() => load()); }}>
              <Field label="Pacote"><Select value={f.v.plan_key} onChange={f.set("plan_key")} options={[["company_enterprise", "Empresa Enterprise"], ["gov_institutional", "GOV institucional"], ["osc_premium", "OSC Premium"], ["company_premium", "Empresa Premium"]]} /></Field>
              <Field label="Meses"><Input inputMode="numeric" value={f.v.months} onChange={f.set("months")} /></Field>
              <Field label="Referência do contrato"><Input value={f.v.reference} onChange={f.set("reference")} /></Field>
              <Button type="submit" variant="ink" busy={busy}>Conceder licença</Button>
            </form>
            <p className="muted">A licença termina no prazo e não renova sozinha; nenhum dado é apagado ao terminar.</p>
          </Panel>
        </div>
        <Panel title="Licenças">
          <ul className="rows">{data.grants?.map((g: any) => (
            <li key={g.id}><span>{label(g.source)} · {g.plan_key || g.feature_key}<br /><span className="muted">{g.reason || "—"}{g.revoke_reason ? ` · revogada: ${g.revoke_reason}` : ""}</span></span>
              <span className="row-actions">{g.revoked_at ? <Pill tone="muted">Revogada</Pill> : <>{g.ends_at ? `até ${date(g.ends_at)}` : "sem prazo"}
                <Button variant="link" onClick={() => { const reason = prompt("Motivo da revogação (mín. 3 caracteres)"); if (reason) run(() => api.post(`/v1/admin/grants/${g.id}/revoke`, { reason }), "Licença revogada").then(() => load()); }}>Revogar</Button></>}</span></li>
          ))}{!data.grants?.length && <li className="muted">Nenhuma licença.</li>}</ul>
        </Panel>
      </>}
    </AdminGate>
  );
}

function KV({ d }: { d: any }) {
  return (
    <dl className="kv">
      <div><dt>Nível</dt><dd>{d.entitlements?.tier_label || "—"}</dd></div>
      <div><dt>Acesso</dt><dd>{d.access?.state || "—"}{d.access?.free_period_end ? ` · concessão até ${date(d.access.free_period_end)}` : ""}</dd></div>
      <div><dt>Contratos</dt><dd>{d.contracts?.length ?? 0}</dd></div>
      <div><dt>Faturas</dt><dd>{d.invoices?.length ?? 0}</dd></div>
    </dl>
  );
}
