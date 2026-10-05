import { useEffect, useRef, useState } from "react";
import { api, describeError } from "../api";
import { date, label } from "../format";
import { Link, navigate, useLocation } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea, useAction, useLoad, useTaxonomy, useToast } from "../ui/kit";
import { ContextHelp } from "./help";
import { DocLink } from "./projects";

/** Botão de upload com validação de tamanho no cliente (o servidor valida tipo real, conteúdo ativo e antivírus). */
export function UploadButton({ docType, projectId, applicationId, onUploaded, label: text = "Enviar arquivo", done, validUntil }: {
  docType: string; projectId?: string; applicationId?: string; onUploaded: (d: any) => void; label?: string; done?: boolean; validUntil?: string;
}) {
  const ref = useRef<any>(null);
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  async function pick(e: any) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 15 * 1048576) return toast("Arquivo maior que 15 MB.", "err");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("doc_type", docType);
    fd.append("title", file.name);
    if (projectId) fd.append("project_id", projectId);
    if (applicationId) fd.append("application_id", applicationId);
    if (validUntil) fd.append("valid_until", validUntil);
    setBusy(true);
    try {
      const d = await api.upload("/v1/documents", fd);
      toast(d.status === "pending_scan" ? "Arquivo recebido; aguardando verificação antivírus" : "Arquivo enviado");
      onUploaded(d);
    } catch (err) {
      toast(describeError(err), "err");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <input ref={ref} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx,.csv,.txt" onChange={pick} />
      <Button variant={done ? "ghost" : "ink"} busy={busy} onClick={() => ref.current?.click()}>{done ? "Arquivo anexado" : text}</Button>
    </>
  );
}

