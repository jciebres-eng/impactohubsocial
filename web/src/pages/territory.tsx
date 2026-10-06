import { useState } from "react";
import { api } from "../api";
import { date } from "../format";
import { Button, Field, Input, PageHead, Pager, Panel, Pill, Select, StateView, TextArea,
         useAction, useForm, useLoad } from "../ui/kit";

// NECESSIDADES DO TERRITÓRIO — e a distinção que a plataforma não deixa borrar:
//
//   "Este projeto atende mulheres em situação de vulnerabilidade"  → atributo do PROJETO/NECESSIDADE (fica aqui)
//   "Esta pessoa pertence a determinado grupo vulnerável"          → dado pessoal sensível (não existe aqui)
//
// O grupo beneficiário é atributo da necessidade. A política de uso do termo, registrada na própria taxonomia do
// banco, proíbe usá-lo para filtrar, segmentar ou inferir característica de pessoa — e esta tela não oferece
// nenhum filtro por grupo beneficiário, de propósito.

const PRIO_LABEL: Record<string, string> = { low: "baixa", medium: "média", high: "alta", critical: "crítica" };

export function TerritoryNeeds() {
  const [uf, setUf] = useState("");
  const [offset, setOffset] = useState(0);
  const qs = `${uf ? `territory=${uf}&` : ""}limit=20&offset=${offset}`;
  const { data, error, loading, reload } = useLoad<any>(`/v1/territory/needs?${qs}`, [uf, offset]);
  const tax = useLoad<any>("/v1/taxonomies?taxonomy=beneficiary_group");
  const policy = tax.data?.items?.[0]?.usage_policy;
  return (
    <>
      <PageHead title="Necessidades do território"
                sub="Demanda declarada por quem conhece o lugar. Toda estimativa de pessoas exige a fonte do número." />
      <Panel quiet>
        <Field label="Território" hint="UF (MT) ou BR-UF (BR-MT)">
          <Input value={uf} onChange={(v) => { setUf(v.toUpperCase()); setOffset(0); }} placeholder="BR-MT" /></Field>
        {policy && <p className="muted small">{policy}</p>}
      </Panel>
      <StateView loading={loading} error={error} onRetry={reload} empty={data && !data.items.length}>
        {data && (
          <>
            <ul className="list">
              {data.items.map((n: any) => (
                <li key={n.id} className="list-row">
                  <div className="grow">
                    <strong>{n.title}</strong>
                    <p className="muted small">
                      {n.territory}
                      {n.org_name && <> · declarada por {n.org_name}</>}
                      {n.cause && <> · {n.cause}</>}
                      {n.people_estimate != null && <> · {n.people_estimate} pessoa(s)</>}
                      {n.source_name && <> · fonte: {n.source_name}</>}
                      {n.source_date && <> ({date(n.source_date)})</>}
                    </p>
                    {n.description && <p className="small">{n.description}</p>}
                    {!!n.beneficiary_groups?.length && (
                      <p className="small">Público atendido pela necessidade: {n.beneficiary_groups.join(", ")}</p>
                    )}
                    {n.source_url && (
                      <p className="small"><a href={n.source_url} target="_blank" rel="noopener noreferrer">Ver a fonte</a></p>
                    )}
                  </div>
                  <div className="col gap">
                    <Pill tone={n.priority === "critical" || n.priority === "high" ? "warn" : undefined}>
                      prioridade {PRIO_LABEL[n.priority] || n.priority}</Pill>
                    <Pill status={n.status}>{n.status}</Pill>
                  </div>
                </li>
              ))}
            </ul>
            <Pager data={data} offset={offset} setOffset={setOffset} />
          </>
        )}
      </StateView>
      <NewNeed onDone={reload} />
    </>
  );
}

