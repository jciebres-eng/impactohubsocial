import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { absorbSession, api, describeError } from "../api";
import { Link, navigate, useLocation } from "../router";
import { useSession } from "../session";
import { Button, Field, Input, Select, StateView, useAction, useForm } from "../ui/kit";

function AuthFrame({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-brand">
        <Link to="/" className="brand brand-light"><span className="brand-mark" aria-hidden="true" />Impacto</Link>
        <div className="auth-pitch">
          {aside ?? (
            <>
              <p className="auth-line">Do edital à prestação de contas, em uma trilha só.</p>
              <ol className="auth-trail" aria-label="Como funciona">
                <li>A OSC encontra editais e fundos compatíveis e vê o que falta para concorrer.</li>
                <li>A candidatura é montada passo a passo, com rascunhos assistidos e validação de profissionais habilitados.</li>
                <li>Quem financia acompanha cada real: aporte, despesa comprovada, evidência e resultado.</li>
              </ol>
            </>
          )}
        </div>
      </div>
      <main className="auth-main" id="conteudo">
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  );
}

export function Landing() {
  return (
    <AuthFrame title="Entre na sua trilha">
      <p className="lead">Plataforma para organizações da sociedade civil, empresas, profissionais parceiros e órgãos públicos.</p>
      <div className="stack">
        <Button variant="primary" onClick={() => navigate("/entrar")}>Entrar</Button>
        <Button variant="ghost" onClick={() => navigate("/cadastro")}>Criar conta</Button>
      </div>
      <p className="fineprint"><Link to="/legal/termos">Termos de uso</Link> · <Link to="/legal/privacidade">Política de privacidade</Link></p>
    </AuthFrame>
  );
}

