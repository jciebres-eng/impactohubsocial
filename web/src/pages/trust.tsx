import { useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import { date, dateTime, money } from "../format";
import { Link, navigate } from "../router";
import { useSession } from "../session";
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
  completed: "Concluído", canceled: "Cancelado", expired: "Expirado", superseded: "Substituído por versão nova" };
const PARTY_ROLE: [string, string][] = [["provider", "Prestador"], ["contractor", "Contratante"], ["funder", "Financiador"],
  ["professional", "Profissional"], ["witness", "Testemunha"], ["beneficiary_rep", "Representante dos beneficiários"], ["proponent", "Proponente (autoria da ideia)"]];
const FEE_PAYER: [string, string][] = [["funder", "Financiador"], ["contractor", "Contratante"], ["provider", "Prestador"]];
const FEE_MODE: [string, string][] = [["deducted", "Aporte único: cada destinatário recebe a sua parte do valor da operação"], ["additional", "Adicional ao valor (o projeto recebe o valor cheio)"]];
const PAYOUT_STATE: Record<string, [string, string]> = {
  awaiting_rule: ["não exigível (regra jurídica desligada)", "muted"], instruction_created: ["instruída", "warn"], payment_pending: ["transferência registrada — aguarda confirmação", "warn"],
  confirmed: ["confirmada por quem recebe", "good"], reconciled: ["conciliada", "good"], failed: ["falhou", "bad"], disputed: ["em disputa", "bad"],
  cancelled: ["cancelada", "muted"], refund_pending: ["devolução pendente", "warn"], refunded: ["devolvida", "muted"],
};
const PAYOUT_LINE: Record<string, string> = { project: "Destinação do projeto", platform_fee: "Infraestrutura e inteligência IMPACTO", proponent: "Participação de autoria e desenvolvimento", third_party: "Terceiros" };
const PART_STATUS: Record<string, [string, string]> = {
  proposed: ["proposta", "warn"], under_review: ["em análise", "warn"], accepted: ["aceita", "good"], consolidated: ["consolidada", "good"],
  eligible: ["elegível", "good"], accrued: ["na matriz do acordo", "good"], validated: ["validada", "good"], payable: ["a pagar", "warn"],
  paid: ["paga", "good"], disputed: ["em disputa", "bad"], cancelled: ["cancelada", "muted"],
};
const PIX_TYPES: [string, string][] = [["cnpj", "CNPJ"], ["cpf", "CPF"], ["email", "E-mail"], ["phone", "Telefone"], ["evp", "Chave aleatória"]];
const CALENDAR: [string, string][] = [["business", "Dias úteis"], ["calendar", "Dias corridos"]];
const OB_STATUS: Record<string, string> = { open: "em aberto", done: "cumprida", overdue: "vencida", waived: "dispensada" };
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

