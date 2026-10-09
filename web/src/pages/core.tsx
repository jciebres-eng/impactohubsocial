import { useState } from "react";
import { api } from "../api";
import { useSession } from "../session";
// Vocabulário oficial: o rótulo de banda sai de config/glossary.json (gerado em src/glossary.ts).
import { CONFIDENCE_BAND, term } from "../glossary";
import { date, dateTime } from "../format";
import { Link, navigate } from "../router";
import { Button, Field, Input, KeyValue, Modal, PageHead, Pager, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";
import { GlossaryTerm, ContextualHelp } from "../ui/help";
// A Trilha é o elemento de identidade da plataforma e, até a v0.21.0, aparecia num lugar só.
import { ASSEMBLY_TRAIL, PROJECT_PHASE_TRAIL, Trail } from "../ui/trail";

// Esta tela é FUNCIONAL: usa o mesmo kit e os mesmos tokens do restante do app. A camada de design vem depois,
// com a designer — aqui o objetivo é que tudo que o backend faz tenha caminho de uso e nada fique escondido.

const STAGE: [string, string][] = [["raw", "Anotada"], ["shaping", "Em amadurecimento"], ["ready", "Pronta para virar projeto"],
  ["archived", "Arquivada"]];
const STAGE_LABEL: Record<string, string> = { raw: "Anotada", shaping: "Em amadurecimento", ready: "Pronta", promoted: "Virou projeto", archived: "Arquivada" };
const RISK_CATEGORY: [string, string][] = [["financial", "Financeiro"], ["operational", "Operacional"], ["legal", "Jurídico"],
  ["documentary", "Documental"], ["eligibility", "Elegibilidade"], ["reputational", "Reputacional"], ["technical", "Técnico"],
  ["partnership", "Parceria"], ["timeline", "Prazo"], ["other", "Outro"]];
const LEVEL: [string, string][] = [["low", "Baixa"], ["medium", "Média"], ["high", "Alta"]];
const RISK_STATUS: [string, string][] = [["open", "Aberto"], ["mitigating", "Em mitigação"], ["accepted", "Aceito"],
  ["resolved", "Resolvido"], ["materialized", "Materializou"], ["dismissed", "Descartado"]];
const SEVERITY_TONE: Record<string, string> = { critical: "bad", high: "bad", medium: "warn", low: "good" };
const ASM_STATUS: Record<string, string> = { drafting: "Em preenchimento", ready: "Pronta para gerar", blocked: "Bloqueada",
  generated: "Documento gerado", in_review: "Em revisão", approved: "Aprovada", rejected: "Recusada na revisão",
  signed: "Assinada", archived: "Arquivada" };
const ASM_TONE: Record<string, string> = { blocked: "bad", rejected: "bad", drafting: "warn", in_review: "warn",
  ready: "good", generated: "good", approved: "good", signed: "good" };
const FEEDBACK: [string, string][] = [["accepted", "Faz sentido para nós"], ["contacted", "Vamos conversar"],
  ["converted", "Virou apoio"], ["not_relevant", "Não é do nosso foco"], ["rejected", "Avaliamos e não seguimos"],
  ["ignored", "Deixei de lado"], ["expired", "Perdemos o prazo"]];

const EMPTY_IDEA = { title: "", problem: "", hypothesis: "", audience: "", territory: "", solution_idea: "",
  expected_impact: "", stage: "raw" };

// Campo opcional em branco vale NULO, não string vazia: o servidor valida formato (território, por exemplo) e
// recusaria "" com um erro de padrão que não diz nada para quem só deixou o campo em branco.
function clean<T extends Record<string, any>>(v: T): T {
  const out: Record<string, any> = {};
  for (const [k, x] of Object.entries(v)) out[k] = typeof x === "string" && x.trim() === "" ? null : x;
  return out as T;
}

// ============================================================ ideias
export function Ideas() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/ideas?limit=25&offset=${offset}`, [offset]);
  const [open, setOpen] = useState(false);
  const f = useForm<any>(EMPTY_IDEA);
  const { busy, run } = useAction();

  async function create() {
    await run(async () => {
      const out = await api.post("/v1/ideas", { ...clean(f.v), ods: [], causes: [] });
      setOpen(false); f.setV(EMPTY_IDEA); reload();
      return `Ideia anotada (${out.id.slice(0, 8)}).`;
    });
  }

  return (
    <>
      <PageHead title="Ideias" sub="Anote antes de estruturar. A ideia não consome cota de projeto e nunca é apagada quando vira projeto."
                actions={<Button variant="primary" onClick={() => setOpen(true)}>Anotar ideia</Button>} />
      <StateView loading={loading} error={error} empty={data && !data.items.length ? "Nenhuma ideia anotada ainda." : undefined} onRetry={reload}>
        {data?.items.map((i: any) => (
          <Panel key={i.id} title={i.title} actions={<Pill tone={i.stage === "promoted" ? "good" : undefined}>{STAGE_LABEL[i.stage] || i.stage}</Pill>}>
            {i.problem && <p>{i.problem}</p>}
            <KeyValue items={[
              ["Hipótese", i.hypothesis || "—"],
              ["Público", i.audience || "—"],
              ["Território", i.territory || "—"],
              ["Anotada em", date(i.created_at)],
              ...(i.promoted_project_id ? [["Virou o projeto", <Link key="p" to={`/projetos/${i.promoted_project_id}`}>abrir projeto</Link>] as [string, any]] : []),
            ]} />
            {i.stage !== "promoted" && <IdeaActions idea={i} onDone={reload} />}
          </Panel>
        ))}
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={open} title="Anotar ideia" onClose={() => setOpen(false)}
             footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button>
                       <Button variant="primary" busy={busy} onClick={create} disabled={f.v.title.trim().length < 3}>Anotar</Button></>}>
        <Field label="Título"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Problema" hint="O que está acontecendo, e com quem."><TextArea value={f.v.problem} onChange={f.set("problem")} rows={3} /></Field>
        <Field label="Hipótese" hint="O que você acredita que resolve."><TextArea value={f.v.hypothesis} onChange={f.set("hypothesis")} rows={2} /></Field>
        <Field label="Público" hint="Descrição agregada. Não escreva dado pessoal de beneficiário aqui.">
          <Input value={f.v.audience} onChange={f.set("audience")} /></Field>
        <Field label="Território" hint="Formato BR-UF ou BR-UF-0000000 (código IBGE)."><Input value={f.v.territory} onChange={f.set("territory")} /></Field>
        <Field label="Estágio"><Select value={f.v.stage} onChange={f.set("stage")} options={STAGE} /></Field>
      </Modal>
    </>
  );
}

function IdeaActions({ idea, onDone }: { idea: any; onDone: () => void }) {
  const { busy, run } = useAction();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(idea.title);
  async function promote() {
    await run(async () => {
      const out = await api.post(`/v1/ideas/${idea.id}/promote`, { title });
      setOpen(false); onDone(); navigate(`/projetos/${out.id}`);
      return "A ideia virou projeto e continua registrada.";
    });
  }
  return (
    <>
      <div className="row-actions">
        <Button variant="primary" onClick={() => setOpen(true)}>Transformar em projeto</Button>
        <Button busy={busy} onClick={() => run(async () => { await api.put(`/v1/ideas/${idea.id}`, clean({ title: idea.title, problem: idea.problem,
        hypothesis: idea.hypothesis, audience: idea.audience, territory: idea.territory,
        solution_idea: idea.solution_idea, expected_impact: idea.expected_impact, stage: "archived",
        ods: idea.ods || [], causes: idea.causes || [] })); onDone(); return "Ideia arquivada."; })}>Arquivar</Button>
      </div>
      <Modal open={open} title="Transformar ideia em projeto" onClose={() => setOpen(false)}
             footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button>
                       <Button variant="primary" busy={busy} onClick={promote}>Criar projeto</Button></>}>
        <p className="muted small">A ideia continua registrada e passa a apontar para o projeto criado. O projeto guarda a
          origem: quem olhar o projeto depois vai saber de onde ele veio.</p>
        <Field label="Título do projeto"><Input value={title} onChange={setTitle} /></Field>
      </Modal>
    </>
  );
}

// ============================================================ ciclo de vida do projeto
export function Lifecycle({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/lifecycle`, [id]);
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();
  const rule = data?.allowed?.find((a: any) => a.to_status === to);

  async function move() {
    await run(async () => {
      const out = await api.post(`/v1/projects/${id}/transitions`, { to_status: to, reason: reason || null });
      setTo(""); setReason(""); reload();
      return out.changed ? `Situação alterada para ${out.label}.` : "O projeto já estava nesta situação.";
    });
  }

  return (
    <>
      <PageHead title="Situação do projeto" back={<Link to={`/projetos/${id}`}>Voltar ao projeto</Link>}
                sub="A máquina de situações é regra do banco: o que não está no grafo é recusado, com a lista do que é possível." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {/* A fase vem do servidor (`core/lifecycle.py::phase()`); a trilha só a desenha. Antes a
                fase era uma palavra solta ao lado da situação, e as 17 situações do projeto não
                tinham mapa nenhum em tela. */}
            <Trail steps={PROJECT_PHASE_TRAIL} current={data.phase}
                   ended={["cancelled", "rejected", "archived"].includes(data.status) ? data.status : undefined} />
            <Panel title="Agora">
              <KeyValue items={[["Situação", <Pill key="s" status={data.status}>{data.label}</Pill>], ["Fase", data.phase]]} />
            </Panel>
            <Panel title="Mudar de situação">
              {!data.allowed.length ? <p className="muted">Não há transição possível a partir desta situação.</p> : (
                <>
                  <Field label="Nova situação">
                    <Select value={to} onChange={setTo} placeholder="Escolha" options={data.allowed.map((a: any) => [a.to_status, (data.labels?.[a.to_status] || a.to_status) + (a.requires_reason ? " (exige motivo)" : "")])} />
                  </Field>
                  {rule?.note && <p className="muted small">{rule.note}</p>}
                  {rule?.requires_reason && (
                    <Field label="Motivo" hint="Fica registrado na transição e na linha de tempo.">
                      <TextArea value={reason} onChange={setReason} rows={2} />
                    </Field>
                  )}
                  <Button variant="primary" busy={busy} onClick={move}
                          disabled={!to || (rule?.requires_reason && reason.trim().length < 3)}>Registrar mudança</Button>
                </>
              )}
            </Panel>
            <Panel title="O que já aconteceu">
              {!data.history.length ? <p className="muted">Nenhuma mudança registrada.</p> : (
                <ul className="timeline">
                  {data.history.map((h: any) => (
                    <li key={h.id}>
                      <strong>{h.from_label} → {h.to_label}</strong>
                      <span className="muted small"> · {dateTime(h.at)}{h.actor_name ? ` · ${h.actor_name}` : ""}{h.automatic ? " · automático" : ""}</span>
                      {h.reason && <p className="small">{h.reason}</p>}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <p className="muted small">
              <Link to={`/projetos/${id}/linha-do-tempo`}>Linha de tempo completa</Link> ·{" "}
              <Link to={`/projetos/${id}/retratos`}>Retratos do projeto</Link> ·{" "}
              <Link to={`/projetos/${id}/riscos`}>Riscos</Link>
            </p>
          </>
        )}
      </StateView>
    </>
  );
}

// ============================================================ linha de tempo
export function Timeline({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/timeline?limit=50&offset=${offset}`, [id, offset]);
  const integrity = useLoad<any>(`/v1/projects/${id}/timeline/integrity`, [id]);

  return (
    <>
      <PageHead title="Linha de tempo" back={<Link to={`/projetos/${id}`}>Voltar ao projeto</Link>}
                sub="Cada entrada guarda o hash da anterior. Nada é editado nem removido: correção entra como fato novo." />
      {integrity.data && (
        <Panel title="Integridade" quiet>
          <KeyValue items={[
            ["Entradas", String(integrity.data.entries ?? 0)],
            ["Encadeamento", <Pill key="v" tone={integrity.data.valid ? "good" : "bad"}>{integrity.data.valid ? "íntegro" : "quebrado"}</Pill>],
            ...(integrity.data.first_broken_seq ? [["Primeira quebra", `#${integrity.data.first_broken_seq}`] as [string, any]] : []),
          ]} />
        </Panel>
      )}
      <StateView loading={loading} error={error} empty={data && !data.items.length ? "Nada registrado ainda." : undefined} onRetry={reload}>
        <Panel title="Fatos registrados">
          <ul className="timeline">
            {data?.items.map((e: any) => (
              <li key={e.seq}>
                <strong>{e.label}</strong>
                <span className="muted small"> · {dateTime(e.at)}{e.actor_name ? ` · ${e.actor_name}` : ""} · #{e.seq}</span>
                {e.payload && Object.keys(e.payload).length > 0 && (
                  <p className="small muted">{Object.entries(e.payload).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && !v.length))
                    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`).join(" · ")}</p>
                )}
              </li>
            ))}
          </ul>
          {data?.note && <p className="muted small">{data.note}</p>}
        </Panel>
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
    </>
  );
}

// ============================================================ retratos comparáveis
export function Snapshots({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/snapshots?limit=50`, [id]);
  const [label, setLabel] = useState("");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [diff, setDiff] = useState<any>(null);
  const { busy, run } = useAction();

  async function take() {
    await run(async () => { await api.post(`/v1/projects/${id}/snapshots`, { label }); setLabel(""); reload(); return "Retrato guardado."; });
  }
  async function compare() {
    await run(async () => { setDiff(await api.get(`/v1/projects/${id}/snapshots/compare?a=${a}&b=${b}`)); return "Comparação pronta."; });
  }
  const options = (data?.items || []).map((s: any) => [s.id, `${s.label} · ${date(s.taken_at)}`] as [string, string]);

  return (
    <>
      <PageHead title="Retratos do projeto" back={<Link to={`/projetos/${id}`}>Voltar ao projeto</Link>}
                sub="Um retrato congela metas, orçamento, marcos, indicadores, riscos e documentos daquele instante, com hash do estado." />
      <Panel title="Guardar um retrato agora">
        <Field label="Como chamar este retrato" hint="Ex.: linha de base, antes da submissão, fim do 1º semestre.">
          <Input value={label} onChange={setLabel} />
        </Field>
        <Button variant="primary" busy={busy} onClick={take} disabled={label.trim().length < 2}>Guardar retrato</Button>
      </Panel>
      <StateView loading={loading} error={error} empty={data && !data.items.length ? "Nenhum retrato guardado." : undefined} onRetry={reload}>
        {options.length >= 2 && (
          <Panel title="Comparar dois retratos">
            <Field label="De"><Select value={a} onChange={setA} placeholder="Escolha" options={options} /></Field>
            <Field label="Para"><Select value={b} onChange={setB} placeholder="Escolha" options={options} /></Field>
            <Button busy={busy} onClick={compare} disabled={!a || !b || a === b}>Comparar</Button>
            {diff && (
              <div className="diff">
                <KeyValue items={[["De", `${diff.from?.label} · ${dateTime(diff.from?.taken_at)}`],
                                  ["Para", `${diff.to?.label} · ${dateTime(diff.to?.taken_at)}`]]} />
                {!diff.changed?.length && !diff.added?.length && !diff.removed?.length && <p className="muted">Nada mudou entre os dois retratos.</p>}
                {!!diff.changed?.length && (<><h3>Mudou</h3><ul>{diff.changed.map((c: any) => (
                  <li key={c.field}><strong>{c.field}</strong>: {String(c.from)} → {String(c.to)}</li>))}</ul></>)}
                {!!diff.added?.length && (<><h3>Entrou</h3><ul>{diff.added.map((c: any) => (
                  <li key={c.field}><strong>{c.field}</strong>: {String(c.to)}</li>))}</ul></>)}
                {!!diff.removed?.length && (<><h3>Saiu</h3><ul>{diff.removed.map((c: any) => (
                  <li key={c.field}><strong>{c.field}</strong>: {String(c.from)}</li>))}</ul></>)}
              </div>
            )}
          </Panel>
        )}
        <Panel title="Retratos guardados">
          <ul className="timeline">
            {data?.items.map((s: any) => (
              <li key={s.id}>
                <strong>{s.label}</strong>
                <span className="muted small"> · {dateTime(s.taken_at)}{s.taken_by_name ? ` · ${s.taken_by_name}` : ""}</span>
                <p className="small muted">hash do estado {s.state_sha256.slice(0, 16)}…</p>
              </li>
            ))}
          </ul>
        </Panel>
      </StateView>
    </>
  );
}

// ============================================================ riscos
const EMPTY_RISK = { category: "operational", title: "", description: "", probability: "medium", impact: "medium", mitigation: "" };

export function Risks({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/risks?limit=100`, [id]);
  const rules = useLoad<any>("/v1/risk-rules");
  const [open, setOpen] = useState(false);
  const f = useForm<any>(EMPTY_RISK);
  const { busy, run } = useAction();

  async function create() {
    await run(async () => { await api.post(`/v1/projects/${id}/risks`, f.v); setOpen(false); f.setV(EMPTY_RISK); reload(); return "Risco registrado."; });
  }
  async function scan() {
    await run(async () => {
      const out = await api.post(`/v1/projects/${id}/risks/scan`);
      reload();
      return `${out.identified.length} risco(s) apontado(s) pelas regras, ${out.auto_resolved.length} encerrado(s) por deixar de valer.`;
    });
  }

  return (
    <>
      <PageHead title="Riscos do projeto" back={<Link to={`/projetos/${id}`}>Voltar ao projeto</Link>}
                sub="Risco declarado pela equipe e risco apontado por regra ficam separados. Regra aponta indício; a avaliação é humana."
                actions={<><Button busy={busy} onClick={scan}>Aplicar as regras</Button>
                           <Button variant="primary" onClick={() => setOpen(true)}>Registrar risco</Button></>} />
      <StateView loading={loading} error={error} empty={data && !data.items.length ? "Nenhum risco registrado. Use “Aplicar as regras” para ver os indícios da plataforma." : undefined} onRetry={reload}>
        {data?.items.map((r: any) => <RiskCard key={r.id} projectId={id} risk={r} onDone={reload} />)}
      </StateView>
      {rules.data && (
        <Panel title={`Regras aplicadas (${rules.data.version})`} quiet>
          <ul>{rules.data.rules.map((r: any) => (
            <li key={r.code}><strong>{r.title}</strong> <Pill tone={SEVERITY_TONE[r.severity]}>{r.severity}</Pill></li>))}</ul>
          <p className="muted small">{rules.data.note}</p>
        </Panel>
      )}
      <Modal open={open} title="Registrar risco" onClose={() => setOpen(false)}
             footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button>
                       <Button variant="primary" busy={busy} onClick={create} disabled={f.v.title.trim().length < 3}>Registrar</Button></>}>
        <Field label="Categoria"><Select value={f.v.category} onChange={f.set("category")} options={RISK_CATEGORY} /></Field>
        <Field label="Risco"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Descrição"><TextArea value={f.v.description} onChange={f.set("description")} rows={3} /></Field>
        <Field label="Probabilidade"><Select value={f.v.probability} onChange={f.set("probability")} options={LEVEL} /></Field>
        <Field label="Impacto"><Select value={f.v.impact} onChange={f.set("impact")} options={LEVEL} /></Field>
        <Field label="Mitigação" hint="O que será feito para reduzir probabilidade ou impacto.">
          <TextArea value={f.v.mitigation} onChange={f.set("mitigation")} rows={2} /></Field>
      </Modal>
    </>
  );
}

function RiskCard({ projectId, risk, onDone }: { projectId: string; risk: any; onDone: () => void }) {
  const [status, setStatus] = useState(risk.status);
  const [note, setNote] = useState("");
  const { busy, run } = useAction();
  const closing = status === "resolved" || status === "dismissed";

  async function save() {
    await run(async () => {
      await api.put(`/v1/projects/${projectId}/risks/${risk.id}`, { status, ...(closing ? { resolution_note: note } : {}) });
      onDone();
      return "Risco atualizado.";
    });
  }
  return (
    <Panel title={risk.title} actions={<Pill tone={SEVERITY_TONE[risk.severity]}>{risk.severity}</Pill>}>
      {risk.description && <p>{risk.description}</p>}
      <KeyValue items={[
        ["Origem", risk.origin === "system_identified" ? "apontado por regra da plataforma" : "declarado pela equipe"],
        ["Probabilidade × impacto", `${risk.probability} × ${risk.impact}`],
        ["Situação", <Pill key="s" status={risk.status}>{risk.status}</Pill>],
        ["Mitigação", risk.mitigation || "—"],
        ...(risk.resolution_note ? [["Encerramento", risk.resolution_note] as [string, any]] : []),
      ]} />
      {risk.status !== "resolved" && risk.status !== "dismissed" && (
        <>
          <Field label="Mudar situação"><Select value={status} onChange={setStatus} options={RISK_STATUS} /></Field>
          {closing && (
            <Field label="Motivo do encerramento" hint="Obrigatório: encerrar risco sem explicação não é registro.">
              <TextArea value={note} onChange={setNote} rows={2} />
            </Field>
          )}
          <Button busy={busy} onClick={save} disabled={status === risk.status || (closing && note.trim().length < 3)}>Salvar</Button>
        </>
      )}
    </Panel>
  );
}

// ============================================================ prontidão e versões do diagnóstico
export function Readiness() {
  const { data, error, loading, reload } = useLoad<any>("/v1/readiness");
  return (
    <>
      <PageHead title={<>Prontidão da organização <ContextualHelp id="diagnostico_prontidao" /></>}
                sub="Separa o que é FATO (evidência com fonte e data), o que é INFERÊNCIA de regra e o que é RECOMENDAÇÃO." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && <AnalysisView a={data} />}
      </StateView>
    </>
  );
}

export function AnalysisView({ a }: { a: any }) {
  return (
    <>
      <Panel title="Leitura da plataforma">
        <KeyValue items={[
          ["Completude", `${a.current_state.completeness}%`],
          ["Confiança", `${a.confidence}% — ${term(CONFIDENCE_BAND, a.confidence_band)}`],
          ["Evidências conhecidas", `${a.evidence_summary.known} de ${a.evidence_summary.total} · ${a.evidence_summary.verified} verificada(s)`],
          ["Motor", a.engine_version],
        ]} />
        <p className="muted small">{a.disclaimer}</p>
      </Panel>
      <Panel title="Por dimensão">
        <ul>{a.current_state.by_dimension.map((d: any) => (
          <li key={d.dimension}><strong>{d.label}</strong>: {d.percent}% ({d.closed}/{d.total})</li>))}</ul>
      </Panel>
      {!!a.strengths.length && (
        <Panel title="Forças (evidência verificada)">
          <ul>{a.strengths.map((s: any) => <li key={s.key}>{s.title}</li>)}</ul>
        </Panel>
      )}
      <Panel title={`Lacunas (${a.gaps.length})`}>
        {!a.gaps.length ? <p className="muted">Nenhuma lacuna aberta.</p> : (
          <ul>{a.gaps.map((g: any) => (
            <li key={g.code}><strong>{g.title}</strong> <Pill tone={SEVERITY_TONE[g.severity]}>{g.severity}</Pill>
              <p className="small muted">Fecha com: {g.evidence_hint}</p></li>))}</ul>
        )}
      </Panel>
      {!!a.unknown.length && (
        <Panel title={`Desconhecido (${a.unknown.length})`} quiet>
          <p className="muted small">A plataforma não tem dado para avaliar estes pontos. Desconhecido não é “ruim”: é desconhecido.</p>
          <ul>{a.unknown.map((u: any) => <li key={u.code}>{u.title}</li>)}</ul>
        </Panel>
      )}
      {!!a.stale_evidence.length && (
        <Panel title="Evidência envelhecendo" quiet>
          <ul>{a.stale_evidence.map((s: any) => (
            <li key={s.key}>{s.key} · {s.freshness_detail}</li>))}</ul>
        </Panel>
      )}
      {!!a.recommended_actions.length && (
        <Panel title="O que fazer em seguida">
          <ol>{a.recommended_actions.map((r: any) => (
            <li key={r.gap_code}><strong>{r.title}</strong> <Pill tone={SEVERITY_TONE[r.priority]}>{r.priority}</Pill>
              <p className="small muted">{r.detail}</p></li>))}</ol>
        </Panel>
      )}
    </>
  );
}

export function DiagnosisVersions({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/diagnoses/${id}/versions`, [id]);
  const actions = useLoad<any>(`/v1/diagnoses/${id}/actions?limit=100`, [id]);
  const preview = useLoad<any>(`/v1/diagnoses/${id}/analysis`, [id]);
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [diff, setDiff] = useState<any>(null);
  const { busy, run } = useAction();

  async function publish() {
    await run(async () => {
      const out = await api.post(`/v1/diagnoses/${id}/versions`);
      reload(); actions.reload(); preview.reload();
      return out.created ? `Versão ${out.version} congelada.` : `Nada mudou desde a versão ${out.version}.`;
    });
  }
  async function compare() {
    await run(async () => { setDiff(await api.get(`/v1/diagnoses/${id}/versions/compare?a=${a}&b=${b}`)); return "Comparação pronta."; });
  }
  const options = (data?.items || []).map((v: any) => [String(v.version), `v${v.version} · ${date(v.created_at)}`] as [string, string]);

  return (
    <>
      <PageHead title="Versões do diagnóstico" back={<Link to={`/diagnosticos/${id}`}>Voltar ao diagnóstico</Link>}
                sub="Cada versão é um retrato imutável. A anterior nunca é alterada: o que mudou é calculado pelo servidor."
                actions={<Button variant="primary" busy={busy} onClick={publish}>Congelar versão agora</Button>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {options.length >= 2 && (
          <Panel title="Comparar versões">
            <Field label="De"><Select value={a} onChange={setA} placeholder="Escolha" options={options} /></Field>
            <Field label="Para"><Select value={b} onChange={setB} placeholder="Escolha" options={options} /></Field>
            <Button busy={busy} onClick={compare} disabled={!a || !b || a === b}>Comparar</Button>
            {diff?.what_changed && <ChangeList changes={diff.what_changed} />}
          </Panel>
        )}
        <Panel title="Versões congeladas">
          {!data?.items.length ? <p className="muted">Nenhuma versão congelada ainda.</p> : (
            <ul className="timeline">
              {data.items.map((v: any) => (
                <li key={v.id}>
                  <strong>v{v.version}</strong>
                  <span className="muted small"> · {dateTime(v.created_at)}{v.created_by_name ? ` · ${v.created_by_name}` : ""} · completude {v.completeness}% · confiança {v.confidence}%</span>
                  <ChangeList changes={v.changes} compact />
                </li>
              ))}
            </ul>
          )}
          {data?.note && <p className="muted small">{data.note}</p>}
        </Panel>
      </StateView>
      <StateView loading={actions.loading} error={actions.error}>
        <Panel title={`Ações (${actions.data?.items.length || 0})`}>
          {!actions.data?.items.length ? <p className="muted">Nenhuma ação. Congele uma versão para gerar as ações das lacunas.</p> : (
            actions.data.items.map((ac: any) => <ActionRow key={ac.id} diagnosisId={id} action={ac} onDone={() => { actions.reload(); }} />)
          )}
        </Panel>
      </StateView>
      {preview.data && (
        <Panel title="Leitura atual (prévia, ainda não congelada)" quiet>
          <AnalysisView a={preview.data} />
        </Panel>
      )}
    </>
  );
}

function ChangeList({ changes, compact }: { changes: any; compact?: boolean }) {
  if (!changes) return null;
  const rows: [string, any][] = [];
  if (changes.first_version) rows.push(["Primeira versão", "sim"]);
  if (changes.closed_gaps?.length) rows.push(["Lacunas fechadas", changes.closed_gaps.join(", ")]);
  if (changes.new_gaps?.length) rows.push(["Lacunas novas", changes.new_gaps.join(", ")]);
  if (changes.new_strengths?.length) rows.push(["Forças novas", changes.new_strengths.join(", ")]);
  if (changes.lost_strengths?.length) rows.push(["Forças perdidas", changes.lost_strengths.join(", ")]);
  if (changes.completeness_delta) rows.push(["Completude", `${changes.completeness_delta > 0 ? "+" : ""}${changes.completeness_delta} p.p.`]);
  if (changes.confidence_delta) rows.push(["Confiança", `${changes.confidence_delta > 0 ? "+" : ""}${changes.confidence_delta} p.p.`]);
  if (!rows.length) return compact ? null : <p className="muted small">Nada mudou.</p>;
  return compact
    ? <p className="small muted">{rows.map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
    : <KeyValue items={rows} />;
}

function ActionRow({ diagnosisId, action, onDone }: { diagnosisId: string; action: any; onDone: () => void }) {
  const [status, setStatus] = useState(action.status);
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();
  async function save() {
    await run(async () => {
      await api.put(`/v1/diagnoses/${diagnosisId}/actions/${action.id}`,
                    { status, ...(status === "dismissed" ? { dismissed_reason: reason } : {}) });
      onDone();
      return "Ação atualizada.";
    });
  }
  return (
    <div className="list-row">
      <div>
        <strong>{action.title}</strong> <Pill tone={SEVERITY_TONE[action.priority]}>{action.priority}</Pill>{" "}
        <Pill status={action.status}>{action.status}</Pill>
        {action.evidence_hint && <p className="small muted">Fecha com: {action.evidence_hint}</p>}
        <p className="small muted">{action.origin === "system_identified" ? "criada a partir de uma lacuna apontada por regra" : "criada pela equipe"}</p>
      </div>
      {action.status !== "done" && action.status !== "dismissed" && (
        <div>
          <Select aria-label="Situação da ação" value={status} onChange={setStatus} options={[["open", "Aberta"], ["in_progress", "Em andamento"], ["done", "Concluída"], ["dismissed", "Descartada"]]} />
          {status === "dismissed" && <Input value={reason} onChange={setReason} placeholder="Motivo do descarte" />}
          <Button busy={busy} onClick={save} disabled={status === action.status || (status === "dismissed" && reason.trim().length < 3)}>Salvar</Button>
        </div>
      )}
    </div>
  );
}

// ============================================================ montagem de documento
export function Assemblies() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useLoad<any>(`/v1/document-assemblies?limit=25&offset=${offset}`, [offset]);
  const templates = useLoad<any>("/v1/document-templates?status=published&limit=100");
  const { me: sessao } = useSession();
  // v0.25.0: projetos são da OSC. Os outros perfis recebiam 403 nesta chamada escondida (o robô de
  // telas viu); a lista só é pedida a quem pode tê-la.
  const projects = useLoad<any>(sessao?.active_org?.kind === "osc" ? "/v1/projects?limit=100" : null);
  const [open, setOpen] = useState(false);
  const f = useForm<any>({ template_id: "", title: "", project_id: "" });
  const { busy, run } = useAction();

  async function create() {
    await run(async () => {
      const out = await api.post("/v1/document-assemblies", {
        template_id: f.v.template_id, title: f.v.title, project_id: f.v.project_id || null });
      setOpen(false); f.setV({ template_id: "", title: "", project_id: "" }); reload();
      navigate(`/documentos/montagens/${out.id}`);
      return "Montagem aberta.";
    });
  }

  return (
    <>
      <PageHead title="Montagem de documentos"
                sub="O modelo diz o que o documento precisa ter. Enquanto faltar campo obrigatório ou evidência, a plataforma recusa gerar."
                actions={<Button variant="primary" onClick={() => setOpen(true)}>Nova montagem</Button>} />
      <StateView loading={loading} error={error} empty={data && !data.items.length ? "Nenhuma montagem aberta." : undefined} onRetry={reload}>
        {data?.items.map((a: any) => (
          <Panel key={a.id} title={<Link to={`/documentos/montagens/${a.id}`}>{a.title}</Link>}
                 actions={<Pill tone={ASM_TONE[a.status]}>{ASM_STATUS[a.status] || a.status}</Pill>}>
            <KeyValue items={[
              ["Modelo", `${a.template_code} v${a.template_version}`],
              ["Completude", `${a.completeness}%`],
              ...(a.blocked_reason ? [["Impede gerar", a.blocked_reason] as [string, any]] : []),
              ...(a.generated_document_id ? [["Documento", <Link key="d" to="/documentos">no cofre ({a.generated_format})</Link>] as [string, any]] : []),
              ["Atualizada", dateTime(a.updated_at)],
            ]} />
          </Panel>
        ))}
        <Pager data={data} offset={offset} setOffset={setOffset} />
      </StateView>
      <Modal open={open} title="Nova montagem" onClose={() => setOpen(false)}
             footer={<><Button onClick={() => setOpen(false)}>Cancelar</Button>
                       <Button variant="primary" busy={busy} onClick={create} disabled={!f.v.template_id || f.v.title.trim().length < 3}>Abrir montagem</Button></>}>
        <Field label="Modelo" hint="Só modelo publicado pode ser usado. Modelo publicado não muda mais.">
          <Select value={f.v.template_id} onChange={f.set("template_id")} placeholder="Escolha o modelo"
                  options={(templates.data?.items || []).map((t: any) => [t.id, `${t.title} (v${t.version})`])} />
        </Field>
        <Field label="Título do documento"><Input value={f.v.title} onChange={f.set("title")} /></Field>
        <Field label="Projeto" hint="O modelo puxa do projeto os campos derivados (título, orçamento, prazo).">
          <Select value={f.v.project_id} onChange={f.set("project_id")} placeholder="Sem projeto"
                  options={(projects.data?.items || []).map((p: any) => [p.id, p.title])} />
        </Field>
      </Modal>
    </>
  );
}

export function AssemblyDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/document-assemblies/${id}`, [id]);
  const docs = useLoad<any>("/v1/documents?limit=100");
  const [values, setValues] = useState<Record<string, any> | null>(null);
  const [evidence, setEvidence] = useState<Record<string, string> | null>(null);
  const [fmt, setFmt] = useState("pdf");
  const [reviewNote, setReviewNote] = useState("");
  const { busy, run } = useAction();
  const tpl = data?.template;
  const ev = data?.evaluation;
  const v = values ?? (data?.values || {});
  const e = evidence ?? (data?.evidence || {});
  const editable = data && ["drafting", "ready", "blocked", "rejected"].includes(data.status);

  async function save() {
    await run(async () => {
      await api.put(`/v1/document-assemblies/${id}`, { values: v, evidence: e });
      setValues(null); setEvidence(null); reload();
      return "Montagem salva. A completude é recalculada pelo servidor.";
    });
  }
  async function generate() {
    await run(async () => {
      const out = await api.post(`/v1/document-assemblies/${id}/generate`, { format: fmt });
      reload();
      return `Documento gerado (${out.format}) e guardado no cofre.`;
    });
  }
  async function review(approve: boolean) {
    await run(async () => {
      await api.post(`/v1/document-assemblies/${id}/review`, { approve, note: reviewNote });
      setReviewNote(""); reload();
      return approve ? "Montagem aprovada." : "Montagem recusada com a observação registrada.";
    });
  }

  return (
    <>
      <PageHead title={data?.title || "Montagem"} back={<Link to="/documentos/montagens">Voltar às montagens</Link>}
                sub={tpl ? `${tpl.title} · v${tpl.version}` : undefined}
                actions={data && <Pill tone={ASM_TONE[data.status]}>{ASM_STATUS[data.status] || data.status}</Pill>} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && ev && (
          <>
            {/* O fluxo MODELO → MONTAGEM → COMPLETUDE → GERAÇÃO → REVISÃO → ASSINATURA existia só
                como desenho ASCII em DOCUMENT_ASSEMBLY.md §1. A tela mostrava um selo de situação e
                não dizia em que ponto do caminho a montagem estava. */}
            <Trail steps={ASSEMBLY_TRAIL} current={data.status}
                   ended={["blocked", "rejected"].includes(data.status) ? data.status : undefined} />
            <Panel title="Situação da montagem">
              <KeyValue items={[
                ["Completude", `${ev.completeness}% (${ev.filled} de ${ev.total} campos)`],
                ["Pode gerar", ev.can_generate ? "sim" : "não"],
                ...(data.generated_sha256 ? [["Hash do arquivo gerado", data.generated_sha256.slice(0, 16) + "…"] as [string, any]] : []),
                ...(data.reviewed_by_name ? [["Revisado por", data.reviewed_by_name] as [string, any]] : []),
                ...(data.review_note ? [["Observação da revisão", data.review_note] as [string, any]] : []),
              ]} />
              {!!ev.blockers?.length && (
                <div className="banner" role="status">
                  <strong>O que impede gerar:</strong>
                  <ul>{ev.blockers.map((b: string) => <li key={b}>{b}</li>)}</ul>
                </div>
              )}
              {!!ev.missing?.length && (
                <>
                  <h3>Falta preencher</h3>
                  <ul>{ev.missing.map((m: any) => (
                    <li key={m.kind + m.key}>{m.label} <span className="muted small">({m.section}{m.derived_from ? ` · vem do projeto: ${m.derived_from}` : ""})</span></li>))}</ul>
                </>
              )}
              {tpl?.source_note && <p className="muted small"><strong>Fonte do modelo:</strong> {tpl.source_note}</p>}
            </Panel>

            {editable && tpl?.sections.map((section: string) => (
              <Panel key={section} title={section}>
                {tpl.fields.filter((fl: any) => fl.section === section).map((fl: any) => (
                  <div key={fl.id}>
                    {fl.derived_from ? (
                      <Field label={`${fl.label}${fl.required ? " *" : ""}`} hint={`Vem do projeto (${fl.derived_from}) — edite no projeto, não aqui.`}>
                        <Input value={String(ev.derived?.[fl.key] ?? "")} onChange={() => {}} disabled />
                      </Field>
                    ) : fl.field_type === "textarea" || fl.field_type === "table" || fl.field_type === "list" ? (
                      <Field label={`${fl.label}${fl.required ? " *" : ""}`} hint={fl.help}>
                        <TextArea value={v[fl.key] ?? ""} rows={3} onChange={(val: string) => setValues({ ...v, [fl.key]: val })} />
                      </Field>
                    ) : (
                      <Field label={`${fl.label}${fl.required ? " *" : ""}`} hint={fl.help}>
                        <Input value={v[fl.key] ?? ""} onChange={(val: string) => setValues({ ...v, [fl.key]: val })} />
                      </Field>
                    )}
                    {fl.requires_evidence && (
                      <Field label={`Evidência de “${fl.label}”`} hint="Documento do cofre que comprova o que foi afirmado.">
                        <Select value={e[fl.key] ?? ""} placeholder="Escolher documento"
                                onChange={(val: string) => setEvidence({ ...e, [fl.key]: val })}
                                options={(docs.data?.items || []).map((d: any) => [d.id, `${d.title} (${d.doc_type})`])} />
                      </Field>
                    )}
                  </div>
                ))}
              </Panel>
            ))}

            {editable && (
              <Panel title="Salvar e gerar">
                <Button variant="primary" busy={busy} onClick={save}>Salvar preenchimento</Button>
                <Field label="Formato do arquivo"><Select value={fmt} onChange={setFmt}
                        options={(tpl?.output_formats || ["pdf"]).map((x: string) => [x, x.toUpperCase()])} /></Field>
                <Button variant="primary" busy={busy} onClick={generate} disabled={!ev.can_generate}>Gerar documento</Button>
                {!ev.can_generate && <p className="muted small">A geração fica indisponível até as pendências acima serem resolvidas.</p>}
              </Panel>
            )}

            {(data.status === "generated" || data.status === "in_review") && (
              <Panel title="Revisão (quatro olhos)">
                <p className="muted small">Quem montou o documento não pode aprová-lo. Peça a revisão a outra pessoa da organização.</p>
                <Field label="Observação da revisão"><TextArea value={reviewNote} onChange={setReviewNote} rows={2} /></Field>
                <div className="row-actions">
                  <Button variant="primary" busy={busy} onClick={() => review(true)} disabled={reviewNote.trim().length < 3}>Aprovar</Button>
                  <Button busy={busy} onClick={() => review(false)} disabled={reviewNote.trim().length < 3}>Recusar</Button>
                </div>
              </Panel>
            )}
          </>
        )}
      </StateView>
    </>
  );
}

export function Templates() {
  const { data, error, loading, reload } = useLoad<any>("/v1/document-templates?limit=100");
  return (
    <>
      <PageHead title="Modelos de documento" back={<Link to="/documentos/montagens">Voltar às montagens</Link>}
                sub="Modelo publicado é imutável: corrigir exige nova versão. Cada modelo diz de onde a estrutura dele vem." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data?.items.map((t: any) => (
          <Panel key={t.id} title={`${t.title} · v${t.version}`} actions={<Pill status={t.status}>{t.status}</Pill>}>
            {t.description && <p>{t.description}</p>}
            <KeyValue items={[
              ["Código", t.code], ["Tipo", t.kind], ["Campos", String(t.fields)],
              ["Formatos", (t.output_formats || []).join(", ")],
              ["Origem", t.owner_org_id ? "da sua organização" : "da plataforma"],
              ["Fonte declarada", t.source_note || "—"],
            ]} />
          </Panel>
        ))}
        {data?.note && <p className="muted small">{data.note}</p>}
      </StateView>
    </>
  );
}

// ============================================================ retorno sobre a recomendação do match
export function MatchFeedbackBox({ matchRunId, onDone }: { matchRunId: string; onDone?: () => void }) {
  const current = useLoad<any>(`/v1/match-runs/${matchRunId}/feedback`, [matchRunId]);
  const [feedback, setFeedback] = useState("");
  const [reason, setReason] = useState("");
  const { busy, run } = useAction();

  async function send() {
    await run(async () => {
      const out = await api.post(`/v1/match-runs/${matchRunId}/feedback`, { feedback, reason: reason || null });
      current.reload(); onDone?.();
      return out.note;
    });
  }
  if (current.data?.feedback) {
    return <p className="muted small">Seu retorno sobre esta recomendação: <strong>{
      FEEDBACK.find(([k]) => k === current.data.feedback)?.[1] || current.data.feedback}</strong>
      {current.data.reason ? ` — ${current.data.reason}` : ""}. O histórico não é reescrito.</p>;
  }
  return (
    <Panel title="Este resultado foi útil?" quiet>
      <p className="muted small">O retorno fica registrado para calibração futura, revisada por pessoas. A plataforma
        não ajusta pesos sozinha, e o seu retorno não muda a nota deste resultado.</p>
      <Field label="O que você faria com esta recomendação">
        <Select value={feedback} onChange={setFeedback} placeholder="Escolha" options={FEEDBACK} />
      </Field>
      <Field label="Por quê (opcional)"><Input value={reason} onChange={setReason} /></Field>
      <Button busy={busy} onClick={send} disabled={!feedback}>Enviar retorno</Button>
    </Panel>
  );
}

// ============================================================ administração: chaves e provedores de assinatura
export function EncryptionKeys() {
  const { data, error, loading, reload } = useLoad<any>("/v1/admin/encryption/keys");
  const [table, setTable] = useState("");
  const { busy, run } = useAction();

  async function register(purpose: string) {
    await run(async () => { await api.post("/v1/admin/encryption/keys", { purpose }); reload(); return "Inventário atualizado."; });
  }
  async function reencrypt() {
    await run(async () => {
      const out = await api.post("/v1/admin/encryption/reencrypt", { table });
      reload();
      return `${out.rows_reencrypted} registro(s) recifrado(s), ${out.rows_failed} falha(s) — situação: ${out.status}.`;
    });
  }

  return (
    <>
      <PageHead title="Chaves de cifragem" sub="A chave NUNCA é gravada. O inventário guarda a impressão digital, que identifica a chave sem revelá-la." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <div className="banner" role="status">{data.kms}</div>
            <Panel title="Inventário" actions={<div className="row-actions">
              {data.purposes.map((p: string) => <Button key={p} busy={busy} onClick={() => register(p)}>Registrar “{p}”</Button>)}
            </div>}>
              {!data.keys.length ? <p className="muted">Nenhuma chave registrada. Use os botões acima para registrar as chaves em uso.</p> : (
                <ul>{data.keys.map((k: any) => (
                  <li key={k.purpose + k.version}>
                    <strong>{k.purpose} v{k.version}</strong> · impressão digital {k.fingerprint} ·{" "}
                    <Pill tone={k.state === "active" ? "good" : k.state === "retired" ? "bad" : "warn"}>{k.state}</Pill>
                    {k.note && <span className="muted small"> · {k.note}</span>}
                  </li>))}</ul>
              )}
              <p className="muted small">{data.note}</p>
            </Panel>
            <Panel title="Recifrar coluna">
              <p className="muted small">Relê e regrava a coluna cifrada com a chave corrente. Rodar duas vezes não causa dano.</p>
              <Field label="Tabela"><Select value={table} onChange={setTable} placeholder="Escolha"
                      options={(data.rotatable_tables || []).map((t: string) => [t, t])} /></Field>
              <Button variant="primary" busy={busy} onClick={reencrypt} disabled={!table}>Recifrar</Button>
            </Panel>
            <Panel title="Rotações registradas" quiet>
              {!data.rotations.length ? <p className="muted">Nenhuma rotação registrada.</p> : (
                <ul>{data.rotations.map((r: any) => (
                  <li key={r.id}>
                    {dateTime(r.started_at)} · {r.table_name} · {r.rows_reencrypted}/{r.rows_total} ·{" "}
                    <Pill tone={r.status === "completed" ? "good" : r.status === "failed" ? "bad" : "warn"}>{r.status}</Pill>
                    {r.detail && <span className="muted small"> · {r.detail}</span>}
                  </li>))}</ul>
              )}
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

export function SignatureProviders() {
  const { data, error, loading, reload } = useLoad<any>("/v1/signature-providers");
  return (
    <>
      <PageHead title="Provedores de assinatura" sub="O estado aqui é o estado REAL. O que depende de contratação diz isso, e o banco recusa assinar com provedor indisponível." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data?.items.map((p: any) => (
          <Panel key={p.key} title={p.name} actions={<Pill tone={p.state === "production" ? "good" : p.state === "unavailable" || p.state === "disabled" ? "bad" : "warn"}>{p.state}</Pill>}>
            <KeyValue items={[
              ["Nível jurídico", `${p.legal_level} — ${data.legal_levels[p.legal_level]}`],
              ["Nível criptográfico", `${p.crypto_level} — ${data.crypto_levels[p.crypto_level]}`],
              ["Identificação mínima", p.identity_level_required],
              ["Carimbo de tempo", p.supports_timestamp ? "sim" : "não"],
              ["Consulta de revogação", p.supports_revocation_check ? "sim" : "não"],
              ["Certificado", p.supports_certificate ? "sim" : "não"],
              ...(p.external_dependency ? [["Depende de", p.external_dependency] as [string, any]] : []),
              ...(p.activation_note ? [["Para ativar", p.activation_note] as [string, any]] : []),
              ["Saúde", `${p.health_state}${p.health_detail ? ` — ${p.health_detail}` : ""}`],
            ]} />
          </Panel>
        ))}
        {data?.note && <div className="banner" role="status">{data.note}</div>}
      </StateView>
    </>
  );
}

export function SignaturePolicies() {
  const { data, error, loading, reload } = useLoad<any>("/v1/signature-policies");
  const f = useForm<any>({ doc_kind: "", min_legal_level: "advanced", min_identity_level: "email", require_timestamp: false, note: "" });
  const { busy, run } = useAction();
  async function save() {
    await run(async () => { await api.put("/v1/signature-policies", f.v); reload(); return "Política definida."; });
  }
  return (
    <>
      <PageHead title="Política de assinatura" sub="Por tipo de documento: que nível jurídico e que identificação a organização exige de quem assina." />
      <StateView loading={loading} error={error} onRetry={reload}>
        <Panel title="Definir política">
          <Field label="Tipo de documento" hint="Ex.: relatorio, termo, contrato."><Input value={f.v.doc_kind} onChange={f.set("doc_kind")} /></Field>
          <Field label="Nível jurídico mínimo" hint="Exigir um nível que nenhum provedor entrega hoje é recusado: bloquearia toda assinatura.">
            <Select value={f.v.min_legal_level} onChange={f.set("min_legal_level")}
                    options={[["simple", "Simples"], ["advanced", "Avançada"], ["qualified", "Qualificada (ICP-Brasil)"]]} />
          </Field>
          <Field label="Identificação mínima">
            <Select value={f.v.min_identity_level} onChange={f.set("min_identity_level")}
                    options={[["none", "Nenhuma"], ["email", "E-mail"], ["phone", "Telefone"], ["document", "Documento"],
                              ["professional", "Credencial profissional"], ["biometric", "Biometria"]]} />
          </Field>
          <Field label="Observação"><Input value={f.v.note} onChange={f.set("note")} /></Field>
          <Button variant="primary" busy={busy} onClick={save} disabled={f.v.doc_kind.trim().length < 2}>Salvar política</Button>
        </Panel>
        <Panel title="Políticas em vigor">
          <ul>{(data?.items || []).map((p: any) => (
            <li key={p.id}><strong>{p.doc_kind}</strong>: nível {p.min_legal_level}, identificação {p.min_identity_level}
              {p.require_timestamp ? ", com carimbo de tempo" : ""} · {p.org_id ? "da sua organização" : "padrão da plataforma"}</li>))}</ul>
          {data?.note && <p className="muted small">{data.note}</p>}
        </Panel>
      </StateView>
    </>
  );
}
