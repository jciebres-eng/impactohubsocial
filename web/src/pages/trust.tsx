import { useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import { date, dateTime, money } from "../format";
import { Link, navigate } from "../router";
import { Button, Field, Input, KeyValue, Modal, PageHead, Panel, Pill, Select, StateView, TextArea, useAction, useForm, useLoad } from "../ui/kit";

const LEVEL_LABEL: Record<string, string> = {
  none: "Não verificada", email: "E-mail confirmado", phone: "Telefone confirmado", document: "Documento conferido",
  professional: "Credencial profissional conferida", biometric: "Biometria confirmada",
};
const IDV_TONE: Record<string, string> = { verified: "good", pending: "warn", under_review: "warn", rejected: "bad", expired: "bad", revoked: "bad" };
const IDV_LABEL: Record<string, string> = { verified: "verificada", pending: "aguardando envio", under_review: "em análise", rejected: "recusada", expired: "expirada", revoked: "revogada" };
const DOC_KINDS: [string, string][] = [["official_id", "Documento oficial de identidade"], ["drivers_license", "Carteira de motorista"],
  ["passport", "Passaporte"], ["proof_of_address", "Comprovante de endereço"], ["council_card", "Carteira do conselho"], ["other", "Outro"]];
const AG_KIND: [string, string][] = [["service", "Prestação de serviço"], ["partnership", "Parceria"], ["funding", "Financiamento"],
  ["volunteer", "Voluntariado"], ["data_sharing", "Compartilhamento de dados"], ["other", "Outro"]];
const AG_STATUS: Record<string, string> = { draft: "Rascunho", awaiting_signatures: "Aguardando assinaturas", active: "Vigente",
  completed: "Concluído", canceled: "Cancelado", expired: "Expirado" };
const PARTY_ROLE: [string, string][] = [["provider", "Prestador"], ["contractor", "Contratante"], ["funder", "Financiador"],
  ["professional", "Profissional"], ["witness", "Testemunha"], ["beneficiary_rep", "Representante dos beneficiários"]];
const MS_STATUS: [string, string][] = [["planned", "Planejada"], ["in_progress", "Em andamento"], ["delivered", "Entregue"],
  ["accepted", "Aceita"], ["rejected", "Recusada"], ["canceled", "Cancelada"]];

// ============================================================ assinatura em duas camadas (reutilizável)
export function SignBox({ subjectType, subjectId, roleOptions, onSigned, extraFields, title = "Assinar" }: {
  subjectType: "document" | "draft" | "agreement"; subjectId: string;
  roleOptions?: [string, string][]; onSigned: (out: any) => void; extraFields?: Record<string, any>; title?: string;
}) {
  const [open, setOpen] = useState(false);
  const [sent, setSent] = useState<any>(null);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [role, setRole] = useState(roleOptions?.[0]?.[0] || "legal_representative");
  const [statement, setStatement] = useState("");
  const { busy, run } = useAction();

  async function askCode() {
    await run(async () => {
      const out = await api.post("/v1/signatures/challenge", { subject_type: subjectType, subject_id: subjectId });
      setSent(out);
      return "Código enviado para o seu e-mail.";
    });
  }
  async function sign() {
    await run(async () => {
      const body: any = { statement, password, code, ...(extraFields || {}) };
      const out = subjectType === "agreement"
        ? await api.post(`/v1/signed-agreements/${subjectId}/sign`, body)
        : await api.post("/v1/signatures", { subject_type: subjectType, subject_id: subjectId, role, ...body });
      setOpen(false); setPassword(""); setCode(""); setStatement(""); setSent(null);
      onSigned(out);
      return "Assinatura registrada.";
    });
  }

  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>{title}</Button>
      <Modal open={open} title="Assinatura em duas camadas" onClose={() => setOpen(false)}
             footer={<>
               <Button onClick={() => setOpen(false)}>Cancelar</Button>
               {!sent
                 ? <Button variant="primary" busy={busy} onClick={askCode}>Enviar código por e-mail</Button>
                 : <Button variant="primary" busy={busy} onClick={sign}
                           disabled={!password || code.length < 4 || statement.trim().length < 10}>Assinar</Button>}
             </>}>
        <p className="muted small">A assinatura exige duas camadas: a sua senha e um código de uso único enviado por
          e-mail. O código vale só para esta versão exata do conteúdo — se o documento mudar, é preciso pedir outro.</p>
        {roleOptions && roleOptions.length > 1 && (
          <Field label="Assino como"><Select value={role} onChange={setRole} options={roleOptions} /></Field>
        )}
        <Field label="Declaração" hint="Fica registrada junto à assinatura e aparece na verificação pública.">
          <TextArea value={statement} onChange={setStatement} rows={3}
                    placeholder="Declaro que as informações são verdadeiras e me responsabilizo por elas." />
        </Field>
        <Field label="Sua senha"><Input type="password" value={password} onChange={setPassword} autoComplete="current-password" /></Field>
        {sent && (
          <Field label="Código recebido por e-mail"
                 hint={`Enviado para ${sent.destination_hint || "seu e-mail"} · vale ${sent.ttl_minutes} minutos`}>
            <Input value={code} onChange={setCode} inputMode="numeric" maxLength={6} />
          </Field>
        )}
      </Modal>
    </>
  );
}