export function Login() {
  const { reload } = useSession();
  const { query } = useLocation();
  const f = useForm({ email: "", password: "" });
  const [mfa, setMfa] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = query.get("proximo") || "/";
  const [sso, setSso] = useState(false);
  useEffect(() => { api.get("/v1/meta/config").then((c) => setSso(!!c.sso_enabled)).catch(() => {}); }, []);

  async function submit(e: any) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      if (!mfa) {
        const r = await api.post("/v1/auth/login", f.v);
        if (r.mfa_required) {
          setMfa(r.mfa_token);
          return;
        }
        await absorbSession(r);
      } else {
        const r = await api.post("/v1/auth/mfa/verify", useRecovery ? { mfa_token: mfa, recovery_code: code } : { mfa_token: mfa, code });
        await absorbSession(r);
      }
      await reload();
      navigate(next.startsWith("/") && !next.startsWith("//") ? next : "/", true);
    } catch (e2) {
      setErr(describeError(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame title={mfa ? "Verificação em duas etapas" : "Entrar"}>
      <form onSubmit={submit} className="form" noValidate>
        {!mfa ? (
          <>
            <Field label="E-mail"><Input type="email" autoComplete="username" required value={f.v.email} onChange={f.set("email")} /></Field>
            <Field label="Senha"><Input type="password" autoComplete="current-password" required value={f.v.password} onChange={f.set("password")} /></Field>
          </>
        ) : (
          <Field label={useRecovery ? "Código de recuperação" : "Código do aplicativo autenticador"} hint={useRecovery ? "Formato XXXX-XXXX-XXXX" : "6 dígitos"}>
            <Input inputMode={useRecovery ? "text" : "numeric"} autoComplete="one-time-code" autoFocus value={code} onChange={setCode} />
          </Field>
        )}
        {err && <p className="form-error" role="alert">{err}</p>}
        <Button type="submit" variant="primary" busy={busy}>{mfa ? "Confirmar" : "Entrar"}</Button>
        {mfa && <Button variant="link" onClick={() => setUseRecovery(!useRecovery)}>{useRecovery ? "Usar o aplicativo autenticador" : "Usar código de recuperação"}</Button>}
      </form>
      {!mfa && (
        <p className="auth-links">
          <Link to="/esqueci-senha">Esqueci minha senha</Link>
          <Link to="/cadastro">Criar conta</Link>
          {sso && <a href={`/v1/auth/oidc/start?redirect=${encodeURIComponent(next)}`}>Entrar com login corporativo (SSO)</a>}
        </p>
      )}
    </AuthFrame>
  );
}

const KINDS: [string, string, string][] = [
  ["osc", "Organização da sociedade civil", "Encontre editais e fundos, monte candidaturas e preste contas."],
  ["company", "Empresa, instituto ou fundação", "Encontre projetos alinhados à sua estratégia e acompanhe o investimento."],
  ["individual", "Apoiador pessoa física", "Apoie projetos e acompanhe o uso do recurso. O nome fica oculto às OSCs, a menos que você escolha mostrá-lo."],
  ["provider", "Profissional parceiro", "Contador, advogado, elaborador de projetos: valide e assine com sua credencial."],
  ["government", "Órgão público", "Publique editais e materiais e acompanhe dados do território."],
];

export function Register() {
  const f = useForm({ email: "", password: "", full_name: "", kind: "osc", legal_name: "", cnpj: "", uf: "", legal_nature_code: "", accept_terms: false });
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: any) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api.post("/v1/auth/register", {
        email: f.v.email, password: f.v.password, full_name: f.v.full_name, accept_terms: f.v.accept_terms,
        organization: { kind: f.v.kind, legal_name: f.v.legal_name, cnpj: f.v.cnpj || null, uf: f.v.uf || null, legal_nature_code: f.v.kind === "osc" && f.v.legal_nature_code ? f.v.legal_nature_code : undefined },
      });
      setDone(true);
    } catch (e2) {
      setErr(describeError(e2));
    } finally {
      setBusy(false);
    }
  }
  if (done) return (
    <AuthFrame title="Confirme seu e-mail">
      <p className="lead">Enviamos um link para <strong>{f.v.email}</strong>. Depois de confirmar, entre com sua senha.</p>
      <Button variant="primary" onClick={() => navigate("/entrar")}>Ir para o login</Button>
    </AuthFrame>
  );
  return (
    <AuthFrame title="Criar conta">
      <form onSubmit={submit} className="form" noValidate>
        <fieldset className="kind-pick">
          <legend>Quem você representa?</legend>
          {KINDS.map(([k, t, d]) => (
            <label key={k} className={`kind${f.v.kind === k ? " kind-on" : ""}`}>
              <input type="radio" name="kind" value={k} checked={f.v.kind === k} onChange={() => f.set("kind")(k)} />
              <span className="kind-title">{t}</span>
              <span className="kind-desc">{d}</span>
            </label>
          ))}
        </fieldset>
        <Field label="Seu nome"><Input autoComplete="name" value={f.v.full_name} onChange={f.set("full_name")} /></Field>
        <Field label="E-mail"><Input type="email" autoComplete="email" value={f.v.email} onChange={f.set("email")} /></Field>
        <Field label="Senha" hint="Mínimo de 10 caracteres. Use uma frase que você lembre."><Input type="password" autoComplete="new-password" value={f.v.password} onChange={f.set("password")} /></Field>
        <Field label={f.v.kind === "provider" ? "Nome do escritório ou profissional" : f.v.kind === "individual" ? "Nome de exibição interno" : "Razão social"}
          hint={f.v.kind === "individual" ? "Fica oculto às organizações, a menos que você escolha mostrá-lo no perfil." : undefined}><Input value={f.v.legal_name} onChange={f.set("legal_name")} /></Field>
        {f.v.kind === "osc" && <Field label="Natureza jurídica" hint="Declaração sua, sem verificação na criação da conta. Grupos sem registro formal escolhem “Coletivo”.">
          <Select value={f.v.legal_nature_code} onChange={f.set("legal_nature_code")} placeholder="Selecione" options={[["association", "Associação privada"], ["foundation", "Fundação privada"], ["cooperative", "Cooperativa"], ["religious_organization", "Organização religiosa"], ["collective", "Coletivo ou iniciativa em estruturação"], ["other", "Outra natureza"]]} /></Field>}
        <div className="row2">
          {f.v.kind !== "individual" && <Field label="CNPJ" hint={f.v.kind === "provider" ? "Opcional para profissionais autônomos" : f.v.kind === "osc" && f.v.legal_nature_code === "collective" ? "Opcional para coletivos sem personalidade jurídica" : "Obrigatório"}><Input inputMode="numeric" value={f.v.cnpj} onChange={f.set("cnpj")} /></Field>}
          <Field label="UF"><Select value={f.v.uf} onChange={f.set("uf")} placeholder="—" options={UFS.map((u) => [u, u])} /></Field>
        </div>
        <label className="check">
          <input type="checkbox" checked={f.v.accept_terms} onChange={(e: any) => f.set("accept_terms")(e.target.checked)} />
          <span>Li e aceito os <Link to="/legal/termos">Termos de uso</Link> e a <Link to="/legal/privacidade">Política de privacidade</Link>.</span>
        </label>
        {err && <p className="form-error" role="alert">{err}</p>}
        <Button type="submit" variant="primary" busy={busy}>Criar conta</Button>
      </form>
      <p className="auth-links"><Link to="/entrar">Já tenho conta</Link></p>
    </AuthFrame>
  );
}

export const UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];

