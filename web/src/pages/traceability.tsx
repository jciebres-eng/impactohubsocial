/**
 * RASTREABILIDADE E INTEGRIDADE — telas de administração da v0.23.0.
 *
 * Quatro telas que existem porque quatro perguntas não tinham onde ser respondidas:
 *
 *   1. "Mostre-me tudo o que aconteceu com ESTE documento."     → LinhaDoTempo
 *   2. "De onde veio este número?"                              → Proveniencia
 *   3. "A plataforma está íntegra?"                             → Integridade
 *   4. "Como eu paro a plataforma agora?"                       → Interruptor
 *
 * A linha do tempo lê EVENTOS REAIS de `audit_events`. Não há dado de exemplo em nenhuma destas
 * telas — tela de auditoria com dado fictício é pior que tela ausente, porque treina quem opera a
 * confiar no que está vendo.
 */
import { useState } from "react";
import { Button, KeyValue, Panel, PageHead, Pill, StateView, useAction, useLoad } from "../ui/kit";
import { api } from "../api";
import { dateTime } from "../format";

const ATOR: Record<string, string> = {
  user: "pessoa", admin: "administração", system: "sistema",
  ai: "inteligência artificial", automation: "automação", integration: "integração",
};

function Ator({ tipo }: { tipo: string }) {
  const tom = tipo === "ai" ? "warn" : tipo === "admin" ? "warn" : "muted";
  return <Pill tone={tom}>{ATOR[tipo] || tipo}</Pill>;
}

