import { useState } from "react";
import { api } from "../api";
import { date, money } from "../format";
import { Link, navigate } from "../router";
import { Button, Field, Input, PageHead, Pager, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// MARKETPLACE — a publicação é ESTADO da entidade, não condição de consulta.
//
// O feed público lê `marketplace_listings WHERE publication_state = 'published'`, e esse filtro está escrito UMA vez,
// no backend (marketplace.public_feed). Esta tela não consulta projeto: se consultasse, voltaria a existir a chance
// de um WHERE esquecido expor rascunho. Era o achado E6 da auditoria.

const STATE_LABEL: Record<string, string> = { draft: "rascunho", review: "em conferência", approved: "aprovado internamente",
  published: "publicado", paused: "pausado", expired: "expirado", archived: "arquivado", suspended: "suspenso pela administração" };
const SEEKING: [string, string][] = [["investment", "Investimento"], ["sponsorship", "Patrocínio"], ["partner", "Organização parceira"],
  ["professional", "Profissional"], ["volunteer", "Voluntariado"], ["mentorship", "Mentoria"], ["equipment", "Equipamento"],
  ["knowledge", "Conhecimento"], ["quota", "Cotas"]];
const SUBJECT: [string, string][] = [["project", "Projeto"], ["opportunity", "Edital"], ["need", "Necessidade"],
  ["service", "Serviço"], ["solution", "Solução"], ["partnership", "Parceria"], ["sponsorship", "Patrocínio"]];

export function Marketplace() {
  const f = useForm({ subject_type: "", seeking: "", territory: "", cause: "", q: "" });
  const [offset, setOffset] = useState(0);
  const qs = new URLSearchParams(
    Object.entries({ ...f.v, limit: "20", offset: String(offset) }).filter(([, v]) => v) as [string, string][]);
  const { data, error, loading, reload } = useLoad<any>(`/v1/marketplace/feed?${qs}`, [qs.toString()]);
  return (
    <>
      <PageHead title="Marketplace de impacto"
                sub="Projetos, necessidades, serviços e soluções publicados por quem está na rede." />
      <Panel quiet>
        <div className="row gap wrap">
          <Field label="O que"><Select value={f.v.subject_type} onChange={(v) => { f.set("subject_type")(v); setOffset(0); }}
            placeholder="Tudo" options={SUBJECT} /></Field>
          <Field label="Busca por"><Select value={f.v.seeking} onChange={(v) => { f.set("seeking")(v); setOffset(0); }}
            placeholder="Qualquer" options={SEEKING} /></Field>
          <Field label="Território" hint="UF ou BR-UF"><Input value={f.v.territory}
            onChange={(v) => { f.set("territory")(v.toUpperCase()); setOffset(0); }} placeholder="BR-MT" /></Field>
          <Field label="Texto"><Input value={f.v.q} onChange={(v) => { f.set("q")(v); setOffset(0); }} /></Field>
        </div>
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <p className="muted small">{data.total} anúncio(s) publicado(s)</p>
            <ul className="list">
              {data.items.map((l: any) => (
                <li key={l.id} className="list-row">
                  <div className="grow">
                    <Link to={`/marketplace/${l.id}`}><strong>{l.headline}</strong></Link>
                    <p className="muted small">
                      {l.org_name} · {l.org_kind}
                      {l.territory && <> · {l.territory}</>}
                      {!!l.seeking?.length && <> · busca {l.seeking.join(", ")}</>}
                      {l.amount_target_cents ? <> · {money(l.amount_target_cents, l.currency)}</> : null}
                      {l.published_at && <> · publicado {date(l.published_at)}</>}
                    </p>
                    {l.summary && <p className="small">{l.summary}</p>}
                  </div>
                </li>
              ))}
            </ul>
            <Pager data={{ items: data.items, has_more: data.offset + data.limit < data.total,
                           next_offset: data.offset + data.limit }} offset={offset} setOffset={setOffset} />
          </>
        )}
      </StateView>
    </>
  );
}