function NewNeed({ onDone }: { onDone: () => void }) {
  const f = useForm({ territory: "", title: "", description: "", cause: "", people_estimate: "",
                      source_name: "", source_url: "", source_date: "", priority: "medium",
                      beneficiary_groups: [] as string[] });
  const act = useAction();
  const tax = useLoad<any>("/v1/taxonomies?taxonomy=beneficiary_group");
  const groups: [string, string][] = (tax.data?.items?.[0]?.terms || []).map((t: any) => [t.code, t.label_pt]);
  const needsSource = !!f.v.people_estimate;
  const create = async () => {
    if (await act.run(() => api.post("/v1/territory/needs", {
      territory: f.v.territory, title: f.v.title, description: f.v.description || undefined,
      cause: f.v.cause || undefined, beneficiary_groups: f.v.beneficiary_groups,
      people_estimate: f.v.people_estimate ? Number(f.v.people_estimate) : undefined,
      source_name: f.v.source_name || undefined, source_url: f.v.source_url || undefined,
      source_date: f.v.source_date || undefined, priority: f.v.priority,
    }), "Necessidade registrada")) { f.setV({ ...f.v, title: "", description: "", people_estimate: "" }); onDone(); }
  };
  return (
    <Panel title="Registrar necessidade">
      <div className="row gap wrap">
        <Field label="Território"><Input value={f.v.territory}
          onChange={(v) => f.set("territory")(v.toUpperCase())} placeholder="BR-MT" /></Field>
        <Field label="Prioridade"><Select value={f.v.priority} onChange={f.set("priority")}
          options={[["low", "Baixa"], ["medium", "Média"], ["high", "Alta"], ["critical", "Crítica"]]} /></Field>
      </div>
      <Field label="Qual é a necessidade" wide><Input value={f.v.title} onChange={f.set("title")} /></Field>
      <Field label="Detalhe" wide><TextArea value={f.v.description} onChange={f.set("description")} rows={3} /></Field>
      <Field label="Quantas pessoas (opcional)"
             hint="Se informar, a fonte passa a ser obrigatória — o banco recusa estimativa sem origem declarada">
        <Input value={f.v.people_estimate} onChange={f.set("people_estimate")} /></Field>
      <div className="row gap wrap">
        <Field label={`Fonte do número${needsSource ? " (obrigatória)" : ""}`}>
          <Input value={f.v.source_name} onChange={f.set("source_name")} placeholder="IBGE, Censo 2022" /></Field>
        <Field label="Link da fonte"><Input value={f.v.source_url} onChange={f.set("source_url")}
          placeholder="https://" /></Field>
        <Field label="Data da fonte"><Input type="date" value={f.v.source_date} onChange={f.set("source_date")} /></Field>
      </div>
      {!!groups.length && (
        <Field label="Público atendido por esta necessidade"
               hint="Atributo da NECESSIDADE. Nunca é usado para filtrar, segmentar ou inferir característica de pessoa." wide>
          <div className="row gap wrap">
            {groups.map(([k, lbl]) => (
              <Button key={k} variant={f.v.beneficiary_groups.includes(k) ? "ink" : "ghost"}
                      onClick={() => f.set("beneficiary_groups")(f.v.beneficiary_groups.includes(k)
                        ? f.v.beneficiary_groups.filter((x) => x !== k) : [...f.v.beneficiary_groups, k])}>{lbl}</Button>
            ))}
          </div>
        </Field>
      )}
      <Button variant="ink" busy={act.busy}
              disabled={!f.v.territory || f.v.title.length < 5 || (needsSource && !f.v.source_name)}
              onClick={create}>Registrar</Button>
    </Panel>
  );
}

// ============================================================================ taxonomias
export function Taxonomies() {
  const { data, error, loading, reload } = useLoad<any>("/v1/taxonomies");
  return (
    <>
      <PageHead title="Vocabulário da plataforma"
                sub="Rótulos não se escrevem na interface: vêm daqui, com versão e política de uso." />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <p className="muted small">{data.note}</p>
            {data.items.map((t: any) => (
              <Panel key={t.key} title={`${t.label_pt} (${t.key} · versão ${t.version})`}>
                <p className="muted small">{t.purpose}</p>
                <p className="small">
                  Sensibilidade: <Pill tone={t.sensitivity === "beneficiary_group" ? "warn" : undefined}>
                    {t.sensitivity}</Pill>
                  {t.source_name && <> · fonte: {t.source_name}</>}
                </p>
                <p className="small"><strong>Política de uso:</strong> {t.usage_policy}</p>
                <ul className="row gap wrap small">
                  {t.terms.map((x: any) => (
                    <li key={x.code}><Pill tone={x.active ? undefined : "warn"}>{x.label_pt}</Pill></li>
                  ))}
                </ul>
              </Panel>
            ))}
          </>
        )}
      </StateView>
    </>
  );
}