// ============================================================ identidade
export function Identity() {
  const { data, error, loading, reload } = useLoad<any>("/v1/trust/identity");
  const { busy, run } = useAction();
  const [docFor, setDocFor] = useState<string | null>(null);
  const [docId, setDocId] = useState("");
  const [docKind, setDocKind] = useState("official_id");

  async function request(level: string) {
    await run(async () => { await api.post("/v1/trust/identity/verifications", { level }); reload(); return "Pedido registrado."; });
  }
  async function attach() {
    await run(async () => {
      await api.post(`/v1/trust/identity/verifications/${docFor}/documents`, { document_id: docId, kind: docKind });
      setDocFor(null); setDocId(""); reload();
      return "Documento anexado. A equipe vai conferir.";
    });
  }

  return (
    <>
      <PageHead title="Minha identidade" sub="Quanto mais forte a identificação, mais a sua assinatura vale para terceiros." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Nível atual">
              <p><Pill tone={data.level === "none" ? "warn" : "good"}>{LEVEL_LABEL[data.level] || data.level}</Pill></p>
              <p className="muted small">{data.note}</p>
            </Panel>
            <Panel title="Verificações" actions={
              data.verifications?.some((v: any) => v.level === "document") ? undefined
                : <Button busy={busy} onClick={() => request("document")}>Pedir verificação por documento</Button>}>
              {data.verifications?.length ? (
                <ul className="rows">{data.verifications.map((v: any) => (
                  <li key={v.id}>
                    <span>{LEVEL_LABEL[v.level] || v.level}
                      {v.decision_note && <><br /><span className="muted small">{v.decision_note}</span></>}
                      {v.expires_at && <><br /><span className="muted small">Validade: {date(v.expires_at)}</span></>}
                    </span>
                    <span>
                      <Pill tone={IDV_TONE[v.status] || "muted"}>{IDV_LABEL[v.status] || v.status}</Pill>{" "}
                      {["pending", "under_review"].includes(v.status) && (
                        <Button onClick={() => setDocFor(v.id)}>Anexar documento</Button>
                      )}
                    </span>
                  </li>
                ))}</ul>
              ) : <p className="muted">Nenhum pedido ainda.</p>}
            </Panel>
            {data.documents?.length > 0 && (
              <Panel title="Documentos enviados">
                <ul className="rows">{data.documents.map((d: any) => (
                  <li key={d.id}><span>{d.title || d.filename}<br /><span className="muted small">{dateTime(d.created_at)}</span></span>
                    <Pill tone={d.status === "accepted" ? "good" : d.status === "rejected" ? "bad" : "warn"}>{d.status}</Pill></li>
                ))}</ul>
              </Panel>
            )}
            <Panel title="O que esta plataforma NÃO faz" quiet>
              <ul>
                <li>{data.unavailable?.biometric}</li>
                <li>{data.unavailable?.phone}</li>
              </ul>
            </Panel>
            <Modal open={!!docFor} title="Anexar documento de identidade" onClose={() => setDocFor(null)}
                   footer={<><Button onClick={() => setDocFor(null)}>Cancelar</Button>
                     <Button variant="primary" busy={busy} onClick={attach} disabled={!docId}>Anexar</Button></>}>
              <p className="muted small">Envie o arquivo primeiro em <Link to="/documentos">Documentos</Link> e cole aqui o
                identificador. A plataforma guarda a referência do arquivo — não extrai nem armazena o número do documento.</p>
              <Field label="Tipo"><Select value={docKind} onChange={setDocKind} options={DOC_KINDS} /></Field>
              <Field label="Identificador do documento"><Input value={docId} onChange={setDocId} placeholder="UUID do documento" /></Field>
            </Modal>
          </>
        )}
      </StateView>
    </>
  );
}