function AntesDepois({ antes, depois }: { antes: any; depois: any }) {
  if (!antes && !depois) return null;
  const chaves = Array.from(new Set([...Object.keys(antes || {}), ...Object.keys(depois || {})]));
  return (
    <table className="table table-compact">
      <thead><tr><th>Campo</th><th>Antes</th><th>Depois</th></tr></thead>
      <tbody>
        {chaves.map((k) => {
          const a = antes?.[k];
          const d = depois?.[k];
          const mudou = JSON.stringify(a) !== JSON.stringify(d);
          return (
            <tr key={k} className={mudou ? "row-changed" : undefined}>
              <td className="mono small">{k}</td>
              <td className="small">{a === undefined ? "—" : JSON.stringify(a)}</td>
              <td className="small">{d === undefined ? "—" : JSON.stringify(d)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

/* ------------------------------------------------------------------ 1. linha do tempo de entidade */

export function LinhaDoTempo() {
  const [tipo, setTipo] = useState("document");
  const [id, setId] = useState("");
  const [consulta, setConsulta] = useState<string | null>(null);
  const { data, error, loading, reload } = useLoad<any>(consulta);

  return (
    <>
      <PageHead
        title="Linha do tempo de uma entidade"
        sub="Tudo o que aconteceu com um documento, projeto ou organização, na ordem em que aconteceu."
      />
      <Panel title="O que você quer rastrear">
        <div className="form-grid">
          <label>
            Tipo
            <select className="input" value={tipo} onChange={(ev: React.ChangeEvent<HTMLSelectElement>) => setTipo(ev.target.value)}>
              {["document", "project", "organization", "application", "indicator_value", "user",
                "session", "kill_switch", "platform_expense", "payment_instruction"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
          <label>
            Identificador
            <input className="input mono" value={id} onChange={(ev: React.ChangeEvent<HTMLInputElement>) => setId(ev.target.value)} placeholder="uuid" />
          </label>
          <Button
            disabled={!id}
            onClick={() => setConsulta(`/v1/admin/audit/timeline?object_type=${encodeURIComponent(tipo)}&object_id=${encodeURIComponent(id)}`)}
          >
            Ver linha do tempo
          </Button>
        </div>
      </Panel>

      {consulta && (
        <StateView loading={loading} error={error} onRetry={reload}
          empty={data && data.count === 0 && (
            <p className="note">
              Nenhum evento registrado para esta entidade. Isso pode significar que o
              identificador está errado, ou que a entidade nunca foi alterada.
            </p>
          )}>
          {data && data.count > 0 && (
            <Panel title={`${data.count} evento(s)`}>
              {data.truncated && <p className="note">{data.note}</p>}
              <ol className="timeline">
                {data.events.map((e: any) => (
                  <li key={e.id}>
                    <div className="timeline-head">
                      <strong>{e.action}</strong>
                      <Ator tipo={e.actor_type} />
                      {e.severity !== "info" && <Pill tone={e.severity === "critical" ? "danger" : "warn"}>{e.severity}</Pill>}
                      {e.status !== "success" && <Pill tone="warn">{e.status}</Pill>}
                      <span className="small">{dateTime(e.at)}</span>
                    </div>
                    <div className="small">
                      {e.resource_name && <>{e.resource_name} · </>}
                      origem {e.source}
                      {e.ip && <> · {e.ip}</>}
                      {e.correlation_id && (
                        <> · <a href={`/admin/rastro?correlation_id=${encodeURIComponent(e.correlation_id)}`}>ver cadeia de causa</a></>
                      )}
                    </div>
                    <AntesDepois antes={e.before_state} depois={e.after_state} />
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </StateView>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ 2. árvore de causa (rastro) */

export function Rastro() {
  const inicial = new URLSearchParams(window.location.search).get("correlation_id") || "";
  const [corr, setCorr] = useState(inicial);
  const [consulta, setConsulta] = useState<string | null>(
    inicial ? `/v1/admin/audit/trail?correlation_id=${encodeURIComponent(inicial)}` : null,
  );
  const { data, error, loading, reload } = useLoad<any>(consulta);

  return (
    <>
      <PageHead
        title="Cadeia de causa"
        sub="Que acontecimento levou a qual. A linha do tempo ordena por tempo; esta tela mostra a causa."
      />
      <Panel title="Rastro">
        <div className="form-grid">
          <label>
            Identificador de correlação
            <input className="input mono" value={corr} onChange={(ev: React.ChangeEvent<HTMLInputElement>) => setCorr(ev.target.value)} />
          </label>
          <Button disabled={!corr} onClick={() => setConsulta(`/v1/admin/audit/trail?correlation_id=${encodeURIComponent(corr)}`)}>
            Abrir
          </Button>
        </div>
      </Panel>
      {consulta && (
        <StateView loading={loading} error={error} onRetry={reload}>
          {data && (
            <Panel title={`${data.events_in_tree} de ${data.events_in_trail} evento(s) na árvore`}>
              {!data.complete && <p className="note state-error">{data.note}</p>}
              <ol className="tree">
                {data.tree.map((n: any) => (
                  <li key={n.id} style={{ marginLeft: `${n.depth * 1.5}rem` }}>
                    <strong>{n.action}</strong> <Ator tipo={n.actor_type} />
                    {n.status !== "success" && <Pill tone="warn">{n.status}</Pill>}
                    <span className="small"> · {dateTime(n.at)}</span>
                    {n.resource_name && <span className="small"> · {n.resource_name}</span>}
                  </li>
                ))}
              </ol>
            </Panel>
          )}
        </StateView>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ 3. proveniência de indicador */

export function Proveniencia() {
  const [id, setId] = useState("");
  const [consulta, setConsulta] = useState<string | null>(null);
  const { data, error, loading, reload } = useLoad<any>(consulta);

  return (
    <>
      <PageHead
        title="De onde veio este número"
        sub="Cadeia completa de uma medição: projeto, indicador, linha de base, documento, evidência, revisão, validação e lançamentos."
      />
      <Panel title="Medição">
        <div className="form-grid">
          <label>
            Identificador do valor do indicador
            <input className="input mono" value={id} onChange={(ev: React.ChangeEvent<HTMLInputElement>) => setId(ev.target.value)} placeholder="uuid" />
          </label>
          <Button disabled={!id} onClick={() => setConsulta(`/v1/indicator-values/${encodeURIComponent(id)}/provenance`)}>
            Rastrear
          </Button>
        </div>
      </Panel>

      {consulta && (
        <StateView loading={loading} error={error} onRetry={reload}>
          {data && (
            <>
              <Panel
                title={
                  data.provenance_complete ? (
                    <>Cadeia completa <Pill tone="ok">rastreável até a evidência</Pill></>
                  ) : (
                    <>Cadeia incompleta <Pill tone="warn">{data.gaps.length} elo(s) faltando</Pill></>
                  )
                }
              >
                <KeyValue
                  items={[
                    ["Valor", `${data.value.value} ${data.indicator.unit || ""}`.trim()],
                    ["Medido em", data.value.measured_on],
                    ["Estado", <Pill status={data.value.status}>{data.value.status}</Pill>],
                    ["Origem declarada", data.value.source_kind],
                    ["Indicador", `${data.indicator.code} — ${data.indicator.name}`],
                    ["Projeto", data.project.title],
                    ["Organização", data.project.org_name],
                    [
                      "Validação",
                      data.validation ? (
                        <>
                          {data.validation.validated_by_org_name}
                          {data.validation.independent
                            ? <Pill tone="ok">independente</Pill>
                            : <Pill tone="danger">não independente</Pill>}
                        </>
                      ) : "não validada",
                    ],
                  ]}
                />
              </Panel>

              {data.gaps.length > 0 && (
                <Panel title="O que falta para provar este número">
                  <p className="note">
                    Esta lista existe para não transformar ausência de prova em aparência de prova.
                    Cada elo diz o efeito dele sobre o que o número demonstra.
                  </p>
                  <table className="table">
                    <thead><tr><th>Elo</th><th>O que falta</th><th>Efeito</th></tr></thead>
                    <tbody>
                      {data.gaps.map((g: any) => (
                        <tr key={g.link}>
                          <td><Pill tone="warn">{g.link}</Pill></td>
                          <td>{g.what}</td>
                          <td className="small">{g.effect}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>
              )}

              <Panel title="A cadeia, passo por passo">
                <ol className="timeline">
                  {data.chain.map((p: any, i: number) => (
                    <li key={i} className={p.present ? undefined : "timeline-missing"}>
                      <div className="timeline-head">
                        <strong>{p.step}</strong>
                        {!p.present && <Pill tone="warn">ausente</Pill>}
                        {p.when && <span className="small">{dateTime(p.when)}</span>}
                      </div>
                      <div className="small">
                        {p.what}
                        {p.who && <> · {p.who}</>}
                      </div>
                    </li>
                  ))}
                </ol>
              </Panel>

              {data.document && (
                <Panel title="Documento de evidência" quiet>
                  <KeyValue
                    items={[
                      ["Arquivo", data.document.filename],
                      ["Versão", String(data.document.version)],
                      ["Hash do conteúdo (sha256)", <span className="mono small">{data.document.sha256}</span>],
                      ["Enviado por", data.document.uploaded_by_name || "—"],
                      ["Validação do documento", data.document.validation_status || "—"],
                      ["Substituído por", data.document.superseded_by_count > 0
                        ? <Pill tone="warn">{data.document.superseded_by_count} versão(ões) mais nova(s)</Pill>
                        : "não"],
                    ]}
                  />
                </Panel>
              )}

              {data.ledger.length > 0 && (
                <Panel title="Lançamentos no Impact Ledger" quiet>
                  <table className="table">
                    <thead><tr><th>Seq</th><th>Tipo</th><th>Quando</th><th>Hash</th></tr></thead>
                    <tbody>
                      {data.ledger.map((l: any) => (
                        <tr key={l.seq}>
                          <td>{l.seq}</td>
                          <td>{l.entry_type}</td>
                          <td>{dateTime(l.at)}</td>
                          <td className="mono small">{(l.entry_hash || "").slice(0, 16)}…</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>
              )}
            </>
          )}
        </StateView>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ 4. integridade relacional */

export function Integridade() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/integrity");
  return (
    <>
      <PageHead
        title="Integridade dos dados"
        sub="Órfãos, referências não resolvidas, deriva de catálogo, cadeias de hash e cobertura de proveniência."
      />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel
              title={
                <>
                  Estado:{" "}
                  <Pill tone={data.state === "VERDE" ? "ok" : data.state === "AMARELO" ? "warn" : "danger"}>
                    {data.state}
                  </Pill>
                </>
              }
            >
              <p className="note">{data.note}</p>
              <KeyValue
                items={[
                  ["Linhas órfãs", String(data.orphan_rows)],
                  ["Cadeias de hash quebradas", String(data.broken_chains)],
                  ["Colunas polimórficas catalogadas", String(data.polymorphic_columns_catalogued)],
                  ["Colunas conferidas nesta execução", String(data.polymorphic_columns_checked)],
                ]}
              />
            </Panel>

            <Panel title="Proveniência das medições">
              <KeyValue
                items={[
                  ["Medições", String(data.provenance.measurements)],
                  ["Com evidência", String(data.provenance.with_evidence)],
                  ["Validadas", String(data.provenance.validated)],
                  [
                    "Validadas SEM evidência",
                    data.provenance.validated_without_evidence > 0
                      ? <Pill tone="danger">{data.provenance.validated_without_evidence}</Pill>
                      : <Pill tone="ok">0</Pill>,
                  ],
                  ["Cobertura", data.provenance.coverage_pct == null ? "—" : `${data.provenance.coverage_pct}%`],
                ]}
              />
              <p className="note">{data.provenance.rule}</p>
            </Panel>

            <Panel title="Cadeias de hash" quiet>
              <table className="table">
                <thead><tr><th>Cadeia</th><th>Escopos</th><th>Quebradas</th></tr></thead>
                <tbody>
                  {["audit", "ledger", "value"].map((k) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{data.chains[k].scopes}</td>
                      <td>
                        {data.chains[k].broken.length === 0
                          ? <Pill tone="ok">nenhuma</Pill>
                          : <Pill tone="danger">{data.chains[k].broken.length}</Pill>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {data.chains.value.rows_without_chain > 0 && (
                <p className="note">
                  {data.chains.value.rows_without_chain} linha(s) de valor sem cadeia.{" "}
                  {data.chains.value.note}
                </p>
              )}
            </Panel>

            {data.catalog_drift.length > 0 && (
              <Panel title="Deriva de catálogo">
                <p className="note">
                  Coluna de referência polimórfica fora do catálogo, ou catalogada e já inexistente.
                  É este relatório que impede o verificador de órfãos de ficar para trás do esquema.
                </p>
                <ul className="list-plain">
                  {data.catalog_drift.map((d: any) => (
                    <li key={`${d.source_table}.${d.id_column}`}>
                      <span className="mono">{d.source_table}.{d.id_column}</span> — {d.situation}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}

            {data.orphans.filter((o: any) => o.orphans > 0).length > 0 && (
              <Panel title="Linhas órfãs">
                <table className="table">
                  <thead><tr><th>Tabela</th><th>Tipo</th><th>Aponta para</th><th>Órfãs</th><th>Conferidas</th></tr></thead>
                  <tbody>
                    {data.orphans.filter((o: any) => o.orphans > 0).map((o: any) => (
                      <tr key={`${o.source_table}-${o.type_value}`}>
                        <td className="mono small">{o.source_table}.{o.id_column}</td>
                        <td>{o.type_value}</td>
                        <td className="mono small">{o.target_table}</td>
                        <td><Pill tone="danger">{o.orphans}</Pill></td>
                        <td>{o.rows_checked}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}

            {data.unresolved_refs.length > 0 && (
              <Panel title="Tipos que o motor não resolve" quiet>
                <p className="note">
                  Valores de tipo presentes nos dados que não resolvem para tabela nenhuma e não têm
                  exceção escrita. É o sinal de que o catálogo está atrás do código.
                </p>
                <ul className="list-plain">
                  {data.unresolved_refs.map((u: any) => (
                    <li key={`${u.source_table}-${u.type_value}`}>
                      <span className="mono">{u.source_table}.{u.type_column}</span> = {u.type_value}{" "}
                      ({u.rows_affected} linha(s))
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </>
        )}
      </StateView>
    </>
  );
}

/* ------------------------------------------------------------------ 5. interruptor de emergência */

const EFEITO_CURTO: Record<string, string> = {
  mutations: "modo somente leitura",
  logins: "bloqueia entrada de quem não é da equipe",
  uploads: "bloqueia envio de arquivo",
  integrations: "bloqueia integrações externas",
  maintenance: "bloqueia tudo, inclusive leitura",
};

export function Interruptor() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/kill-switch");
  const { run, busy } = useAction();
  const [motivo, setMotivo] = useState("");
  const [escopo, setEscopo] = useState<string | null>(null);

  async function acionar(scope: string, action: "engage" | "release") {
    if (motivo.trim().length < 10) return;
    await run(async () => {
      await api.post("/v1/admin/kill-switch", { scope, action, reason: motivo.trim() });
      setMotivo("");
      setEscopo(null);
      await reload();
    }, action === "engage" ? "Escopo acionado." : "Escopo liberado.");
  }

  return (
    <>
      <PageHead
        title="Interruptor de emergência"
        sub="Para a plataforma durante um incidente. A auditoria nunca é bloqueada, em nenhum escopo."
      />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <Panel title="Escopos">
              <p className="note">
                O acionamento leva até {data.propagation_seconds} segundos para valer em todos os
                processos. {data.note}
              </p>
              <table className="table">
                <thead><tr><th>Escopo</th><th>Efeito</th><th>Estado</th><th>Desde</th><th /></tr></thead>
                <tbody>
                  {data.scopes.map((s: any) => (
                    <tr key={s.scope}>
                      <td><strong>{s.scope}</strong><div className="small">{EFEITO_CURTO[s.scope]}</div></td>
                      <td className="small">{s.effect}</td>
                      <td>
                        {s.engaged ? <Pill tone="danger">acionado</Pill> : <Pill tone="ok">liberado</Pill>}
                        {s.engaged && s.reason && <div className="small">{s.reason}</div>}
                      </td>
                      <td>{s.since ? dateTime(s.since) : "—"}</td>
                      <td>
                        <Button
                          variant={s.engaged ? "ghost" : "danger"}
                          disabled={busy}
                          onClick={() => setEscopo(s.engaged ? `release:${s.scope}` : `engage:${s.scope}`)}
                        >
                          {s.engaged ? "Liberar" : "Acionar"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            {escopo && (
              <Panel title={escopo.startsWith("engage") ? "Confirmar acionamento" : "Confirmar liberação"}>
                <p className="note">
                  {escopo.startsWith("engage")
                    ? "Isto interrompe o trabalho de todas as organizações ao mesmo tempo. Descreva o motivo: é o que a investigação posterior vai ler."
                    : "Descreva por que o incidente está encerrado."}
                </p>
                <div className="form-grid">
                  <label style={{ flex: 1 }}>
                    Motivo (mínimo 10 caracteres)
                    <input className="input" value={motivo} onChange={(ev: React.ChangeEvent<HTMLInputElement>) => setMotivo(ev.target.value)} />
                  </label>
                  <Button
                    variant="danger"
                    disabled={busy || motivo.trim().length < 10}
                    onClick={() => acionar(escopo.split(":")[1], escopo.split(":")[0] as "engage" | "release")}
                  >
                    Confirmar
                  </Button>
                  <Button variant="ghost" onClick={() => { setEscopo(null); setMotivo(""); }}>Cancelar</Button>
                </div>
              </Panel>
            )}

            <Panel title="Rotas que o interruptor NUNCA bloqueia" quiet>
              <p className="note">
                Cada isenção tem motivo escrito. A auditoria continua funcionando durante o
                incidente porque é justamente nesse momento que registrar o que acontece é o que
                não se pode perder.
              </p>
              <table className="table">
                <thead><tr><th>Caminho</th><th>Motivo</th></tr></thead>
                <tbody>
                  {data.exempt.map((e: any) => (
                    <tr key={e.path}><td className="mono small">{e.path}</td><td className="small">{e.reason}</td></tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            <Panel title="Histórico de incidentes" quiet>
              {data.history.length === 0 ? (
                <p className="note">O interruptor nunca foi acionado nesta instalação.</p>
              ) : (
                <table className="table">
                  <thead><tr><th>Quando</th><th>Escopo</th><th>Ação</th><th>Motivo</th><th>Quem</th></tr></thead>
                  <tbody>
                    {data.history.map((h: any) => (
                      <tr key={h.id}>
                        <td>{dateTime(h.created_at)}</td>
                        <td>{h.scope}</td>
                        <td>{h.action === "engage" ? <Pill tone="danger">acionou</Pill> : <Pill tone="ok">liberou</Pill>}</td>
                        <td className="small">{h.reason}</td>
                        <td className="small">{h.actor_email || "sistema"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}