function TokenPage({ title, path, okText, extra }: { title: string; path: string; okText: string; extra?: (token: string) => any }) {
  const { query } = useLocation();
  const token = query.get("token") || "";
  const [state, setState] = useState<"idle" | "ok" | "err">("idle");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    if (extra) return;
    api.post(path, { token }).then(() => setState("ok")).catch((e) => { setMsg(describeError(e)); setState("err"); });
  }, []);  // eslint-disable-line
  return (
    <AuthFrame title={title}>
      {extra ? extra(token) : state === "idle" ? <StateView loading /> : state === "ok" ? (
        <><p className="lead">{okText}</p><Button variant="primary" onClick={() => navigate("/")}>Continuar</Button></>
      ) : <p className="form-error" role="alert">{msg}</p>}
    </AuthFrame>
  );
}

export const VerifyEmail = () => <TokenPage title="Confirmação de e-mail" path="/v1/auth/verify-email" okText="E-mail confirmado. Todas as funções estão liberadas." />;

export function Forgot() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const { busy, run } = useAction();
  return (
    <AuthFrame title="Recuperar acesso">
      {sent ? <p className="lead">Se o e-mail estiver cadastrado, você receberá um link válido por 30 minutos.</p> : (
        <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/auth/forgot-password", { email })).then(() => setSent(true)); }}>
          <Field label="E-mail da conta"><Input type="email" value={email} onChange={setEmail} /></Field>
          <Button type="submit" variant="primary" busy={busy}>Enviar link</Button>
        </form>
      )}
    </AuthFrame>
  );
}

export function Reset() {
  const [pw, setPw] = useState("");
  const [ok, setOk] = useState(false);
  const { busy, run } = useAction();
  return (
    <TokenPage title="Nova senha" path="" okText="" extra={(token) => ok ? (
      <><p className="lead">Senha alterada. Por segurança, todas as sessões foram encerradas.</p><Button variant="primary" onClick={() => navigate("/entrar")}>Entrar</Button></>
    ) : (
      <form className="form" onSubmit={(e: any) => { e.preventDefault(); run(() => api.post("/v1/auth/reset-password", { token, password: pw })).then((r) => r && setOk(true)); }}>
        <Field label="Nova senha" hint="Mínimo de 10 caracteres"><Input type="password" autoComplete="new-password" value={pw} onChange={setPw} /></Field>
        <Button type="submit" variant="primary" busy={busy}>Salvar nova senha</Button>
      </form>
    )} />
  );
}

export function AcceptInvite() {
  const { me, reload } = useSession();
  const { query } = useLocation();
  const { busy, run } = useAction();
  if (!me) return (
    <AuthFrame title="Convite para equipe">
      <p className="lead">Entre ou crie sua conta com o e-mail que recebeu o convite para continuar.</p>
      <Button variant="primary" onClick={() => navigate(`/entrar?proximo=${encodeURIComponent("/convite?token=" + (query.get("token") || ""))}`)}>Entrar</Button>
    </AuthFrame>
  );
  return (
    <AuthFrame title="Convite para equipe">
      <p className="lead">Você está entrando como {me.user.email}.</p>
      <Button variant="primary" busy={busy} onClick={() => run(() => api.post("/v1/auth/accept-invite", { token: query.get("token") }), "Convite aceito").then(async (r) => { if (r) { await reload(); navigate("/"); } })}>Aceitar convite</Button>
    </AuthFrame>
  );
}

/** Renderiza Markdown simples (títulos, parágrafos, listas) como elementos React — sem HTML bruto (proteção XSS). */
export function MarkdownText({ text }: { text: string }) {
  const blocks: any[] = [];
  let list: string[] = [];
  const flush = () => { if (list.length) { blocks.push(<ul key={blocks.length}>{list.map((l, i) => <li key={i}>{l}</li>)}</ul>); list = []; } };
  for (const line of text.split("\n")) {
    if (/^\s*[-*] /.test(line)) { list.push(line.replace(/^\s*[-*] /, "")); continue; }
    flush();
    if (line.startsWith("### ")) blocks.push(<h3 key={blocks.length}>{line.slice(4)}</h3>);
    else if (line.startsWith("## ")) blocks.push(<h2 key={blocks.length}>{line.slice(3)}</h2>);
    else if (line.startsWith("# ")) blocks.push(<h1 key={blocks.length}>{line.slice(2)}</h1>);
    else if (line.trim()) blocks.push(<p key={blocks.length}>{line.replace(/\*\*/g, "")}</p>);
  }
  flush();
  return <div className="prose">{blocks}</div>;
}

export function Legal({ doc }: { doc: string }) {
  const [text, setText] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch(`/v1/legal/${doc}`).then((r) => (r.ok ? r.text() : Promise.reject(new Error("x")))).then(setText).catch(() => setErr("Documento indisponível."));
  }, [doc]);
  return (
    <main className="legal" id="conteudo">
      <Link to="/" className="brand"><span className="brand-mark" aria-hidden="true" />Impacto</Link>
      <StateView loading={text === null && !err} error={err}>{text && <MarkdownText text={text} />}</StateView>
    </main>
  );
}
