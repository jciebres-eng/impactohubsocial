import { useState } from "react";
import { api } from "../api";
import { money } from "../format";
import { Link, navigate } from "../router";
import { Button, PageHead, Panel, Pill, StateView, useAction, useLoad } from "../ui/kit";
import { JourneyTrail } from "../ui/trail";

// WORKSPACE — não é "dashboard por perfil".
//
// A diferença é concreta e está nesta tela: um painel mostra NÚMEROS; o workspace mostra PRÓXIMAS AÇÕES, cada uma
// com a razão e o destino. O backend decide persona, capacidades, ordem das seções e o conteúdo de cada uma
// (GET /v1/workspace); aqui só desenhamos o que vem. Nenhuma regra de visibilidade vive no navegador.
//
// Esta camada é FUNCIONAL. O visual vem com a designer; o que importa agora é que tudo o que o backend faz tenha
// caminho de uso e nada fique escondido.

const BAND_TONE: Record<string, string> = { pronto: "good", quase: "good", "em construção": "warn", inicial: "bad" };

export function Workspace() {
  const [persona, setPersona] = useState<string | null>(null);
  const q = persona ? `?persona=${encodeURIComponent(persona)}` : "";
  const { data, error, loading, reload } = useLoad<any>(`/v1/workspace${q}`, [persona]);
  if (!data) return <StateView loading={loading} error={error} onRetry={reload} />;
  const p = data.persona;
  return (
    <>
      <PageHead
        title={p.label || "Área de trabalho"}
        sub={p.job}
        actions={p.available?.length > 1 ? (
          <div className="row gap">
            {p.available.map((k: string) => (
              <Button key={k} variant={k === p.key ? "ink" : "ghost"} onClick={() => setPersona(k)}>{k}</Button>
            ))}
          </div>
        ) : undefined}
      />
      <p className="muted small">{data.note}</p>
      {/* A JORNADA DO PERFIL, na entrada do perfil. Ela já era calculada pelo servidor
          (`GET /v1/help/start`, de `config/onboarding_paths.json`, marcada por dado real e não por
          autodeclaração) e só aparecia dentro de /ajuda, atrás do link do rodapé do menu — ou seja,
          o mapa do caminho de cada perfil existia e ficava onde ninguém passa. */}
      <JourneyAtWork />
      {data.layout.map((sec: any) => (
        <Section key={sec.key} id={sec.key} title={sec.title} data={data.sections[sec.key]}
                 counts={data.counts} reload={reload} />
      ))}
    </>
  );
}


/** A jornada do perfil, resumida: a Trilha e quantas etapas faltam.

 *  Carrega à parte do workspace de propósito — se a jornada falhar, a área de trabalho continua
 *  abrindo. Um mapa é orientação, não pré-requisito para trabalhar. */
function JourneyAtWork() {
  const { data } = useLoad<any>("/v1/help/start");
  if (!data?.steps?.length) return null;
  const falta = data.total - data.done;
  return (
    <div className="stack">
      <JourneyTrail steps={data.steps} />
      <p className="muted small">
        {falta === 0 ? "Jornada concluída." : `${falta} etapa${falta === 1 ? "" : "s"} para concluir sua jornada.`}
        {" "}<Link to="/ajuda/comece-aqui">Ver o caminho completo</Link>
      </p>
    </div>
  );
}