export function Documents() {
  const tax = useTaxonomy();
  const [offset, setOffset] = useState(0);
  const [type, setType] = useState("");
  const { data, error, loading, reload } = useLoad<any>(`/v1/documents?offset=${offset}${type ? `&doc_type=${type}` : ""}`, [offset, type]);
  const [upType, setUpType] = useState("estatuto_social");
  const [validUntil, setValidUntil] = useState("");
  const [suggest, setSuggest] = useState<any>(null);
  const { run } = useAction();
  const docOpts = Object.entries(tax?.document_types || {}).map(([k, v]: any) => [k, v.label]) as [string, string][];
  return (
    <>
      <PageHead title="Documentos" sub="Cofre privado: cada arquivo tem tipo verificado, hash SHA-256, validade e acesso só para quem precisa."
                actions={<><Link to="/documentos/montagens">Montagem de documentos</Link>{" · "}
                           <Link to="/documentos/modelos">Modelos</Link></>} />
      <ContextHelp ctxKey="documents.upload" />
      <Panel title="Enviar documento">
        <div className="inline-form">
          <Field label="Tipo"><Select value={upType} onChange={setUpType} options={docOpts} /></Field>
          {tax?.document_types?.[upType]?.expires && <Field label="Válido até"><Input type="date" value={validUntil} onChange={setValidUntil} /></Field>}
          <Field label="Arquivo" hint="PDF, imagem, DOCX, XLSX, CSV ou TXT — até 15 MB">
            <UploadButton docType={upType} validUntil={validUntil || undefined} onUploaded={(d) => { setSuggest(d.suggestion ? { ...d.suggestion, id: d.id } : null); reload(); }} />
          </Field>
        </div>
        {suggest && suggest.suggested_type !== "outro" && (
          <p className="assist">Pelo conteúdo, este arquivo parece ser <strong>{tax?.document_types?.[suggest.suggested_type]?.label}</strong>
            {suggest.valid_until && <> com validade até <strong>{date(suggest.valid_until)}</strong></>}.{" "}
            {suggest.valid_until && <Button variant="link" onClick={() => run(() => api.patch(`/v1/documents/${suggest.id}`, { valid_until: suggest.valid_until }), "Validade registrada").then(() => { setSuggest(null); reload(); })}>Usar esta validade</Button>}
          </p>
        )}
      </Panel>
      <div className="filters"><Field label="Filtrar por tipo"><Select value={type} onChange={(v) => { setType(v); setOffset(0); }} placeholder="Todos" options={docOpts} /></Field></div>
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhum documento enviado."}>
        <table className="table">
          <thead><tr><th>Documento</th><th>Tipo</th><th>Validade</th><th>Verificação</th><th /></tr></thead>
          <tbody>
            {data?.items.map((d: any) => (
              <tr key={d.id}>
                <td>{d.title}<br /><code className="hash" title={d.sha256}>{d.sha256.slice(0, 12)}…</code></td>
                <td>{tax?.document_types?.[d.doc_type]?.label || d.doc_type}</td>
                <td>{d.expired ? <Pill tone="bad">Vencido em {date(d.valid_until)}</Pill> : d.expiring_soon ? <Pill tone="warn">Vence {date(d.valid_until)}</Pill> : date(d.valid_until)}</td>
                <td><Pill status={d.status} /></td>
                <td className="row-actions"><DocLink id={d.id} />
                  <Button variant="link" onClick={() => confirm("Excluir este documento? A trilha de auditoria é mantida.") && run(() => api.del(`/v1/documents/${d.id}`), "Documento excluído").then(reload)}>Excluir</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}

const DRAFT_KINDS: [string, string][] = [["project_proposal", "Proposta de projeto"], ["work_plan", "Plano de trabalho"], ["budget_justification", "Justificativa orçamentária"],
  ["cover_letter", "Carta de apresentação"], ["progress_report", "Relatório parcial"], ["final_report", "Relatório final"]];

export function Drafts() {
  const { query } = useLocation();
  const { me } = useSession();
  const { data, error, loading, reload } = useLoad<any>("/v1/drafts?limit=100");
  const projects = useLoad<any>(me?.active_org?.kind === "osc" ? "/v1/projects?limit=100" : null);
  const [kind, setKind] = useState("project_proposal");
  const [project, setProject] = useState(query.get("projeto") || "");
  const [instr, setInstr] = useState("");
  const { busy, run } = useAction();
  const appId = query.get("novo");
  async function create(withAi: boolean) {
    let content = "";
    let ai = false;
    if (withAi) {
      const r = await run(() => api.post("/v1/ai/draft", { kind, project_id: project, call_id: query.get("edital") || null, instructions: instr || null }));
      if (!r) return;
      content = r.content;
      ai = true;
    }
    const title = DRAFT_KINDS.find((k) => k[0] === kind)?.[1] || "Rascunho";
    const d = await run(() => api.post("/v1/drafts", { kind, title, content: content || " ", project_id: project || null, application_id: appId || null, ai_assisted: ai }), "Rascunho criado");
    if (d) navigate(`/rascunhos/${d.id}`);
  }
  return (
    <>
      <PageHead title="Rascunhos" sub="Propostas, planos e relatórios produzidos na plataforma, com versão, validação profissional e assinatura." />
      {me?.active_org?.kind === "osc" && (
        <Panel title="Novo rascunho">
          <div className="inline-form">
            <Field label="Documento"><Select value={kind} onChange={setKind} options={DRAFT_KINDS} /></Field>
            <Field label="Projeto"><Select value={project} onChange={setProject} placeholder="Escolha" options={(projects.data?.items || []).map((p: any) => [p.id, p.title])} /></Field>
            <Field label="Orientações para a assistência (opcional)"><Input value={instr} onChange={setInstr} placeholder="ex.: destacar parceria com a escola" /></Field>
          </div>
          <div className="stack-row">
            <Button variant="primary" busy={busy} disabled={!project} onClick={() => create(true)}>Gerar rascunho a partir do projeto</Button>
            <Button variant="ghost" busy={busy} onClick={() => create(false)}>Começar em branco</Button>
          </div>
          <p className="fineprint">A assistência usa apenas dados já cadastrados e marca com [COMPLETAR] o que falta. Ela não inventa números nem envia nada sem você.</p>
        </Panel>
      )}
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhum rascunho ainda."}>
        <table className="table">
          <thead><tr><th>Título</th><th>Versão</th><th>Situação</th><th>Atualizado</th></tr></thead>
          <tbody>{data?.items.map((d: any) => (
            <tr key={d.id}><td><Link to={`/rascunhos/${d.id}`}>{d.title}</Link>{d.ai_assisted && <span className="muted"> · com assistência</span>}</td><td>v{d.version}</td><td><Pill status={d.status} /></td><td>{date(d.updated_at)}</td></tr>
          ))}</tbody>
        </table>
      </StateView>
    </>
  );
}

export function DraftEditor({ id }: { id: string }) {
  const { me } = useSession();
  const { data: d, error, loading, reload } = useLoad<any>(`/v1/drafts/${id}`);
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [sign, setSign] = useState(false);
  const [pw, setPw] = useState("");
  const [statement, setStatement] = useState("Declaro, como representante legal, que as informações deste documento são verdadeiras.");
  const { busy, run } = useAction();
  useEffect(() => { if (d) { setText(d.content); setTitle(d.title); } }, [d]);
  const mine = d?.org_id === me?.active_org?.id;
  const locked = d && ["approved", "signed", "superseded"].includes(d.status);
  const missing = (text.match(/\[COMPLETAR[^\]]*\]/g) || []).length;
  return (
    <StateView loading={loading && !d} error={error} onRetry={reload}>
      {d && (
        <>
          <PageHead back={<Link to="/rascunhos" className="back">Rascunhos</Link>} title={d.title}
            sub={<>Versão {d.version} · <Pill status={d.status} />{d.ai_assisted && " · elaborado com assistência de IA"}</>}
            actions={mine && (
              <>
                {locked ? <Button variant="ghost" onClick={() => run(() => api.post(`/v1/drafts/${id}/new-version`), "Nova versão criada").then((r: any) => r && navigate(`/rascunhos/${r.id}`))}>Criar nova versão</Button>
                  : <Button variant="ink" busy={busy} onClick={() => run(() => api.patch(`/v1/drafts/${id}`, { title, content: text }), "Rascunho salvo").then(reload)}>Salvar</Button>}
                <Button variant="ghost" onClick={() => run(() => api.post(`/v1/drafts/${id}/export-pdf`), "PDF gerado e guardado em Documentos")}>Gerar PDF</Button>
                {["owner", "admin"].includes(me?.active_org?.role || "") && <Button variant="primary" onClick={() => setSign(true)}>Assinar como representante legal</Button>}
              </>
            )} />
          <div className="detail">
            <div className="detail-main">
              {missing > 0 && <p className="banner">Há {missing} trecho(s) marcados com [COMPLETAR]. Complete antes de enviar ou assinar.</p>}
              {mine && !locked && <Field label="Título" wide><Input value={title} onChange={setTitle} /></Field>}
              <textarea className="input editor" aria-label="Conteúdo" value={text} readOnly={!mine || !!locked} onChange={(e: any) => setText(e.target.value)} />
            </div>
            <aside className="detail-side">
              <Panel title="Validação profissional" quiet>
                {d.reviews.length === 0 ? <p className="muted">Nenhuma solicitação.</p> :
                  <ul className="rows">{d.reviews.map((r: any) => <li key={r.id}><span>{r.professional}</span><Pill status={r.status} /></li>)}</ul>}
                {mine && <Button variant="ghost" onClick={() => navigate(`/profissionais?rascunho=${id}`)}>Solicitar validação</Button>}
              </Panel>
              <Panel title="Assinaturas" quiet>
                {d.signatures.length === 0 ? <p className="muted">Ainda não assinado.</p> : (
                  <ul className="rows">{d.signatures.map((s: any, i: number) => (
                    <li key={i}><span>{s.signer} · {label(s.role === "professional" ? "Profissional" : s.role === "legal_representative" ? "Representante legal" : "Financiador")}<br />
                      <span className="muted">{date(s.signed_at)}{s.with_credential && " · com credencial"}</span></span>
                      {s.matches_current ? <Pill tone="good">Íntegra</Pill> : <Pill tone="bad">Conteúdo alterado</Pill>}</li>))}</ul>
                )}
                <p className="fineprint">Hash do texto: <code className="hash">{d.content_sha256.slice(0, 16)}…</code></p>
              </Panel>
            </aside>
          </div>
          <Modal open={sign} title="Assinar documento" onClose={() => setSign(false)} footer={
            <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/signatures", { subject_type: "draft", subject_id: id, role: "legal_representative", statement, password: pw }), "Documento assinado").then((r) => { if (r) { setSign(false); setPw(""); reload(); } })}>Assinar</Button>}>
            <p>A assinatura vincula seu nome, o hash exato desta versão, data, hora e endereço IP. Alterações posteriores exigem nova versão.</p>
            <Field label="Declaração"><TextArea rows={3} value={statement} onChange={setStatement} /></Field>
            <Field label="Confirme sua senha"><Input type="password" autoComplete="current-password" value={pw} onChange={setPw} /></Field>
            <p className="fineprint">Assinatura eletrônica avançada da plataforma. Exigências de assinatura qualificada ICP-Brasil ou gov.br dependem de integração externa.</p>
          </Modal>
        </>
      )}
    </StateView>
  );
}

export function Directory() {
  const tax = useTaxonomy();
  const { query } = useLocation();
  const [cat, setCat] = useState("");
  const [terr, setTerr] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/directory/professionals?offset=${offset}${cat ? `&category=${cat}` : ""}${terr ? `&territory=${terr}` : ""}`, [cat, terr, offset]);
  const drafts = useLoad<any>("/v1/drafts?limit=100");
  const [req, setReq] = useState<any>(null);
  const [subject, setSubject] = useState(query.get("rascunho") || "");
  const [scope, setScope] = useState("");
  const { busy, run } = useAction();
  return (
    <>
      <PageHead title="Profissionais parceiros" sub="Contadores, advogados e especialistas que validam e assinam com credencial verificada. Contratação e honorários são combinados diretamente entre as partes." />
      <div className="filters">
        <Field label="Especialidade"><Select value={cat} onChange={setCat} placeholder="Todas" options={Object.entries(tax?.professional_categories || {}) as any} /></Field>
        <Field label="Território"><Input value={terr} onChange={(v) => setTerr(v.toUpperCase())} placeholder="BR-MT" /></Field>
      </div>
      <p className="fineprint">A ordem segue credencial verificada, especialidade e território. Nenhum plano compra posição neste diretório.</p>
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhum profissional encontrado com esses filtros."}>
        <ul className="calls">
          {data?.items.map((p: any) => (
            <li key={p.org_id} className="call">
              <div className="call-main">
                <h3>{p.name}</h3>
                <p className="muted">{(p.categories || []).map((c: string) => tax?.professional_categories?.[c] || c).join(", ")} · {p.city ? `${p.city}/${p.uf}` : p.uf}{p.remote && " · atende remotamente"}</p>
                <p>{(p.services || []).join(" · ")}</p>
                <p className="call-facts">{(p.credentials || []).map((c: any) => <Pill key={c.number} status={c.status}>{c.council}/{c.uf} {c.number}</Pill>)}</p>
              </div>
              <div className="call-match"><Button variant="ink" onClick={() => setReq(p)}>Solicitar validação</Button></div>
            </li>
          ))}
        </ul>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={!!req} title={`Solicitar validação a ${req?.name || ""}`} onClose={() => setReq(null)} footer={
        <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/professional-reviews", { professional_org_id: req.org_id, subject_type: "draft", subject_id: subject, scope }), "Solicitação enviada").then((r) => r && setReq(null))}>Enviar solicitação</Button>}>
        <Field label="Documento a validar"><Select value={subject} onChange={setSubject} placeholder="Escolha um rascunho" options={(drafts.data?.items || []).map((d: any) => [d.id, `${d.title} (v${d.version})`])} /></Field>
        <Field label="O que precisa ser validado"><TextArea rows={4} value={scope} onChange={setScope} placeholder="ex.: conferir orçamento e assinar a justificativa de custos" /></Field>
      </Modal>
    </>
  );
}

export function Reviews() {
  const { data, error, loading, reload } = useLoad<any>("/v1/professional-reviews?limit=100");
  return (
    <>
      <PageHead title="Validações" sub="Solicitações recebidas e enviadas. A aprovação exige credencial verificada e vigente." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data?.items.length === 0 && "Nenhuma solicitação."}>
        <table className="table">
          <thead><tr><th>Solicitação</th><th>Solicitante</th><th>Profissional</th><th>Situação</th><th>Prazo</th></tr></thead>
          <tbody>{data?.items.map((r: any) => (
            <tr key={r.id}><td><Link to={`/revisoes/${r.id}`}>{r.scope.slice(0, 80)}</Link><br /><span className="muted">{r.direction === "incoming" ? "Recebida" : "Enviada"}</span></td>
              <td>{r.requester}</td><td>{r.professional}</td><td><Pill status={r.status} /></td><td>{date(r.due_on)}</td></tr>
          ))}</tbody>
        </table>
      </StateView>
    </>
  );
}

export function ReviewDetail({ id }: { id: string }) {
  const { me } = useSession();
  const { data: r, error, loading, reload } = useLoad<any>(`/v1/professional-reviews/${id}`);
  const creds = useLoad<any>(me?.active_org?.kind === "provider" ? "/v1/org/credentials" : null);
  const [note, setNote] = useState("");
  const [cred, setCred] = useState("");
  const [pw, setPw] = useState("");
  const [statement, setStatement] = useState("Revisei o conteúdo desta versão e valido-o no âmbito da minha atuação profissional.");
  const { busy, run } = useAction();
  const isPro = r?.professional_org_id === me?.active_org?.id;
  const respond = (status: string) => run(() => api.post(`/v1/professional-reviews/${id}/respond`, { status, note: note || null, credential_id: cred || null }), "Resposta registrada").then(reload);
  return (
    <StateView loading={loading && !r} error={error} onRetry={reload}>
      {r && (
        <>
          <PageHead back={<Link to="/revisoes" className="back">Validações</Link>} title="Validação profissional" sub={<>{r.requester} → {r.professional} · <Pill status={r.status} /></>} />
          <div className="detail">
            <div className="detail-main">
              <Panel title="Escopo"><p className="pre">{r.scope}</p>{r.response_note && <p><strong>Resposta:</strong> {r.response_note}</p>}</Panel>
              {r.subject?.content !== undefined && <Panel title={r.subject.title}><pre className="doc-view">{r.subject.content}</pre></Panel>}
            </div>
            {isPro && (
              <aside className="detail-side">
                <Panel title="Responder" quiet>
                  <Field label="Observações"><TextArea rows={3} value={note} onChange={setNote} /></Field>
                  {["accepted", "changes_requested"].includes(r.status) && (
                    <Field label="Credencial usada" hint="Somente credenciais verificadas pela administração">
                      <Select value={cred} onChange={setCred} placeholder="Escolha" options={(creds.data?.items || []).map((c: any) => [c.id, `${c.council}/${c.uf || ""} ${c.number} — ${label(c.verification_status)}`])} />
                    </Field>
                  )}
                  <div className="stack">
                    {r.status === "requested" && <><Button variant="primary" busy={busy} onClick={() => respond("accepted")}>Aceitar</Button><Button variant="ghost" onClick={() => respond("declined")}>Recusar</Button></>}
                    {["accepted", "changes_requested"].includes(r.status) && <><Button variant="primary" busy={busy} onClick={() => respond("approved")}>Aprovar</Button><Button variant="ghost" onClick={() => respond("changes_requested")}>Pedir ajustes</Button></>}
                  </div>
                </Panel>
                {r.status === "approved" && r.subject_type === "draft" && (
                  <Panel title="Assinar" quiet>
                    <Field label="Declaração"><TextArea rows={3} value={statement} onChange={setStatement} /></Field>
                    <Field label="Confirme sua senha"><Input type="password" value={pw} onChange={setPw} /></Field>
                    <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/signatures", { subject_type: "draft", subject_id: r.subject_id, role: "professional", review_id: id, statement, password: pw }), "Assinatura registrada").then(reload)}>Assinar com minha credencial</Button>
                  </Panel>
                )}
              </aside>
            )}
          </div>
        </>
      )}
    </StateView>
  );
}
