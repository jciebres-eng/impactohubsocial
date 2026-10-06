import { useState } from "react";
import { api } from "../api";
import { date, dateTime, money } from "../format";
import { Link, navigate } from "../router";
import { Button, Field, Input, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// Telas FUNCIONAIS da rede: relações, propostas, conversas com contexto, marketplace, perfil público e relatório de
// impacto. Nenhuma regra de visibilidade mora aqui — a RLS e o campo `visibility` decidem no banco, e estas telas
// apenas mostram o que a API devolve. O visual vem depois, com a designer.

// ============================================================================ relações
const REL_STATUS_LABEL: Record<string, string> = { pending: "aguardando aceite", active: "ativa", paused: "pausada",
  ended: "encerrada", declined: "recusada", revoked: "revogada" };
const VIS_LABEL: Record<string, string> = { private: "só você", participants: "as partes", organization: "sua organização",
  network: "quem tem conta", public: "qualquer pessoa" };

export function Relationships() {
  const [dir, setDir] = useState("all");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const qs = `direction=${dir}${status ? `&status=${status}` : ""}&limit=20&offset=${offset}`;
  const { data, error, loading, reload } = useLoad<any>(`/v1/network/relationships?${qs}`, [dir, status, offset]);
  const kinds = useLoad<any>("/v1/network/relationship-kinds");
  const act = useAction();
  const [note, setNote] = useState<Record<string, string>>({});

  const move = async (id: string, to: string) => {
    const reason = note[id];
    const closing = ["ended", "declined", "revoked"].includes(to);
    if (closing && (!reason || reason.trim().length < 3)) {
      alert("Informe o motivo do encerramento (mínimo 3 caracteres).");
      return;
    }
    if (await act.run(() => api.post(`/v1/network/relationships/${id}/transition`, { to, reason }), "Relação atualizada")) reload();
  };

  return (
    <>
      <PageHead title="Relações" sub="Com quem a sua organização está ligada, por quê, e quem pode ver isso."
                actions={<Link to="/rede/grafo">Ver vizinhança</Link>} />
      <Panel quiet>
        <div className="row gap wrap">
          <Field label="Direção"><Select value={dir} onChange={(v) => { setDir(v); setOffset(0); }}
            options={[["all", "Todas"], ["out", "Criadas por nós"], ["in", "Recebidas"]]} /></Field>
          <Field label="Situação"><Select value={status} onChange={(v) => { setStatus(v); setOffset(0); }}
            placeholder="Qualquer" options={Object.entries(REL_STATUS_LABEL)} /></Field>
        </div>
        <p className="muted small">{kinds.data?.note}</p>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <ul className="list">
              {data.items.map((r: any) => (
                <li key={r.id} className="list-row">
                  <div className="grow">
                    <strong>{r.label}</strong>
                    <p className="muted small">
                      {r.direction === "out" ? "para " : "de "}
                      {r.target_org_name || r.target_project_title || r.target_user_name
                        || r.source_org_name || r.source_user_name || "—"}
                      {r.role && <> · papel {r.role}</>}
                      {" · visível para "}{VIS_LABEL[r.visibility] || r.visibility}
                      {r.mirrored_from && <> · espelho de {r.mirrored_from}</>}
                      {" · "}{date(r.created_at)}
                    </p>
                    {r.note && <p className="small">{r.note}</p>}
                    {r.ended_reason && <p className="small muted">Encerrada: {r.ended_reason}</p>}
                  </div>
                  <div className="col gap">
                    <Pill status={r.status}>{REL_STATUS_LABEL[r.status]}</Pill>
                    {!r.mirrored_from && r.status !== "ended" && (
                      <div className="col gap">
                        {r.status === "pending" && r.direction === "in" && (
                          <div className="row gap">
                            <Button variant="ink" busy={act.busy} onClick={() => move(r.id, "active")}>Aceitar</Button>
                            <Button variant="ghost" onClick={() => move(r.id, "declined")}>Recusar</Button>
                          </div>
                        )}
                        {r.status === "active" && (
                          <div className="row gap">
                            <Button variant="ghost" onClick={() => move(r.id, "paused")}>Pausar</Button>
                            <Button variant="ghost" onClick={() => move(r.id, "ended")}>Encerrar</Button>
                          </div>
                        )}
                        {(r.status === "pending" || r.status === "active") && (
                          <Input value={note[r.id] || ""} placeholder="motivo (exigido ao encerrar)"
                                 onChange={(v) => setNote({ ...note, [r.id]: v })} />
                        )}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <Pager data={data} offset={offset} setOffset={setOffset} />
          </>
        )}
      </StateView>
    </>
  );
}

export function NetworkGraph() {
  const [depth, setDepth] = useState(1);
  const { data, error, loading, reload } = useLoad<any>(`/v1/network/graph?depth=${depth}&limit=100`, [depth]);
  return (
    <>
      <PageHead title="Vizinhança na rede" sub="Organizações a um ou dois passos, por relações não privadas." />
      <Panel quiet>
        <Field label="Distância"><Select value={String(depth)} onChange={(v) => setDepth(Number(v))}
          options={[["1", "Um passo"], ["2", "Até dois passos"]]} /></Field>
        {data && <p className="muted small">{data.note}</p>}
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.nodes.length}>
        {data && (
          <Panel title={`${data.count} organização(ões)`}>
            <ul className="list">
              {data.nodes.map((o: any) => (
                <li key={o.org_id} className="list-row">
                  <span className="grow"><Link to={`/instituicoes/${o.org_id}`}>{o.name}</Link>
                    <span className="muted small"> · {o.org_kind}{o.uf && ` · ${o.uf}`}</span></span>
                  <Pill>{o.hop === 1 ? "um passo" : "dois passos"}</Pill>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </StateView>
    </>
  );
}

// ============================================================================ propostas
export function Proposals() {
  const [box, setBox] = useState("received");
  const [status, setStatus] = useState("open");
  const [offset, setOffset] = useState(0);
  const qs = `box=${box}${status ? `&status=${status}` : ""}&limit=20&offset=${offset}`;
  const { data, error, loading, reload } = useLoad<any>(`/v1/proposals?${qs}`, [box, status, offset]);
  const counts = useLoad<any>("/v1/proposals/counts");
  return (
    <>
      <PageHead title="Propostas" sub="Proposta não é contrato, não é compromisso financeiro e não é pagamento."
                actions={<Button variant="ink" onClick={() => navigate("/propostas/nova")}>Nova proposta</Button>} />
      {counts.data && (
        <Panel quiet>
          <p>
            <strong>{counts.data.awaiting_me}</strong> espera(m) por você ·
            {" "}<strong>{counts.data.needs_my_revision}</strong> para revisar ·
            {" "}<strong>{counts.data.awaiting_other}</strong> aguardando a outra parte ·
            {" "}<strong>{counts.data.accepted}</strong> aceita(s) ·
            {" "}<strong>{counts.data.drafts}</strong> rascunho(s)
          </p>
        </Panel>
      )}
      <Panel quiet>
        <div className="row gap wrap">
          <Field label="Caixa"><Select value={box} onChange={(v) => { setBox(v); setOffset(0); }}
            options={[["received", "Recebidas"], ["sent", "Enviadas"], ["all", "Todas"]]} /></Field>
          <Field label="Situação"><Select value={status} onChange={(v) => { setStatus(v); setOffset(0); }}
            placeholder="Qualquer" options={[["open", "Em aberto"], ["draft", "Rascunho"], ["accepted", "Aceita"],
              ["declined", "Recusada"], ["expired", "Expirada"], ["withdrawn", "Retirada"]]} /></Field>
        </div>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <ul className="list">
              {data.items.map((p: any) => (
                <li key={p.id} className="list-row">
                  <div className="grow">
                    <Link to={`/propostas/${p.id}`}><strong>{p.title}</strong></Link>
                    <p className="muted small">
                      {p.label} · {p.side === "receiver" ? `de ${p.sender_name}` : `para ${p.receiver_name}`}
                      {p.amount_cents != null && <> · {money(p.amount_cents, p.currency)} (proposto)</>}
                      {p.project_title && <> · {p.project_title}</>}
                      {p.version > 1 && <> · versão {p.version}</>}
                    </p>
                  </div>
                  <div className="row gap">
                    {p.awaiting_me && <Pill tone="warn">espera por você</Pill>}
                    <Pill status={p.status}>{p.status_label}</Pill>
                  </div>
                </li>
              ))}
            </ul>
            <Pager data={data} offset={offset} setOffset={setOffset} />
          </>
        )}
      </StateView>
    </>
  );
}

export function ProposalDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/proposals/${id}`, [id]);
  const act = useAction();
  const [note, setNote] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const move = async (to: string, requiresNote: boolean) => {
    if (requiresNote && note.trim().length < 3) { setOpen(to); return; }
    if (await act.run(() => api.post(`/v1/proposals/${id}/transition`, { to, note: note || undefined }),
                      "Proposta atualizada")) { setNote(""); setOpen(null); reload(); }
  };

  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  const p = data;
  return (
    <>
      <PageHead title={p.title} sub={`${p.label} · ${p.side === "receiver" ? `de ${p.sender_name}` : `para ${p.receiver_name}`}`}
                back="/propostas" actions={<Pill status={p.status}>{p.status_label}</Pill>} />
      <Panel title="O que está sendo proposto">
        <p>{p.purpose}</p>
        {p.terms && <><h3>Condições</h3><p>{p.terms}</p></>}
        <ul className="small">
          {p.amount_cents != null && <li>Valor proposto: <strong>{money(p.amount_cents, p.currency)}</strong></li>}
          {p.support_mode && <li>Modalidade: {p.support_mode}</li>}
          {p.compensation && <li>Remuneração: {p.compensation}</li>}
          {p.project_title && <li>Projeto: <Link to={`/projetos/${p.project_id}`}>{p.project_title}</Link></li>}
          <li>Versão {p.version}</li>
          {p.expires_at && <li>Prazo: {date(p.expires_at)}</li>}
        </ul>
        {/* Este aviso vem do backend e é parte do contrato da API: a tela não pode esquecê-lo. */}
        <p className="muted small">{p.financial_notice}</p>
      </Panel>

      {!!p.actions?.length && (
        <Panel title="O que você pode fazer agora">
          <div className="row gap wrap">
            {p.actions.map((a: any) => (
              <Button key={a.to_status} variant={a.to_status === "accepted" ? "ink" : "ghost"} busy={act.busy}
                      onClick={() => move(a.to_status, a.requires_note)}>
                {ACTION_LABEL[a.to_status] || a.to_status}{a.requires_note ? " (com justificativa)" : ""}
              </Button>
            ))}
          </div>
          {p.status === "changes_requested" && p.side === "sender" && (
            <p className="muted small">Ao reenviar, a proposta ganha uma nova versão; a anterior fica no histórico.</p>
          )}
        </Panel>
      )}

      <Panel title="Documentos anexados">
        {p.attachments?.length
          ? <ul className="list">{p.attachments.map((a: any) => (
              <li key={a.document_id} className="list-row">
                <span className="grow">{a.title} <span className="muted small">({a.doc_type})</span></span>
                <span className="muted small">{date(a.added_at)}</span>
              </li>))}</ul>
          : <p className="muted">Nenhum documento anexado.</p>}
        <AttachDocument proposalId={id} onDone={reload} />
      </Panel>

      <Panel title="Histórico">
        <ul className="list">
          {p.events.map((e: any, i: number) => (
            <li key={i} className="list-row">
              <span className="grow">
                {e.from_status ? `${e.from_status} → ${e.to_status}` : e.to_status}
                {e.actor_name && <span className="muted small"> · {e.actor_name}</span>}
                {e.note && <div className="small">{e.note}</div>}
              </span>
              <span className="muted small">{dateTime(e.at)}</span>
            </li>
          ))}
        </ul>
      </Panel>

      <Modal open={!!open} title="Justificativa" onClose={() => setOpen(null)}
             footer={<Button variant="ink" busy={act.busy} onClick={() => open && move(open, false)}>Confirmar</Button>}>
        <Field label="O que precisa ser dito" hint="Mínimo 3 caracteres. A outra parte vê este texto.">
          <TextArea value={note} onChange={setNote} rows={4} />
        </Field>
      </Modal>
    </>
  );
}
const ACTION_LABEL: Record<string, string> = {
  sent: "Enviar", viewed: "Marcar como vista", in_review: "Pôr em análise", accepted: "Aceitar",
  declined: "Recusar", changes_requested: "Pedir ajuste", withdrawn: "Retirar", cancelled: "Cancelar",
};

function AttachDocument({ proposalId, onDone }: { proposalId: string; onDone: () => void }) {
  const docs = useLoad<any>("/v1/documents?limit=50");
  const act = useAction();
  const [doc, setDoc] = useState("");
  return (
    <div className="row gap">
      <Field label="Anexar documento do cofre">
        <Select value={doc} onChange={setDoc} placeholder="Escolha um documento"
                options={(docs.data?.items || []).map((d: any) => [d.id, `${d.title} (${d.doc_type})`])} />
      </Field>
      <Button variant="ghost" busy={act.busy} disabled={!doc}
              onClick={async () => {
                if (await act.run(() => api.post(`/v1/proposals/${proposalId}/attachments`, { document_id: doc }),
                                  "Documento anexado e equipe avisada")) { setDoc(""); onDone(); }
              }}>Anexar</Button>
    </div>
  );
}

export function NewProposal() {
  const f = useForm({ kind: "investment", receiver_org_id: "", title: "", purpose: "", terms: "",
                      amount: "", support_mode: "", project_id: "", need_id: "", call_id: "", solution_id: "" });
  const act = useAction();
  const graph = useLoad<any>("/v1/proposals/graph");
  const feed = useLoad<any>("/v1/marketplace/feed?limit=50");
  const send = async () => {
    const body: any = {
      kind: f.v.kind, receiver_org_id: f.v.receiver_org_id, title: f.v.title, purpose: f.v.purpose,
      terms: f.v.terms || undefined, support_mode: f.v.support_mode || undefined,
      amount_cents: f.v.amount ? Math.round(Number(f.v.amount.replace(",", ".")) * 100) : undefined,
    };
    for (const k of ["project_id", "need_id", "call_id", "solution_id"] as const) if ((f.v as any)[k]) body[k] = (f.v as any)[k];
    const r = await act.run(() => api.post("/v1/proposals", body), "Proposta criada em rascunho");
    if (r) navigate(`/propostas/${(r as any).id}`);
  };
  return (
    <>
      <PageHead title="Nova proposta" back="/propostas"
                sub="A proposta exige contexto: projeto, necessidade, edital ou solução. Proposta sem contexto é mensagem fria." />
      <Panel>
        <Field label="Tipo" wide>
          <Select value={f.v.kind} onChange={f.set("kind")}
                  options={(graph.data?.kinds || []).map((k: any) => [k.kind, k.label])} />
        </Field>
        <Field label="Organização destinatária" hint="Escolha a partir de um anúncio publicado no marketplace" wide>
          <Select value={f.v.receiver_org_id} onChange={(v) => {
            f.set("receiver_org_id")(v);
            const item = (feed.data?.items || []).find((i: any) => i.org_id === v);
            if (item?.project_id) f.set("project_id")(item.project_id);
          }} placeholder="Escolha"
            options={Array.from(new Map((feed.data?.items || [])
              .map((i: any) => [i.org_id, `${i.org_name} — ${i.headline}`])).entries()) as [string, string][]} />
        </Field>
        <Field label="Título" wide><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Para quê" hint="Mínimo 10 caracteres" wide>
          <TextArea value={f.v.purpose} onChange={f.set("purpose")} rows={4} /></Field>
        <Field label="Condições (opcional)" wide><TextArea value={f.v.terms} onChange={f.set("terms")} rows={3} /></Field>
        <div className="row gap wrap">
          <Field label="Valor proposto" hint="Opcional. Valor PROPOSTO — não é compromisso.">
            <Input value={f.v.amount} onChange={f.set("amount")} placeholder="0,00" /></Field>
          <Field label="Modalidade">
            <Select value={f.v.support_mode} onChange={f.set("support_mode")} placeholder="Não declarar"
              options={[["financial", "Financeira"], ["service", "Serviço"], ["equipment", "Equipamento"],
                        ["knowledge", "Conhecimento"], ["volunteer", "Voluntariado"], ["sponsorship", "Patrocínio"],
                        ["mentorship", "Mentoria"], ["other", "Outra"]]} /></Field>
        </div>
        <Button variant="ink" busy={act.busy} disabled={!f.v.receiver_org_id || !f.v.title || f.v.purpose.length < 10}
                onClick={send}>Criar rascunho</Button>
        <p className="muted small">{graph.data?.note}</p>
      </Panel>
    </>
  );
}