function Section({ id, title, data, counts, reload }: any) {
  if (data == null || (Array.isArray(data) && !data.length)) {
    return <Panel title={title} quiet><p className="muted">Nada aqui ainda.</p></Panel>;
  }
  switch (id) {
    case "next_actions": return <NextActions title={title} items={data} reload={reload} />;
    case "readiness": return <ReadinessCards title={title} items={data} />;
    case "proposals_in":
    case "proposals_out": return <Proposals title={title} items={data} />;
    case "projects": return <Projects title={title} items={data} />;
    case "listings": return <Listings title={title} items={data} />;
    case "reports_due": return <ReportsDue title={title} items={data} />;
    case "reports_to_review": return <ReportsToReview title={title} items={data} />;
    case "conversations": return <Threads title={title} items={data} />;
    case "network": return <Network title={title} data={data} counts={counts} />;
    case "pipeline": return <Pipeline title={title} items={data} />;
    case "supported": return <Supported title={title} items={data} />;
    case "discover":
    case "opportunities": return <Discover title={title} items={data} />;
    case "engagements": return <Engagements title={title} items={data} />;
    case "profile": return <ProfileBox title={title} data={data} />;
    case "credentials": return <Credentials title={title} data={data} />;
    case "territory": return <Territory title={title} items={data} />;
    case "programs": return <Programs title={title} items={data} />;
    case "monitored": return <Monitored title={title} items={data} />;
    case "indicators": return <Indicators title={title} items={data} />;
    case "moderation": return <Moderation title={title} data={data} />;
    case "queues": return <Queues title={title} data={data} />;
    case "platform": return <PlatformHealth title={title} data={data} />;
    default: return <Panel title={title} quiet><pre className="small">{JSON.stringify(data, null, 1)}</pre></Panel>;
  }
}