const EMPTY_AG = { kind: "service", title: "", summary: "", document_id: "", effective_from: "", effective_to: "", value: "",
  fee_pct: "", fee_payer_role: "funder", fee_mode: "deducted", review_days: "10", calendar_type: "business", dispute_days: "5" };

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
      if (f.v.kind !== "funding" && f.v.fee_pct) {
        body.platform_fee_bps = Math.round(parseFloat(f.v.fee_pct.replace(",", ".")) * 100);
        body.fee_payer_role = f.v.fee_payer_role;
      }
      body.fee_mode = f.v.fee_mode;
      if (f.v.review_days) body.review_days = parseInt(f.v.review_days, 10);
      body.calendar_type = f.v.calendar_type;
      if (f.v.dispute_days !== "") body.dispute_days = parseInt(f.v.dispute_days, 10);
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
          <h3>Regras de operação do contrato</h3>
          <p className="muted small">
            Estas cláusulas viram obrigações, prazos e a matriz de distribuição quando o acordo entra em vigor. A taxa da plataforma,
            se houver, é calculada na origem e paga por quem o contrato indicar, em cobrança separada — nunca descontada de dinheiro
            em trânsito. Ela só é cobrada quando a regra comercial estiver ativa com parecer jurídico registrado.
          </p>
          {f.v.kind === "funding" ? (
            <p className="small">
              <strong>Acordo de financiamento:</strong> a camada econômica vem da versão de preços vigente, não deste formulário —
              infraestrutura e inteligência IMPACTO (3,50%) e, quando houver autoria elegível aceita, participação de autoria e
              desenvolvimento da ideia (1,50%). Quem financia faz um aporte único, direcionado a cada destinatário pela chave PIX
              informada no contrato; a plataforma calcula, instrui e concilia, sem custodiar.
            </p>
          ) : (<>
            <Field label="Taxa de serviço da plataforma (%)" hint="Deixe em branco se o contrato não prevê taxa.">
              <Input value={f.v.fee_pct} onChange={f.set("fee_pct")} placeholder="ex.: 3" inputMode="decimal" />
            </Field>
            <Field label="Quem paga a taxa"><Select value={f.v.fee_payer_role} onChange={f.set("fee_payer_role")} options={FEE_PAYER} /></Field>
          </>)}
          <Field label="Como a camada econômica se relaciona com o valor" wide><Select value={f.v.fee_mode} onChange={f.set("fee_mode")} options={FEE_MODE} /></Field>
          <Field label="Prazo para aceitar uma entrega" hint="Contado a partir do registro da entrega.">
            <Input type="number" min={1} max={120} value={f.v.review_days} onChange={f.set("review_days")} />
          </Field>
          <Field label="Contagem do prazo"><Select value={f.v.calendar_type} onChange={f.set("calendar_type")} options={CALENDAR} /></Field>
          <Field label="Prazo para contestar (dias)"><Input type="number" min={0} max={60} value={f.v.dispute_days} onChange={f.set("dispute_days")} /></Field>
          <Button type="submit" variant="primary" busy={busy} disabled={!f.v.title || !f.v.document_id}>Criar rascunho</Button>
        </form>
      </Panel>
    </>
  );
}

function AllocationMatrix({ alloc, parties, owner, preview }: { alloc: any; parties: any[]; owner: { id: string; name: string }; preview: boolean }) {
  const name = (orgId: string | null, role: string | null, toName?: string | null) =>
    orgId ? ((toName || parties.find((p) => p.org_id === orgId)?.legal_name || (orgId === owner.id ? owner.name : orgId.slice(0, 8))) + (role === "proponent" ? " (autoria)" : orgId === owner.id ? " (executa)" : ""))
      : role === "platform" ? "Plataforma Impacto — infraestrutura e inteligência" : "—";
  return (
    <>
      {preview && <p className="muted small">Prévia calculada a partir das cláusulas. A matriz definitiva é congelada quando o acordo entra em vigor.</p>}
      <table className="table">
        <thead><tr><th>Destino</th><th>Base</th><th>Quem paga</th><th>Valor</th></tr></thead>
        <tbody>
          {(alloc.lines || []).map((l: any, i: number) => (
            <tr key={i}>
              <td>{name(l.to_org_id, l.role, l.to_name)}{l.kind === "platform_fee" && (
                <> <Pill tone={l.chargeable ? "good" : "muted"}>{l.chargeable ? "cobrável" : "registrada, não cobrada"}</Pill></>)}</td>
              <td className="small">{l.basis}</td>
              <td className="small">{l.paid_by}</td>
              <td>{money(l.cents)}</td>
            </tr>
          ))}
          <tr><td><strong>Valor da operação</strong></td><td className="muted small">aporte único de quem financia · não é receita da plataforma</td><td /><td><strong>{money(alloc.gross_cents)}</strong></td></tr>
        </tbody>
      </table>
      <KeyValue items={[
        ["Camada econômica", `${money(alloc.economic_layer_cents ?? ((alloc.platform_fee_cents || 0) + (alloc.proponent_cents || 0)))} = plataforma ${money(alloc.platform_fee_cents || 0)}${alloc.proponent_cents ? ` + autoria ${money(alloc.proponent_cents)}` : ""}`],
        ["Taxa da plataforma", alloc.fee_bps ? `${(alloc.fee_bps / 100).toFixed(2)}% · ${alloc.fee_mode === "deducted" ? "dentro do valor da operação" : "adicional ao valor"}` : "não prevista no contrato"],
        ...(alloc.proponent_reason ? [["Participação de autoria", alloc.proponent_reason] as [string, ReactNode]] : []),
        ["Situação da taxa", alloc.fee_reason],
        ...(alloc.platform_charge_id ? [["Cobrança própria", <span key="c">nº <code className="small">{alloc.platform_charge_id.slice(0, 8)}</code> emitida ao pagador da taxa — separada do dinheiro do projeto</span>] as [string, ReactNode]] : []),
        ["Tabela de preços", alloc.pricing_version || "—"],
        ["Impressão digital", <code key="h" className="small">{alloc.allocation_hash}</code>],
      ]} />
      <p className="muted small">{alloc.note || "A plataforma calcula, instrui e concilia. Não custodia: cada linha é paga por quem paga, pelo meio que as partes escolheram."}</p>
    </>
  );
}

