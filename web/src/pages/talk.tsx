import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { dateTime } from "../format";
import { Link } from "../router";
import { Button, Field, PageHead, Panel, Pill, Select, StateView, TextArea,
         useAction, useLoad } from "../ui/kit";

// CONVERSA COM CONTEXTO — nunca um chat solto quando a relação é profissional.
//
// O backend recusa abrir conversa profissional sem contexto (projeto, proposta, necessidade ou edital) e exige
// vínculo registrado entre as duas organizações. Esta tela mostra o contexto em cada linha, porque é isso que
// permite entender, seis meses depois, por que aquelas duas organizações estavam conversando.

export function Conversations() {
  const [status, setStatus] = useState("open");
  const { data, error, loading, reload } = useLoad<any>(`/v1/conversations?status=${status}&limit=30`, [status]);
  const unread = useLoad<any>("/v1/conversations/unread");
  return (
    <>
      <PageHead title="Conversas" sub="Toda conversa profissional nasce com um contexto."
                actions={unread.data ? <Pill tone={unread.data.unread ? "warn" : undefined}>
                  {unread.data.unread} não lido(s)</Pill> : undefined} />
      <Panel quiet>
        <Field label="Situação"><Select value={status} onChange={setStatus}
          options={[["open", "Abertas"], ["archived", "Arquivadas"], ["closed", "Encerradas"]]} /></Field>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <ul className="list">
            {data.items.map((t: any) => (
              <li key={t.id} className="list-row">
                <div className="grow">
                  <Link to={`/conversas/${t.id}`}><strong>{t.other_name}</strong></Link>
                  <p className="muted small">
                    {t.subject || "sem assunto"}
                    {t.project_title && <> · sobre {t.project_title}</>}
                    {!t.has_context && <> · <em>sem contexto registrado</em></>}
                    {t.last_message_at && <> · {dateTime(t.last_message_at)}</>}
                  </p>
                  {t.last_body && <p className="small muted">{String(t.last_body).slice(0, 120)}</p>}
                </div>
                {t.unread > 0 && <Pill tone="warn">{t.unread}</Pill>}
              </li>
            ))}
          </ul>
        )}
      </StateView>
    </>
  );
}

export function Conversation({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/conversations/${id}?limit=100`, [id]);
  const act = useAction();
  const [body, setBody] = useState("");
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (data) api.post(`/v1/conversations/${id}/read`, {}).catch(() => {});
    endRef.current?.scrollIntoView({ block: "end" });
  }, [data, id]);

  const send = async () => {
    if (!body.trim()) return;
    if (await act.run(() => api.post(`/v1/conversations/${id}/messages`, { body }), "Enviado")) {
      setBody("");
      reload();
    }
  };

  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  const c = data.conversation;
  return (
    <>
      <PageHead title={c.subject || "Conversa"} back="/conversas"
                sub={c.context_project_id ? "Conversa vinculada a um projeto" : "Conversa sem projeto vinculado"}
                actions={<Pill status={c.status}>{c.status}</Pill>} />
      {c.context_project_id && (
        <Panel quiet><Link to={`/projetos/${c.context_project_id}`}>Abrir o projeto desta conversa</Link></Panel>
      )}
      <Panel title="Recados">
        <ul className="list">
          {data.messages.map((m: any) => (
            <li key={m.id} className={`list-row ${m.mine ? "mine" : ""}`}>
              <div className="grow">
                {/* Recado de sistema é FATO (proposta enviada, documento anexado), não texto de pessoa. */}
                {m.kind === "system"
                  ? <p className="muted small"><em>{m.body}</em></p>
                  : <>
                      <p>{m.body}</p>
                      <p className="muted small">
                        {m.mine ? "você" : m.sender_name || "a outra parte"} · {dateTime(m.created_at)}
                        {m.ref_type && <> · referência: {m.ref_type}</>}
                      </p>
                    </>}
                {!!m.documents?.length && (
                  <ul className="small">
                    {m.documents.map((d: any) => <li key={d.id}>{d.title} ({d.doc_type})</li>)}
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ul>
        <div ref={endRef} />
        <Field label="Escrever" wide><TextArea value={body} onChange={setBody} rows={3} /></Field>
        <Button variant="ink" busy={act.busy} disabled={!body.trim()} onClick={send}>Enviar</Button>
      </Panel>
    </>
  );
}

// ============================================================================ notificações da rede
export function NetworkEvents() {
  const { data, error, loading, reload } = useLoad<any>("/v1/network/events?limit=50");
  return (
    <>
      <PageHead title="Atividade da rede" sub="Os fatos registrados pela plataforma, na ordem em que aconteceram." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <p className="muted small">{data.items.length} fato(s). O número de pessoas avisadas aparece em cada linha —
              zero é resposta legítima quando quem agiu era a única pessoa envolvida.</p>
            <ul className="list">
              {data.items.map((e: any) => (
                <li key={e.id} className="list-row">
                  <div className="grow">
                    <strong>{e.label}</strong>
                    <p className="muted small">
                      {e.actor_name || "plataforma"}
                      {e.subject_type && <> · {e.subject_type}</>}
                      {" · "}{dateTime(e.at)}
                    </p>
                  </div>
                  <Pill>{e.notified} avisada(s)</Pill>
                </li>
              ))}
            </ul>
          </>
        )}
      </StateView>
    </>
  );
}

export function ProjectTeam({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/team`, [id]);
  return (
    <>
      <PageHead title="Equipe do projeto" back={`/projetos/${id}`}
                sub="Quem está nesta lista é avisado em cada mudança de etapa e cada documento juntado." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <ul className="list">
              {data.items.map((p: any) => (
                <li key={p.user_id + p.org_id} className="list-row">
                  <span className="grow">{p.name} <span className="muted small">· {p.org_name}</span></span>
                  <Pill>{RELATION_LABEL[p.relation] || p.relation}</Pill>
                </li>
              ))}
            </ul>
            <p className="muted small">{data.note}</p>
          </>
        )}
      </StateView>
    </>
  );
}
const RELATION_LABEL: Record<string, string> = { owner: "organização executora", participant: "organização participante",
  funder: "quem apoia" };