// ---------------------------------------------------------------------------- próximas ações
function NextActions({ title, items, reload }: any) {
  const act = useAction();
  const resolve = async (id: string, status: string) => {
    const r = await act.run(() => api.post(`/v1/recommendations/${id}/resolve`, { status }),
                            status === "done" ? "Marcada como feita" : "Dispensada");
    if (r) reload();
  };
  return (
    <Panel title={title} actions={<Button variant="ghost" busy={act.busy}
      onClick={async () => { if (await act.run(() => api.post("/v1/recommendations/refresh", {}), "Recalculado")) reload(); }}>
      Recalcular</Button>}>
      <ul className="list">
        {items.map((r: any) => (
          <li key={r.id || r.action + r.subject_id} className="list-row">
            <div className="grow">
              <div className="row gap">
                <strong>{r.title}</strong>
                {r.priority >= 85 && <Pill tone="bad">prioritário</Pill>}
                {r.confidence_band === "insufficient_data" && <Pill tone="warn">sem base para confiança</Pill>}
              </div>
              {/* A razão é obrigatória no backend. Mostrá-la é o que separa recomendação de palpite. */}
              <p className="muted small">{r.rationale}</p>
            </div>
            <div className="row gap">
              <Button variant="ink" onClick={() => navigate(r.link)}>Abrir</Button>
              {r.id && <>
                <Button variant="ghost" onClick={() => resolve(r.id, "done")}>Feito</Button>
                <Button variant="ghost" onClick={() => resolve(r.id, "dismissed")}>Dispensar</Button>
              </>}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- prontidão
function ReadinessCards({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/prontidao/finalidades">Ver detalhe</Link>}>
      {items.map((r: any) => (
        <div key={r.project_id} className="stack-sm">
          <div className="row gap">
            <Link to={`/projetos/${r.project_id}`}><strong>{r.title}</strong></Link>
            <Pill tone={BAND_TONE[r.band]}>{r.overall}% · {r.band}</Pill>
          </div>
          <div className="row gap wrap small muted">
            {Object.entries(r.scores).map(([k, v]: any) => <span key={k}>{LABEL_READINESS[k] || k}: {v}%</span>)}
          </div>
          {!!r.blockers?.length && (
            <ul className="small">{r.blockers.map((b: any, i: number) => <li key={i}>{b.label}: {b.blocker}</li>)}</ul>
          )}
        </div>
      ))}
    </Panel>
  );
}
const LABEL_READINESS: Record<string, string> = {
  document_readiness: "Documentação", project_readiness: "Projeto", funding_readiness: "Captação",
  governance_readiness: "Governança", execution_readiness: "Execução", evidence_readiness: "Evidência",
};

// ---------------------------------------------------------------------------- propostas
function Proposals({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/propostas">Ver todas</Link>}>
      <ul className="list">
        {items.map((p: any) => (
          <li key={p.id} className="list-row">
            <div className="grow">
              <Link to={`/propostas/${p.id}`}><strong>{p.title}</strong></Link>
              <p className="muted small">
                {p.label} · {p.side === "receiver" ? `de ${p.sender_name}` : `para ${p.receiver_name}`}
                {p.amount_cents != null && <> · {money(p.amount_cents, p.currency)}</>}
                {p.project_title && <> · {p.project_title}</>}
              </p>
            </div>
            <div className="row gap">
              <Pill status={p.status}>{p.status_label}</Pill>
              {p.awaiting_me && <Pill tone="warn">espera por você</Pill>}
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- projetos e anúncios
function Projects({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/projetos">Ver todos</Link>}>
      <ul className="list">
        {items.map((p: any) => (
          <li key={p.id} className="list-row">
            <div className="grow">
              <Link to={`/projetos/${p.id}`}><strong>{p.title}</strong></Link>
              <p className="muted small">
                equipe: {p.team_size} pessoa(s)
                {p.budget_total_cents ? <> · orçamento {money(p.budget_total_cents)}</> : null}
                {/* "comprometido" nunca é escrito como "recebido": são etapas diferentes do apoio. */}
                {p.committed_cents ? <> · comprometido {money(p.committed_cents)}</> : null}
              </p>
            </div>
            <div className="row gap"><Pill status={p.status}>{p.status}</Pill><Pill>{p.visibility}</Pill></div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Listings({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/marketplace/meus">Gerenciar</Link>}>
      <ul className="list">
        {items.map((l: any) => (
          <li key={l.id} className="list-row">
            <div className="grow"><strong>{l.headline}</strong>
              <p className="muted small">{l.subject_type} · {(l.seeking || []).join(", ") || "sem busca declarada"}</p>
            </div>
            <Pill status={l.publication_state}>{l.state_label}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- prestação de contas
function ReportsDue({ title, items }: any) {
  return (
    <Panel title={title}>
      <ul className="list">
        {items.map((p: any) => (
          <li key={p.id} className="list-row">
            <div className="grow"><Link to={`/projetos/${p.id}/relatorios`}><strong>{p.title}</strong></Link>
              <p className="muted small">
                {p.last_accepted_period
                  ? `último relatório aceito cobre até ${p.last_accepted_period}`
                  : "nenhum relatório aceito ainda"}
                {p.latest_status && p.latest_status !== "published" && <> · em andamento: {p.latest_status}</>}
              </p>
            </div>
            <Button variant="ink" onClick={() => navigate(`/projetos/${p.id}/relatorios`)}>Relatar</Button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function ReportsToReview({ title, items }: any) {
  return (
    <Panel title={title}>
      <ul className="list">
        {items.map((u: any) => (
          <li key={u.id} className="list-row">
            <div className="grow"><Link to={`/relatorios-impacto/${u.id}`}><strong>{u.project_title}</strong></Link>
              <p className="muted small">{u.org_name} · {u.period_start} a {u.period_end} ·
                {" "}{u.evidence_count} evidência(s)</p>
            </div>
            <Button variant="ink" onClick={() => navigate(`/relatorios-impacto/${u.id}`)}>Analisar</Button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- conversas e rede
function Threads({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/conversas">Ver todas</Link>}>
      <ul className="list">
        {items.map((t: any) => (
          <li key={t.id} className="list-row">
            <div className="grow"><Link to={`/conversas/${t.id}`}><strong>{t.other_name}</strong></Link>
              <p className="muted small">
                {t.subject || "sem assunto"}
                {t.project_title && <> · {t.project_title}</>}
                {!t.has_context && <> · <em>sem contexto</em></>}
              </p>
            </div>
            {t.unread > 0 && <Pill tone="warn">{t.unread} não lido(s)</Pill>}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Network({ title, data, counts }: any) {
  return (
    <Panel title={title} actions={<Link to="/rede/relacoes">Ver relações</Link>}>
      <p className="muted small">
        {counts?.relationships?.active ?? 0} relação(ões) ativa(s) ·
        {" "}{counts?.relationships?.pending_in ?? 0} aguardando sua resposta ·
        {" "}{data.graph?.count ?? 0} organização(ões) a um passo
      </p>
      {!!data.pending?.length && (
        <ul className="list">
          {data.pending.map((r: any) => (
            <li key={r.id} className="list-row">
              <div className="grow"><strong>{r.label}</strong>
                <p className="muted small">de {r.source_org_name || r.source_user_name}</p></div>
              <Button variant="ink" onClick={() => navigate("/rede/relacoes")}>Responder</Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ---------------------------------------------------------------------------- investidor
function Pipeline({ title, items }: any) {
  return (
    <Panel title={title}>
      <p className="muted small">Favoritos e acompanhamentos são PRIVADOS: ninguém além da sua organização vê.</p>
      <ul className="list">
        {items.map((r: any) => (
          <li key={r.id} className="list-row">
            <div className="grow"><Link to={`/projetos/${r.project_id}`}><strong>{r.title}</strong></Link>
              <p className="muted small">{r.org_name}
                {r.budget_total_cents ? <> · pede {money(r.budget_total_cents)}</> : null}</p>
            </div>
            <Pill>{r.kind}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Supported({ title, items }: any) {
  return (
    <Panel title={title}>
      {/* A distinção que a plataforma não deixa borrar: intenção ≠ compromisso ≠ dinheiro recebido. */}
      <p className="muted small">Intenção registrada não é compromisso firmado, e compromisso não é valor recebido.</p>
      <ul className="list">
        {items.map((s: any) => (
          <li key={s.id} className="list-row">
            <div className="grow"><Link to={`/projetos/${s.id}`}><strong>{s.title}</strong></Link>
              <p className="muted small">{s.org_name}
                {s.intent_amount_cents != null && <> · pretendido {money(s.intent_amount_cents, s.currency)}</>}
                {s.has_commitment ? " · compromisso firmado" : " · sem compromisso firmado"}
                {s.project_committed_cents ? <> · projeto já comprometeu {money(s.project_committed_cents)}</> : null}
              </p>
            </div>
            <Pill status={s.intent_status}>{s.intent_status}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Discover({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/marketplace">Ver marketplace</Link>}>
      <ul className="list">
        {items.map((l: any) => (
          <li key={l.id} className="list-row">
            <div className="grow"><Link to={`/marketplace/${l.id}`}><strong>{l.headline}</strong></Link>
              <p className="muted small">{l.org_name}
                {l.territory && <> · {l.territory}</>}
                {!!l.seeking?.length && <> · busca {l.seeking.join(", ")}</>}
                {l.amount_target_cents ? <> · {money(l.amount_target_cents, l.currency)}</> : null}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Engagements({ title, items }: any) {
  return (
    <Panel title={title}>
      <ul className="list">
        {items.map((r: any) => (
          <li key={r.id} className="list-row">
            <div className="grow"><strong>{r.label}</strong>
              <p className="muted small">{r.target_org_name || r.target_project_title || r.target_user_name}
                {r.role && <> · {r.role}</>}</p></div>
            <Pill status={r.status}>{r.status}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- profissional
function ProfileBox({ title, data }: any) {
  const mine = data.person || data.org;
  return (
    <Panel title={title} actions={<Link to="/perfil-publico">Editar</Link>}>
      {mine ? (
        <p>
          <strong>@{mine.handle}</strong> — {mine.display_name}
          {mine.verified_badge && <> · <Pill tone="good">verificado: {mine.verified_badge}</Pill></>}
          {mine.suspended && <> · <Pill tone="bad">suspenso</Pill></>}
        </p>
      ) : <p className="muted">Você ainda não tem perfil público. <Link to="/perfil-publico">Criar agora</Link>.</p>}
    </Panel>
  );
}

function Credentials({ title, data }: any) {
  return (
    <Panel title={title} actions={<Link to="/perfil-publico/experiencias">Gerenciar</Link>}>
      <p className="muted small">
        Só experiência CONFIRMADA por quem administra a organização citada aparece no perfil público.
      </p>
      <ul className="list">
        {(data.credentials || []).map((c: any) => (
          <li key={c.id} className="list-row">
            <span className="grow">{c.council}{c.uf && `/${c.uf}`}</span>
            <Pill status={c.verification_status}>{c.verification_status}</Pill>
          </li>
        ))}
        {(data.experiences || []).map((e: any) => (
          <li key={e.id} className="list-row">
            <span className="grow">{e.role} — {e.org_name}</span>
            <Pill status={e.state}>{e.state}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- governo
function Territory({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/territorio/necessidades">Registrar necessidade</Link>}>
      <ul className="list">
        {items.map((n: any) => (
          <li key={n.id} className="list-row">
            <div className="grow"><strong>{n.title}</strong>
              <p className="muted small">
                {n.territory}
                {n.people_estimate != null && <> · {n.people_estimate} pessoa(s)</>}
                {/* Número sem fonte não existe nesta tabela: o banco recusa estimativa sem origem declarada. */}
                {n.source_name && <> · fonte: {n.source_name}</>}
              </p></div>
            <Pill>prioridade {n.priority}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Programs({ title, items }: any) {
  return (
    <Panel title={title} actions={<Link to="/editais">Gerenciar</Link>}>
      <ul className="list">
        {items.map((c: any) => (
          <li key={c.id} className="list-row">
            <div className="grow"><Link to={`/editais/${c.id}/candidaturas`}><strong>{c.title}</strong></Link>
              <p className="muted small">{c.instrument}
                {c.closes_at && <> · encerra {String(c.closes_at).slice(0, 10)}</>}</p></div>
            <Pill status={c.status}>{c.status}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Monitored({ title, items }: any) {
  return (
    <Panel title={title}>
      <ul className="list">
        {items.map((p: any) => (
          <li key={p.id} className="list-row">
            <div className="grow"><Link to={`/projetos/${p.id}`}><strong>{p.title}</strong></Link>
              <p className="muted small">{p.org_name} · {p.territory}
                {p.committed_cents ? <> · comprometido {money(p.committed_cents)}</> : null}</p></div>
            <Pill status={p.status}>{p.status}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Indicators({ title, items }: any) {
  return (
    <Panel title={title}>
      <p className="muted small">Somente medições VALIDADAS de projetos publicados.</p>
      <ul className="list">
        {items.map((i: any) => (
          <li key={i.code} className="list-row">
            <span className="grow">{i.name} <span className="muted small">({i.unit})</span></span>
            <span>{i.validated_sum ?? "—"} · {i.projects} projeto(s)</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ---------------------------------------------------------------------------- administração
function Moderation({ title, data }: any) {
  return (
    <Panel title={title} actions={<Link to="/admin/denuncias">Abrir fila</Link>}>
      <p>{data.open_reports} denúncia(s) em aberto</p>
      <ul className="list">
        {(data.recent_actions || []).map((a: any) => (
          <li key={a.id} className="list-row">
            <span className="grow">{a.measure} <span className="muted small">({a.rule_ref})</span></span>
            <Pill status={a.status}>{a.status}</Pill>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Queues({ title, data }: any) {
  const rows: [string, string, string][] = [
    ["Documentos em análise", data.documents, "/admin/compliance"],
    ["Organizações em análise", data.orgs, "/admin/compliance"],
    ["Credenciais pendentes", data.credentials, "/admin/credenciais"],
    ["Relatórios de impacto", data.impact_updates, "/admin"],
  ];
  return (
    <Panel title={title}>
      <ul className="list">
        {rows.map(([label, n, to]) => (
          <li key={label} className="list-row">
            <span className="grow">{label}</span><strong>{n}</strong>
            <Button variant="ghost" onClick={() => navigate(to)}>Abrir</Button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function PlatformHealth({ title, data }: any) {
  return (
    <Panel title={title}>
      <ul className="list">
        {Object.entries(data).map(([k, v]: any) => (
          <li key={k} className="list-row"><span className="grow">{PLATFORM_LABEL[k] || k}</span><strong>{v}</strong></li>
        ))}
      </ul>
    </Panel>
  );
}
const PLATFORM_LABEL: Record<string, string> = {
  organizations: "Organizações", projects_published: "Projetos publicados",
  listings_published: "Anúncios publicados", relationships_active: "Relações ativas",
  proposals_open: "Propostas em aberto", events_24h: "Fatos nas últimas 24 h",
};
