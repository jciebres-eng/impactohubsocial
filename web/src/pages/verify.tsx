import { useEffect, useState } from "react";
import { api, describeError } from "../api";
import { dateTime } from "../format";
import { navigate, useLocation } from "../router";
import { Button, Field, Input, KeyValue, Panel, Pill, StateView } from "../ui/kit";

// Página PÚBLICA de verificação. Sem login, sem dado pessoal além do necessário para conferir autenticidade.
const STATUS_LABEL: Record<string, string> = {
  active: "Válido", superseded: "Substituído por uma versão mais nova", revoked: "REVOGADO", expired: "Expirado",
};
const STATUS_TONE: Record<string, string> = { active: "good", superseded: "warn", revoked: "bad", expired: "bad" };

export function VerifyForm() {
  const [code, setCode] = useState("");
  return (
    <>
      <h1>Verificação de documento</h1>
      <p>Confira se o documento é genuíno, qual versão foi assinada e se a integridade continua intacta. Qualquer pessoa
        pode conferir — não é preciso ter conta.</p>
      <form onSubmit={(e: any) => { e.preventDefault(); if (code.trim()) navigate(`/verificar/${encodeURIComponent(code.trim())}`); }}>
        <Field label="Código de verificação" hint="Está impresso no documento, junto ao QR Code. Formato IMP-XXXX-XXXX-XXXX.">
          <Input value={code} onChange={setCode} placeholder="IMP-XXXX-XXXX-XXXX" autoCapitalize="characters"
                 aria-label="Código de verificação" />
        </Field>
        <Button type="submit" variant="primary">Verificar</Button>
      </form>
    </>
  );
}

export function VerifyResult({ code }: { code: string }) {
  const [state, setState] = useState<{ data?: any; error?: string; loading: boolean }>({ loading: true });
  useEffect(() => {
    setState({ loading: true });
    api.get(`/v1/public/verify/${encodeURIComponent(code)}`)
      .then((data) => setState({ data, loading: false }))
      .catch((e) => setState({ error: describeError(e), loading: false }));
  }, [code]);
  const d = state.data;
  return (
    <StateView loading={state.loading} error={state.error}>
      {d && (
        <>
          <h1>{d.title}</h1>
          <p>
            <Pill tone={STATUS_TONE[d.status] || "muted"}>{STATUS_LABEL[d.status] || d.status}</Pill>{" "}
            <Pill tone={d.integrity?.intact === false ? "bad" : "good"}>
              {d.integrity?.intact === false ? "Integridade comprometida" : "Integridade intacta"}
            </Pill>{" "}
            {d.version_is_current === false && <Pill tone="warn">Existe versão mais nova</Pill>}
          </p>
          {d.status === "revoked" && (
            <Panel title="Este registro foi revogado">
              <KeyValue items={[["Revogado em", dateTime(d.revoked_at)], ["Motivo", d.revocation_reason]]} />
              <p className="muted small">Um documento revogado não deve ser usado como válido, mesmo que o arquivo
                continue existindo.</p>
            </Panel>
          )}
          {d.integrity?.intact === false && (
            <Panel title="Atenção: o conteúdo não corresponde ao registrado">
              <p role="alert">{d.integrity.detail || "O conteúdo atual é diferente do que foi assinado."}</p>
            </Panel>
          )}
          {d.integrity?.storage_verified === false && (
            <Panel title="Atenção: o arquivo guardado não confere">
              <p role="alert">O hash registrado continua o mesmo, mas o arquivo armazenado não corresponde a ele.
                Procure a organização emissora antes de aceitar este documento.</p>
            </Panel>
          )}
          <Panel title="O que foi verificado">
            <KeyValue items={[
              ["Código", <code key="c">{d.code}</code>],
              ["Organização emissora", d.organization ? `${d.organization.name}${d.organization.city ? ` — ${d.organization.city}/${d.organization.uf}` : ""}` : "—"],
              ["Versão assinada", String(d.signed_version)],
              ["Versão atual na plataforma", String(d.current_version ?? d.signed_version)],
              ["Registrado em", dateTime(d.issued_at)],
              ["Impressão digital do conteúdo (SHA-256)", <code key="h" className="small">{d.content_sha256}</code>],
              ["Cadeia de custódia", d.custody_chain?.valid ? `${d.custody_chain.entries} evento(s), encadeamento íntegro` : "encadeamento com divergência"],
            ]} />
          </Panel>
          <Panel title="Quem assinou">
            {d.signers?.length ? (
              <ul className="rows">{d.signers.map((s: any, i: number) => (
                <li key={i}>
                  <span>{s.display}<br /><span className="muted small">{dateTime(s.signed_at)}</span></span>
                  <Pill tone={s.revoked ? "bad" : "good"}>{s.revoked ? "assinatura revogada" : "assinada"}</Pill>
                </li>
              ))}</ul>
            ) : <p className="muted">Nenhuma assinatura registrada neste documento.</p>}
          </Panel>
          {d.timestamps?.length > 0 && (
            <Panel title="Carimbos de tempo">
              <ul className="rows">{d.timestamps.map((t: any, i: number) => (
                <li key={i}><span>{t.authority}</span><Pill tone="muted">{dateTime(t.stamped_at)}</Pill></li>
              ))}</ul>
              <p className="muted small">Carimbo interno da plataforma. Não é carimbo de Autoridade de Carimbo de Tempo (ACT).</p>
            </Panel>
          )}
          <p className="muted small">{d.privacy_note}</p>
          <p><Button onClick={() => navigate("/verificar")}>Verificar outro código</Button></p>
        </>
      )}
    </StateView>
  );
}

export function VerifyPage() {
  const { path } = useLocation();
  const code = path.replace(/^\/verificar\/?/, "");
  return code ? <VerifyResult code={decodeURIComponent(code)} /> : <VerifyForm />;
}
