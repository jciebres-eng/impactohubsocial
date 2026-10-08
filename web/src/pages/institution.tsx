import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, qs } from "../api";
import { date, dateTime, money, parseMoney } from "../format";
import { Link } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, KeyValue, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";
import { UploadButton } from "./documents";
import { AdminAgreements, AdminMentoring, AgreementsTab, FormalizationTab, PersonaTab } from "./institution_extra";

// ------------------------------------------------------------------------------------------------ rótulos e tons
const ELIG_TONE: Record<string, string> = { eligible: "good", probably_eligible: "good", pending: "warn", needs_professional_validation: "warn", not_eligible: "bad" };
const REQ_TONE: Record<string, string> = { met: "good", unmet: "bad", expired: "bad", pending_validation: "warn", unknown: "warn" };
const QUAL_TONE: Record<string, string> = { verified: "good", declared: "muted", document_submitted: "warn", under_review: "warn", rejected: "bad", revoked: "bad", expired: "bad" };
const DOC_TONE: Record<string, string> = { validated: "good", pending_validation: "warn", absent: "muted", expired: "bad", rejected: "bad" };
const NEED_LABEL: Record<string, string> = { financing: "Financiamento", partner: "Parceria", replication: "Replicação", technical: "Apoio técnico", institutional: "Fortalecimento institucional", territorial_expansion: "Expansão territorial" };
const FEATURE_NOTE = "Informações declaradas pela organização só viram “verificadas” depois da conferência da administração. A plataforma não emite certificação oficial.";

function catOptions(cat: any, key: string): [string, string][] {
  return ((cat?.catalogs?.[key] || []) as any[]).map((i) => [i.code, i.label]);
}

function PersonaIntro({ kind, hasCnpj, level }: { kind: string; hasCnpj: boolean; level?: number }) {
  let title = "";
  let text = "";
  if (kind === "osc" && !hasCnpj) {
    title = "Iniciativa em estruturação";
    text = "Sem CNPJ você pode participar do Banco de Ideias, da Biblioteca de Soluções e da rede. Para concorrer a editais e receber recursos é preciso formalizar a organização — veja o caminho abaixo e consulte um profissional habilitado.";
  } else if (kind === "osc") {
    title = "Sua organização como proponente";
    text = "Natureza jurídica, qualificações (como OSC, OSCIP, OS, CEBAS) e documentos são coisas diferentes. Cada oportunidade define o que exige; aqui você vê o que já está comprovado e o que falta.";
  } else if (kind === "company") {
    title = "Empresa, instituto ou fundação financiadora";
    text = "Defina no perfil de investimento quais naturezas jurídicas, qualificações e nível de maturidade você exige. Projetos que não atendem aparecem bloqueados, com o motivo explicado.";
  } else if (kind === "government") {
    title = "Órgão público";
    text = "Ao cadastrar editais, informe modalidade, naturezas jurídicas aceitas e maturidade mínima. A plataforma avalia cada proponente com esses critérios e mostra o que falta a ele.";
  } else if (kind === "provider") {
    title = "Profissional ou pesquisador";
    text = "Seu perfil institucional é individual. Qualificações como OSC/OSCIP/OS se aplicam a organizações; sua credencial profissional é verificada em Validações.";
  } else {
    title = "Apoiador pessoa física";
    text = "Informe seu perfil de atuação. Os critérios institucionais se aplicam a quem propõe e recebe recursos.";
  }
  return (
    <Panel title={title} quiet>
      <p>{text}</p>
      {typeof level === "number" && <p className="muted">Maturidade institucional atual: nível {level} de 6.</p>}
      <p className="muted">{FEATURE_NOTE}</p>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ página principal
export function Institution() {
  const { me } = useSession();
  const kind = me?.active_org?.kind || "osc";
  const proponent = kind === "osc";
  const tabs: [string, string][] = [["resumo", "Resumo"], ["perfil", "Perfil"]];
  if (proponent || kind === "company" || kind === "government") tabs.push(["documentos", "Documentos"]);
  if (proponent) tabs.push(["qualificacoes", "Qualificações"], ["perfis", "OS / OSCIP"], ["instrumentos", "Instrumentos"], ["elegibilidade", "Elegibilidade"], ["formalizacao", "Formalização e mentoria"], ["necessidades", "Necessidades"]);
  tabs.push(["conquistas", "Conquistas"]);
  if (proponent) tabs.push(["declaracao", "Declaração"]);
  const [tab, setTab] = useState("resumo");
  return (
    <>
      <PageHead title="Instituição" sub="Natureza jurídica, qualificações, documentos e elegibilidade — o que está comprovado e o que falta." />
      <div className="tabs" role="tablist">
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab${tab === k ? " on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "resumo" && <Summary kind={kind} />}
      {tab === "perfil" && <ProfileTab kind={kind} />}
      {tab === "documentos" && <DocumentsTab />}
      {tab === "qualificacoes" && <QualificationsTab />}
      {tab === "perfis" && <PersonaTab />}
      {tab === "instrumentos" && <AgreementsTab />}
      {tab === "formalizacao" && <FormalizationTab />}
      {tab === "elegibilidade" && <EligibilityTab />}
      {tab === "necessidades" && <NeedsTab />}
      {tab === "conquistas" && <BadgesTab />}
      {tab === "declaracao" && <StatementTab />}
    </>
  );
}

// ------------------------------------------------------------------------------------------------ resumo
function Summary({ kind }: { kind: string }) {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/overview");
  const mat = data?.maturity;
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <PersonaIntro kind={kind} hasCnpj={!!data.organization.cnpj_present} level={mat?.applicable ? mat.level : undefined} />
          <div className="grid-home">
            <Panel title={data.participation.label}>
              <ul className="rows">{data.participation.scope.map((s: string) => <li key={s}><span>{s}</span><Pill tone="good">Sim</Pill></li>)}</ul>
            </Panel>
            <Panel title={data.can_receive.label}>
              {data.can_receive.modalities.length ? (
                <ul className="rows">{data.can_receive.modalities.map((m: any) => <li key={m.modality}><span>{m.label}<br /><span className="muted">{m.state_label}</span></span><Pill tone={ELIG_TONE[m.state] || "muted"}>{m.state_label}</Pill></li>)}</ul>
              ) : <p className="muted">Nenhuma modalidade confirmada. Onde não há regra publicada, não foi possível confirmar — isso não significa que você esteja apta ou inapta.</p>}
            </Panel>
            <Panel title={data.needs.label}>
              {data.needs.items.length ? data.needs.items.map((n: any) => (
                <div key={n.modality}><strong>{n.label}</strong>
                  <ul>{n.missing.map((m: any, i: number) => <li key={i}>{m.requirement}{m.action ? <span className="muted"> — {m.action}</span> : null}</li>)}</ul></div>
              )) : <p className="muted">Sem pendências identificadas nas regras publicadas.</p>}
            </Panel>
          </div>
          {mat?.applicable && <Maturity m={mat} />}
          <Panel title="Modalidades de financiamento" quiet>
            <table className="table"><thead><tr><th>Modalidade</th><th>Situação</th></tr></thead>
              <tbody>{data.modalities.map((m: any) => <tr key={m.modality}><td>{m.label}</td><td><Pill tone={m.evaluable ? ELIG_TONE[m.state] || "muted" : "muted"}>{m.state_label}</Pill></td></tr>)}</tbody></table>
            <p className="muted">{data.disclaimer}</p>
          </Panel>
        </>
      )}
    </StateView>
  );
}