export function ListingDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/marketplace/listings/${id}`, [id]);
  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  const l = data;
  return (
    <>
      <PageHead title={l.headline} sub={`${l.org_name} · ${l.subject_type}`} back="/marketplace"
                actions={<Button variant="ink" onClick={() => navigate("/propostas/nova")}>Propor</Button>} />
      <Panel>
        {l.summary && <p>{l.summary}</p>}
        <ul className="small">
          {!!l.seeking?.length && <li>Busca: {l.seeking.join(", ")}</li>}
          {l.amount_target_cents ? <li>Valor pretendido: {money(l.amount_target_cents, l.currency)}</li> : null}
          {l.territory && <li>Território: {l.territory}</li>}
          {!!l.causes?.length && <li>Causas: {l.causes.join(", ")}</li>}
          {!!l.ods?.length && <li>ODS: {l.ods.join(", ")}</li>}
          {l.stage && <li>Estágio: {l.stage}</li>}
          {l.project_id && <li><Link to={`/projetos/${l.project_id}`}>Ver o projeto</Link></li>}
        </ul>
      </Panel>
      <Panel title="Como começar" quiet>
        <p className="muted small">
          A conversa com contexto e a proposta são os dois caminhos. Registrar um contato é o que abre a conversa —
          a plataforma exige vínculo registrado para evitar abordagem fria.
        </p>
        <div className="row gap">
          <Button variant="ghost" onClick={() => navigate("/rede/relacoes")}>Registrar contato</Button>
          <Button variant="ink" onClick={() => navigate("/propostas/nova")}>Enviar proposta</Button>
        </div>
      </Panel>
    </>
  );
}

export function MyListings() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/marketplace/listings?limit=20&offset=${offset}`, [offset]);
  const act = useAction();
  const move = async (lid: string, to: string) => {
    // As transições que a organização faz não exigem motivo. Suspender exige — e suspender é da administração,
    // então esta tela não a oferece.
    if (await act.run(() => api.post(`/v1/marketplace/listings/${lid}/transition`, { to }), "Anúncio atualizado")) reload();
  };
  return (
    <>
      <PageHead title="Meus anúncios" sub="Nenhum anúncio nasce no ar: publicar é uma decisão registrada."
                actions={<Button variant="ink" onClick={() => navigate("/marketplace/novo")}>Novo anúncio</Button>} />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <ul className="list">
              {data.items.map((l: any) => (
                <li key={l.id} className="list-row">
                  <div className="grow">
                    <strong>{l.headline}</strong>
                    <p className="muted small">
                      {l.subject_type}
                      {!!l.seeking?.length && <> · busca {l.seeking.join(", ")}</>}
                      {l.views ? <> · {l.views} visualização(ões)</> : null}
                      {l.expires_at && <> · prazo {date(l.expires_at)}</>}
                    </p>
                    {l.publication_state === "suspended" && l.suspended_reason && (
                      <p className="small">Motivo da suspensão: {l.suspended_reason}</p>
                    )}
                  </div>
                  <div className="col gap">
                    <Pill status={l.publication_state}>{l.state_label || STATE_LABEL[l.publication_state]}</Pill>
                    <div className="row gap wrap">
                      {(l.actions || []).map((to: string) => (
                        <Button key={to} variant={to === "published" ? "ink" : "ghost"} busy={act.busy}
                                onClick={() => move(l.id, to)}>{STATE_ACTION[to] || to}</Button>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            <Pager data={data} offset={offset} setOffset={setOffset} />
          </>
        )}
      </StateView>
      <Panel quiet>
        <p className="muted small">
          Publicar exige que o item também esteja publicado: anúncio de projeto em rascunho é recusado pelo banco,
          não por uma checagem desta tela.
        </p>
      </Panel>
    </>
  );
}
const STATE_ACTION: Record<string, string> = { review: "Enviar para conferência", approved: "Aprovar internamente",
  published: "Publicar", paused: "Pausar", archived: "Arquivar", draft: "Voltar ao rascunho" };

export function NewListing() {
  const f = useForm({ subject_type: "project", subject_id: "", headline: "", summary: "", seeking: [] as string[],
                      amount: "", territory: "", stage: "" });
  const act = useAction();
  const projects = useLoad<any>("/v1/projects?limit=50");
  const create = async () => {
    const r = await act.run(() => api.post("/v1/marketplace/listings", {
      subject_type: f.v.subject_type, subject_id: f.v.subject_id, headline: f.v.headline,
      summary: f.v.summary || undefined, seeking: f.v.seeking,
      amount_target_cents: f.v.amount ? Math.round(Number(f.v.amount.replace(",", ".")) * 100) : undefined,
      territory: f.v.territory || undefined, stage: f.v.stage || undefined,
    }), "Anúncio criado em rascunho");
    if (r) navigate("/marketplace/meus");
  };
  return (
    <>
      <PageHead title="Novo anúncio" back="/marketplace/meus" />
      <Panel>
        <Field label="O que está anunciando" wide>
          <Select value={f.v.subject_type} onChange={f.set("subject_type")} options={SUBJECT} /></Field>
        <Field label="Projeto" hint="O item anunciado precisa ser da sua organização" wide>
          <Select value={f.v.subject_id} onChange={f.set("subject_id")} placeholder="Escolha"
                  options={(projects.data?.items || []).map((p: any) => [p.id, `${p.title} (${p.status})`])} /></Field>
        <Field label="Chamada" hint="10 a 200 caracteres: é o que aparece no feed" wide>
          <Input value={f.v.headline} onChange={f.set("headline")} /></Field>
        <Field label="Resumo (opcional)" wide><TextArea value={f.v.summary} onChange={f.set("summary")} rows={3} /></Field>
        <Field label="O que você busca" wide>
          <div className="row gap wrap">
            {SEEKING.map(([k, lbl]) => (
              <Button key={k} variant={f.v.seeking.includes(k) ? "ink" : "ghost"}
                      onClick={() => f.set("seeking")(f.v.seeking.includes(k)
                        ? f.v.seeking.filter((x) => x !== k) : [...f.v.seeking, k])}>{lbl}</Button>
            ))}
          </div>
        </Field>
        <div className="row gap wrap">
          <Field label="Valor pretendido (opcional)"><Input value={f.v.amount} onChange={f.set("amount")} placeholder="0,00" /></Field>
          <Field label="Território"><Input value={f.v.territory} onChange={(v) => f.set("territory")(v.toUpperCase())} placeholder="BR-MT" /></Field>
          <Field label="Estágio"><Select value={f.v.stage} onChange={f.set("stage")} placeholder="Não declarar"
            options={[["idea", "Ideia"], ["building", "Em construção"], ["ready", "Pronto"], ["seeking", "Captando"],
                      ["executing", "Em execução"], ["completed", "Concluído"]]} /></Field>
        </div>
        <Button variant="ink" busy={act.busy} disabled={!f.v.subject_id || f.v.headline.length < 10} onClick={create}>
          Criar rascunho
        </Button>
      </Panel>
    </>
  );
}
