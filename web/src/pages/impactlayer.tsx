import { useState } from "react";
import { api } from "../api";
import { useSession } from "../session";
import { date } from "../format";
import { CLAIM_KIND, CLAIM_STATUS, EQUITY_DENOMINATOR, EQUITY_METHOD, EQUITY_STANDING,
         REPUTATION_BAND, SEAL_STATUS } from "../glossary";
import { Button, Field, Input, KeyValue, PageHead, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// AS SEIS TELAS QUE FALTAVAM (§94) — reputação, selos, afirmações, equidade, ODS, responsabilidade.
//
// O documento desta rodada é explícito: não confundir API IMPLEMENTED com PRODUCT COMPLETE. Estas
// seis áreas tinham API, serviço, banco, eventos, permissões, testes e documentação — e NENHUMA
// tela. Enquanto isso, a tela de primeiro acesso dizia honestamente `to_be_designed` para as seis,
// o que é melhor que mentir e ainda assim deixa a pessoa sem poder usar o produto.
//
// Isto é UI MÍNIMA FUNCIONAL, no sentido exato de §94: existe para que o fluxo possa ser validado
// de ponta a ponta por uma pessoa, e não para ser bonita. O refinamento visual é do Designer, sobre
// um contrato técnico congelado.
//
// Uma regra atravessa as seis telas: TODO rótulo vem de `glossary.ts`, gerado de
// `config/glossary.json`. A interface não inventa sinônimo — "pendente", "em análise" e "aguardando"
// para o mesmo estado é como um produto de evidência começa a parecer três produtos.

const band = (b: string) => REPUTATION_BAND[b] || b;

// ============================================================================ 1. Reputação
export function Reputation() {
  const { data, error, loading, reload } = useLoad<any>("/v1/reputation/me");
  const [open, setOpen] = useState<string | null>(null);
  const act = useAction();
  const f = useForm({ dimension: "", what_is_contested: "", expected_correction: "" });
  const contest = async () => {
    if (f.v.what_is_contested.trim().length < 20 || f.v.expected_correction.trim().length < 20) {
      alert("Descreva o que está sendo contestado e a correção esperada (20+ caracteres cada).");
      return;
    }
    if (await act.run(() => api.post("/v1/reputation/disputes", f.v), "Contestação registrada")) {
      setOpen(null);
      reload();
    }
  };
  return (
    <>
      <PageHead title="Reputação" sub="Por dimensão, a partir do que foi observado — nunca uma nota só." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <p className="muted small">{data.note}</p>
            {(data.dimensions || []).map((d: any) => (
              <Panel key={d.dimension} title={d.label || d.dimension}
                     actions={<Pill tone={d.band === "strong" ? "good" : d.band === "weak" ? "warn" : ""}>
                       {band(d.band)}</Pill>}>
                <KeyValue items={[
                  ["Valor", d.value == null ? "sem base suficiente" : String(d.value)],
                  ["Confiança", d.confidence_label || d.confidence],
                  ["Observações", `${d.observations} (${d.verified_observations} verificadas, ${d.self_declared_observations} autodeclaradas)`],
                  ["Como foi calculada", <span className="small">{d.how}</span>],
                ]} />
                {open === d.dimension ? (
                  <div className="form-grid">
                    <Field label="O que está sendo contestado" wide>
                      <TextArea value={f.v.what_is_contested} onChange={f.set("what_is_contested")} rows={3} />
                    </Field>
                    <Field label="Correção esperada" wide>
                      <TextArea value={f.v.expected_correction} onChange={f.set("expected_correction")} rows={3} />
                    </Field>
                    <div className="row">
                      <Button variant="primary" busy={act.busy} onClick={contest}>Enviar contestação</Button>
                      <Button onClick={() => setOpen(null)}>Cancelar</Button>
                    </div>
                  </div>
                ) : (
                  <Button onClick={() => { f.setV({ ...f.v, dimension: d.dimension }); setOpen(d.dimension); }}>
                    Contestar esta dimensão
                  </Button>
                )}
              </Panel>
            ))}
            <Panel title="O que esta tela não faz" quiet>
              <p className="small muted">
                Não existe nota única nem posição em ranking: cada dimensão é lida separadamente, com
                as observações que a sustentam. Denúncia aberta NÃO entra aqui — só infração apurada
                e concluída, depois de manifestação da parte denunciada.
              </p>
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

// ============================================================================ 2. Selos
export function Seals() {
  const awards = useLoad<any>("/v1/seals/awards");
  const defs = useLoad<any>("/v1/seals/definitions");
  const evals = useLoad<any>("/v1/seals/evaluations");
  return (
    <>
      <PageHead title="Selos" sub="A regra é pública, e a avaliação que NÃO concedeu também fica registrada." />
      <StateView loading={awards.loading} error={awards.error} onRetry={awards.reload}>
        <Panel title="Selos da organização">
          {awards.data?.items?.length ? awards.data.items.map((a: any) => (
            <div key={a.id} className="bordered">
              <h4>{a.title} <Pill tone={a.status === "active" ? "good" : "warn"}>
                {SEAL_STATUS[a.status] || a.status}</Pill></h4>
              <KeyValue items={[
                ["O que atesta", a.what_it_attests],
                ["O que NÃO atesta", <strong>{a.what_it_does_not_attest}</strong>],
                ["Concedido em", date(a.awarded_at)],
                ["Vence em", a.expires_on ? date(a.expires_on) : "sem prazo declarado"],
              ]} />
              {a.revocation && (
                <p className="small"><strong>Revogado:</strong> {a.revocation.reason_label} — {a.revocation.detail}</p>
              )}
            </div>
          )) : <p className="muted">Nenhum selo concedido. A lista abaixo mostra o que existe e o que cada um exige.</p>}
        </Panel>
      </StateView>
      <Panel title="Selos que existem, e o critério de cada um">
        {(defs.data?.items || []).map((d: any) => (
          <div key={d.id} className="bordered">
            <h4>{d.title} <span className="muted small">v{d.version}</span></h4>
            <p className="small">{d.what_it_attests}</p>
            <p className="small muted"><strong>Não atesta:</strong> {d.what_it_does_not_attest}</p>
            <ul className="small">{(d.rules || []).map((r: any) => (
              <li key={r.code}>{r.description}</li>))}</ul>
          </div>
        ))}
      </Panel>
      <Panel title="Avaliações — inclusive as que não concederam" quiet>
        <p className="small muted">{evals.data?.note}</p>
        {(evals.data?.items || []).map((e: any) => (
          <div key={e.id} className="small bordered">
            <strong>{e.title}</strong> — {e.all_met ? "todos os critérios satisfeitos" : "faltou critério"}
            <ul>{(e.detail || []).filter((x: any) => !x.met).map((x: any, i: number) => (
              <li key={i}>{x.rule_code}: {x.detail}</li>))}</ul>
          </div>
        ))}
      </Panel>
    </>
  );
}

// ============================================================================ 3. Afirmações de impacto
export function Claims() {
  const { data, error, loading, reload } = useLoad<any>("/v1/claims");
  const rules = useLoad<any>("/v1/claims/rules");
  const projetos = useLoad<any>("/v1/projects");
  const act = useAction();
  const [novo, setNovo] = useState(false);
  // Uma afirmação é SEMPRE sobre alguma coisa: projeto, programa, organização, solução ou
  // relatório. Afirmação sem sujeito não tem como ser verificada — e a primeira versão desta tela
  // esquecia o sujeito, o que a API recusava com 422. Quem encontrou foi o teste adversarial.
  const f = useForm({ subject_type: "project", subject_id: "", claim_kind: "result",
                      statement: "", period_start: "", period_end: "" });
  const criar = async () => {
    if (!f.v.subject_id) { alert("Escolha o projeto sobre o qual é a afirmação."); return; }
    if (await act.run(() => api.post("/v1/claims", f.v), "Afirmação registrada")) {
      setNovo(false);
      reload();
    }
  };
  const verificar = async (id: string) => {
    if (await act.run(() => api.post(`/v1/claims/${id}/check`, {}), "Verificação feita")) reload();
  };
  return (
    <>
      <PageHead title="Afirmações de impacto"
                sub="O que a organização afirma, e o que a evidência sustenta."
                actions={<Button variant="primary" onClick={() => setNovo(!novo)}>Nova afirmação</Button>} />
      {novo && (
        <Panel title="Declarar uma afirmação">
          <div className="form-grid">
            <Field label="Sobre qual projeto" hint="Afirmação sem sujeito não tem como ser verificada.">
              <Select value={f.v.subject_id} onChange={f.set("subject_id")} placeholder="escolha"
                      options={(projetos.data?.items || []).map((p: any) => [p.id, p.title])} />
            </Field>
            <Field label="Tipo">
              <Select value={f.v.claim_kind} onChange={f.set("claim_kind")}
                      options={Object.entries(CLAIM_KIND)} />
            </Field>
            <Field label="Período (início)"><Input type="date" value={f.v.period_start} onChange={f.set("period_start")} /></Field>
            <Field label="Período (fim)"><Input type="date" value={f.v.period_end} onChange={f.set("period_end")} /></Field>
            <Field label="A afirmação, nas suas palavras" wide
                   hint="A plataforma não reescreve o que você afirma: ela confere o que sustenta.">
              <TextArea value={f.v.statement} onChange={f.set("statement")} rows={3} />
            </Field>
          </div>
          <Button variant="primary" busy={act.busy} onClick={criar}>Registrar</Button>
        </Panel>
      )}
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items?.length}>
        {(data?.items || []).map((c: any) => (
          <Panel key={c.id} title={c.statement}
                 actions={<Pill tone={c.status === "supported" ? "good" : c.status === "unsupported" ? "bad" : ""}>
                   {CLAIM_STATUS[c.status] || c.status}</Pill>}>
            <KeyValue items={[
              ["Tipo", CLAIM_KIND[c.claim_kind] || c.claim_kind],
              ["Período", `${date(c.period_start)} a ${date(c.period_end)}`],
              ["Rodadas de verificação", String(c.check_rounds ?? 0)],
            ]} />
            <Button busy={act.busy} onClick={() => verificar(c.id)}>Verificar agora</Button>
          </Panel>
        ))}
      </StateView>
      <Panel title="As regras de verificação, antes de você afirmar" quiet>
        <p className="small muted">{rules.data?.note}</p>
        <ul className="small">{(rules.data?.items || []).map((r: any) => (
          <li key={r.code}><strong>{r.code}</strong>: {r.description}</li>))}</ul>
      </Panel>
    </>
  );
}

// ============================================================================ 4. Equidade
export function Equity({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/projects/${id}/equity`);
  const cat = useLoad<any>("/v1/equity/catalog");
  const norm = useLoad<any>(`/v1/projects/${id}/equity/normalization`);
  const act = useAction();
  const f = useForm({ barrier_code: "", standing: "declared", note: "" });
  const addBarreira = async () => {
    if (await act.run(() => api.post(`/v1/projects/${id}/equity/barriers`, f.v),
                      "Barreira registrada")) reload();
  };
  return (
    <>
      <PageHead title="Equidade e contexto"
                sub="Comparar sem denominador comum é comparar coisas diferentes." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {/* v0.25.0: `methods` vem da API como OBJETO (método → resultado), não lista — a tela
                quebrava com "map is not a function" ao abrir. Também lia `why`/`denominator`, que a
                API chama `reason`/`denominator_kind`, e `label`, que no catálogo é `name_pt`. */}
            <Panel title="Denominadores disponíveis para este projeto">
              {Object.entries(norm.data?.methods || {}).map(([chave, m]: [string, any]) => (
                <div key={chave} className="small bordered">
                  <strong>{EQUITY_METHOD[chave] || m.label || chave}</strong>
                  {" — "}{m.available ? "disponível" : "indisponível"}
                  {m.denominator_kind && <> · base: {EQUITY_DENOMINATOR[m.denominator_kind] || m.denominator_kind}</>}
                  {m.available && <> · valor: {m.value} (fonte: {m.source_name}, {date(m.source_date)})</>}
                  {m.reason && <div className="muted">{m.reason}</div>}
                </div>
              ))}
              <p className="small muted">{norm.data?.note}</p>
            </Panel>
            <Panel title="Barreiras declaradas">
              {(data.barriers || []).map((b: any) => (
                <div key={b.barrier_code} className="small bordered">
                  <strong>{b.name_pt || b.barrier_code}</strong>
                  {" "}<Pill>{EQUITY_STANDING[b.standing] || b.standing}</Pill>
                  <div className="muted">{b.note}</div>
                </div>
              ))}
              <div className="form-grid">
                <Field label="Barreira">
                  <Select value={f.v.barrier_code} onChange={f.set("barrier_code")}
                          placeholder="escolha"
                          options={(cat.data?.items || []).map((b: any) => [b.code, b.name_pt])} />
                </Field>
                <Field label="Situação" hint="Declarada, documentada ou com evidência — e a diferença importa.">
                  <Select value={f.v.standing} onChange={f.set("standing")}
                          options={Object.entries(EQUITY_STANDING)} />
                </Field>
                <Field label="Observação" wide>
                  <TextArea value={f.v.note} onChange={f.set("note")} rows={2} />
                </Field>
              </div>
              <Button variant="primary" busy={act.busy} onClick={addBarreira}>Registrar barreira</Button>
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

// ============================================================================ 5. ODS
export function OdsTargets({ id }: { id: string }) {
  const ods = useLoad<any>("/v1/ods");
  const [numero, setNumero] = useState<string>("");
  const alvos = useLoad<any>(numero ? `/v1/ods/${numero}/targets` : null, [numero]);
  const atual = useLoad<any>(`/v1/projects/${id}`);
  const act = useAction();
  const [sel, setSel] = useState<string[]>([]);
  const salvar = async () => {
    await act.run(() => api.put(`/v1/projects/${id}/ods-targets`,
                                { targets: sel.map((code) => ({ ods: Number(code.split(".")[0]), target_code: code })) }),
                  "Metas vinculadas");
  };
  return (
    <>
      <PageHead title="ODS do projeto" sub="Objetivo e META — vincular ao objetivo sem a meta diz pouco." />
      <Panel title="Escolha o objetivo">
        <Select value={numero} onChange={setNumero} placeholder="Objetivo de Desenvolvimento Sustentável"
                options={(ods.data?.items || []).map((o: any) => [String(o.number), `${o.number}. ${o.name}`])} />
      </Panel>
      {numero && (
        <Panel title="Metas deste objetivo">
          {alvos.data?.items?.length ? alvos.data.items.map((t: any) => (
            <label key={t.code} className="row small">
              <input type="checkbox" checked={sel.includes(t.code)}
                     onChange={(e: any) => setSel(e.target.checked ? [...sel, t.code] : sel.filter((c) => c !== t.code))} />
              <span><strong>{t.code}</strong> — {t.description}</span>
            </label>
          )) : (
            <p className="muted small">
              Nenhuma meta carregada para este objetivo. As metas oficiais entram por importação de
              arquivo da fonte (<code>scripts/import_ods_targets.py</code>), com publicador, licença e
              data de consulta — a plataforma não transcreve o texto oficial de memória.
            </p>
          )}
          {!!sel.length && <Button variant="primary" busy={act.busy} onClick={salvar}>Vincular ao projeto</Button>}
        </Panel>
      )}
      <Panel title="Vinculado hoje" quiet>
        <p className="small muted">{(atual.data?.ods || []).join(", ") || "nenhum objetivo vinculado"}</p>
      </Panel>
    </>
  );
}

// ============================================================================ 6. Responsabilidade
export function Responsibility() {
  // v0.25.0: a tela chamava `/v1/responsibility/current` SEM `scope` e `subject_id`, que a API
  // exige — 422 para todo perfil, e a área nunca tinha mostrado uma atribuição. Também lia campos
  // que a API não devolve (`role_label`, `person_name`). O escopo aqui é a ORGANIZAÇÃO ativa.
  const { me } = useSession();
  const org = me?.active_org?.id;
  const q = org ? `?scope=organization&subject_id=${org}` : null;
  const atual = useLoad<any>(q && `/v1/responsibility/current${q}`, [q]);
  const papeis = useLoad<any>("/v1/responsibility/roles");
  const decisoes = useLoad<any>(q && `/v1/responsibility/decisions${q}`, [q]);
  return (
    <>
      <PageHead title="Responsabilidade"
                sub="Quem responde por quê na organização, desde quando — e quem decidiu o quê." />
      <StateView loading={atual.loading} error={atual.error} onRetry={atual.reload}>
        <Panel title="Quem responde hoje">
          {(atual.data?.items || []).map((a: any) => (
            <div key={a.assignment_id} className="small bordered">
              <strong>{a.role_name}</strong> — {a.who}
              <div className="muted">
                Desde {date(a.starts_on)}{a.mandate_basis ? ` · base: ${a.mandate_basis}` : ""}
              </div>
            </div>
          ))}
          {!atual.data?.items?.length && (
            <p className="muted small">
              Nenhuma atribuição vigente. Sem isso, "a organização decidiu" não tem sujeito — e
              prestação de contas sem sujeito não é prestação de contas.
            </p>
          )}
        </Panel>
        {!!atual.data?.without_responsible?.length && (
          <Panel title="Papéis sem responsável" quiet>
            <ul className="small">{atual.data.without_responsible.map((r: any) => (
              <li key={r.code}><strong>{r.name_pt}</strong>: {r.answers_for}</li>))}</ul>
          </Panel>
        )}
      </StateView>
      <Panel title="Papéis que existem" quiet>
        <StateView loading={papeis.loading} error={papeis.error} onRetry={papeis.reload}>
          <ul className="small">{(papeis.data?.items || []).map((r: any) => (
            <li key={r.code}><strong>{r.name_pt}</strong>: {r.answers_for}
              {r.does_not_answer_for && <span className="muted"> — não responde por: {r.does_not_answer_for}</span>}</li>))}</ul>
        </StateView>
      </Panel>
      <Panel title="Decisões registradas">
        <StateView loading={decisoes.loading} error={decisoes.error} onRetry={decisoes.reload}>
          {(decisoes.data?.items || []).map((d: any) => (
            <div key={d.id} className="small bordered">
              <strong>{d.kind_name}</strong> <span className="muted">{date(d.taken_on)} · {d.role_name}: {d.who}</span>
              <div>{d.statement}</div>
              {d.requires_two && <Pill tone="good">dois responsáveis{d.second_who ? ` (${d.second_who})` : ""}</Pill>}
            </div>
          ))}
          {!decisoes.data?.items?.length && <p className="muted small">Nenhuma decisão registrada ainda.</p>}
        </StateView>
      </Panel>
    </>
  );
}