// ============================================================ registros públicos de verificação
export function VerifiableRecords() {
  const { data, error, loading, reload } = useLoad<any>("/v1/verifiable-records");
  const { busy, run } = useAction();
  const [revoking, setRevoking] = useState<any>(null);
  const [reason, setReason] = useState("");

  async function revoke() {
    await run(async () => {
      await api.post(`/v1/verifiable-records/${revoking.id}/revoke`, { reason });
      setRevoking(null); setReason(""); reload();
      return "Registro revogado. A página pública passa a mostrar o motivo.";
    });
  }

  return (
    <>
      <PageHead title="Verificação pública" sub="Códigos que qualquer pessoa pode conferir sem ter conta na plataforma." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <Panel title={`${data.items.length} registro(s)`}>
            <ul className="rows">{data.items.map((r: any) => (
              <li key={r.id}>
                <span>
                  <strong>{r.title}</strong><br />
                  <code className="small">{r.code}</code> · versão {r.subject_version} · {dateTime(r.issued_at)}
                  <br /><span className="muted small">
                    {r.access_count} consulta(s) pública(s){r.last_accessed_at ? ` · última em ${dateTime(r.last_accessed_at)}` : ""}
                  </span>
                  {r.revocation_reason && <><br /><span className="muted small">Motivo da revogação: {r.revocation_reason}</span></>}
                </span>
                <span>
                  <Pill tone={r.status === "active" ? "good" : r.status === "revoked" ? "bad" : "warn"}>{r.status}</Pill>{" "}
                  <a href={`/v1/verifiable-records/${r.id}/qr`} target="_blank" rel="noreferrer">QR</a>{" "}
                  <Link to={`/verificar/${r.code}`}>Abrir página</Link>{" "}
                  {r.status === "active" && <Button onClick={() => setRevoking(r)}>Revogar</Button>}
                </span>
              </li>
            ))}</ul>
          </Panel>
        )}
        <Modal open={!!revoking} title="Revogar registro público" onClose={() => setRevoking(null)}
               footer={<><Button onClick={() => setRevoking(null)}>Cancelar</Button>
                 <Button variant="danger" busy={busy} onClick={revoke} disabled={reason.trim().length < 10}>Revogar</Button></>}>
          <p>O código continua existindo, mas a página pública passa a dizer <strong>REVOGADO</strong>, com a data e o
            motivo. Nada é apagado.</p>
          <Field label="Motivo (aparece na página pública)">
            <TextArea value={reason} onChange={setReason} rows={3} placeholder="Ex.: documento substituído por erro material." />
          </Field>
        </Modal>
      </StateView>
    </>
  );
}

// ============================================================ acordos assinados
export function Agreements() {
  const { data, error, loading, reload } = useLoad<any>("/v1/signed-agreements");
  return (
    <>
      <PageHead title="Acordos" sub="Contratos e termos assinados por todas as partes, com acompanhamento ao longo do tempo."
                actions={<Button variant="primary" onClick={() => navigate("/acordos/novo")}>Novo acordo</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data?.items?.length > 0 && (
          <ul className="rows">{data.items.map((a: any) => (
            <li key={a.id}>
              <span>
                <Link to={`/acordos/${a.id}`}><strong>{a.title}</strong></Link><br />
                <span className="muted small">
                  {AG_KIND.find(([k]) => k === a.kind)?.[1] || a.kind} · {a.signed_parties}/{a.required_parties} assinatura(s)
                  {a.value_cents ? ` · ${money(a.value_cents)}` : ""}
                </span>
              </span>
              <span>
                {a.awaiting_me && <Pill tone="warn">aguardando você</Pill>}{" "}
                <Pill tone={a.status === "active" ? "good" : a.status === "canceled" ? "bad" : "muted"}>{AG_STATUS[a.status] || a.status}</Pill>
              </span>
            </li>
          ))}</ul>
        )}
      </StateView>
    </>
  );
}

