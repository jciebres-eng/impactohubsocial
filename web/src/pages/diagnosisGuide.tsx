import { useEffect, useState } from "react";
import { api } from "../api";
import { Link } from "../router";
import { Button, Field, Input, Panel, PageHead, Pill, Select, StateView, TextArea, useAction, useLoad } from "../ui/kit";

// Diagnóstico guiado: etapa a etapa, com documentos exigidos e progresso medido pelo que foi realmente preenchido.
const STATUS_TONE: Record<string, string> = { complete: "good", skipped: "muted", in_progress: "warn", pending: "muted" };
const STATUS_LABEL: Record<string, string> = { complete: "concluída", skipped: "pulada", in_progress: "em andamento", pending: "pendente" };

function StageField({ q, value, onChange }: { q: any; value: any; onChange: (v: any) => void }) {
  if (q.type === "boolean") {
    return <Field label={q.label} hint={q.help}>
      <Select value={value === true ? "1" : value === false ? "0" : ""} onChange={(v) => onChange(v === "1")}
              options={[["1", "Sim"], ["0", "Não"]]} placeholder="Escolha…" />
    </Field>;
  }
  if (q.type === "enum") {
    return <Field label={q.label} hint={q.help}>
      <Select value={value || ""} onChange={onChange}
              options={(q.options || []).map((o: string) => [o, o] as [string, string])} placeholder="Escolha…" />
    </Field>;
  }
  if (q.type === "textarea") {
    return <Field label={q.label} hint={q.help} wide><TextArea value={value || ""} onChange={onChange} rows={4} /></Field>;
  }
  if (q.type === "list" || q.type === "goals" || q.type === "actions" || q.type === "budget") {
    return <Field label={q.label} hint={q.help || "Um item por linha."} wide>
      <TextArea value={Array.isArray(value) ? value.join("\n") : (value || "")} rows={4}
                onChange={(v) => onChange(v.split("\n").map((x) => x.trim()).filter(Boolean))} />
    </Field>;
  }
  if (q.type === "money") {
    return <Field label={q.label} hint={q.help}><Input value={value ?? ""} onChange={onChange} placeholder="0,00" /></Field>;
  }
  return <Field label={q.label} hint={q.help}><Input value={value ?? ""} onChange={onChange} /></Field>;
}

export function DiagnosisGuide({ id }: { id: string }) {
  const { data, error, loading, reload } = useLoad<any>(`/v1/diagnoses/${id}/guide`, [id]);
  const { busy, run } = useAction();
  const [open, setOpen] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [docs, setDocs] = useState("");
  const [skip, setSkip] = useState("");

  useEffect(() => {
    if (data && !open && data.next_stage) setOpen(data.next_stage);
  }, [data, open]);

  function load(stage: any) {
    setOpen(stage.code);
    setAnswers(stage.progress?.answers || {});
    setDocs((stage.progress?.document_ids || []).join(", "));
    setSkip("");
  }

  async function save(stage: any, complete: boolean) {
    await run(async () => {
      const body: any = { answers, complete };
      const ids = docs.split(",").map((x) => x.trim()).filter(Boolean);
      if (ids.length) body.document_ids = ids;
      if (skip.trim()) body.skip_reason = skip.trim();
      await api.put(`/v1/diagnoses/${id}/guide/${stage.code}`, body);
      reload();
      return complete ? "Etapa concluída." : "Etapa salva.";
    });
  }

  return (
    <>
      <PageHead title="Diagnóstico guiado" back={`/diagnosticos/${id}`}
                sub={data ? `${data.completed_stages} de ${data.total_stages} etapas · ${data.percent}%` : undefined} />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <div className="bar" role="img" aria-label={`${data.percent}% concluído`}>
              <div className="bar-fill" style={{ width: `${data.percent}%` }} />
            </div>
            {data.stages.map((st: any) => (
              <Panel key={st.code} title={<>{st.position}. {st.title} <Pill tone={STATUS_TONE[st.progress.status]}>
                {STATUS_LABEL[st.progress.status]}</Pill></>}
                     actions={open === st.code ? undefined : <Button onClick={() => load(st)}>Abrir</Button>}>
                <p className="muted">{st.purpose}</p>
                {open === st.code && (
                  <>
                    {(st.questions || []).map((q: any) => (
                      <StageField key={q.key} q={q} value={answers[q.key]}
                                  onChange={(v) => setAnswers({ ...answers, [q.key]: v })} />
                    ))}
                    {(st.required_documents || []).length > 0 && (
                      <Field label="Documentos" wide
                             hint={`Envie em Documentos e cole os identificadores separados por vírgula. Exigidos: ${
                               st.required_documents.map((d: any) => d.label + (d.required ? " (obrigatório)" : "")).join("; ")}`}>
                        <Input value={docs} onChange={setDocs} placeholder="uuid, uuid" />
                      </Field>
                    )}
                    <Field label="Pular esta etapa" hint="Informe o motivo para registrar por que ficou de fora.">
                      <Input value={skip} onChange={setSkip} placeholder="Ex.: vamos preencher junto com a equipe." />
                    </Field>
                    <Button busy={busy} onClick={() => save(st, false)}>Salvar sem concluir</Button>{" "}
                    <Button variant="primary" busy={busy} onClick={() => save(st, true)}>
                      {skip.trim() ? "Pular etapa" : "Concluir etapa"}
                    </Button>
                    {st.help_key && <p className="muted small">Precisa de ajuda? Veja <Link to="/ajuda/busca">a Central de Conhecimento</Link>.</p>}
                  </>
                )}
              </Panel>
            ))}
            <p className="muted small">{data.note}</p>
          </>
        )}
      </StateView>
    </>
  );
}
