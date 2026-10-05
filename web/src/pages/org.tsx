import { useEffect, useState } from "react";
import { api } from "../api";
import { centsToInput, date, dateTime, label, money, n, parseMoney } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
import { Bars, Button, Chips, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad, useTaxonomy } from "../ui/kit";
import { UFS } from "./public";
import { UploadButton } from "./documents";

export function CreateOrg() {
  const { reload } = useSession();
  const f = useForm({ kind: "osc", legal_name: "", cnpj: "", uf: "" });
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Crie ou entre em uma organização" sub="Toda atividade na plataforma acontece em nome de uma organização. Se você recebeu um convite, abra o link do e-mail." />
      <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/orgs", { ...f.v, cnpj: f.v.cnpj || null, uf: f.v.uf || null }), "Organização criada").then(async (r) => { if (r) { await reload(); navigate("/"); } }); }}>
        <Field label="Tipo"><Select value={f.v.kind} onChange={f.set("kind")} options={[["osc", "Organização da sociedade civil"], ["company", "Empresa, instituto ou fundação"], ["individual", "Apoiador pessoa física"], ["provider", "Profissional parceiro"], ["government", "Órgão público"]]} /></Field>
        <Field label="Razão social"><Input value={f.v.legal_name} onChange={f.set("legal_name")} /></Field>
        <Field label="CNPJ"><Input value={f.v.cnpj} onChange={f.set("cnpj")} /></Field>
        <Field label="UF"><Select value={f.v.uf} onChange={f.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
        <Button type="submit" variant="primary" busy={busy}>Criar organização</Button>
      </form>
    </>
  );
}

export function OrgProfile() {
  const tax = useTaxonomy();
  const { me } = useSession();
  const { data, error, loading, reload } = useLoad<any>("/v1/org");
  const f = useForm<any>({});
  const { busy, run } = useAction();
  useEffect(() => {
    if (data) f.setV({ ...data.organization, founded_on: data.organization.founded_on || "", ods: (data.organization.ods || []).map(String), territories: (data.organization.territories || []).join(", ") });
  }, [data]);  // eslint-disable-line
  const canEdit = ["owner", "admin"].includes(me?.active_org?.role || "");
  const kind = data?.organization.kind;
  async function save(e: any) {
    e.preventDefault();
    const v = f.v;
    await run(() => api.patch("/v1/org", {
      legal_name: v.legal_name, trade_name: v.trade_name || null, founded_on: v.founded_on || null, description: v.description || null, website: v.website || null,
      contact_email: v.contact_email || null, phone: v.phone || null, city: v.city || null, uf: v.uf || null, ibge_code: v.ibge_code || null,
      causes: v.causes, ods: v.ods.map(Number),
      territories: (v.territories || "").split(",").map((s: string) => s.trim().toUpperCase()).filter(Boolean),
      team_size: v.team_size === "" || v.team_size === null ? null : Number(v.team_size),
    }), "Perfil atualizado");
    reload();
  }
  return (
    <>
      <PageHead title="Organização" sub={data?.organization.legal_name}
        actions={<><Button variant="ghost" onClick={() => navigate("/organizacao/equipe")}>Equipe</Button><Button variant="ghost" onClick={() => navigate("/organizacao/compliance")}>Verificação do cadastro</Button></>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <form className="form form-wide" onSubmit={save}>
              <fieldset disabled={!canEdit} className="form-wide-fieldset">
                <Field label="Razão social"><Input value={f.v.legal_name} onChange={f.set("legal_name")} /></Field>
                <Field label="Nome fantasia"><Input value={f.v.trade_name} onChange={f.set("trade_name")} /></Field>
                <Field label="CNPJ" hint="Alteração somente pelo suporte"><Input value={f.v.cnpj || ""} onChange={() => {}} readOnly /></Field>
                <Field label="Data de fundação"><Input type="date" value={f.v.founded_on} onChange={f.set("founded_on")} /></Field>
                <Field label="Município"><Input value={f.v.city} onChange={f.set("city")} /></Field>
                <Field label="UF"><Select value={f.v.uf} onChange={f.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
                <Field label="Código IBGE do município" hint="7 dígitos — usado para compatibilidade territorial"><Input inputMode="numeric" value={f.v.ibge_code} onChange={f.set("ibge_code")} /></Field>
                <Field label="Site"><Input value={f.v.website} onChange={f.set("website")} placeholder="https://" /></Field>
                <Field label="Descrição" wide><TextArea rows={4} value={f.v.description} onChange={f.set("description")} /></Field>
                {kind === "osc" && <>
                  <Field label="Causas de atuação" wide><Chips options={Object.entries(tax?.causes || {}) as any} value={f.v.causes || []} onChange={f.set("causes")} /></Field>
                  <Field label="ODS" wide><Chips options={Object.entries(tax?.ods || {}).map(([k]) => [k, `ODS ${k}`]) as any} value={f.v.ods || []} onChange={f.set("ods")} /></Field>
                  <Field label="Qualificações e certificações" wide hint="Natureza jurídica, OSC/OSCIP/OS/CEBAS e comprovantes ficam em Instituição, com estado de verificação.">
                    <Link to="/instituicao">Abrir Instituição →</Link>
                  </Field>
                  <Field label="Territórios de atuação" hint="Separados por vírgula"><Input value={f.v.territories} onChange={f.set("territories")} /></Field>
                  <Field label="Tamanho da equipe"><Input inputMode="numeric" value={f.v.team_size ?? ""} onChange={f.set("team_size")} /></Field>
                </>}
                {canEdit && <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>Salvar perfil</Button></div>}
              </fieldset>
            </form>
            {(kind === "company" || kind === "individual") && <FunderProfile initial={data.funder_profile} />}
            {kind === "provider" && <ProviderProfile initial={data.provider_profile} />}
          </>
        )}
      </StateView>
    </>
  );
}