const EMPTY_AG = { kind: "service", title: "", summary: "", document_id: "", effective_from: "", effective_to: "", value: "" };

export function AgreementForm() {
  const f = useForm<any>(EMPTY_AG);
  const { busy, run } = useAction();
  async function create(e: any) {
    e.preventDefault();
    await run(async () => {
      const body: any = { kind: f.v.kind, title: f.v.title, document_id: f.v.document_id };
      if (f.v.summary) body.summary = f.v.summary;
      if (f.v.effective_from) body.effective_from = f.v.effective_from;
      if (f.v.effective_to) body.effective_to = f.v.effective_to;
      if (f.v.value) body.value_cents = Math.round(parseFloat(f.v.value.replace(",", ".")) * 100);
      const out = await api.post("/v1/signed-agreements", body);
      navigate(`/acordos/${out.id}`);
      return "Acordo criado em rascunho.";
    });
  }
  return (
    <>
      <PageHead title="Novo acordo" back="/acordos" />
      <Panel>
        <form onSubmit={create}>
          <Field label="Tipo"><Select value={f.v.kind} onChange={f.set("kind")} options={AG_KIND} /></Field>
          <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
          <Field label="Resumo" wide><TextArea value={f.v.summary} onChange={f.set("summary")} rows={3} /></Field>
          <Field label="Documento do acordo"
                 hint="Envie o arquivo em Documentos primeiro. O hash do arquivo é congelado quando o acordo vai para assinatura.">
            <Input value={f.v.document_id} onChange={f.set("document_id")} placeholder="UUID do documento" />
          </Field>
          <Field label="Vigência — início"><Input type="date" value={f.v.effective_from} onChange={f.set("effective_from")} /></Field>
          <Field label="Vigência — fim"><Input type="date" value={f.v.effective_to} onChange={f.set("effective_to")} /></Field>
          <Field label="Valor (R$)"><Input value={f.v.value} onChange={f.set("value")} placeholder="0,00" /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={!f.v.title || !f.v.document_id}>Criar rascunho</Button>
        </form>
      </Panel>
    </>
  );
}