function Maturity({ m }: { m: any }) {
  return (
    <Panel title={`Maturidade institucional: nível ${m.level} — ${m.label}`}>
      {m.next ? (
        <>
          <p>Para o nível {m.next.level} ({m.next.label}):</p>
          <ul className="rows">{m.next.requirements.map((r: any) => (
            <li key={r.code}><span><strong>{r.label}</strong><br /><span className="muted">{r.detail}{!r.met && r.how_to_fix ? ` — ${r.how_to_fix}` : ""}</span></span><Pill tone={r.met ? "good" : "warn"}>{r.met ? "Atendido" : "Falta"}</Pill></li>
          ))}</ul>
        </>
      ) : <p>Nível máximo atingido.</p>}
      {m.path?.length > 0 && (
        <details>
          <summary>Caminho de formalização e fortalecimento</summary>
          <ol>{m.path.map((p: any) => (
            <li key={p.level}><strong>Nível {p.level} — {p.label}</strong> {p.done && <Pill tone="good">Concluído</Pill>}
              <ul>{p.steps.map((s: any, i: number) => <li key={i}>{s.text} <span className="muted">({s.area})</span></li>)}</ul></li>
          ))}</ol>
        </details>
      )}
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ perfil
function ProfileTab({ kind }: { kind: string }) {
  const { me } = useSession();
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/profile");
  const cat = useLoad<any>("/v1/institutional/catalogs");
  const f = useForm<any>({});
  const { busy, run } = useAction();
  const canEdit = ["owner", "admin"].includes(me?.active_org?.role || "");
  useEffect(() => {
    if (data) {
      const o = data.organization;
      f.setV({ legal_nature_code: o.legal_nature_code || "", institutional_profile: o.institutional_profile || "", mission: o.mission || "", vision: o.vision || "",
        geographic_scope: o.geographic_scope || "", operating_regions: (o.operating_regions || []).join(", ") });
    }
  }, [data]);  // eslint-disable-line
  const natures = (cat.data?.catalogs?.legal_nature || []).filter((n: any) => !n.attributes?.allowed_kinds || n.attributes.allowed_kinds.includes(kind));
  const sel = natures.find((n: any) => n.code === f.v.legal_nature_code);
  async function save(e: any) {
    e.preventDefault();
    const body: any = { mission: f.v.mission || null, vision: f.v.vision || null, geographic_scope: f.v.geographic_scope || null,
      operating_regions: (f.v.operating_regions || "").split(",").map((s: string) => s.trim().toUpperCase()).filter(Boolean) };
    if (f.v.legal_nature_code) body.legal_nature_code = f.v.legal_nature_code;
    if (f.v.institutional_profile) body.institutional_profile = f.v.institutional_profile;
    await run(() => api.put("/v1/institutional/profile", body), "Perfil institucional salvo");
    reload();
  }
  const o = data?.organization;
  return (
    <StateView loading={loading || cat.loading} error={error || cat.error} onRetry={reload}>
      {o && (
        <div className="split">
          <Panel title="Identificação">
            <KeyValue items={[
              ["Natureza jurídica", <>{o.labels.legal_nature || "Não informada"} {o.legal_nature_code && <Pill tone="muted">declarada</Pill>}</>],
              ["Perfil de atuação", o.labels.institutional_profile || "Não informado"],
              ["Situação institucional", <><Pill tone={o.institutional_status === "regular" ? "good" : o.institutional_status === "irregular" || o.institutional_status === "suspended" ? "bad" : "warn"}>{o.labels.institutional_status}</Pill>{o.institutional_status_note && <span className="muted"> {o.institutional_status_note}</span>}</>],
              ["CNPJ", o.cnpj || "Sem CNPJ cadastrado"],
              ["Sede", [o.headquarters.city, o.headquarters.uf].filter(Boolean).join(" / ") || "—"],
            ]} />
            <p className="muted">{data.notes.join(" ")}</p>
          </Panel>
          <Panel title="Natureza e perfil">
            <form className="form" onSubmit={save}>
              <fieldset disabled={!canEdit} className="form-wide-fieldset">
                <Field label="Natureza jurídica" hint={sel ? `${sel.description || ""}${sel.attributes?.requires_cnpj ? " Exige CNPJ." : ""}` : "É diferente de qualificação (OSC, OSCIP, OS…)."}>
                  <Select value={f.v.legal_nature_code} onChange={f.set("legal_nature_code")} placeholder="Selecione" options={natures.map((n: any) => [n.code, n.label])} />
                </Field>
                <Field label="Perfil de atuação" hint="Como a organização atua (cultural, saúde, educação…). Não é natureza jurídica.">
                  <Select value={f.v.institutional_profile} onChange={f.set("institutional_profile")} placeholder="Selecione" options={catOptions(cat.data, "institutional_profile")} />
                </Field>
                <Field label="Missão" wide><TextArea rows={3} value={f.v.mission} onChange={f.set("mission")} /></Field>
                <Field label="Visão" wide><TextArea rows={3} value={f.v.vision} onChange={f.set("vision")} /></Field>
                <Field label="Alcance geográfico"><Select value={f.v.geographic_scope} onChange={f.set("geographic_scope")} placeholder="—" options={[["local", "Local"], ["municipal", "Municipal"], ["regional", "Regional"], ["estadual", "Estadual"], ["nacional", "Nacional"], ["internacional", "Internacional"]]} /></Field>
                <Field label="Regiões de atuação" hint="Separadas por vírgula (ex.: BR-MT, BR-MT-5103403)"><Input value={f.v.operating_regions} onChange={f.set("operating_regions")} /></Field>
                {canEdit && <div className="form-actions"><Button type="submit" variant="primary" busy={busy}>Salvar</Button></div>}
              </fieldset>
            </form>
          </Panel>
        </div>
      )}
    </StateView>
  );
}

// ------------------------------------------------------------------------------------------------ documentos
function DocumentsTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/documents");
  const [docType, setDocType] = useState("estatuto_social");
  return (
    <Panel title="Documentos institucionais" actions={<>
      <Select aria-label="Tipo do documento" value={docType} onChange={setDocType} options={(data?.items || []).map((i: any) => [i.doc_type, i.label] as [string, string])} />
      <UploadButton docType={docType} onUploaded={reload} /></>}>
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {data.missing_base.length > 0 && <p className="banner">Documentos básicos ausentes: {data.items.filter((i: any) => i.base && i.state === "absent").map((i: any) => i.label).join(", ")}.</p>}
            <table className="table"><thead><tr><th>Documento</th><th>Estado</th><th>Validade</th><th>Versões</th></tr></thead>
              <tbody>{data.items.map((i: any) => (
                <tr key={i.doc_type}><td>{i.label}{i.base && <span className="muted"> · básico</span>}</td>
                  <td><Pill tone={DOC_TONE[i.state] || "muted"}>{i.state_label}</Pill></td>
                  <td>{i.latest ? date(i.latest.valid_until) : "—"}</td><td>{i.versions}</td></tr>
              ))}</tbody></table>
            <p className="muted">“Validado” significa conferido pela administração; o antivírus não substitui a validação. Documentos vencidos deixam de comprovar requisitos.</p>
          </>
        )}
      </StateView>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ qualificações
function QualificationsTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/qualifications");
  const cat = useLoad<any>("/v1/institutional/catalogs");
  const docs = useLoad<any>("/v1/documents?limit=100");
  const f = useForm<any>({ qualification_type: "", issuing_authority: "", certificate_number: "", protocol: "", issue_date: "", expiration_date: "", verification_url: "", document_id: "", notes: "", areas: "" });
  const { busy, run } = useAction();
  const [events, setEvents] = useState<{ id: string; items: any[] } | null>(null);
  async function add(e: any) {
    e.preventDefault();
    const b: any = {};
    for (const [k, v] of Object.entries(f.v)) if (v !== "" && k !== "areas") b[k] = v;
    if (f.v.areas) b.areas = String(f.v.areas).split(",").map((x) => x.trim().toLowerCase().replace(/\s+/g, "_")).filter(Boolean);
    const r = await run(() => api.post("/v1/institutional/qualifications", b), "Qualificação registrada como declarada");
    if (r) { f.setV({ qualification_type: "", issuing_authority: "", certificate_number: "", protocol: "", issue_date: "", expiration_date: "", verification_url: "", document_id: "", notes: "", areas: "" }); reload(); }
  }
  async function remove(id: string) { await run(() => api.del(`/v1/institutional/qualifications/${id}`), "Removida"); reload(); }
  async function showEvents(id: string) { const r = await run(() => api.get(`/v1/institutional/qualifications/${id}/events`)); if (r) setEvents({ id, items: r.items }); }
  return (
    <div className="split">
      <Panel title="Qualificações e certificações">
        <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nenhuma qualificação registrada. Registre ao lado e anexe o comprovante.</p> : false}>
          <ul className="rows">{data?.items.map((q: any) => (
            <li key={q.id}>
              <span><strong>{q.type_label}</strong> <Pill tone={QUAL_TONE[q.effective_status] || "muted"}>{q.status_label}</Pill><br />
                <span className="muted">{q.issuing_authority || "autoridade não informada"} · nº {q.certificate_number || q.protocol || "—"} · validade {date(q.expiration_date)}{q.expires_soon && " (vence em breve)"}</span>
                {q.validation_note && <><br /><span className="muted">Nota da verificação: {q.validation_note}</span></>}</span>
              <span className="row-actions">
                <Button variant="link" onClick={() => showEvents(q.id)}>Histórico</Button>
                {["declared", "document_submitted", "rejected"].includes(q.verification_status) && <Button variant="link" onClick={() => remove(q.id)}>Remover</Button>}
              </span>
            </li>
          ))}</ul>
          {events && (
            <div className="panel panel-quiet"><strong>Histórico (somente leitura)</strong>
              <ul>{events.items.map((e: any, i: number) => <li key={i}>{dateTime(e.at)} — {e.event}{e.to_status ? ` → ${e.to_status}` : ""}{e.note ? ` · ${e.note}` : ""}</li>)}</ul></div>
          )}
          <p className="muted">Declarar não comprova. A administração verifica com a autoridade concedente e o comprovante; só então a qualificação passa a valer em elegibilidade e match.</p>
        </StateView>
      </Panel>
      <Panel title="Registrar qualificação">
        <form className="form" onSubmit={add}>
          <Field label="Tipo"><Select value={f.v.qualification_type} onChange={f.set("qualification_type")} placeholder="Selecione" options={catOptions(cat.data, "qualification_type")} /></Field>
          <Field label="Autoridade concedente"><Input value={f.v.issuing_authority} onChange={f.set("issuing_authority")} /></Field>
          <Field label="Número do certificado"><Input value={f.v.certificate_number} onChange={f.set("certificate_number")} /></Field>
          <Field label="Protocolo"><Input value={f.v.protocol} onChange={f.set("protocol")} /></Field>
          <Field label="Data de emissão"><Input type="date" value={f.v.issue_date} onChange={f.set("issue_date")} /></Field>
          <Field label="Validade"><Input type="date" value={f.v.expiration_date} onChange={f.set("expiration_date")} /></Field>
          <Field label="Endereço de verificação oficial" hint="https://… (consulta pública do órgão)"><Input value={f.v.verification_url} onChange={f.set("verification_url")} /></Field>
          <Field label="Documento comprobatório"><Select value={f.v.document_id} onChange={f.set("document_id")} placeholder="Nenhum" options={(docs.data?.items || []).map((d: any) => [d.id, `${d.title || d.filename}`])} /></Field>
          <Field label="Áreas de atuação" hint="Separe por vírgula (ex.: saude, educacao) — para OS/OSCIP"><Input value={f.v.areas} onChange={f.set("areas")} /></Field>
          <Field label="Observações" wide><TextArea rows={2} value={f.v.notes} onChange={f.set("notes")} /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={!f.v.qualification_type}>Registrar</Button>
        </form>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ elegibilidade
export function EligibilityResult({ r }: { r: any }) {
  return (
    <div>
      <p><Pill tone={ELIG_TONE[r.state] || "muted"}>{r.state_label}</Pill> <strong>{r.can_compete_label}</strong></p>
      <p>{r.summary}</p>
      {r.missing_to_become_eligible?.length > 0 && (
        <>
          <h3>O que falta</h3>
          <ul>{r.missing_to_become_eligible.map((m: any, i: number) => <li key={i}><strong>{m.requirement}</strong>{m.action ? ` — ${m.action}` : ""}{m.documents?.length ? <span className="muted"> (documentos: {m.documents.join(", ")})</span> : null}</li>)}</ul>
        </>
      )}
      <h3>Requisitos avaliados</h3>
      <table className="table"><thead><tr><th>Requisito</th><th>Situação</th><th>Fonte</th></tr></thead>
        <tbody>{r.requirements.map((q: any) => (
          <tr key={q.code}><td>{q.label}<br /><span className="muted">{q.detail}</span>{!q.mandatory && <span className="muted"> · não obrigatório</span>}</td>
            <td><Pill tone={REQ_TONE[q.status] || "muted"}>{q.status_label}</Pill></td>
            <td>{q.source ? <span className="muted">{q.source.citation}{q.source.rule_code ? ` · ${q.source.rule_code} v${q.source.version}` : ""}{q.source.consulted_on ? ` · consultada ${date(q.source.consulted_on)}` : ""}{q.source.confidence ? ` · confiança ${q.source.confidence}` : ""}{q.needs_professional_validation ? " · requer validação profissional" : ""}</span> : "—"}</td></tr>
        ))}</tbody></table>
      {r.fiscal && (
        <>
          <h3>Camadas fiscais (separadas)</h3>
          <ul className="rows">{Object.entries(r.fiscal).map(([k, v]: any) => <li key={k}><span><strong>{k}</strong><br /><span className="muted">{v.note || v.state_label || (v.requirements !== undefined ? `${v.met}/${v.requirements} documentos atendidos` : "")}</span></span></li>)}</ul>
        </>
      )}
      <p className="muted">Avaliado em {date(r.evaluated_on)} · motor {r.engine_version} · maturidade {r.maturity?.level}. {r.disclaimer}</p>
    </div>
  );
}

function EligibilityTab() {
  const mods = useLoad<any>("/v1/institutional/catalogs");
  const calls = useLoad<any>("/v1/calls?limit=50");
  const [subject, setSubject] = useState<[string, string]>(["modality", ""]);
  const [res, setRes] = useState<any>(null);
  const { busy, run } = useAction();
  const hist = useLoad<any>("/v1/institutional/eligibility?limit=10", [res]);
  const options: [string, string][] = [
    ...catOptions(mods.data, "funding_modality").map(([v, l]) => [`modality|${v}`, `Modalidade — ${l}`] as [string, string]),
    ...((calls.data?.items || []) as any[]).map((c) => [`call|${c.id}`, `Edital — ${c.title}`] as [string, string]),
  ];
  return (
    <div className="split">
      <Panel title="Posso concorrer?">
        <Field label="Oportunidade ou modalidade"><Select value={`${subject[0]}|${subject[1]}`} onChange={(v) => { const [a, b] = v.split("|"); setSubject([a, b]); setRes(null); }} placeholder="Selecione" options={options} /></Field>
        <Button variant="primary" busy={busy} disabled={!subject[1]} onClick={() => run(() => api.post("/v1/institutional/eligibility", { subject_type: subject[0], subject_id: subject[1] })).then((r) => r && setRes(r))}>Avaliar elegibilidade</Button>
        {res && <EligibilityResult r={res} />}
      </Panel>
      <Panel title="Avaliações anteriores" quiet>
        <StateView loading={hist.loading} error={hist.error} onRetry={hist.reload}>
          <ul className="rows">{(hist.data?.items || []).map((h: any) => <li key={h.id}><span>{h.subject_type} · {String(h.subject_ref).slice(0, 36)}<br /><span className="muted">{dateTime(h.created_at)} · {h.engine_version}</span></span><Pill tone={ELIG_TONE[h.state] || "muted"}>{h.state}</Pill></li>)}</ul>
        </StateView>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ necessidades
function NeedsTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/needs");
  const f = useForm<any>({ need_type: "financing", detail: "", amount: "", territory: "" });
  const { busy, run } = useAction();
  async function add(e: any) {
    e.preventDefault();
    const r = await run(() => api.post("/v1/institutional/needs", { need_type: f.v.need_type, detail: f.v.detail || null, amount_cents: parseMoney(f.v.amount), territory: f.v.territory || null }), "Necessidade registrada");
    if (r) { f.setV({ need_type: "financing", detail: "", amount: "", territory: "" }); reload(); }
  }
  return (
    <div className="split">
      <Panel title="O que precisamos">
        <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nenhuma necessidade declarada.</p> : false}>
          <ul className="rows">{data?.items.map((n: any) => (
            <li key={n.id}><span><strong>{NEED_LABEL[n.need_type] || n.need_type}</strong> {n.amount_cents ? `· ${money(n.amount_cents)}` : ""}<br /><span className="muted">{n.detail || "—"} {n.territory ? `· ${n.territory}` : ""}</span></span>
              <span className="row-actions"><Pill tone={n.status === "open" ? "warn" : "good"}>{n.status === "open" ? "Aberta" : n.status === "met" ? "Atendida" : "Encerrada"}</Pill>
                {n.status === "open" && <Button variant="link" onClick={() => run(() => api.patch(`/v1/institutional/needs/${n.id}`, { status: "met" })).then(reload)}>Atendida</Button>}
                <Button variant="link" onClick={() => run(() => api.del(`/v1/institutional/needs/${n.id}`)).then(reload)}>Excluir</Button></span></li>
          ))}</ul>
        </StateView>
        <p className="muted">Necessidades orientam a busca e o match; não são compromisso de ninguém.</p>
      </Panel>
      <Panel title="Declarar necessidade">
        <form className="form" onSubmit={add}>
          <Field label="Tipo"><Select value={f.v.need_type} onChange={f.set("need_type")} options={Object.entries(NEED_LABEL)} /></Field>
          <Field label="Valor (R$)"><Input inputMode="decimal" value={f.v.amount} onChange={f.set("amount")} /></Field>
          <Field label="Território"><Input value={f.v.territory} onChange={f.set("territory")} placeholder="BR-MT" /></Field>
          <Field label="Detalhes" wide><TextArea rows={3} value={f.v.detail} onChange={f.set("detail")} /></Field>
          <Button type="submit" variant="primary" busy={busy}>Registrar</Button>
        </form>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ conquistas e declaração
export function BadgeList({ items }: { items: any[] }) {
  return (
    <ul className="rows">{items.map((b: any) => (
      <li key={b.code}>
        <span><strong>{b.label}</strong> <Pill tone={b.status === "earned" ? "good" : b.status === "expired" ? "bad" : "muted"}>{b.status === "earned" ? "Concedido" : b.status === "expired" ? "Expirado" : "Não concedido"}</Pill><br />
          <span className="muted">{b.definition}</span><br />
          <span className="muted">Critério: {b.detail} · Fonte: {b.source}{b.verified_at ? ` · verificado em ${date(b.verified_at)}` : ""}{b.valid_until ? ` · válido até ${date(b.valid_until)}` : ""}</span></span>
      </li>
    ))}</ul>
  );
}

function BadgesTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/badges");
  return (
    <Panel title="Selos institucionais">
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && <><BadgeList items={data.items} /><p className="muted">{data.items[0]?.disclaimer}</p></>}
      </StateView>
    </Panel>
  );
}

function StatementTab() {
  const { data, error, loading, reload } = useLoad<any>("/v1/institutional/statement");
  return (
    <Panel title="Declaração institucional de apoio" actions={<Button variant="ghost" onClick={() => window.print()}>Imprimir</Button>}>
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <ul className="rows">{data.lines.map((l: any, i: number) => (
              <li key={i}><span>{l.text}<br /><span className="muted">Fonte: {l.source}</span></span><Pill tone={l.state === "verified" ? "good" : l.state === "declared" ? "muted" : l.state === "expired" ? "bad" : "warn"}>{l.state === "verified" ? "Verificado" : l.state === "declared" ? "Declarado" : l.state === "expired" ? "Expirado" : "Não confirmado"}</Pill></li>
            ))}</ul>
            <p className="muted">{data.disclaimer} Gerado por {data.generated_by} em {date(data.generated_on)}.</p>
          </>
        )}
      </StateView>
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ perfil público institucional
export function PublicOrg({ id }: { id: string }) {
  // v0.25.0: o banco só mostra os fatos institucionais de OUTRA organização a financiadores, poder
  // público, apoiadores e à administração (`org_institutional_facts`). Uma OSC ou um profissional que
  // abria este endereço recebia o 403 cru, com "Tentar novamente". A regra continua no banco; aqui
  // a tela só não pergunta o que já sabe que vai ser recusado, e explica.
  const { me } = useSession();
  const kind = me?.active_org?.kind || "";
  const pode = id === me?.active_org?.id || ["company", "government", "platform", "individual"].includes(kind);
  const { data, error, loading, reload } = useLoad<any>(pode ? `/v1/institutional/orgs/${id}` : null, [pode]);
  return (
    <>
      <PageHead title={data?.organization?.name || "Organização"} sub="Perfil institucional público" />
      <StateView loading={loading} error={error} onRetry={reload}
                 empty={!pode && <><h2>Perfil institucional visível a quem apoia</h2>
                   <p>Os dados institucionais de outra organização aparecem para financiadores, poder público e apoiadores.
                     O perfil público da organização continua aberto a todos.</p></>}>
        {data && (
          <div className="split">
            <Panel title="Identificação">
              <KeyValue items={[
                ["Natureza jurídica", <>{data.legal_nature.label || "Não informada"} <Pill tone="muted">{data.legal_nature.status}</Pill></>],
                ["Perfil de atuação", data.institutional_profile || "—"],
                ["Situação institucional", data.institutional_status.label],
                ["Maturidade", data.maturity ? `Nível ${data.maturity.level} — ${data.maturity.label}` : "—"],
              ]} />
              <p className="muted">{data.disclaimer}</p>
            </Panel>
            <Panel title="Qualificações verificadas">
              {data.verified_qualifications.length ? (
                <ul className="rows">{data.verified_qualifications.map((q: any) => <li key={q.type}><span><strong>{q.label || q.type}</strong><br /><span className="muted">{q.issuing_authority || "—"} · verificada em {date(q.validation_date)} · validade {date(q.expiration_date)}</span></span><Pill tone="good">Verificada</Pill></li>)}</ul>
              ) : <p className="muted">Nenhuma qualificação verificada. Qualificações apenas declaradas não são exibidas.</p>}
            </Panel>
            <Panel title="Selos">
              {data.badges.length ? <BadgeList items={data.badges} /> : <p className="muted">Nenhum selo concedido no momento.</p>}
            </Panel>
          </div>
        )}
      </StateView>
    </>
  );
}

// ------------------------------------------------------------------------------------------------ administração
function AdminGate({ children }: { children: ReactNode }) {
  const { me } = useSession();
  if (me && !me.user.mfa_verified) return (
    <div className="state state-empty"><h1>Verificação em duas etapas necessária</h1><p>As ações administrativas exigem MFA ativo.</p><Link to="/conta">Ir para minha conta</Link></div>
  );
  return <>{children}</>;
}

const WF_TONE: Record<string, string> = { draft: "muted", review: "warn", approved: "good", published: "good", archived: "muted" };
const WF_LABEL: Record<string, string> = { draft: "Rascunho", review: "Em revisão", approved: "Aprovada", published: "Publicada", archived: "Arquivada" };

export function InstitutionAdmin() {
  const [tab, setTab] = useState("visao");
  const tabs: [string, string][] = [["visao", "Visão geral"], ["qualificacoes", "Qualificações"], ["documentos", "Documentos"], ["instrumentos", "Instrumentos"], ["mentoria", "Mentoria"], ["regras", "Regras"], ["catalogo", "Catálogos"], ["organizacao", "Situação da organização"]];
  return (
    <AdminGate>
      <PageHead title="Institucional" sub="Verificação de qualificações e documentos, regras de elegibilidade e catálogos — com fluxo rascunho → revisão → aprovação (outra pessoa) → publicação." />
      <div className="tabs" role="tablist">
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={`tab${tab === k ? " on" : ""}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {tab === "visao" && <AdminOverview />}
      {tab === "qualificacoes" && <AdminQualifications />}
      {tab === "documentos" && <AdminDocuments />}
      {tab === "instrumentos" && <AdminAgreements />}
      {tab === "mentoria" && <AdminMentoring />}
      {tab === "regras" && <AdminRules />}
      {tab === "catalogo" && <AdminCatalog />}
      {tab === "organizacao" && <AdminOrgStatus />}
    </AdminGate>
  );
}

function AdminOverview() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/overview");
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <div className="grid-home">
          <Panel title="Filas"><KeyValue items={[["Qualificações a analisar", data.qualifications_pending], ["Documentos a validar", data.documents_pending]]} /></Panel>
          <Panel title="Regras por estado"><KeyValue items={Object.entries(data.rules).map(([k, v]: any) => [WF_LABEL[k] || k, v] as [string, ReactNode])} /></Panel>
          <Panel title="Catálogos por estado"><KeyValue items={Object.entries(data.catalog).map(([k, v]: any) => [WF_LABEL[k] || k, v] as [string, ReactNode])} /></Panel>
          <Panel title="Organizações por situação"><KeyValue items={Object.entries(data.organizations_by_status).map(([k, v]: any) => [k, v] as [string, ReactNode])} /></Panel>
        </div>
      )}
    </StateView>
  );
}

function AdminQualifications() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/qualifications" + qs({ status }));
  const { run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const decide = (id: string, decision: string) => run(() => api.post(`/v1/admin/institutional/qualifications/${id}/decide`, { decision, note: note[id] || null }), "Decisão registrada").then(reload);
  return (
    <Panel title="Fila de qualificações" actions={<Select aria-label="Filtrar a fila por estado" value={status} onChange={setStatus} placeholder="Comprovante enviado / em análise" options={[["declared", "Declaradas"], ["verified", "Verificadas"], ["rejected", "Rejeitadas"], ["revoked", "Revogadas"]]} />}>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nada na fila.</p> : false}>
        <table className="table"><thead><tr><th>Organização</th><th>Qualificação</th><th>Comprovação</th><th>Decisão</th></tr></thead>
          <tbody>{data?.items.map((q: any) => (
            <tr key={q.id}>
              <td>{q.org_name}<br /><span className="muted">{q.cnpj}</span></td>
              <td><strong>{q.type_label}</strong><br /><Pill tone={QUAL_TONE[q.effective_status] || "muted"}>{q.status_label}</Pill></td>
              <td>{q.issuing_authority || "—"}<br /><span className="muted">nº {q.certificate_number || q.protocol || "—"} · validade {date(q.expiration_date)}</span><br />
                {q.verification_url && <a href={q.verification_url} target="_blank" rel="noopener noreferrer">Consulta oficial</a>}
                {q.document_id && <span className="muted"> · documento {q.document_validation === "validated" ? "validado" : "não validado"}</span>}</td>
              <td><Input value={note[q.id] || ""} onChange={(v: string) => setNote({ ...note, [q.id]: v })} placeholder="Nota (obrigatória)" />
                <span className="row-actions">
                  <Button variant="link" onClick={() => decide(q.id, "verify")}>Verificar</Button>
                  <Button variant="link" onClick={() => decide(q.id, "request_info")}>Pedir informações</Button>
                  <Button variant="link" onClick={() => decide(q.id, "reject")}>Rejeitar</Button>
                  {q.verification_status === "verified" && <Button variant="link" onClick={() => decide(q.id, "revoke")}>Revogar</Button>}
                </span></td>
            </tr>
          ))}</tbody></table>
      </StateView>
    </Panel>
  );
}

function AdminDocuments() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/documents");
  const { run } = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const decide = (id: string, decision: string) => run(() => api.post(`/v1/admin/institutional/documents/${id}/validate`, { decision, note: note[id] || null }), "Decisão registrada").then(reload);
  return (
    <Panel title="Documentos a validar">
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length ? <p>Nenhum documento aguardando validação.</p> : false}>
        <table className="table"><thead><tr><th>Organização</th><th>Documento</th><th>Validade</th><th>Decisão</th></tr></thead>
          <tbody>{data?.items.map((d: any) => (
            <tr key={d.id}><td>{d.org_name}</td><td>{d.label}<br /><span className="muted">{d.filename} · {d.sha256.slice(0, 12)}…</span></td><td>{date(d.valid_until)}</td>
              <td><Input value={note[d.id] || ""} onChange={(v: string) => setNote({ ...note, [d.id]: v })} placeholder="Motivo (obrigatório ao rejeitar)" />
                <span className="row-actions"><Button variant="link" onClick={() => decide(d.id, "validate")}>Validar</Button><Button variant="link" onClick={() => decide(d.id, "reject")}>Rejeitar</Button></span></td></tr>
          ))}</tbody></table>
      </StateView>
    </Panel>
  );
}

function WorkflowButtons({ item, base, reload }: { item: any; base: string; reload: () => void }) {
  const { run } = useAction();
  const act = (action: string) => {
    let body: any = { action };
    if (action === "publish" && base.includes("rules")) {
      const d = window.prompt("Data em que a fonte foi consultada (AAAA-MM-DD):", new Date().toISOString().slice(0, 10));
      if (!d) return;
      body.source_consulted_on = d;
    }
    return run(() => api.post(`${base}/${item.id}/action`, body), "Atualizado").then(reload);
  };
  return (
    <span className="row-actions">
      {item.status === "draft" && <Button variant="link" onClick={() => act("submit")}>Enviar à revisão</Button>}
      {item.status === "review" && <><Button variant="link" onClick={() => act("approve")}>Aprovar</Button><Button variant="link" onClick={() => act("return_to_draft")}>Devolver</Button></>}
      {item.status === "approved" && <><Button variant="link" onClick={() => act("publish")}>Publicar</Button><Button variant="link" onClick={() => act("return_to_draft")}>Devolver</Button></>}
      {["review", "approved", "published"].includes(item.status) && <Button variant="link" onClick={() => act("archive")}>Arquivar</Button>}
    </span>
  );
}

function AdminRules() {
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/rules" + qs({ status, limit: 100 }));
  const cat = useLoad<any>("/v1/institutional/catalogs");
  const { busy, run } = useAction();
  const f = useForm<any>({ code: "", name: "", scope_type: "modality", scope_ref: "", rtype: "qualification_all", values: "", level: "", months: "", source_citation: "", source_url: "", confidence: "medium", pv: true, how_to_fix: "" });
  function requirement() {
    const list = (f.v.values || "").split(",").map((s: string) => s.trim()).filter(Boolean);
    switch (f.v.rtype) {
      case "qualification_all": case "qualification_any": case "legal_nature_in": case "org_status_in": return { type: f.v.rtype, values: list };
      case "maturity_min": return { type: "maturity_min", level: Number(f.v.level) };
      case "org_age_min": return { type: "org_age_min", months: Number(f.v.months) };
      case "document_valid": return { type: "document_valid", doc_types: list, require_validated: true };
      default: return { type: f.v.rtype };
    }
  }
  async function create(e: any) {
    e.preventDefault();
    const r = await run(() => api.post("/v1/admin/institutional/rules", {
      code: f.v.code, name: f.v.name, scope_type: f.v.scope_type, scope_ref: f.v.scope_type === "global" ? null : f.v.scope_ref, requirement: requirement(),
      source_citation: f.v.source_citation, source_url: f.v.source_url || null, confidence: f.v.confidence, needs_professional_validation: !!f.v.pv, how_to_fix: f.v.how_to_fix || null,
    }), "Regra criada como rascunho");
    if (r) reload();
  }
  return (
    <>
      <Panel title="Regras de elegibilidade" actions={<>
        <Select aria-label="Filtrar por estado" value={status} onChange={setStatus} placeholder="Todos os estados" options={Object.entries(WF_LABEL)} />
        <Button variant="ghost" onClick={() => run(() => api.post("/v1/admin/institutional/rules/import-candidates"), "Candidatas importadas como rascunho").then(reload)}>Importar candidatas</Button></>}>
        <StateView loading={loading} error={error} onRetry={reload}>
          <table className="table"><thead><tr><th>Regra</th><th>Escopo e requisito</th><th>Fonte</th><th>Estado</th><th /></tr></thead>
            <tbody>{data?.items.map((r: any) => (
              <tr key={r.id}><td>{r.name}<br /><span className="muted">{r.code} v{r.version}</span></td>
                <td>{r.scope_type}{r.scope_ref ? `: ${r.scope_ref}` : ""}<br /><code>{JSON.stringify(r.requirement)}</code></td>
                <td>{r.source_url ? <a href={r.source_url} target="_blank" rel="noopener noreferrer">{r.source_citation}</a> : r.source_citation}<br /><span className="muted">consultada {date(r.source_consulted_on)} · confiança {r.confidence}{r.needs_professional_validation ? " · validação profissional" : ""}</span></td>
                <td><Pill tone={WF_TONE[r.status]}>{WF_LABEL[r.status]}</Pill></td>
                <td><WorkflowButtons item={r} base="/v1/admin/institutional/rules" reload={reload} /></td></tr>
            ))}</tbody></table>
          <p className="muted">Quem cria a regra não pode aprová-la. Só regras publicadas e vigentes entram na elegibilidade e no match.</p>
        </StateView>
      </Panel>
      <Panel title="Nova regra (rascunho)">
        <form className="form" onSubmit={create}>
          <Field label="Código" hint="MAIÚSCULAS, números e hífen"><Input value={f.v.code} onChange={f.set("code")} /></Field>
          <Field label="Nome"><Input value={f.v.name} onChange={f.set("name")} /></Field>
          <Field label="Escopo"><Select value={f.v.scope_type} onChange={f.set("scope_type")} options={[["global", "Global"], ["modality", "Modalidade"], ["call", "Edital"], ["funder", "Financiador"]]} /></Field>
          {f.v.scope_type === "modality" ? <Field label="Modalidade"><Select value={f.v.scope_ref} onChange={f.set("scope_ref")} placeholder="Selecione" options={catOptions(cat.data, "funding_modality")} /></Field>
            : f.v.scope_type !== "global" && <Field label="Identificador (id do edital ou da organização)"><Input value={f.v.scope_ref} onChange={f.set("scope_ref")} /></Field>}
          <Field label="Tipo de requisito"><Select value={f.v.rtype} onChange={f.set("rtype")} options={[["qualification_all", "Todas as qualificações"], ["qualification_any", "Alguma das qualificações"], ["legal_nature_in", "Natureza jurídica entre"], ["maturity_min", "Maturidade mínima"], ["org_status_in", "Situação institucional entre"], ["document_valid", "Documentos válidos"], ["org_age_min", "Tempo mínimo de existência"], ["cnpj_required", "CNPJ obrigatório"], ["compliance_approved", "Compliance aprovado"]]} /></Field>
          {["qualification_all", "qualification_any", "legal_nature_in", "org_status_in", "document_valid"].includes(f.v.rtype) && <Field label="Códigos" hint="Separados por vírgula (ex.: oscip, cebas)"><Input value={f.v.values} onChange={f.set("values")} /></Field>}
          {f.v.rtype === "maturity_min" && <Field label="Nível (0–6)"><Input inputMode="numeric" value={f.v.level} onChange={f.set("level")} /></Field>}
          {f.v.rtype === "org_age_min" && <Field label="Meses"><Input inputMode="numeric" value={f.v.months} onChange={f.set("months")} /></Field>}
          <Field label="Fonte (obrigatória)" wide><Input value={f.v.source_citation} onChange={f.set("source_citation")} placeholder="Norma, artigo, edital… e versão consultada" /></Field>
          <Field label="Endereço da fonte"><Input value={f.v.source_url} onChange={f.set("source_url")} placeholder="https://" /></Field>
          <Field label="Confiança"><Select value={f.v.confidence} onChange={f.set("confidence")} options={[["high", "Alta"], ["medium", "Média"], ["low", "Baixa"]]} /></Field>
          <Field label="Como resolver" wide><Input value={f.v.how_to_fix} onChange={f.set("how_to_fix")} /></Field>
          <label className="check"><input type="checkbox" checked={!!f.v.pv} onChange={(e: any) => f.set("pv")(e.target.checked)} /> Origem legal: exige validação profissional</label>
          <Button type="submit" variant="primary" busy={busy}>Criar rascunho</Button>
        </form>
      </Panel>
    </>
  );
}

function AdminCatalog() {
  const [catalog, setCatalog] = useState("");
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/institutional/catalog" + qs({ catalog, limit: 100 }));
  const { busy, run } = useAction();
  const f = useForm<any>({ catalog: "legal_nature", code: "", label: "", description: "", attributes: "{}", source_citation: "", confidence: "medium", pv: true });
  async function create(e: any) {
    e.preventDefault();
    let attrs: any;
    try { attrs = JSON.parse(f.v.attributes || "{}"); } catch { return run(async () => { throw new Error("Atributos devem ser JSON válido"); }); }
    const r = await run(() => api.post("/v1/admin/institutional/catalog", { catalog: f.v.catalog, code: f.v.code, label: f.v.label, description: f.v.description || null, attributes: attrs,
      source_citation: f.v.source_citation || null, confidence: f.v.confidence, needs_professional_validation: !!f.v.pv }), "Item criado como rascunho");
    if (r) reload();
  }
  return (
    <>
      <Panel title="Itens de catálogo" actions={<Select aria-label="Filtrar por catálogo" value={catalog} onChange={setCatalog} placeholder="Todos os catálogos" options={[["legal_nature", "Naturezas jurídicas"], ["qualification_type", "Qualificações"], ["institutional_profile", "Perfis de atuação"], ["funding_modality", "Modalidades"], ["badge", "Selos"]]} />}>
        <StateView loading={loading} error={error} onRetry={reload}>
          <table className="table"><thead><tr><th>Item</th><th>Fonte</th><th>Estado</th><th /></tr></thead>
            <tbody>{data?.items.map((r: any) => (
              <tr key={r.id}><td>{r.label}<br /><span className="muted">{r.catalog} · {r.code} v{r.version}</span></td>
                <td>{r.source_citation || "—"}<br /><span className="muted">confiança {r.confidence}{r.needs_professional_validation ? " · revisão jurídica pendente" : ""}</span></td>
                <td><Pill tone={WF_TONE[r.status]}>{WF_LABEL[r.status]}</Pill></td>
                <td><WorkflowButtons item={r} base="/v1/admin/institutional/catalog" reload={reload} /></td></tr>
            ))}</tbody></table>
        </StateView>
      </Panel>
      <Panel title="Novo item (rascunho)">
        <form className="form" onSubmit={create}>
          <Field label="Catálogo"><Select value={f.v.catalog} onChange={f.set("catalog")} options={[["legal_nature", "Natureza jurídica"], ["qualification_type", "Tipo de qualificação"], ["institutional_profile", "Perfil de atuação"], ["funding_modality", "Modalidade"], ["badge", "Selo"]]} /></Field>
          <Field label="Código"><Input value={f.v.code} onChange={f.set("code")} placeholder="minusculas_e_sublinhado" /></Field>
          <Field label="Rótulo"><Input value={f.v.label} onChange={f.set("label")} /></Field>
          <Field label="Descrição" wide><Input value={f.v.description} onChange={f.set("description")} /></Field>
          <Field label="Atributos (JSON)" hint='Natureza: {"allowed_kinds":["osc"],"requires_cnpj":true} · Selo: {"scope":"organization","criterion":"org_verified","validity_days":365}' wide><TextArea rows={3} value={f.v.attributes} onChange={f.set("attributes")} /></Field>
          <Field label="Fonte" wide><Input value={f.v.source_citation} onChange={f.set("source_citation")} /></Field>
          <Field label="Confiança"><Select value={f.v.confidence} onChange={f.set("confidence")} options={[["high", "Alta"], ["medium", "Média"], ["low", "Baixa"]]} /></Field>
          <label className="check"><input type="checkbox" checked={!!f.v.pv} onChange={(e: any) => f.set("pv")(e.target.checked)} /> Requer revisão jurídica</label>
          <Button type="submit" variant="primary" busy={busy}>Criar rascunho</Button>
        </form>
      </Panel>
    </>
  );
}

function AdminOrgStatus() {
  const [orgId, setOrgId] = useState("");
  const [snap, setSnap] = useState<any>(null);
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  const load = () => run(() => api.get(`/v1/admin/institutional/organizations/${orgId}`)).then((r) => r && setSnap(r));
  return (
    <Panel title="Situação institucional de uma organização">
      <div className="form">
        <Field label="Identificador da organização"><Input value={orgId} onChange={setOrgId} placeholder="UUID" /></Field>
        <Button variant="ghost" busy={busy} disabled={orgId.length < 30} onClick={load}>Consultar</Button>
      </div>
      {snap && (
        <>
          <KeyValue items={[
            ["Situação atual", snap.facts.institutional_status],
            ["Sugestão do sistema", <>{snap.suggested_status.status} <span className="muted">— {snap.suggested_status.reason}</span></>],
            ["Maturidade", snap.maturity?.applicable ? `Nível ${snap.maturity.level} — ${snap.maturity.label}` : "—"],
          ]} />
          <p className="muted">A sugestão não altera nada: a decisão é humana, justificada e auditada.</p>
          <div className="form">
            <Field label="Nova situação"><Select value={status} onChange={setStatus} placeholder="Selecione" options={[["in_structuring", "Em estruturação"], ["registered", "Cadastrada"], ["documents_pending", "Documentos pendentes"], ["partially_regular", "Parcialmente regular"], ["regular", "Regular"], ["irregular", "Irregular"], ["under_review", "Em revisão"], ["suspended", "Suspensa"], ["archived", "Arquivada"]]} /></Field>
            <Field label="Justificativa" wide><TextArea rows={2} value={note} onChange={setNote} /></Field>
            <Button variant="primary" busy={busy} disabled={!status} onClick={() => run(() => api.post(`/v1/admin/institutional/organizations/${orgId}/status`, { status, note: note || null }), "Situação atualizada").then(load)}>Aplicar</Button>
          </div>
        </>
      )}
    </Panel>
  );
}
