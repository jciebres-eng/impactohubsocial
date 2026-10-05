import { useState } from "react";
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
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/admin/voucher-batches", { campaign: f.v.campaign, type: f.v.type, plan_key: f.v.type === "grant_feature" ? null : f.v.plan_key, feature_key: f.v.type === "grant_feature" ? f.v.feature_key : null, duration_days: Number(f.v.duration_days), quantity: Number(f.v.quantity), max_redemptions: Number(f.v.max_redemptions), scope_roles: f.v.scope_roles ? [f.v.scope_roles] : [] }), "Lote criado").then((r: any) => { if (r) { setCodes(r.codes); reload(); } }); }}>
            <Field label="Campanha"><Input value={f.v.campaign} onChange={f.set("campaign")} /></Field>
            <Field label="Tipo"><Select value={f.v.type} onChange={f.set("type")} options={[["grant_plan", "Gratuidade de plano"], ["grant_feature", "Liberar recurso"], ["free_period", "Período gratuito"]]} /></Field>
            {f.v.type !== "grant_feature" ? <Field label="Plano"><Select value={f.v.plan_key} onChange={f.set("plan_key")} options={[["osc_premium", "OSC Captação"], ["company_premium", "Empresa Impacto"], ["provider_premium", "Profissional Plus"]]} /></Field>
              : <Field label="Recurso"><Input value={f.v.feature_key} onChange={f.set("feature_key")} placeholder="alerts.saved_search" /></Field>}
            <Field label="Duração (dias)"><Input inputMode="numeric" value={f.v.duration_days} onChange={f.set("duration_days")} /></Field>
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

export function Reports() {
  const [status, setStatus] = useState("open");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/reports?status=${status}`, [status]);
  const { run } = useAction();
  const decide = (id: string, st: string) => { const resolution = prompt("Registro da decisão:"); if (resolution) run(() => api.post(`/v1/admin/reports/${id}`, { status: st, resolution }), "Denúncia atualizada").then(reload); };
  return (
    <AdminGate>
      <PageHead title="Denúncias" sub="Denúncia não é fato verificado: apure, registre e dê direito de resposta." />
      <div className="filters"><Field label="Situação"><Select value={status} onChange={setStatus} options={[["open", "Abertas"], ["triaged", "Em triagem"], ["actioned", "Com providência"], ["dismissed", "Arquivadas"]]} /></Field></div>
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma denúncia nesta situação."}>
        <table className="table"><thead><tr><th>Alvo</th><th>Motivo</th><th>Detalhes</th><th>Recebida</th><th /></tr></thead>
          <tbody>{data?.items.map((r: any) => (
            <tr key={r.id}><td>{r.target_type}<br /><code className="hash">{r.target_id.slice(0, 8)}</code></td><td>{r.reason}</td><td>{r.details}</td><td>{date(r.created_at)}</td>
              <td className="row-actions"><Button variant="link" onClick={() => decide(r.id, "triaged")}>Triar</Button><Button variant="link" onClick={() => decide(r.id, "actioned")}>Providência</Button><Button variant="link" onClick={() => decide(r.id, "dismissed")}>Arquivar</Button></td></tr>
          ))}</tbody></table>
      </StateView>
    </AdminGate>
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