function FunderProfile({ initial }: { initial: any }) {
  const tax = useTaxonomy();
  const i = initial || {};
  const f = useForm<any>({ ...i, ods: (i.ods || []).map(String), territories: (i.territories || []).join(", "), excluded_territories: (i.excluded_territories || []).join(", "),
    ticket_min: centsToInput(i.ticket_min_cents), ticket_max: centsToInput(i.ticket_max_cents), annual_budget: centsToInput(i.annual_budget_cents),
    min_org_age_months: i.min_org_age_months ?? "", causes: i.causes || [], excluded_causes: i.excluded_causes || [], esg_focus: i.esg_focus || [],
    required_document_types: i.required_document_types || [], accepts_fractioning: i.accepts_fractioning ?? true, policies: i.policies || "",
    accepted_legal_natures: i.accepted_legal_natures || [], required_qualifications: i.required_qualifications || [], funding_modalities: i.funding_modalities || [],
    min_maturity: i.min_maturity ?? "" });
  const instCat = useLoad<any>("/v1/institutional/catalogs");
  const catOpts = (k: string) => ((instCat.data?.catalogs?.[k] || []) as any[]).map((x) => [x.code, x.label] as [string, string]);
  const { me: sess } = useSession();
  const isPF = sess?.active_org?.kind === "individual";
  const { busy, run } = useAction();
  const list = (s: string) => s.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
  const docOpts = Object.entries(tax?.document_types || {}).map(([k, v]: any) => [k, v.label]) as [string, string][];
  return (
    <Panel title="Perfil de investimento" actions={<span className="muted">Define a ordenação do feed e os bloqueios automáticos</span>}>
      <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.put("/v1/org/funder-profile", {
        causes: f.v.causes, ods: f.v.ods.map(Number), esg_focus: f.v.esg_focus, territories: list(f.v.territories), excluded_causes: f.v.excluded_causes,
        excluded_territories: list(f.v.excluded_territories), ticket_min_cents: parseMoney(f.v.ticket_min), ticket_max_cents: parseMoney(f.v.ticket_max),
        annual_budget_cents: parseMoney(f.v.annual_budget), required_document_types: f.v.required_document_types,
        min_org_age_months: f.v.min_org_age_months === "" ? null : Number(f.v.min_org_age_months), accepts_fractioning: f.v.accepts_fractioning, policies: f.v.policies || null, ...(isPF ? { public_name: !!f.v.public_name } : {}),
        accepted_legal_natures: f.v.accepted_legal_natures, required_qualifications: f.v.required_qualifications, funding_modalities: f.v.funding_modalities,
        min_maturity: f.v.min_maturity === "" ? null : Number(f.v.min_maturity),
      }), "Perfil de investimento salvo"); }}>
        <Field label="Causas prioritárias" wide><Chips options={Object.entries(tax?.causes || {}) as any} value={f.v.causes} onChange={f.set("causes")} /></Field>
        <Field label="ODS prioritários" wide><Chips options={Object.entries(tax?.ods || {}).map(([k]) => [k, `ODS ${k}`]) as any} value={f.v.ods} onChange={f.set("ods")} /></Field>
        <Field label="Foco ESG" wide><Chips options={Object.entries(tax?.esg || {}) as any} value={f.v.esg_focus} onChange={f.set("esg_focus")} /></Field>
        <Field label="Territórios prioritários"><Input value={f.v.territories} onChange={f.set("territories")} placeholder="BR-MT, BR-SP-3550308" /></Field>
        <Field label="Territórios excluídos"><Input value={f.v.excluded_territories} onChange={f.set("excluded_territories")} /></Field>
        {isPF && <Field label="Privacidade" wide hint="Por padrão as OSCs veem “Apoiador pessoa física”."><label><input type="checkbox" checked={!!f.v.public_name} onChange={(e: any) => f.set("public_name")(e.target.checked)} /> Mostrar meu nome às organizações que eu apoiar</label></Field>}
        <Field label="Causas excluídas" wide><Chips options={Object.entries(tax?.causes || {}) as any} value={f.v.excluded_causes} onChange={f.set("excluded_causes")} /></Field>
        <Field label="Ticket mínimo (R$)"><Input inputMode="decimal" value={f.v.ticket_min} onChange={f.set("ticket_min")} /></Field>
        <Field label="Ticket máximo (R$)"><Input inputMode="decimal" value={f.v.ticket_max} onChange={f.set("ticket_max")} /></Field>
        <Field label="Orçamento anual (R$)"><Input inputMode="decimal" value={f.v.annual_budget} onChange={f.set("annual_budget")} /></Field>
        <Field label="Tempo mínimo de existência da OSC (meses)"><Input inputMode="numeric" value={f.v.min_org_age_months} onChange={f.set("min_org_age_months")} /></Field>
        <Field label="Documentos exigidos" wide><Chips options={docOpts} value={f.v.required_document_types} onChange={f.set("required_document_types")} /></Field>
        <Field label="Naturezas jurídicas aceitas" wide hint="Vazio = aceita qualquer. Proponentes fora da lista aparecem bloqueados, com o motivo."><Chips options={catOpts("legal_nature")} value={f.v.accepted_legal_natures} onChange={f.set("accepted_legal_natures")} /></Field>
        <Field label="Qualificações exigidas (verificadas)" wide hint="Só vale qualificação verificada pela plataforma; declarar não basta."><Chips options={catOpts("qualification_type")} value={f.v.required_qualifications} onChange={f.set("required_qualifications")} /></Field>
        <Field label="Maturidade institucional mínima (0–6)"><Input inputMode="numeric" value={f.v.min_maturity} onChange={f.set("min_maturity")} /></Field>
        <Field label="Modalidades de financiamento que pratico" wide><Chips options={catOpts("funding_modality")} value={f.v.funding_modalities} onChange={f.set("funding_modalities")} /></Field>
        <label className="check"><input type="checkbox" checked={f.v.accepts_fractioning} onChange={(e: any) => f.set("accepts_fractioning")(e.target.checked)} /> Aceito apoiar etapas de projetos maiores (fracionamento)</label>
        <Field label="Políticas e restrições" wide><TextArea rows={3} value={f.v.policies} onChange={f.set("policies")} /></Field>
        <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>Salvar perfil de investimento</Button></div>
      </form>
    </Panel>
  );
}

