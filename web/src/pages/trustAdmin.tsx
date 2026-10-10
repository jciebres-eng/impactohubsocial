import { useState } from "react";
import { api } from "../api";
import { date, dateTime, money } from "../format";
import { Button, Field, Input, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

const LEVEL_LABEL: Record<string, string> = { email: "E-mail", phone: "Telefone", document: "Documento",
  professional: "Credencial profissional", biometric: "Biometria" };

// ============================================================ fila de identidade
const ID_STATUS: Record<string, string> = { verified: "verificada", suspended: "suspensa", rejected: "recusada", revoked: "revogada", expired: "vencida" };

export function IdentityQueue() {
  const [state, setState] = useState("open");
  const { data, error, loading, reload } = useLoad<any>(`/v1/admin/trust/identity/queue?state=${state}`);
  const { busy, run } = useAction();
  const [changing, setChanging] = useState<any>(null);
  const [toStatus, setToStatus] = useState("suspended");
  const [changeNote, setChangeNote] = useState("");

  async function change() {
    await run(async () => {
      await api.post(`/v1/admin/trust/identity/${changing.id}/status`, { status: toStatus, note: changeNote });
      setChanging(null); setChangeNote(""); reload();
      return "Estado da verificação alterado.";
    });
  }
  const [deciding, setDeciding] = useState<any>(null);
  const [approve, setApprove] = useState(true);
  const [note, setNote] = useState("");

  async function decide() {
    await run(async () => {
      await api.post(`/v1/admin/trust/identity/${deciding.id}/decide`, { approve, note });
      setDeciding(null); setNote(""); reload();
      return approve ? "Identidade verificada." : "Pedido recusado.";
    });
  }

  return (
    <>
      <PageHead title="Identidade — conferência humana"
                sub="A plataforma não faz biometria nem consulta base oficial: a decisão é de uma pessoa da equipe. Ninguém decide a própria verificação."
                actions={<Select aria-label="Quais verificações mostrar" value={state} onChange={setState} options={[["open", "Aguardando decisão"], ["decided", "Já decididas"]]} />} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <ul className="rows">{data.items.map((v: any) => (
            <li key={v.id}>
              <span>{v.user_name}<br /><span className="muted small">
                {LEVEL_LABEL[v.level] || v.level} · {v.documents} documento(s) · pedido em {dateTime(v.created_at)}
              </span></span>
              {state === "open" ? (
              <span>
                <Pill tone="warn">{v.status === "pending" ? "aguardando documento" : "em análise"}</Pill>{" "}
                <Button onClick={() => { setDeciding(v); setApprove(true); }}>Decidir</Button>
              </span>
              ) : (
              <span>
                <Pill tone={v.status === "verified" ? "good" : "warn"}>{ID_STATUS[v.status] || v.status}</Pill>{" "}
                {["verified", "suspended"].includes(v.status) && <Button onClick={() => { setChanging(v); setToStatus(v.status === "verified" ? "suspended" : "verified"); }}>Mudar estado</Button>}
              </span>
              )}
            </li>
          ))}</ul>
        )}
      </StateView>
      <Modal open={!!deciding} title="Decidir verificação de identidade" onClose={() => setDeciding(null)}
             footer={<><Button onClick={() => setDeciding(null)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={decide} disabled={note.trim().length < 5}>Registrar decisão</Button></>}>
        <Field label="Decisão">
          <Select value={approve ? "1" : "0"} onChange={(v) => setApprove(v === "1")}
                  options={[["1", "Aprovar"], ["0", "Recusar"]]} />
        </Field>
        <Field label="Justificativa" hint="Fica na trilha de auditoria e na cadeia de custódia.">
          <TextArea value={note} onChange={setNote} rows={3} />
        </Field>
      </Modal>
      <Modal open={!!changing} title="Mudar o estado de uma verificação decidida" onClose={() => setChanging(null)}
             footer={<><Button onClick={() => setChanging(null)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={change} disabled={changeNote.trim().length < 10}>Registrar</Button></>}>
        <Field label="Novo estado">
          <Select value={toStatus} onChange={setToStatus}
                  options={changing?.status === "suspended" ? [["verified", "Restabelecer (verificada)"], ["revoked", "Revogar (definitivo)"]]
                                                             : [["suspended", "Suspender (em apuração, reversível)"], ["revoked", "Revogar (definitivo)"]]} />
        </Field>
        <Field label="Motivo (mínimo 10 caracteres)" hint="Fica na trilha de auditoria e na cadeia de custódia.">
          <TextArea value={changeNote} onChange={setChangeNote} rows={3} />
        </Field>
      </Modal>
    </>
  );
}

// ============================================================ fila de credenciais profissionais
export function CredentialQueue() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/trust/credentials/queue");
  const { busy, run } = useAction();
  const [deciding, setDeciding] = useState<any>(null);
  const [approve, setApprove] = useState(true);
  const [note, setNote] = useState("");
  const [validUntil, setValidUntil] = useState("");

  async function decide() {
    await run(async () => {
      await api.post(`/v1/admin/trust/credentials/${deciding.id}/decide`,
                     { approve, note, ...(validUntil ? { valid_until: validUntil } : {}) });
      setDeciding(null); setNote(""); setValidUntil(""); reload();
      return approve ? "Credencial verificada." : "Credencial recusada.";
    });
  }

  return (
    <>
      <PageHead title="Credenciais profissionais — conferência documental"
                sub="“Verificada” significa que a equipe conferiu o documento. A plataforma não consulta conselho on-line." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <ul className="rows">{data.items.map((c: any) => (
            <li key={c.id}>
              <span><strong>{c.council} {c.number}{c.uf ? `/${c.uf}` : ""}</strong> — {c.holder_name}<br />
                <span className="muted small">{c.legal_name} · enviada em {dateTime(c.created_at)}
                  {c.valid_until ? ` · validade ${date(c.valid_until)}` : ""}</span></span>
              <Button onClick={() => { setDeciding(c); setApprove(true); }}>Conferir</Button>
            </li>
          ))}</ul>
        )}
      </StateView>
      <Modal open={!!deciding} title="Conferir credencial" onClose={() => setDeciding(null)}
             footer={<><Button onClick={() => setDeciding(null)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={decide} disabled={note.trim().length < 5}>Registrar decisão</Button></>}>
        <Field label="Decisão">
          <Select value={approve ? "1" : "0"} onChange={(v) => setApprove(v === "1")} options={[["1", "Aprovar"], ["0", "Recusar"]]} />
        </Field>
        <Field label="O que foi conferido" hint="Descreva o documento conferido. Não afirme consulta ao conselho se não houve.">
          <TextArea value={note} onChange={setNote} rows={3} />
        </Field>
        <Field label="Validade do registro"><Input type="date" value={validUntil} onChange={setValidUntil} /></Field>
      </Modal>
    </>
  );
}

