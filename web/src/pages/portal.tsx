// /portal — a entrada que RESOLVE em vez de perguntar.
//
// O DEFEITO QUE ISTO CORRIGE
//
// Havia uma tela inicial por tipo de organização, escolhida no frontend, e a pessoa com mais de um
// vínculo (consultora que atende três OSCs, servidora que também é apoiadora, alguém da equipe
// interna que tem a própria organização) caía sempre na mesma e tinha de se achar no menu.
//
// A CADEIA É DECIDIDA NO SERVIDOR
//
// quem entra → organização → perfil → função → plano → recursos → situação financeira →
// operações → painel. O endereço final vem de `GET /v1/me/context` (`dashboard`), que é a mesma
// autoridade que decide o acesso. O frontend aqui MOSTRA a decisão e deixa trocar de contexto; ele
// não recalcula nada — recalcular seria criar uma segunda regra para discordar da primeira.
import { useEffect } from "react";
import { api } from "../api";
import { navigate } from "../router";
import { Button, Panel, Pill, StateView, useAction } from "../ui/kit";
import { useAccess } from "../access";
import { useSession } from "../session";

const PERFIL: Record<string, string> = { osc: "Organização da sociedade civil", company: "Empresa", individual: "Apoiador", provider: "Profissional", government: "Governo", platform: "Administração da plataforma" };
const FUNCAO: Record<string, string> = { owner: "Proprietária", admin: "Administração", manager: "Gestão", analyst: "Análise", member: "Participação", viewer: "Leitura" };
const ESTADO_COMERCIAL: Record<string, [string, string]> = {
  free_period: ["Período gratuito", "good"], trial: ["Em teste", "good"], active: ["Assinatura ativa", "good"],
  pending_authorization: ["Aguardando autorização de cobrança", "warn"], past_due: ["Pagamento em atraso", "bad"],
  suspended: ["Suspensa", "bad"], none: ["Sem contratação", "muted"],
};

export function Portal() {
  const { me } = useSession();
  const { ctx, loading, reload } = useAccess();
  const { busy, run } = useAction();

  // Com UM vínculo e nada a decidir, não há portal a mostrar: a pessoa vai direto ao painel.
  useEffect(() => {
    if (!ctx) return;
    const umSo = (me?.organizations.length || 0) <= 1;
    if (umSo && ctx.organization) navigate(ctx.dashboard, true);
  }, [ctx, me]);

  if (loading || !ctx) return <div className="boot"><StateView loading /></div>;

  const org = ctx.organization;
  const [rotuloComercial, tomComercial] = ESTADO_COMERCIAL[ctx.commercial.state || "none"] || [ctx.commercial.state || "—", "muted"];
  const cadeia: [string, React.ReactNode][] = [
    ["Quem está entrando", <>{me?.user.full_name} <span className="muted">· {ctx.user.email}</span></>],
    ["Organização", org ? <>{org.name}</> : <span className="muted">nenhuma organização ainda</span>],
    ["Perfil", org ? PERFIL[org.kind] || org.kind : "—"],
    ["Função", org ? FUNCAO[org.role] || org.role : "—"],
    ["Plano", ctx.commercial.plans.length ? ctx.commercial.plans.join(", ") : <span className="muted">nenhum plano contratado</span>],
    ["Recursos liberados", `${ctx.entitlements.features.includes("*") ? "todos" : ctx.entitlements.features.length} recurso(s)`],
    ["Situação financeira", <Pill tone={tomComercial}>{rotuloComercial}</Pill>],
    ["Papéis internos", ctx.staff.roles.length ? ctx.staff.roles.join(", ") : <span className="muted">nenhum</span>],
    ["Painel", <code>{ctx.dashboard}</code>],
  ];

  return (
    <div className="portal">
      <h1>Entrar no Impacto</h1>
      <p className="muted">O servidor resolveu seu acesso. Esta tela mostra a decisão; você pode trocar de contexto antes de entrar.</p>
      <div className="stack-lg">
        <Panel title="Como seu acesso foi resolvido">
          <ol className="chain">
            {cadeia.map(([rotulo, valor]) => (
              <li key={rotulo}><span className="chain-label">{rotulo}</span><span className="chain-value">{valor}</span></li>
            ))}
          </ol>
        </Panel>

        {(me?.organizations.length || 0) > 1 && (
          <Panel title="Trocar de contexto">
            <p className="muted">Você participa de mais de uma organização. O acesso, o plano e o painel mudam com a escolha.</p>
            <ul className="rows">
              {me!.organizations.map((o) => (
                <li key={o.id}>
                  <span><strong>{o.trade_name || o.legal_name}</strong>
                    <div className="muted">{PERFIL[o.kind] || o.kind} · {FUNCAO[o.role] || o.role}</div></span>
                  {o.id === org?.id
                    ? <Pill tone="good">Contexto atual</Pill>
                    : <Button variant="ghost" busy={busy}
                        onClick={() => run(() => api.post("/v1/me/switch-org", { org_id: o.id }), "Contexto trocado").then(async () => { await reload(); })}>
                        Usar esta
                      </Button>}
                </li>
              ))}
            </ul>
          </Panel>
        )}

        {ctx.commercial.free_period_end && (
          <Panel title="Período gratuito" quiet>
            <p>Seu período gratuito vai até <strong>{ctx.commercial.free_period_end}</strong>. Nenhuma cobrança acontece sem sua autorização expressa
              {ctx.commercial.charge_authorized ? ", e você já autorizou." : ", e você ainda não autorizou."}</p>
          </Panel>
        )}

        {ctx.staff.roles.length > 0 && ctx.menu.length > 0 && (
          <Panel title="Suas áreas internas">
            <p className="muted">
              O menu interno vem do servidor, derivado das suas permissões: o que não aparece aqui também não passa pela porta da API.
              {ctx.staff.read_only && " Seus papéis são apenas de leitura — nenhuma área oferece alteração."}
            </p>
            <ul className="bullets">
              {ctx.menu.map((g) => <li key={g.group}><strong>{g.group}:</strong> {g.items.map((i) => i.label).join(" · ")}</li>)}
            </ul>
          </Panel>
        )}

        <div className="stack-row">
          <Button variant="ink" onClick={() => navigate(ctx.dashboard)}>Entrar{org ? ` como ${PERFIL[org.kind] || org.kind}` : ""}</Button>
          {!org && <Button variant="ghost" onClick={() => navigate("/organizacao/nova")}>Criar organização</Button>}
        </div>

        {typeof ctx.entitlements.limits?.ai_monthly === "number" && (
          <p className="muted">Limite de IA do seu plano: {ctx.entitlements.limits.ai_monthly} chamadas por mês.</p>
        )}
      </div>
    </div>
  );
}
