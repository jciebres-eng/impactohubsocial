import { useState } from "react";
import { api } from "../api";
import { Button, Field, Panel, Select, StateView, useAction, useLoad } from "../ui/kit";

// Marcadores ODS / ESG / determinantes sociais. Reutilizável em projeto, solução, diagnóstico, necessidade e organização.
// Os EMBLEMAS oficiais da ONU não acompanham a plataforma (marca protegida): usamos código, nome e a cor oficial.
export function ImpactTags({ subjectType, subjectId, readOnly }: {
  subjectType: "project" | "solution" | "diagnosis" | "need" | "call" | "organization" | "agreement";
  subjectId: string; readOnly?: boolean;
}) {
  const path = `/v1/impact-tags?subject_type=${subjectType}&subject_id=${subjectId}`;
  const { data, error, loading, reload } = useLoad<any>(path, [subjectType, subjectId]);
  const tax = useLoad<any>("/v1/impact-taxonomy");
  const { busy, run } = useAction();
  const [taxonomy, setTaxonomy] = useState("sdg");
  const [code, setCode] = useState("");

  const options: [string, string][] = taxonomy === "sdg"
    ? (tax.data?.sdg || []).map((g: any) => [g.code, `${g.code} — ${g.name_pt}`] as [string, string])
    : taxonomy === "esg"
      ? (tax.data?.esg || []).map((p: any) => [p.code, `${p.code} — ${p.name_pt}`] as [string, string])
      : (tax.data?.determinants || []).map((d: any) => [d.code, d.name_pt] as [string, string]);

  async function add() {
    await run(async () => {
      await api.post("/v1/impact-tags", { subject_type: subjectType, subject_id: subjectId, taxonomy, code });
      setCode(""); reload();
      return "Marcador aplicado.";
    });
  }

  return (
    <Panel title="Impacto declarado (ODS, ESG e determinantes sociais)">
      <StateView loading={loading} error={error} onRetry={reload}>
        {data?.items?.length ? (
          <p>{data.items.map((t: any) => (
            <span key={t.id} className="pill" style={t.color_hex ? { background: t.color_hex, color: "#fff" } : undefined}>
              {t.name || t.code}
              {!readOnly && (
                <> <button type="button" className="btn-link" aria-label={`Remover ${t.name || t.code}`}
                           onClick={() => run(async () => { await api.del(`/v1/impact-tags/${t.id}`); reload(); return "Marcador removido."; })}>×</button></>
              )}
            </span>
          ))}</p>
        ) : <p className="muted">Nenhum marcador ainda.</p>}
      </StateView>
      {!readOnly && (
        <>
          <Field label="Taxonomia">
            <Select value={taxonomy} onChange={(v) => { setTaxonomy(v); setCode(""); }}
                    options={[["sdg", "ODS (Agenda 2030)"], ["esg", "Pilar ESG"], ["determinant", "Determinante social"]]} />
          </Field>
          <Field label="Item"><Select value={code} onChange={setCode} options={options} placeholder="Escolha…" /></Field>
          <Button busy={busy} disabled={!code} onClick={add}>Aplicar marcador</Button>
          {taxonomy === "sdg" && tax.data?.notes?.sdg && <p className="muted small">{tax.data.notes.sdg}</p>}
          {taxonomy === "determinant" && tax.data?.notes?.determinants && <p className="muted small">{tax.data.notes.determinants}</p>}
        </>
      )}
    </Panel>
  );
}