function ProviderProfile({ initial }: { initial: any }) {
  const tax = useTaxonomy();
  const i = initial || {};
  const f = useForm<any>({ services: (i.services || []).join("\n"), categories: i.categories || [], territories: (i.territories || []).join(", "), remote: i.remote ?? true,
    price_info: i.price_info || "", accepting_requests: i.accepting_requests ?? true });
  const creds = useLoad<any>("/v1/org/credentials");
  const c = useForm({ council: "CRC", number: "", uf: "", holder_name: "", valid_until: "", document_id: "" });
  const { busy, run } = useAction();
  return (
    <>
      <Panel title="Perfil profissional">
        <form className="form form-wide" onSubmit={(e: any) => { e.preventDefault(); run(() => api.put("/v1/org/provider-profile", {
          services: f.v.services.split("\n").map((s: string) => s.trim()).filter((s: string) => s.length >= 2), categories: f.v.categories,
          territories: f.v.territories.split(",").map((s: string) => s.trim().toUpperCase()).filter(Boolean), remote: f.v.remote, price_info: f.v.price_info || null,
          accepting_requests: f.v.accepting_requests }), "Perfil salvo"); }}>
          <Field label="Especialidades" wide><Chips options={Object.entries(tax?.professional_categories || {}) as any} value={f.v.categories} onChange={f.set("categories")} /></Field>
          <Field label="Serviços (um por linha)" wide><TextArea rows={4} value={f.v.services} onChange={f.set("services")} /></Field>
          <Field label="Territórios"><Input value={f.v.territories} onChange={f.set("territories")} /></Field>
          <Field label="Faixa de honorários (informativa)"><Input value={f.v.price_info} onChange={f.set("price_info")} /></Field>
          <label className="check"><input type="checkbox" checked={f.v.remote} onChange={(e: any) => f.set("remote")(e.target.checked)} /> Atendo remotamente</label>
          <label className="check"><input type="checkbox" checked={f.v.accepting_requests} onChange={(e: any) => f.set("accepting_requests")(e.target.checked)} /> Aceitando novas solicitações</label>
          <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>Salvar</Button></div>
        </form>
      </Panel>
      <Panel title="Credenciais profissionais" actions={<span className="muted">A administração confere no cadastro público do conselho antes de liberar validações</span>}>
        <ul className="rows">{creds.data?.items.map((x: any) => (
          <li key={x.id}><span>{x.council}/{x.uf} {x.number} — {x.holder_name}<br /><span className="muted">validade {date(x.valid_until)}{x.verification_note && ` · ${x.verification_note}`}</span></span><Pill status={x.verification_status} /></li>
        ))}</ul>
        <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/org/credentials", { ...c.v, uf: c.v.uf || null, valid_until: c.v.valid_until || null, document_id: c.v.document_id || null }), "Credencial enviada para verificação").then((r) => r && creds.reload()); }}>
          <Field label="Conselho"><Select value={c.v.council} onChange={c.set("council")} options={Object.keys(tax?.councils || { CRC: 1 }).map((k) => [k, k])} /></Field>
          <Field label="Número"><Input value={c.v.number} onChange={c.set("number")} /></Field>
          <Field label="UF"><Select value={c.v.uf} onChange={c.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
          <Field label="Nome no registro"><Input value={c.v.holder_name} onChange={c.set("holder_name")} /></Field>
          <Field label="Validade"><Input type="date" value={c.v.valid_until} onChange={c.set("valid_until")} /></Field>
          <Field label="Comprovante"><UploadButton docType="credencial_profissional" onUploaded={(d) => c.set("document_id")(d.id)} done={!!c.v.document_id} /></Field>
          <Button type="submit" variant="ink" busy={busy}>Adicionar credencial</Button>
        </form>
      </Panel>
    </>
  );
}

export function Compliance() {
  const { data, error, loading, reload } = useLoad<any>("/v1/compliance");
  const { reload: reloadMe } = useSession();
  const { busy, run } = useAction();
  const CHECK: Record<string, string> = { cnpj_format: "CNPJ válido", cnpj_registry: "Situação cadastral na Receita", sanctions_ceis_cnep: "Listas de sanções (CEIS/CNEP)",
    documents_basic: "Documentos institucionais", documents_expiring: "Validade dos documentos", profile_completeness: "Perfil completo", open_reports: "Denúncias em aberto" };
  return (
    <>
      <PageHead title="Verificação do cadastro" sub="Necessária para receber aprovação de financiadores e publicar editais. A decisão final é humana."
        back={<Link to="/organizacao" className="back">Organização</Link>}
        actions={data?.compliance_status !== "in_review" && <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/compliance/request-review"), "Verificação solicitada").then(() => { reload(); reloadMe(); })}>Solicitar verificação</Button>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Situação">
              <KeyValue items={[["Status", <Pill key="s" status={data.compliance_status} />], ["Risco", data.compliance_risk || "—"], ["Última decisão", date(data.compliance_reviewed_at)]]} />
            </Panel>
            <Panel title="Verificações automáticas">
              {data.checks.length === 0 ? <p className="muted">Ainda não executadas.</p> : (
                <ul className="rows">{data.checks.map((c: any) => (
                  <li key={c.check_type}><span><strong>{CHECK[c.check_type] || c.check_type}</strong><br /><span className="muted">
                    {c.details?.missing?.length ? `Faltam: ${c.details.missing.join(", ")}` : c.details?.message || (c.details?.missing_fields?.length ? `Complete: ${c.details.missing_fields.join(", ")}` : `fonte: ${c.source}`)}</span></span>
                    <Pill tone={c.status === "pass" ? "good" : c.status === "fail" ? "bad" : c.status === "not_configured" ? "muted" : "warn"}>
                      {({ pass: "ok", fail: "falhou", warning: "atenção", pending: "pendente", error: "erro na consulta", not_configured: "não configurada" } as any)[c.status]}</Pill></li>
                ))}</ul>
              )}
            </Panel>
            {data.reviews.length > 0 && <Panel title="Histórico de análises"><ul className="rows">{data.reviews.map((r: any) => <li key={r.id}><span>{date(r.created_at)}{r.decision_note && ` — ${r.decision_note}`}</span><Pill status={r.status} /></li>)}</ul></Panel>}
          </>
        )}
      </StateView>
    </>
  );
}