export function AgreementDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/signed-agreements/${id}`, [id]);
  const { busy, run } = useAction();
  const { me } = useSession();
  const [partyOrg, setPartyOrg] = useState("");
  const [partyRole, setPartyRole] = useState("provider");
  const [declining, setDeclining] = useState(false);
  const [declineReason, setDeclineReason] = useState("");
  const [msTitle, setMsTitle] = useState("");
  const [msDue, setMsDue] = useState("");
  const [msAmount, setMsAmount] = useState("");
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [rejectNote, setRejectNote] = useState("");
  const [versioning, setVersioning] = useState(false);
  const [pixParty, setPixParty] = useState<string | null>(null);
  const [pixKey, setPixKey] = useState("");
  const [pixType, setPixType] = useState("cnpj");
  const [transferFor, setTransferFor] = useState<string | null>(null);
  const [trAmount, setTrAmount] = useState("");
  const [trRef, setTrRef] = useState("");
  const [trDate, setTrDate] = useState(new Date().toISOString().slice(0, 10));
  const [rejectingTransfer, setRejectingTransfer] = useState<string | null>(null);
  const [rejectTransferNote, setRejectTransferNote] = useState("");
  const [cancelling, setCancelling] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const { data: value } = useLoad<any>(`/v1/signed-agreements/${id}/value`, [id, data?.status]);
  const [vDoc, setVDoc] = useState("");
  const [vReason, setVReason] = useState("");

  const act = (fn: () => Promise<any>, msg: string) => run(async () => { await fn(); reload(); return msg; });
  const myOrg = me?.active_org?.id;
  const isOwner = data && myOrg === data.org_id;
  const isParty = data && data.parties?.some((p: any) => p.org_id === myOrg);
  const isCounterparty = isParty && !isOwner;
  const editable = data && data.status === "draft";
  const live = data && data.status === "active";
  const terms = data?.terms || {};
  const alloc = data?.allocation || data?.allocation_preview;
  const openObligations = (data?.obligations || []).filter((o: any) => o.status === "open");
  const mine = openObligations.filter((o: any) => o.obligor_org_id === myOrg);

  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {data && (
        <>
          <PageHead title={data.title} back="/acordos"
                    sub={<><Pill tone={data.status === "active" ? "good" : ["canceled", "superseded"].includes(data.status) ? "bad" : "muted"}>{AG_STATUS[data.status] || data.status}</Pill>{" "}
                      <span className="muted">versão {terms.version || 1}</span>{" "}
                      {data.pending_signatures > 0 && <span className="muted">· {data.pending_signatures} assinatura(s) pendente(s)</span>}</>}
                    actions={<>
                      {editable && isOwner && (
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
                      {["awaiting_signatures", "active"].includes(data.status) && isOwner && (
                        <Button onClick={() => setVersioning(true)}>Nova versão</Button>
                      )}
                      {data.status === "active" && (isOwner || data.parties?.some((p: any) => p.org_id === myOrg && p.role === "funder")) && (
                        <Button onClick={() => setCancelling(true)}>Cancelar acordo</Button>
                      )}
                      {["active", "completed"].includes(data.status) && (
                        <Button busy={busy} onClick={() => act(
                          () => api.post("/v1/verifiable-records", { subject_type: "agreement", subject_id: id }),
                          "Código público gerado — veja em Verificação pública.")}>Gerar código público</Button>
                      )}
                    </>} />
          {data.status === "superseded" && (
            <Panel>
              <p>Esta versão foi substituída{terms.version_reason ? `: ${terms.version_reason}` : "."}{" "}
                {terms.superseded_by_id && <Link to={`/acordos/${terms.superseded_by_id}`}>Abrir a versão vigente</Link>}</p>
            </Panel>
          )}
          {mine.length > 0 && (
            <Panel title="Precisa da sua decisão">
              <ul className="rows">{mine.map((o: any) => (
                <li key={o.id}><span>{o.title}{o.due_on && <><br /><span className="muted small">até {date(o.due_on)}</span></>}</span>
                  {o.overdue ? <Pill tone="bad">vencida</Pill> : <Pill tone="warn">aberta</Pill>}</li>
              ))}</ul>
            </Panel>
          )}
          <Panel title="Dados">
            <KeyValue items={[
              ["Tipo", AG_KIND.find(([k]) => k === data.kind)?.[1] || data.kind],
              ["Resumo", data.summary || "—"],
              ["Vigência", data.effective_from ? `${date(data.effective_from)} a ${data.effective_to ? date(data.effective_to) : "indeterminado"}` : "—"],
              ["Valor", data.value_cents ? money(data.value_cents) : "—"],
              ["Em vigor desde", terms.activated_at ? dateTime(terms.activated_at) : "—"],
              ["Impressão digital do documento", <code key="h" className="small">{data.content_sha256}</code>],
              ...(data.verification_code ? [["Código público", <Link key="v" to={`/verificar/${data.verification_code}`}>{data.verification_code}</Link>] as [string, ReactNode]] : []),
            ]} />
          </Panel>
          <Panel title="Regras de operação">
            <KeyValue items={[
              ["Taxa da plataforma", terms.platform_fee_bps ? `${(terms.platform_fee_bps / 100).toFixed(2)}%, paga por ${FEE_PAYER.find(([k]) => k === terms.fee_payer_role)?.[1]?.toLowerCase() || "parte não definida"} (${terms.fee_mode === "deducted" ? "descontada do valor" : "adicional ao valor"})` : "não prevista"],
              ["Aceite de entregas", `${terms.review_days ?? 10} ${terms.calendar_type === "calendar" ? "dias corridos" : "dias úteis"} após o registro da entrega${terms.auto_accept ? " · aceite tácito ao vencer" : " · sem aceite tácito"}`],
              ["Participação de autoria", terms.proponent_participation_bps ? `${(terms.proponent_participation_bps / 100).toFixed(2)}% quando houver proponente elegível e parte no acordo` : "não prevista"],
              ["Versão de preços", terms.economic_rule_version || "— (cláusula livre entre as partes)"],
              ["Contestação", `${terms.dispute_days ?? 5} dias`],
              ["Versão", `${terms.version || 1}${terms.supersedes_id ? " (substitui versão anterior)" : ""}`],
            ]} />
          </Panel>
          {alloc && (data.value_cents > 0) && (
            <Panel title="Matriz de distribuição">
              <AllocationMatrix alloc={alloc} parties={data.parties} owner={{ id: data.org_id, name: data.owner_name }} preview={!data.allocation} />
            </Panel>
          )}
          <Panel title="Partes" actions={editable && isOwner
            ? <Button busy={busy} disabled={!partyOrg}
                      onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/parties`, { org_id: partyOrg, role: partyRole }),
                                         "Parte acrescentada.")}>Acrescentar</Button>
            : undefined}>
            <ul className="rows">{data.parties.map((p: any) => (
              <li key={p.id}>
                <span>{p.legal_name}<br /><span className="muted small">
                  {PARTY_ROLE.find(([k]) => k === p.role)?.[1] || p.role}{p.required ? " · obrigatória" : " · opcional"}
                </span>{p.decline_reason && <><br /><span className="muted small">Recusou: {p.decline_reason}</span></>}
                  <br /><span className="muted small">PIX: {p.pix_key ? <code className="small">{p.pix_key}</code> : p.pix_key_masked ? <code className="small">{p.pix_key_masked}</code> : "não informada"}{p.pix_key_type ? ` (${p.pix_key_type})` : ""}</span>
                  {p.org_id === myOrg && !["canceled", "superseded", "completed"].includes(data.status) && (
                    <span className="small"> · <button type="button" className="linklike" onClick={() => { setPixParty(p.id); setPixKey(""); setPixType("cnpj"); }}>{p.pix_key ? "alterar" : "informar minha chave"}</button></span>
                  )}</span>
                <Pill tone={p.signed_at ? "good" : p.declined_at ? "bad" : "warn"}>
                  {p.signed_at ? `assinou em ${dateTime(p.signed_at)}` : p.declined_at ? "recusou" : "pendente"}
                </Pill>
              </li>
            ))}</ul>
            {editable && isOwner && (
              <>
                <Field label="Organização (identificador)"><Input value={partyOrg} onChange={setPartyOrg} placeholder="UUID da organização" /></Field>
                <Field label="Papel"><Select value={partyRole} onChange={setPartyRole} options={PARTY_ROLE} /></Field>
              </>
            )}
          </Panel>
          <Panel title="Entregas e aceite" actions={editable && isOwner ? (
            <Button busy={busy} disabled={!msTitle}
                    onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/milestones`,
                                                      { title: msTitle, ...(msDue ? { due_on: msDue } : {}),
                                                        ...(msAmount ? { amount_cents: Math.round(parseFloat(msAmount.replace(",", ".")) * 100) } : {}) }),
                                       "Entrega registrada.").then(() => { setMsTitle(""); setMsDue(""); setMsAmount(""); })}>
              Acrescentar entrega
            </Button>) : undefined}>
            <p className="muted small">Quem executa registra a entrega; a outra parte aceita ou recusa dentro do prazo do contrato. Ninguém aceita a própria entrega.</p>
            {data.milestones?.length ? (
              <ul className="rows">{data.milestones.map((m: any) => (
                <li key={m.id}>
                  <span>{m.seq ? `${m.seq}. ` : ""}{m.title}{m.amount_cents ? ` · ${money(m.amount_cents)}` : ""}
                    {m.due_on && <><br /><span className="muted small">Prazo: {date(m.due_on)}</span></>}
                    {m.delivered_at && <><br /><span className="muted small">Entregue em {dateTime(m.delivered_at)}{m.acceptance_due_on ? ` · aceite até ${date(m.acceptance_due_on)}` : ""}</span></>}
                    {m.accepted_at && <><br /><span className="muted small">{m.status === "accepted" ? "Aceita" : "Recusada"} em {dateTime(m.accepted_at)}</span></>}
                    {m.rejection_reason && <><br /><span className="muted small">Motivo: {m.rejection_reason}</span></>}
                    {m.note && m.note !== m.rejection_reason && <><br /><span className="muted small">{m.note}</span></>}</span>
                  <span>
                    <Pill tone={m.status === "accepted" ? "good" : m.status === "rejected" ? "bad" : m.status === "delivered" ? "warn" : "muted"}>
                      {MS_STATUS.find(([k]) => k === m.status)?.[1] || m.status}
                    </Pill>{" "}
                    {live && isOwner && ["planned", "in_progress", "rejected"].includes(m.status) && (
                      <Button busy={busy} onClick={() => act(() => api.patch(`/v1/signed-agreements/${id}/milestones/${m.id}`, { status: "delivered" }), "Entrega registrada. A outra parte tem o prazo do contrato para aceitar.")}>
                        Registrar entrega
                      </Button>
                    )}
                    {live && isCounterparty && m.status === "delivered" && (
                      <>
                        <Button variant="primary" busy={busy} onClick={() => act(() => api.patch(`/v1/signed-agreements/${id}/milestones/${m.id}`, { status: "accepted" }), "Entrega aceita. A obrigação de pagar ficou em aberto com prazo.")}>
                          Aceitar
                        </Button>{" "}
                        <Button busy={busy} onClick={() => { setRejecting(m.id); setRejectNote(""); }}>Recusar</Button>
                      </>
                    )}
                  </span>
                </li>
              ))}</ul>
            ) : <p className="muted">Nenhuma entrega registrada.</p>}
            {editable && isOwner && (
              <>
                <Field label="Nova entrega"><Input value={msTitle} onChange={setMsTitle} placeholder="Ex.: Entrega do diagnóstico" /></Field>
                <Field label="Prazo"><Input type="date" value={msDue} onChange={setMsDue} /></Field>
                <Field label="Valor desta entrega (R$)"><Input value={msAmount} onChange={setMsAmount} placeholder="0,00" inputMode="decimal" /></Field>
              </>
            )}
          </Panel>
          {data.obligations?.length > 0 && (
            <Panel title="Obrigações derivadas do contrato">
              <table className="table">
                <thead><tr><th>Obrigação</th><th>Responsável</th><th>Prazo</th><th>Situação</th></tr></thead>
                <tbody>{data.obligations.map((o: any) => (
                  <tr key={o.id}>
                    <td>{o.title}</td>
                    <td className="small">{o.obligor_name}</td>
                    <td className="small">{o.due_on ? date(o.due_on) : "—"}</td>
                    <td><Pill tone={o.status === "done" ? "good" : o.overdue || o.status === "overdue" ? "bad" : o.status === "waived" ? "muted" : "warn"}>
                      {o.overdue && o.status === "open" ? "vencida" : OB_STATUS[o.status] || o.status}</Pill></td>
                  </tr>
                ))}</tbody>
              </table>
            </Panel>
          )}
          {data.payouts?.length > 0 && (
            <Panel title="Repasses: quem paga a quem, por qual chave, e o que já foi confirmado" actions={
              <Pill tone={data.settlement?.settled ? "good" : data.settlement?.status === "payment_pending" ? "warn" : "muted"}>
                {data.settlement?.settled ? "operação quitada" : data.settlement?.status === "confirmed" ? "repasses confirmados" : data.settlement?.status === "payment_pending" ? "aguardando confirmação" : "instruída"}
              </Pill>}>
              <p className="muted small">A plataforma não move dinheiro. Quem paga transfere pela chave informada no contrato e registra a transferência; quem recebe confirma. Nada fica "pago" por existir registro.</p>
              <ul className="rows">{data.payouts.map((po: any) => (
                <li key={po.id}>
                  <span>{PAYOUT_LINE[po.line_kind] || po.line_kind}: <strong>{po.recipient_label}</strong> · {money(po.amount_cents)}
                    <br /><span className="muted small">chave PIX: {po.pix_key ? <code className="small">{po.pix_key}</code> : po.pix_key_masked ? <code className="small">{po.pix_key_masked}</code> : (po.line_kind === "platform_fee" ? "NÃO CONFIGURADA" : "não informada no contrato")}
                      {po.confirmed_cents > 0 ? ` · confirmado ${money(po.confirmed_cents)}` : ""}{po.paid_cents > po.confirmed_cents ? ` · registrado ${money(po.paid_cents)}` : ""}</span>
                    {po.transfers?.length > 0 && <ul className="small">{po.transfers.map((t: any) => (
                      <li key={t.id}>{money(t.amount_cents)} · ref. {t.reference} · {date(t.paid_on)} · {t.status === "confirmed" ? "confirmada" : t.status === "rejected" ? `recusada: ${t.rejection_reason}` : "registrada"}
                        {t.status === "registered" && po.recipient_org_id === myOrg && (<> · <Button busy={busy} onClick={() => act(() => api.post(`/v1/payout-transfers/${t.id}/confirm`), "Recebimento confirmado.")}>Confirmar recebimento</Button>{" "}
                          <Button busy={busy} onClick={() => { setRejectingTransfer(t.id); setRejectTransferNote(""); }}>Não chegou</Button></>)}
                      </li>))}</ul>}
                  </span>
                  <span>
                    <Pill tone={PAYOUT_STATE[po.state]?.[1] || "muted"}>{PAYOUT_STATE[po.state]?.[0] || po.state}</Pill>{" "}
                    {po.payer_org_id === myOrg && ["instruction_created", "payment_pending", "failed", "disputed"].includes(po.state) && po.remaining_cents > 0 && (
                      <Button variant="primary" onClick={() => { setTransferFor(po.id); setTrAmount(((po.amount_cents - po.paid_cents) / 100).toFixed(2).replace(".", ",")); setTrRef(""); }}>Registrar transferência</Button>
                    )}
                    {po.recipient_org_id === myOrg && po.state === "confirmed" && (
                      <Button busy={busy} onClick={() => act(() => api.post(`/v1/payouts/${po.id}/reconcile`, { reason: "Conferido com o extrato bancário." }), "Repasse conciliado.")}>Conciliar com extrato</Button>
                    )}
                  </span>
                </li>
              ))}</ul>
            </Panel>
          )}
          {value && (
            <Panel title="O que o IMPACTO fez nesta operação">
              <ul className="rows">{value.items.map((it: any, i: number) => (
                <li key={i}><span>{it.what}<br /><span className="muted small">{it.evidence}</span></span><span className="muted small">{it.source}</span></li>
              ))}</ul>
              <p className="muted small">{value.note} {value.value_capture?.ratio_note}</p>
            </Panel>
          )}
          {data.participations?.length > 0 && (
            <Panel title="Participação de autoria e desenvolvimento da ideia">
              <ul className="rows">{data.participations.map((pp: any) => (
                <li key={pp.id}><span>{pp.proponent_name}<br /><span className="muted small">{pp.authorship_type === "author" ? "autoria" : "coautoria"} · fração {(pp.share_bps / 100).toFixed(2)}%</span></span>
                  <Pill tone={PART_STATUS[pp.status]?.[1] || "muted"}>{PART_STATUS[pp.status]?.[0] || pp.status}</Pill></li>
              ))}</ul>
            </Panel>
          )}
          {data.versions?.length > 0 && (
            <Panel title="Histórico de versões">
              <ul className="rows">{data.versions.map((v: any) => (
                <li key={v.version}>
                  <span>Versão {v.version}{v.reason && <><br /><span className="muted small">{v.reason}</span></>}
                    <br /><code className="small">{v.content_sha256.slice(0, 16)}…</code></span>
                  <span className="muted small">{dateTime(v.created_at)}</span>
                </li>
              ))}</ul>
            </Panel>
          )}
          <Modal open={declining} title="Recusar o acordo" onClose={() => setDeclining(false)}
                 footer={<><Button onClick={() => setDeclining(false)}>Cancelar</Button>
                   <Button variant="danger" busy={busy} disabled={declineReason.trim().length < 10}
                           onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/decline`, { reason: declineReason }),
                                              "Acordo recusado.").then(() => setDeclining(false))}>Recusar</Button></>}>
            <p>O acordo é cancelado para todas as partes e o motivo fica registrado.</p>
            <Field label="Motivo"><TextArea value={declineReason} onChange={setDeclineReason} rows={3} /></Field>
          </Modal>
          <Modal open={!!rejecting} title="Recusar a entrega" onClose={() => setRejecting(null)}
                 footer={<><Button onClick={() => setRejecting(null)}>Cancelar</Button>
                   <Button variant="danger" busy={busy} disabled={rejectNote.trim().length < 10}
                           onClick={() => act(() => api.patch(`/v1/signed-agreements/${id}/milestones/${rejecting}`, { status: "rejected", note: rejectNote }),
                                              "Entrega recusada. Quem executa pode corrigir e registrar de novo.").then(() => setRejecting(null))}>Recusar entrega</Button></>}>
            <p>A entrega volta para quem executa, com o motivo registrado no acordo e no razão do projeto.</p>
            <Field label="Motivo"><TextArea value={rejectNote} onChange={setRejectNote} rows={3} /></Field>
          </Modal>
          <Modal open={!!pixParty} title="Minha chave PIX neste acordo" onClose={() => setPixParty(null)}
                 footer={<><Button onClick={() => setPixParty(null)}>Cancelar</Button>
                   <Button variant="primary" busy={busy} disabled={pixKey.trim().length < 3}
                           onClick={() => act(() => api.put(`/v1/signed-agreements/${id}/parties/${pixParty}/pix`, { pix_key: pixKey, pix_key_type: pixType }),
                                              "Chave PIX registrada no acordo.").then(() => setPixParty(null))}>Registrar chave</Button></>}>
            <p>A chave fica no contrato e aparece na instrução de repasse para quem paga. A plataforma nunca a usa para mover dinheiro.</p>
            <Field label="Tipo"><Select value={pixType} onChange={setPixType} options={PIX_TYPES} /></Field>
            <Field label="Chave"><Input value={pixKey} onChange={setPixKey} placeholder={pixType === "cnpj" ? "somente números" : pixType === "phone" ? "+55 DDD número" : ""} /></Field>
          </Modal>
          <Modal open={!!transferFor} title="Registrar transferência feita" onClose={() => setTransferFor(null)}
                 footer={<><Button onClick={() => setTransferFor(null)}>Cancelar</Button>
                   <Button variant="primary" busy={busy} disabled={!trAmount || trRef.trim().length < 3}
                           onClick={() => act(() => api.post(`/v1/payouts/${transferFor}/transfers`, { amount_cents: Math.round(parseFloat(trAmount.replace(",", ".")) * 100), reference: trRef, paid_on: trDate }),
                                              "Transferência registrada. Quem recebe vai confirmar.").then(() => setTransferFor(null))}>Registrar</Button></>}>
            <p>Registre a transferência que você fez pela chave do contrato (pode ser parcial). A mesma referência nunca é contada duas vezes. Quem recebe confirma o recebimento.</p>
            <Field label="Valor (R$)"><Input value={trAmount} onChange={setTrAmount} inputMode="decimal" /></Field>
            <Field label="Referência (E2E / comprovante)"><Input value={trRef} onChange={setTrRef} placeholder="E2E…" /></Field>
            <Field label="Data"><Input type="date" value={trDate} onChange={setTrDate} /></Field>
          </Modal>
          <Modal open={!!rejectingTransfer} title="Transferência não recebida" onClose={() => setRejectingTransfer(null)}
                 footer={<><Button onClick={() => setRejectingTransfer(null)}>Cancelar</Button>
                   <Button variant="danger" busy={busy} disabled={rejectTransferNote.trim().length < 10}
                           onClick={() => act(() => api.post(`/v1/payout-transfers/${rejectingTransfer}/reject`, { reason: rejectTransferNote }),
                                              "Transferência recusada; o repasse ficou em disputa.").then(() => setRejectingTransfer(null))}>Recusar</Button></>}>
            <Field label="O que aconteceu"><TextArea value={rejectTransferNote} onChange={setRejectTransferNote} rows={3} /></Field>
          </Modal>
          <Modal open={cancelling} title="Cancelar o acordo vigente" onClose={() => setCancelling(false)}
                 footer={<><Button onClick={() => setCancelling(false)}>Voltar</Button>
                   <Button variant="danger" busy={busy} disabled={cancelReason.trim().length < 10}
                           onClick={() => act(() => api.post(`/v1/signed-agreements/${id}/cancel`, { reason: cancelReason }),
                                              "Acordo cancelado; repasses não confirmados foram cancelados com estorno.").then(() => setCancelling(false))}>Cancelar acordo</Button></>}>
            <p>Obrigações abertas são dispensadas; instruções de repasse não confirmadas são canceladas e estornadas no ledger econômico. O que já foi confirmado fica registrado.</p>
            <Field label="Motivo"><TextArea value={cancelReason} onChange={setCancelReason} rows={3} /></Field>
          </Modal>
          <Modal open={versioning} title="Nova versão do acordo" onClose={() => setVersioning(false)}
                 footer={<><Button onClick={() => setVersioning(false)}>Cancelar</Button>
                   <Button variant="primary" busy={busy} disabled={!vDoc || vReason.trim().length < 10}
                           onClick={() => run(async () => {
                             const out = await api.post(`/v1/signed-agreements/${id}/new-version`, { document_id: vDoc, reason: vReason });
                             setVersioning(false);
                             navigate(`/acordos/${out.id}`);
                             return "Nova versão criada em rascunho. A anterior foi substituída e as assinaturas dela não valem para esta.";
                           })}>Criar versão</Button></>}>
            <p>Mudar o contrato cria uma versão nova: as partes assinam de novo e a aprovação anterior deixa de valer. Partes e entregas são copiadas.</p>
            <Field label="Documento da nova versão" hint="Envie o arquivo em Documentos primeiro.">
              <Input value={vDoc} onChange={setVDoc} placeholder="UUID do documento" />
            </Field>
            <Field label="O que mudou e por quê"><TextArea value={vReason} onChange={setVReason} rows={3} /></Field>
          </Modal>
        </>
      )}
    </StateView>
  );
}