// ============================================================ tabelas de honorários
const EMPTY_T = { council_code: "CRP", title: "", version: "", reference_year: "", source_name: "", source_url: "", source_date: "", notes: "" };
const EMPTY_I = { service_code: "", description: "", unit: "session", reference: "", min: "", max: "" };
const UNITS: [string, string][] = [["hour", "Hora"], ["session", "Sessão"], ["document", "Documento"], ["report", "Relatório"],
  ["visit", "Visita"], ["month", "Mês"], ["project", "Projeto"], ["other", "Outro"]];

export function FeeTables() {
  const { data, error, loading, reload } = useLoad<any>("/v1/fee-tables");
  const { data: councils } = useLoad<any>("/v1/trust/councils");
  const f = useForm<any>(EMPTY_T);
  const fi = useForm<any>(EMPTY_I);
  const { busy, run } = useAction();
  const [creating, setCreating] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);

  async function create(e: any) {
    e.preventDefault();
    await run(async () => {
      const body: any = { council_code: f.v.council_code, title: f.v.title, version: f.v.version };
      for (const k of ["source_name", "source_url", "notes"]) if (f.v[k]) body[k] = f.v[k];
      if (f.v.source_date) body.source_date = f.v.source_date;
      if (f.v.reference_year) body.reference_year = parseInt(f.v.reference_year, 10);
      await api.post("/v1/admin/fee-tables", body);
      setCreating(false); f.setV(EMPTY_T); reload();
      return "Tabela criada em rascunho.";
    });
  }
  async function addItem() {
    await run(async () => {
      const body: any = { service_code: fi.v.service_code, description: fi.v.description, unit: fi.v.unit };
      for (const [k, field] of [["reference_cents", "reference"], ["min_cents", "min"], ["max_cents", "max"]] as [string, string][]) {
        if (fi.v[field]) body[k] = Math.round(parseFloat(String(fi.v[field]).replace(",", ".")) * 100);
      }
      await api.post(`/v1/admin/fee-tables/${adding}/items`, body);
      setAdding(null); fi.setV(EMPTY_I); reload();
      return "Item acrescentado.";
    });
  }

  return (
    <>
      <PageHead title="Tabelas de honorários"
                sub="Valores de referência vêm das tabelas publicadas pelos conselhos. Publicar exige fonte, URL e data."
                actions={<Button variant="primary" onClick={() => setCreating(true)}>Nova tabela</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.map((t: any) => (
          <Panel key={t.id} title={`${t.council_code} · ${t.title} (${t.version})`} actions={<>
            <Button onClick={() => setAdding(t.id)}>Acrescentar item</Button>{" "}
            <Button variant="primary" busy={busy}
                    onClick={() => run(async () => { await api.post(`/v1/admin/fee-tables/${t.id}/publish`); reload(); return "Tabela publicada."; })}>
              Publicar
            </Button>
          </>}>
            <p className="muted small">
              Fonte: {t.source_name || <strong>não informada</strong>}
              {t.source_url && <> · <a href={t.source_url} target="_blank" rel="noreferrer">documento</a></>}
              {t.source_date && <> · consultada em {date(t.source_date)}</>} · {t.items} item(ns)
            </p>
          </Panel>
        ))}
        {data?.note && <p className="muted small">{data.note}</p>}
      </StateView>
      <Modal open={creating} title="Nova tabela de honorários" onClose={() => setCreating(false)}
             footer={<><Button onClick={() => setCreating(false)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={create} disabled={!f.v.title || !f.v.version}>Criar rascunho</Button></>}>
        <p className="muted small">A plataforma não estima honorário: os valores precisam vir de uma tabela publicada pelo
          conselho, com fonte e data de consulta.</p>
        <Field label="Conselho">
          <Select value={f.v.council_code} onChange={f.set("council_code")}
                  options={(councils?.items || []).map((c: any) => [c.code, `${c.code} — ${c.profession}`] as [string, string])} />
        </Field>
        <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Versão"><Input value={f.v.version} onChange={f.set("version")} placeholder="2026.1" /></Field>
        <Field label="Ano de referência"><Input value={f.v.reference_year} onChange={f.set("reference_year")} inputMode="numeric" /></Field>
        <Field label="Nome da fonte"><Input value={f.v.source_name} onChange={f.set("source_name")} /></Field>
        <Field label="URL da fonte (https)"><Input value={f.v.source_url} onChange={f.set("source_url")} /></Field>
        <Field label="Data da consulta"><Input type="date" value={f.v.source_date} onChange={f.set("source_date")} /></Field>
        <Field label="Observações" wide><TextArea value={f.v.notes} onChange={f.set("notes")} rows={2} /></Field>
      </Modal>
      <Modal open={!!adding} title="Acrescentar item" onClose={() => setAdding(null)}
             footer={<><Button onClick={() => setAdding(null)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={addItem}
                       disabled={!fi.v.service_code || !fi.v.description}>Acrescentar</Button></>}>
        <Field label="Código do serviço"><Input value={fi.v.service_code} onChange={fi.set("service_code")} placeholder="consulta.individual" /></Field>
        <Field label="Descrição"><Input value={fi.v.description} onChange={fi.set("description")} /></Field>
        <Field label="Unidade"><Select value={fi.v.unit} onChange={fi.set("unit")} options={UNITS} /></Field>
        <Field label="Valor de referência (R$)" hint="Exatamente como consta na fonte."><Input value={fi.v.reference} onChange={fi.set("reference")} /></Field>
        <Field label="Mínimo (R$)"><Input value={fi.v.min} onChange={fi.set("min")} /></Field>
        <Field label="Máximo (R$)"><Input value={fi.v.max} onChange={fi.set("max")} /></Field>
      </Modal>
    </>
  );
}

// ============================================================ catálogo de atividades do profissional
const EMPTY_S = { title: "", description: "", modality: "hybrid", unit: "session", price: "", duration: "" };
const MODALITIES: [string, string][] = [["online", "On-line"], ["in_person", "Presencial"], ["hybrid", "Híbrido"]];

export function MyServices() {
  const { data, error, loading, reload } = useLoad<any>("/v1/professional-services");
  const { data: fees } = useLoad<any>("/v1/fee-tables");
  const f = useForm<any>(EMPTY_S);
  const { busy, run } = useAction();
  const [creating, setCreating] = useState(false);

  async function create() {
    await run(async () => {
      const body: any = { title: f.v.title, modality: f.v.modality, unit: f.v.unit };
      if (f.v.description) body.description = f.v.description;
      if (f.v.price) body.price_cents = Math.round(parseFloat(String(f.v.price).replace(",", ".")) * 100);
      if (f.v.duration) body.duration_min = parseInt(f.v.duration, 10);
      await api.post("/v1/professional-services", body);
      setCreating(false); f.setV(EMPTY_S); reload();
      return "Atividade cadastrada em rascunho.";
    });
  }

  return (
    <>
      <PageHead title="Minhas atividades" sub="O que você oferece, com preço próprio e margem para negociação."
                actions={<Button variant="primary" onClick={() => setCreating(true)}>Nova atividade</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <ul className="rows">{data.items.map((s: any) => (
            <li key={s.id}>
              <span><strong>{s.title}</strong><br /><span className="muted small">
                {MODALITIES.find(([k]) => k === s.modality)?.[1]} · {s.price_cents ? money(s.price_cents) : "a combinar"}
                {s.negotiable ? " · negociável" : ""}{s.duration_min ? ` · ${s.duration_min} min` : ""}
                {s.council ? ` · ${s.council} ${s.number}` : ""}
              </span></span>
              <span>
                <Pill tone={s.status === "published" ? "good" : "muted"}>{s.status}</Pill>{" "}
                <Select aria-label="Situação do selo" value={s.status} options={[["draft", "Rascunho"], ["published", "Publicada"], ["paused", "Pausada"]]}
                        onChange={(v) => run(async () => { await api.patch(`/v1/professional-services/${s.id}`, { status: v }); reload(); return "Atualizada."; })} />
              </span>
            </li>
          ))}</ul>
        )}
      </StateView>
      <Modal open={creating} title="Nova atividade" onClose={() => setCreating(false)}
             footer={<><Button onClick={() => setCreating(false)}>Cancelar</Button>
               <Button variant="primary" busy={busy} onClick={create} disabled={!f.v.title}>Cadastrar</Button></>}>
        {fees?.items?.length === 0 && (
          <p className="muted small">Nenhuma tabela de honorários publicada ainda. Você pode definir o seu preço livremente —
            a plataforma não sugere valor.</p>
        )}
        <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Descrição" wide><TextArea value={f.v.description} onChange={f.set("description")} rows={3} /></Field>
        <Field label="Modalidade"><Select value={f.v.modality} onChange={f.set("modality")} options={MODALITIES} /></Field>
        <Field label="Unidade"><Select value={f.v.unit} onChange={f.set("unit")} options={UNITS} /></Field>
        <Field label="Preço (R$)" hint="Em branco = a combinar."><Input value={f.v.price} onChange={f.set("price")} /></Field>
        <Field label="Duração (minutos)"><Input value={f.v.duration} onChange={f.set("duration")} inputMode="numeric" /></Field>
      </Modal>
    </>
  );
}
