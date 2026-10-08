import { useState } from "react";
import { api } from "../api";
import { date } from "../format";
import { TrajectoryCard } from "./participations";
import { Link, navigate, useLocation } from "../router";
import { Button, Field, Input, PageHead, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// PERFIL PÚBLICO em /@identificador.
//
// A página pública lê SÓ a projeção curada que o servidor monta (`public_fields`), nunca tabela privada. Isso não é
// disciplina desta tela: a API de perfil público devolve apenas essa projeção, e nada mais existe para mostrar.
// Se amanhã uma coluna sensível for acrescentada a `organizations`, ela não aparece aqui por descuido.

export function PublicProfilePage({ handle: fromRoute }: { handle?: string } = {}) {
  const { path } = useLocation();
  // O roteador já entrega o identificador como parâmetro de `/@:handle`; a leitura do caminho é o reserva para
  // quando a página é montada fora da rota (por exemplo, numa pré-visualização).
  const handle = fromRoute || decodeURIComponent(path.replace(/^\/@/, ""));
  const { data, error, loading, reload } = useLoad<any>(`/v1/public/profiles/${encodeURIComponent(handle)}`, [handle]);
  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  const p = data.profile || {};
  return (
    <>
      <PageHead title={p.display_name || `@${data.handle}`} sub={p.headline}
                actions={data.verified_badge ? <Pill tone="good">verificado: {data.verified_badge}</Pill> : undefined} />
      <Panel quiet>
        <p className="muted small">
          @{data.handle} · {p.kind === "organization" ? "organização" : "pessoa"}
          {p.member_since && <> · na rede desde {p.member_since}</>}
          {p.territory?.uf && <> · {p.territory.city ? `${p.territory.city}/` : ""}{p.territory.uf}</>}
        </p>
      </Panel>
      {p.bio && <Panel title="Sobre"><p>{p.bio}</p></Panel>}
      {p.mission && <Panel title="Missão"><p>{p.mission}</p></Panel>}
      {/* v0.27.0 — trajetória cumulativa (contagens e datas; nunca valores): nasce de conclusão e quitação */}
      {p.trajectory && <TrajectoryCard trajectory={p.trajectory} />}

      {!!p.projects?.length && (
        <Panel title={`Projetos publicados (${p.projects_count ?? p.projects.length})`}>
          <ul className="list">
            {p.projects.map((pr: any, i: number) => (
              <li key={i} className="list-row">
                <div className="grow"><strong>{pr.title}</strong>
                  <p className="muted small">{pr.territory}
                    {!!pr.causes?.length && <> · {pr.causes.join(", ")}</>}
                    {pr.published_at && <> · {date(pr.published_at)}</>}</p>
                  {pr.summary && <p className="small">{pr.summary}</p>}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {!!p.impact?.length && (
        <Panel title="Resultados relatados e aceitos">
          {/* Só relatório PUBLICADO entra aqui, e publicar só acontece depois de alguém de fora aceitar. */}
          <ul className="list">
            {p.impact.map((u: any, i: number) => (
              <li key={i} className="list-row">
                <div className="grow"><strong>{u.project_title}</strong>
                  <p className="muted small">{u.period_start} a {u.period_end}</p>
                  <p className="small">{u.summary}</p>
                  {u.outcomes && <p className="small">{u.outcomes}</p>}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {!!p.credentials?.length && (
        <Panel title="Registros profissionais verificados">
          <p className="muted small">A plataforma confirma a existência do registro; o número não é publicado.</p>
          <ul className="list">
            {p.credentials.map((c: any, i: number) => (
              <li key={i} className="list-row">
                <span className="grow">{c.council}{c.uf && `/${c.uf}`}</span>
                {c.valid_until && <span className="muted small">válido até {date(c.valid_until)}</span>}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {!!p.experiences?.length && (
        <Panel title="Experiência confirmada">
          <p className="muted small">Cada item foi confirmado por quem administra a organização citada.</p>
          <ul className="list">
            {p.experiences.map((e: any, i: number) => (
              <li key={i} className="list-row">
                <span className="grow">{e.role} — {e.org_name}</span>
                <span className="muted small">{e.started_on} {e.ended_on ? `a ${e.ended_on}` : "— atual"}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {!!p.organizations?.length && (
        <Panel title="Organizações">
          <ul className="list">{p.organizations.map((o: any, i: number) => (
            <li key={i} className="list-row"><span className="grow">{o.name}</span><Pill>{o.role}</Pill></li>))}</ul>
        </Panel>
      )}

      {!!p.public_relationships?.length && (
        <Panel title="Relações públicas">
          <p className="muted small">Somente relações que esta organização marcou como públicas.</p>
          <ul className="list">{p.public_relationships.map((r: any, i: number) => (
            <li key={i} className="list-row"><span className="grow">{r.with_name}</span><Pill>{r.kind}</Pill></li>))}</ul>
        </Panel>
      )}

      {!!p.links?.length && (
        <Panel title="Links">
          <ul className="list">{p.links.map((l: any, i: number) => (
            <li key={i}><a href={l.url} rel="noopener noreferrer nofollow" target="_blank">{l.label}</a></li>))}</ul>
        </Panel>
      )}

      {p.contact && Object.keys(p.contact).length > 0 && (
        <Panel title="Contato">
          <ul className="list">{Object.entries(p.contact).map(([k, v]: any) => (
            <li key={k} className="list-row"><span className="grow">{k}</span><span>{String(v)}</span></li>))}</ul>
        </Panel>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------- gestão do próprio perfil
export function MyPublicProfile() {
  const { data, error, loading, reload } = useLoad<any>("/v1/profiles/mine");
  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  return (
    <>
      <PageHead title="Perfil público" sub="O endereço que você compartilha, e o que ele mostra." />
      <ProfileEditor label="Perfil da organização" owner="org" profile={data.org} onDone={reload} meta={data} />
      <ProfileEditor label="Seu perfil pessoal" owner="user" profile={data.person} onDone={reload} meta={data} />
      <Panel title="O que NUNCA entra na página pública" quiet>
        <p className="muted small">
          Estes campos são recusados pelo servidor ao montar a projeção, mesmo que alguém os acrescente por engano:
          {" "}{(data.never_public || []).join(", ")}.
        </p>
      </Panel>
    </>
  );
}

function ProfileEditor({ label, owner, profile, onDone, meta }: any) {
  const act = useAction();
  const f = useForm({
    handle: profile?.handle || "", display_name: profile?.display_name || "", headline: profile?.headline || "",
    bio: profile?.bio || "", visibility: profile?.visibility || "public",
    show_territory: profile?.show_territory ?? true, show_projects: profile?.show_projects ?? true,
    show_credentials: profile?.show_credentials ?? true, show_organizations: profile?.show_organizations ?? true,
    show_impact_history: profile?.show_impact_history ?? true, show_contact: profile?.show_contact ?? false,
  });
  const [check, setCheck] = useState<any>(null);
  const verify = async () => {
    const r = await api.get(`/v1/profiles/handle-available?handle=${encodeURIComponent(f.v.handle)}`);
    setCheck(r);
  };
  const create = async () => {
    const r = await act.run(() => api.post("/v1/profiles", {
      handle: f.v.handle, display_name: f.v.display_name, headline: f.v.headline || undefined,
      bio: f.v.bio || undefined, owner }), "Perfil criado");
    if (r) onDone();
  };
  const save = async () => {
    const r = await act.run(() => api.patch(`/v1/profiles/${profile.id}`, {
      handle: f.v.handle !== profile.handle ? f.v.handle : undefined,
      display_name: f.v.display_name, headline: f.v.headline || undefined, bio: f.v.bio || undefined,
      visibility: f.v.visibility, show_territory: f.v.show_territory, show_projects: f.v.show_projects,
      show_credentials: f.v.show_credentials, show_organizations: f.v.show_organizations,
      show_impact_history: f.v.show_impact_history, show_contact: f.v.show_contact,
    }), "Perfil atualizado");
    if (r) onDone();
  };
  return (
    <Panel title={label} actions={profile ? <Link to={`/@${profile.handle}`}>Ver página</Link> : undefined}>
      <Field label="Identificador" hint="3 a 30 caracteres: letras, números, ponto, hífen ou sublinhado" wide>
        <div className="row gap">
          <Input value={f.v.handle} onChange={(v) => { f.set("handle")(v); setCheck(null); }} placeholder="minha.organizacao" />
          <Button variant="ghost" onClick={verify} disabled={!f.v.handle}>Conferir</Button>
        </div>
      </Field>
      {check && (
        <p className={check.available ? "small" : "small muted"}>
          @{check.handle} — {check.available ? "disponível" : `indisponível: ${check.reason}`}
          {check.rule && <> ({check.rule})</>}
        </p>
      )}
      <Field label="Nome exibido" wide><Input value={f.v.display_name} onChange={f.set("display_name")} /></Field>
      <Field label="Uma linha sobre" wide><Input value={f.v.headline} onChange={f.set("headline")} /></Field>
      <Field label="Apresentação" wide><TextArea value={f.v.bio} onChange={f.set("bio")} rows={4} /></Field>
      {profile && (
        <>
          <Field label="Quem vê a página" wide>
            <Select value={f.v.visibility} onChange={f.set("visibility")}
                    options={[["public", "Qualquer pessoa"], ["network", "Somente quem tem conta"],
                              ["private", "Ninguém (fora do ar)"]]} /></Field>
          <Field label="O que a página mostra" wide>
            <div className="col gap">
              {([["show_territory", "Território"], ["show_projects", "Projetos publicados"],
                 ["show_impact_history", "Resultados relatados"], ["show_credentials", "Registros profissionais"],
                 ["show_organizations", "Organizações"], ["show_contact", "Contato (desligado por padrão)"]] as const)
                .map(([k, lbl]) => (
                  <label key={k} className="row gap">
                    <input type="checkbox" checked={(f.v as any)[k]}
                           onChange={(ev: any) => (f.set(k as any) as any)(ev.target.checked)} />
                    <span>{lbl}</span>
                  </label>
                ))}
            </div>
          </Field>
          <p className="muted small">
            Você escolhe os interruptores; o servidor monta a projeção. Os campos possíveis são uma lista fechada:
            {" "}{(meta.projectable || []).join(", ")}.
          </p>
        </>
      )}
      <div className="row gap">
        {profile
          ? <>
              <Button variant="ink" busy={act.busy} onClick={save}>Salvar</Button>
              <Button variant="ghost" busy={act.busy}
                      onClick={async () => { if (await act.run(() => api.post(`/v1/profiles/${profile.id}/rebuild`, {}),
                        "Página pública atualizada")) onDone(); }}>Atualizar página</Button>
              <Button variant="ghost" onClick={() => navigate(`/perfil-publico/${profile.id}/identificadores`)}>
                Histórico de identificadores</Button>
            </>
          : <Button variant="ink" busy={act.busy} disabled={!f.v.handle || !f.v.display_name} onClick={create}>
              Criar perfil</Button>}
      </div>
    </Panel>
  );
}

export function HandleHistory({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/profiles/${id}/handle-history`, [id]);
  return (
    <>
      <PageHead title="Histórico de identificadores" back="/perfil-publico"
                sub="Trocar é permitido; apagar o rastro não. O identificador antigo não volta a ficar livre de imediato." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <ul className="list">
            {data.items.map((h: any, i: number) => (
              <li key={i} className="list-row">
                <span className="grow">@{h.handle}</span>
                <span className="muted small">{h.changed_by ? `${h.changed_by} · ` : ""}{date(h.at)}</span>
              </li>
            ))}
          </ul>
        )}
      </StateView>
    </>
  );
}

// ---------------------------------------------------------------------------- experiência profissional
export function Experiences() {
  const { data, error, loading, reload } = useLoad<any>("/v1/profile/experiences");
  const f = useForm({ org_name: "", role: "", description: "", started_on: "", ended_on: "", visibility: "network" });
  const act = useAction();
  const add = async () => {
    if (await act.run(() => api.post("/v1/profile/experiences", {
      org_name: f.v.org_name, role: f.v.role, description: f.v.description || undefined,
      started_on: f.v.started_on, ended_on: f.v.ended_on || undefined, visibility: f.v.visibility,
    }), "Experiência declarada")) { f.setV({ ...f.v, org_name: "", role: "", description: "" }); reload(); }
  };
  return (
    <>
      <PageHead title="Experiência profissional" back="/perfil-publico"
                sub="Declarada não aparece no perfil público. Só a confirmada por quem administra a organização citada." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <Panel title="Suas experiências">
            {data.items.length ? (
              <ul className="list">
                {data.items.map((e: any) => (
                  <li key={e.id} className="list-row">
                    <div className="grow"><strong>{e.role}</strong> — {e.org_name}
                      <p className="muted small">{e.started_on} {e.ended_on ? `a ${e.ended_on}` : "— atual"}
                        {e.confirmed_by_name && <> · confirmada por {e.confirmed_by_name}</>}
                        {e.dispute_note && <> · contestada: {e.dispute_note}</>}</p></div>
                    <Pill status={e.state}>{STATE_LABEL[e.state] || e.state}</Pill>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">Nenhuma experiência declarada.</p>}
          </Panel>
        )}
      </StateView>
      <Panel title="Declarar experiência">
        <div className="row gap wrap">
          <Field label="Organização"><Input value={f.v.org_name} onChange={f.set("org_name")} /></Field>
          <Field label="Papel"><Input value={f.v.role} onChange={f.set("role")} /></Field>
          <Field label="Início"><Input type="date" value={f.v.started_on} onChange={f.set("started_on")} /></Field>
          <Field label="Fim (opcional)"><Input type="date" value={f.v.ended_on} onChange={f.set("ended_on")} /></Field>
        </div>
        <Field label="O que você fez" wide><TextArea value={f.v.description} onChange={f.set("description")} rows={3} /></Field>
        <Button variant="ink" busy={act.busy} disabled={!f.v.org_name || !f.v.role || !f.v.started_on} onClick={add}>
          Declarar</Button>
      </Panel>
    </>
  );
}
const STATE_LABEL: Record<string, string> = { declared: "declarada", pending_confirmation: "aguardando confirmação",
  confirmed: "confirmada", disputed: "contestada", revoked: "revogada" };

export function ExperienceRequests() {
  const { data, error, loading, reload } = useLoad<any>("/v1/org/experience-requests");
  const act = useAction();
  const [note, setNote] = useState<Record<string, string>>({});
  const decide = async (eid: string, decision: string) => {
    if (decision === "disputed" && (note[eid] || "").trim().length < 3) {
      alert("Contestar exige dizer o motivo."); return;
    }
    if (await act.run(() => api.post(`/v1/org/experience-requests/${eid}/decide`,
                                     { decision, note: note[eid] || undefined }), "Decisão registrada")) reload();
  };
  return (
    <>
      <PageHead title="Experiências declaradas na sua organização"
                sub="Confirmar é afirmar que a pessoa atuou aqui. Ninguém confirma a própria experiência." />
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <ul className="list">
            {data.items.map((e: any) => (
              <li key={e.id} className="list-row">
                <div className="grow"><strong>{e.person}</strong> — {e.role}
                  <p className="muted small">{e.started_on} {e.ended_on ? `a ${e.ended_on}` : "— atual"}</p>
                  {e.description && <p className="small">{e.description}</p>}
                  <Input value={note[e.id] || ""} placeholder="motivo (exigido ao contestar)"
                         onChange={(v) => setNote({ ...note, [e.id]: v })} />
                </div>
                <div className="row gap">
                  <Button variant="ink" busy={act.busy} onClick={() => decide(e.id, "confirmed")}>Confirmar</Button>
                  <Button variant="ghost" onClick={() => decide(e.id, "disputed")}>Contestar</Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </StateView>
    </>
  );
}