export function Team() {
  const { me } = useSession();
  const members = useLoad<any>("/v1/org/members");
  const isAdmin = ["owner", "admin"].includes(me?.active_org?.role || "");
  const invites = useLoad<any>(isAdmin ? "/v1/org/invitations" : null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const { busy, run } = useAction();
  const ROLES: [string, string][] = [["admin", "Administrador"], ["manager", "Gestor"], ["analyst", "Analista"], ["member", "Membro"], ["viewer", "Leitura"]];
  return (
    <>
      <PageHead title="Equipe" back={<Link to="/organizacao" className="back">Organização</Link>} />
      {isAdmin && (
        <Panel title="Convidar pessoa">
          <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/org/invitations", { email, role }), "Convite enviado").then((r) => { if (r) { setEmail(""); invites.reload(); } }); }}>
            <Field label="E-mail"><Input type="email" value={email} onChange={setEmail} /></Field>
            <Field label="Papel"><Select value={role} onChange={setRole} options={ROLES} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Enviar convite</Button>
          </form>
        </Panel>
      )}
      <Panel title="Membros">
        <StateView loading={members.loading} error={members.error}>
          <table className="table">
            <thead><tr><th>Nome</th><th>E-mail</th><th>Papel</th><th>MFA</th>{isAdmin && <th />}</tr></thead>
            <tbody>{members.data?.items.map((m: any) => (
              <tr key={m.user_id}><td>{m.full_name}</td><td>{m.email}</td>
                <td>{isAdmin && m.role !== "owner" && m.user_id !== me?.user.id ? (
                  <Select value={m.role} onChange={(v) => run(() => api.patch(`/v1/org/members/${m.user_id}`, { role: v }), "Papel alterado").then(members.reload)} options={ROLES} />
                ) : label(m.role === "owner" ? "Proprietário" : m.role)}</td>
                <td>{m.mfa_enabled ? <Pill tone="good">ativo</Pill> : <Pill tone="muted">não</Pill>}</td>
                {isAdmin && <td>{m.role !== "owner" && m.user_id !== me?.user.id && <Button variant="link" onClick={() => confirm(`Remover ${m.full_name}?`) && run(() => api.del(`/v1/org/members/${m.user_id}`), "Membro removido").then(members.reload)}>Remover</Button>}</td>}
              </tr>
            ))}</tbody>
          </table>
        </StateView>
      </Panel>
      {isAdmin && invites.data?.items.length > 0 && (
        <Panel title="Convites">
          <ul className="rows">{invites.data.items.map((i: any) => (
            <li key={i.id}><span>{i.email} · {label(i.role)}<br /><span className="muted">{i.accepted_at ? `aceito ${date(i.accepted_at)}` : i.revoked_at ? "revogado" : `expira ${date(i.expires_at)}`}</span></span>
              {!i.accepted_at && !i.revoked_at && <Button variant="link" onClick={() => run(() => api.del(`/v1/org/invitations/${i.id}`), "Convite revogado").then(invites.reload)}>Revogar</Button>}</li>
          ))}</ul>
        </Panel>
      )}
    </>
  );
}

export function Account() {
  const { me, reload, logout } = useSession();
  const sessions = useLoad<any>("/v1/auth/sessions");
  const [setup, setSetup] = useState<any>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const pw = useForm({ current_password: "", new_password: "" });
  const [del, setDel] = useState(false);
  const [delPw, setDelPw] = useState("");
  const { busy, run } = useAction();
  if (!me) return null;
  return (
    <>
      <PageHead title="Minha conta" sub={`${me.user.full_name} · ${me.user.email}`} />
      <div className="split">
        <Panel title="Verificação em duas etapas">
          {me.user.mfa_enabled ? <p><Pill tone="good">Ativa</Pill> Seu login pede um código do aplicativo autenticador.</p> : (
            <>
              <p className="muted">{me.user.is_platform_admin ? "Obrigatória para a área administrativa." : "Recomendada para quem aprova, assina ou administra."}</p>
              {!setup ? <Button variant="ink" busy={busy} onClick={() => run(() => api.post("/v1/auth/mfa/setup")).then(setSetup)}>Configurar</Button> : (
                <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/auth/mfa/enable", { code }), "Verificação em duas etapas ativada").then((r: any) => { if (r) { setCodes(r.recovery_codes); setSetup(null); reload(); } }); }}>
                  <p>No aplicativo autenticador, adicione uma conta com a chave abaixo (ou abra o link no celular):</p>
                  <code className="secret">{setup.secret.match(/.{1,4}/g).join(" ")}</code>
                  <a href={setup.otpauth_uri}>Abrir no aplicativo autenticador</a>
                  <Field label="Código de 6 dígitos"><Input inputMode="numeric" value={code} onChange={setCode} /></Field>
                  <Button type="submit" variant="primary" busy={busy}>Ativar</Button>
                </form>
              )}
            </>
          )}
          {codes && (
            <div className="assist">
              <p><strong>Guarde estes códigos de recuperação.</strong> Cada um funciona uma vez, se você perder o celular. Eles não serão mostrados novamente.</p>
              <ul className="codes">{codes.map((c) => <li key={c}><code>{c}</code></li>)}</ul>
            </div>
          )}
        </Panel>
        <Panel title="Senha">
          <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/auth/change-password", pw.v), "Senha alterada; outras sessões foram encerradas").then((r) => r && pw.setV({ current_password: "", new_password: "" })); }}>
            <Field label="Senha atual"><Input type="password" autoComplete="current-password" value={pw.v.current_password} onChange={pw.set("current_password")} /></Field>
            <Field label="Nova senha" hint="Mínimo de 10 caracteres"><Input type="password" autoComplete="new-password" value={pw.v.new_password} onChange={pw.set("new_password")} /></Field>
            <Button type="submit" variant="ink" busy={busy}>Alterar senha</Button>
          </form>
        </Panel>
      </div>
      <Panel title="Sessões ativas" actions={<Button variant="ghost" onClick={() => run(() => api.post("/v1/auth/logout-all")).then(async () => { await logout(); navigate("/entrar"); })}>Sair de todos os dispositivos</Button>}>
        <ul className="rows">{sessions.data?.items.map((s: any) => (
          <li key={s.id}><span>{s.user_agent?.slice(0, 80) || "Dispositivo"}{s.current && <strong> (esta sessão)</strong>}<br /><span className="muted">{s.ip} · ativa em {dateTime(s.last_seen_at)}</span></span>
            {!s.current && <Button variant="link" onClick={() => run(() => api.del(`/v1/auth/sessions/${s.id}`), "Sessão encerrada").then(sessions.reload)}>Encerrar</Button>}</li>
        ))}</ul>
      </Panel>
      <Panel title="Privacidade e dados pessoais (LGPD)">
        <p>Você pode baixar uma cópia dos seus dados ou excluir sua conta. Registros financeiros e de auditoria permanecem pseudonimizados pelo prazo legal.</p>
        <div className="stack-row">
          <a className="btn btn-ghost" href="/v1/privacy/export">Baixar meus dados</a>
          <Button variant="danger" onClick={() => setDel(true)}>Excluir minha conta</Button>
          <Link to="/legal/privacidade">Política de privacidade</Link>
        </div>
      </Panel>
      <Modal open={del} title="Excluir conta" onClose={() => setDel(false)} footer={
        <Button variant="danger" busy={busy} onClick={() => run(() => api.post("/v1/privacy/delete-account", { password: delPw, confirm: true }), "Conta excluída").then(async (r) => { if (r) { await logout(); navigate("/"); } })}>Excluir definitivamente</Button>}>
        <p>Seus dados pessoais serão anonimizados e todas as sessões encerradas. Se você é o único proprietário de uma organização com outros membros, transfira a propriedade antes.</p>
        <Field label="Confirme sua senha"><Input type="password" value={delPw} onChange={setDelPw} /></Field>
      </Modal>
    </>
  );
}

export function Plan() {
  const { me, reload: reloadMe } = useSession();
  const plans = useLoad<any>("/v1/plans");
  const billing = useLoad<any>("/v1/billing");
  const [code, setCode] = useState("");
  const { busy, run } = useAction();
  const kind = me?.active_org?.kind;
  const role = kind === "company" ? "company" : kind;
  const current = new Set(me?.entitlements?.plans || []);
  const FEATURE: Record<string, string> = { "catalog.search": "Banco de oportunidades", "match.explain": "Compatibilidade explicada", "applications.assisted": "Candidatura assistida",
    "documents.vault": "Cofre de documentos", "evidence.post": "Evidências e prestação de contas", "professional.request": "Validação por profissionais parceiros",
    "alerts.saved_search": "Rastreio automático e alertas de editais", "opportunity.tracking": "Acompanhamento de oportunidades", "ai.assist.advanced": "Mais assistência de IA",
    "reports.export": "Exportação de relatórios", templates: "Modelos", "feed.projects": "Feed de projetos", "portfolio.tracking": "Rastreio do investimento",
    "reports.basic": "Relatórios", "reports.advanced": "Relatórios avançados", "conflict.management": "Gestão de conflito de interesse", "fiscal.estimates": "Incentivos fiscais (estimativas)",
    "territory.analytics": "Análise territorial", sso: "Login corporativo (SSO)", "audit.export": "Exportação de auditoria", "api.access": "Acesso à API",
    "directory.listing": "Presença no diretório", "reviews.receive": "Receber solicitações", "signatures.sign": "Assinar com credencial", "calls.publish": "Publicar editais",
    "materials.publish": "Publicar materiais", "gov.data": "Dados do território" };
  return (
    <>
      <PageHead title="Plano" sub={me?.entitlements?.plan_names?.join(" + ")} />
      {plans.data && !plans.data.billing_live && <p className="banner">Cobrança online em modo {plans.data.billing_provider === "sandbox" ? "de testes (nenhuma cobrança real)" : "não configurado"}. Contratações podem ser feitas por proposta comercial ou voucher.</p>}
      <StateView loading={plans.loading} error={plans.error} onRetry={plans.reload}>
        <div className="plans">
          {plans.data?.items.filter((p: any) => p.role === role).map((p: any) => (
            <article key={p.plan_key} className={`plan${current.has(p.plan_key) ? " plan-current" : ""}`}>
              <h2>{p.name}</h2>
              <p className="plan-price">{p.price_cents === 0 ? "Gratuito" : p.price_cents ? `${money(p.price_cents)} / ${p.interval === "year" ? "ano" : "mês"}` : "Sob proposta"}</p>
              <ul>{p.features.map((f: string) => <li key={f}>{FEATURE[f] || f}</li>)}</ul>
              <p className="muted">{Object.entries(p.limits).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v === null ? "ilimitado" : v}`).join(" · ")}</p>
              {current.has(p.plan_key) ? <Pill tone="good">Plano atual</Pill> : p.price_cents ? (
                <Button variant="primary" busy={busy} disabled={!p.available || me?.active_org?.role !== "owner"}
                  onClick={() => run(() => api.post("/v1/billing/checkout", { plan_key: p.plan_key })).then(async (r: any) => { if (r?.url) location.href = r.url; else if (r) { await reloadMe(); billing.reload(); } })}>Contratar</Button>
              ) : p.price_cents === null && <a className="btn btn-ghost" href="mailto:comercial@impacto.app">Solicitar proposta</a>}
            </article>
          ))}
        </div>
      </StateView>
      <div className="split">
        <Panel title="Tenho um voucher">
          <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/vouchers/redeem", { code }), "Voucher aplicado").then(async (r) => { if (r) { setCode(""); await reloadMe(); billing.reload(); } }); }}>
            <Field label="Código"><Input value={code} onChange={(v) => setCode(v.toUpperCase())} placeholder="XXXX-XXXX-XXXX" /></Field>
            <Button type="submit" variant="ink" busy={busy}>Aplicar</Button>
          </form>
        </Panel>
        <Panel title="Assinatura e faturas" actions={billing.data?.entitlements?.subscription && <Button variant="link" onClick={() => confirm("Cancelar a assinatura? Seus dados não serão apagados.") && run(() => api.post("/v1/billing/cancel"), "Cancelamento solicitado").then(reloadMe)}>Cancelar assinatura</Button>}>
          {billing.data?.entitlements?.subscription && <p>Assinatura: <Pill status={billing.data.entitlements.subscription.status} /> até {date(billing.data.entitlements.subscription.current_period_end)}</p>}
          <ul className="rows">{billing.data?.invoices.map((i: any) => <li key={i.id}><span>{i.description || "Assinatura"} · {date(i.created_at)}</span><span>{money(i.amount_cents)} <Pill status={i.status} /></span></li>)}
            {billing.data?.invoices.length === 0 && <li className="muted">Nenhuma fatura.</li>}</ul>
        </Panel>
      </div>
    </>
  );
}

export function Fiscal() {
  const { can } = useSession();
  const tp = useLoad<any>("/v1/org/tax-profile");
  const est = useLoad<any>(can("fiscal.estimates") ? "/v1/fiscal/estimates" : null);
  const f = useForm<any>({ regime: "unknown", fiscal_year: "", ir: "", uf: "" });
  const { busy, run } = useAction();
  useEffect(() => { if (tp.data) f.setV({ regime: tp.data.regime, fiscal_year: tp.data.fiscal_year || "", ir: centsToInput(tp.data.estimated_ir_due_cents), uf: tp.data.uf || "" }); }, [tp.data]);  // eslint-disable-line
  return (
    <>
      <PageHead title="Incentivos fiscais" sub="Mecanismos possivelmente aplicáveis, a partir de regras revisadas por especialistas. Não é aconselhamento tributário." />
      <Panel title="Perfil fiscal da empresa">
        <form className="inline-form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.put("/v1/org/tax-profile", { regime: f.v.regime, fiscal_year: f.v.fiscal_year ? Number(f.v.fiscal_year) : null, estimated_ir_due_cents: parseMoney(f.v.ir), uf: f.v.uf || null }), "Perfil fiscal salvo").then(() => est.reload()); }}>
          <Field label="Regime"><Select value={f.v.regime} onChange={f.set("regime")} options={[["lucro_real", "Lucro real"], ["lucro_presumido", "Lucro presumido"], ["simples", "Simples Nacional"], ["isenta", "Isenta/imune"], ["unknown", "Não informado"]]} /></Field>
          <Field label="Ano-calendário"><Input inputMode="numeric" value={f.v.fiscal_year} onChange={f.set("fiscal_year")} /></Field>
          <Field label="IR devido estimado (R$)" hint="Usado só para calcular tetos estimados"><Input inputMode="decimal" value={f.v.ir} onChange={f.set("ir")} /></Field>
          <Field label="UF"><Select value={f.v.uf} onChange={f.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
          <Button type="submit" variant="ink" busy={busy}>Salvar</Button>
        </form>
      </Panel>
      {!can("fiscal.estimates") ? <Panel title="Estimativas"><p>Disponível no plano Empresa Impacto ou superior.</p><Button variant="primary" onClick={() => navigate("/conta/plano")}>Ver planos</Button></Panel> : (
        <StateView loading={est.loading} error={est.error} onRetry={est.reload}>
          {est.data && (
            <>
              <p className="banner">{est.data.disclaimer}</p>
              {est.data.notice && <p className="muted">{est.data.notice}</p>}
              {est.data.items.map((it: any) => (
                <Panel key={it.rule.code} title={it.rule.name} actions={<Pill tone={it.eligibility.status === "provavel" ? "good" : it.eligibility.status === "improvavel" ? "bad" : "warn"}>
                  Elegibilidade {it.eligibility.status === "provavel" ? "provável" : it.eligibility.status === "improvavel" ? "improvável" : "indeterminada"}</Pill>}>
                  <div className="fiscal-grid">
                    <div><h3>Regra</h3><p>{it.rule.source_citation} · versão {it.rule.version}</p>{it.rule.source_url && <a href={it.rule.source_url} target="_blank" rel="noopener noreferrer">Fonte oficial</a>}{it.rule.limit_note && <p className="muted">{it.rule.limit_note}</p>}</div>
                    <div><h3>Elegibilidade provável</h3><ul>{it.eligibility.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul></div>
                    <div><h3>Estimativa</h3>{it.estimate ? <><p className="big-figure">até {money(it.estimate.max_deductible_cents)}</p><p className="muted">{it.estimate.basis}. {it.estimate.notes}</p></> : <p className="muted">Sem estimativa para esta regra.</p>}</div>
                    <div><h3>Validação profissional</h3><p>Obrigatória antes de qualquer decisão.</p>{it.checklist.length > 0 && <ul>{it.checklist.map((c: any) => <li key={c.code}>{c.label}</li>)}</ul>}</div>
                  </div>
                </Panel>
              ))}
            </>
          )}
        </StateView>
      )}
    </>
  );
}

export function Materials() {
  const { me } = useSession();
  const canPublish = ["government", "platform"].includes(me?.active_org?.kind || "");
  const { data, error, loading, reload } = useLoad<any>("/v1/materials?limit=100");
  const [open, setOpen] = useState(false);
  const f = useForm({ title: "", summary: "", category: "guide", url: "", status: "published", document_id: "" });
  const { busy, run } = useAction();
  const CAT: Record<string, string> = { guide: "Guia", legislation: "Legislação", template: "Modelo", data: "Dados", manual: "Manual", training: "Capacitação", other: "Outro" };
  return (
    <>
      <PageHead title="Materiais" sub="Guias, legislação, modelos e dados publicados por órgãos públicos e pela plataforma." actions={canPublish && <Button variant="primary" onClick={() => setOpen(true)}>Publicar material</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhum material publicado ainda."}>
        <ul className="calls">{data?.items.map((m: any) => (
          <li key={m.id} className="call"><div className="call-main"><p className="call-funder">{CAT[m.category]} · {m.publisher}</p><h3>{m.title}</h3>{m.summary && <p>{m.summary}</p>}
            <p className="call-facts">{m.url && <a href={m.url} target="_blank" rel="noopener noreferrer">Abrir fonte</a>}{m.document_id && <span>Arquivo anexo</span>}<span className="muted">{date(m.published_at)}</span></p></div></li>
        ))}</ul>
      </StateView>
      <Modal open={open} title="Publicar material" onClose={() => setOpen(false)} footer={
        <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/materials", { ...f.v, url: f.v.url || null, summary: f.v.summary || null, document_id: f.v.document_id || null }), "Material publicado").then((r) => { if (r) { setOpen(false); reload(); } })}>Publicar</Button>}>
        <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Resumo"><TextArea rows={3} value={f.v.summary} onChange={f.set("summary")} /></Field>
        <Field label="Categoria"><Select value={f.v.category} onChange={f.set("category")} options={Object.entries(CAT) as any} /></Field>
        <Field label="Link (opcional)"><Input value={f.v.url} onChange={f.set("url")} placeholder="https://" /></Field>
        <Field label="Arquivo (opcional)"><UploadButton docType="material_governo" onUploaded={(d) => f.set("document_id")(d.id)} done={!!f.v.document_id} /></Field>
      </Modal>
    </>
  );
}

export function GovData() {
  const tax = useTaxonomy();
  const [terr, setTerr] = useState("BR");
  const [q, setQ] = useState("BR");
  const { data, error, loading, reload } = useLoad<any>(`/v1/gov/territory-stats?territory=${q}`, [q]);
  const byCause: Record<string, number> = {};
  for (const g of data?.groups || []) byCause[g.cause] = (byCause[g.cause] || 0) + Number(g.committed_cents);
  return (
    <>
      <PageHead title="Dados do território" sub="Agregados anonimizados: grupos com menos de 3 projetos não são exibidos." />
      <form className="filters" onSubmit={(e: any) => { e.preventDefault(); setQ(terr); }}>
        <Field label="Território" hint="BR, BR-MT ou BR-MT-5105259"><Input value={terr} onChange={(v) => setTerr(v.toUpperCase())} /></Field>
        <Button type="submit" variant="ink">Consultar</Button>
      </form>
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <div className="grid-home">
            <Panel title="Recursos comprometidos por causa"><Bars rows={Object.entries(byCause).map(([k, v]) => ({ label: tax?.causes?.[k] || k, value: v }))} format={money} /></Panel>
            <Panel title="Editais abertos por esfera"><Bars rows={data.open_calls_by_sphere.map((r: any) => ({ label: `${r.sphere} · ${r.instrument}`, value: r.n, tone: "ochre" }))} format={(v) => n(v)} /></Panel>
            <Panel title="Detalhe por município e causa">
              <table className="table"><thead><tr><th>Território</th><th>Causa</th><th>Projetos</th><th>Beneficiários</th><th>Comprometido</th><th>Evidências aceitas</th></tr></thead>
                <tbody>{data.groups.map((g: any) => <tr key={g.territory + g.cause}><td>{g.territory}</td><td>{tax?.causes?.[g.cause] || g.cause}</td><td>{g.projects}</td><td>{n(g.beneficiaries)}</td><td>{money(g.committed_cents)}</td><td>{g.accepted_evidences}</td></tr>)}
                  {data.groups.length === 0 && <tr><td colSpan={6} className="muted">Sem grupos com dados suficientes para exibição anônima.</td></tr>}</tbody></table>
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}