export function AgreementDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/signed-agreements/${id}`, [id]);
  const { busy, run } = useAction();
  const [partyOrg, setPartyOrg] = useState("");
  const [partyRole, setPartyRole] = useState("provider");
  const [declining, setDeclining] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [msTitle, setMsTitle] = useState("");
  const [msDue, setMsDue] = useState("");

  const act = (fn: () => Promise<any>, msg: string) => run(async () => { await fn(); reload(); return msg; });

  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <PageHead title={data.title} back="/acordos"
                    sub={<><Pill tone={data.status === "active" ? "good" : data.status === "canceled" ? "bad" : "muted"}>{AG_STATUS[data.status]}</Pill>{" "}
                      {data.pending_signatures > 0 && <span className="muted">{data.pending_signatures} assinatura(s) pendente(s)</span>}</>}
                    actions={<>
                      {data.status === "draft" && (
                        <Button variant="primary" busy={busy}
                                onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/publish`), "Enviado para assinatura.")}>
                          Enviar para assinatura
                        </Button>
                      )}
                      {data.status === "awaiting_signatures" && (
                        <>
                          <SignBox subjectType="agreement" subjectId={id} onSigned={reload} title="Assinar acordo" />
                          <Button onClick={() => setDeclining(true)}>Recusar</Button>
                        </>
                      )}
                      {["active", "completed"].includes(data.status) && (
                        <Button busy={busy} onClick={() => act(
                          () => api.post("/v1/verifiable-records", { subject_type: "agreement", subject_id: id }),
                          "Código público gerado — veja em Verificação pública.")}>Gerar código público</Button>
                      )}
                    </>} />
          <Panel title="Dados">
            <KeyValue items={[
              ["Tipo", AG_KIND.find(([k]) => k === data.kind)?.[1] || data.kind],
              ["Resumo", data.summary || "—"],
              ["Vigência", data.effective_from ? `${date(data.effective_from)} a ${data.effective_to ? date(data.effective_to) : "indeterminado"}` : "—"],
              ["Valor", data.value_cents ? money(data.value_cents) : "—"],
              ["Impressão digital do documento", <code key="h" className="small">{data.content_sha256}</code>],
              ...(data.verification_code ? [["Código público", <Link key="v" to={`/verificar/${data.verification_code}`}>{data.verification_code}</Link>] as [string, ReactNode]] : []),
            ]} />
          </Panel>
          <Panel title="Partes" actions={data.status === "draft"
            ? <Button busy={busy} disabled={!partyOrg}
                      onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/parties`, { org_id: partyOrg, role: partyRole }),
                                         "Parte acrescentada.")}>Acrescentar</Button>
            : undefined}>
            <ul className="rows">{data.parties.map((p: any) => (
              <li key={p.id}>
                <span>{p.legal_name}<br /><span className="muted small">
                  {PARTY_ROLE.find(([k]) => k === p.role)?.[1] || p.role}{p.required ? " · obrigatória" : " · opcional"}
                </span>{p.decline_reason && <><br /><span className="muted small">Recusou: {p.decline_reason}</span></>}</span>
                <Pill tone={p.signed_at ? "good" : p.declined_at ? "bad" : "warn"}>
                  {p.signed_at ? `assinou em ${dateTime(p.signed_at)}` : p.declined_at ? "recusou" : "pendente"}
                </Pill>
              </li>
            ))}</ul>
            {data.status === "draft" && (
              <>
                <Field label="Organização (identificador)"><Input value={partyOrg} onChange={setPartyOrg} placeholder="UUID da organização" /></Field>
                <Field label="Papel"><Select value={partyRole} onChange={setPartyRole} options={PARTY_ROLE} /></Field>
              </>
            )}
          </Panel>
          <Panel title="Acompanhamento" actions={
            <Button busy={busy} disabled={!msTitle}
                    onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/milestones`,
                                                      { title: msTitle, ...(msDue ? { due_on: msDue } : {}) }),
                                       "Entrega registrada.").then(() => { setMsTitle(""); setMsDue(""); })}>
              Acrescentar entrega
            </Button>}>
            {data.milestones?.length ? (
              <ul className="rows">{data.milestones.map((m: any) => (
                <li key={m.id}>
                  <span>{m.title}{m.due_on && <><br /><span className="muted small">Prazo: {date(m.due_on)}</span></>}
                    {m.note && <><br /><span className="muted small">{m.note}</span></>}</span>
                  <Select aria-label="Situação do marco" value={m.status} options={MS_STATUS}
                          onChange={(v) => act(() => api.patch(`/v1/signed-agreements/${id}/milestones/${m.id}`, { status: v }),
                                               "Entrega atualizada.")} />
                </li>
              ))}</ul>
            ) : <p className="muted">Nenhuma entrega registrada.</p>}
            <Field label="Nova entrega"><Input value={msTitle} onChange={setMsTitle} placeholder="Ex.: Entrega do diagnóstico" /></Field>
            <Field label="Prazo"><Input type="date" value={msDue} onChange={setMsDue} /></Field>
          </Panel>
          <Modal open={declining} title="Recusar o acordo" onClose={() => setDeclining(false)}
                 footer={<><Button onClick={() => setDeclining(false)}>Cancelar</Button>
                   <Button variant="danger" busy={busy} disabled={declineReason.trim().length < 10}
                           onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/decline`, { reason: declineReason }),
                                              "Acordo recusado.").then(() => setDeclining(false))}>Recusar</Button></>}>
            <p>O acordo é cancelado para todas as partes e o motivo fica registrado.</p>
            <Field label="Motivo"><TextArea value={declineReason} onChange={setDeclineReason} rows={3} /></Field>
          </Modal>
        </>
      )}
    </StateView>
  );
}
