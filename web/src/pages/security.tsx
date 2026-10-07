/**
 * CENTRO DE SEGURANÇA DA CONTA e PAINEL DE IA.
 *
 * Duas telas que a v0.23.0 acrescentou porque as informações passaram a existir e não tinham onde
 * aparecer. Antes desta versão: sessões ficavam numa rota que nenhuma tela consumia, eventos de
 * segurança do próprio titular não eram acessíveis a ele, e `GET /v1/ai/usage` devolvia três
 * números que nenhum componente leu.
 *
 * DECISÃO DE DESENHO
 *
 * Nenhuma das duas telas usa cor como único sinal. Evento grave aparece com a palavra "atenção"
 * escrita, não só em vermelho — quem está conferindo um acesso suspeito pode estar num celular ao
 * sol, e um daltônico não deve precisar adivinhar. A mesma regra vale para o estado do orçamento.
 */
import { useState } from "react";
import { Button, KeyValue, Panel, PageHead, Pill, StateView, useAction, useLoad } from "../ui/kit";
import { api } from "../api";
import { dateTime, money } from "../format";

function Linha({ children }: { children: React.ReactNode }) {
  return <div className="form-grid">{children}</div>;
}

/** Rótulo em palavras para gravidade. Cor acompanha; nunca substitui. */
function Gravidade({ nivel, estado }: { nivel: string; estado?: string }) {
  const tom = nivel === "critical" ? "danger" : nivel === "warning" ? "warn" : "muted";
  const texto = nivel === "critical" ? "crítico" : nivel === "warning" ? "atenção" : "informação";
  return (
    <>
      <Pill tone={tom}>{texto}</Pill>
      {estado && estado !== "success" && (
        <Pill tone="warn">{estado === "denied" ? "recusado" : "falhou"}</Pill>
      )}
    </>
  );
}

export function CentroDeSeguranca() {
  const { data, error, loading, reload } = useLoad<any>("/v1/me/security");
  const { run, busy } = useAction();

  async function revogar(id: string) {
    await run(async () => {
      await api.del(`/v1/auth/sessions/${id}`);
      await reload();
    }, "Sessão revogada.");
  }

  return (
    <>
      <PageHead
        title="Segurança da conta"
        sub="Sessões abertas, segundo fator, eventos recentes e mudanças no seu acesso."
      />
      <StateView loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            {data.attention.length > 0 && (
              <Panel title={`Precisa de atenção (${data.attention.length})`}>
                <p className="note">
                  Eventos de gravidade alta ou operações recusadas na sua conta. Se você não
                  reconhece algum, troque a senha e revogue as sessões abertas.
                </p>
                <table className="table">
                  <thead>
                    <tr><th>Quando</th><th>O que</th><th>Gravidade</th><th>Origem</th></tr>
                  </thead>
                  <tbody>
                    {data.attention.map((e: any) => (
                      <tr key={e.id}>
                        <td>{dateTime(e.at)}</td>
                        <td>{e.action}</td>
                        <td><Gravidade nivel={e.severity} estado={e.status} /></td>
                        <td className="mono small">{e.ip || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}

            <Panel title="Sua conta">
              <KeyValue
                items={[
                  ["E-mail", data.account.email],
                  [
                    "Segundo fator (MFA)",
                    data.account.mfa_enabled ? (
                      <Pill tone="ok">ativo</Pill>
                    ) : (
                      <>
                        <Pill tone="warn">desligado</Pill>{" "}
                        <a href="/conta/preferencias">ligar agora</a>
                      </>
                    ),
                  ],
                  [
                    "Códigos de recuperação restantes",
                    data.account.mfa_enabled ? String(data.account.recovery_codes_left) : "—",
                  ],
                  ["Último acesso", data.account.last_login_at ? dateTime(data.account.last_login_at) : "—"],
                  ["Tentativas de entrada falhas", String(data.account.failed_login_count)],
                  ["Conta bloqueada", data.account.locked ? <Pill tone="danger">sim</Pill> : "não"],
                  ["E-mail confirmado", data.account.email_verified_at ? dateTime(data.account.email_verified_at) : <Pill tone="warn">não</Pill>],
                ]}
              />
            </Panel>

            <Panel title={`Sessões (${data.sessions.active} abertas)`}>
              <p className="note">{data.session_limits.note}</p>
              <table className="table">
                <thead>
                  <tr><th>Dispositivo</th><th>Origem</th><th>Última atividade</th><th>Estado</th><th /></tr>
                </thead>
                <tbody>
                  {data.sessions.items.map((s: any) => (
                    <tr key={s.id}>
                      <td className="small">{s.user_agent || "não informado"}</td>
                      <td className="mono small">{s.ip || "—"}</td>
                      <td>{s.last_seen_at ? dateTime(s.last_seen_at) : dateTime(s.created_at)}</td>
                      <td>
                        {s.current && <Pill tone="ok">esta sessão</Pill>}
                        {!s.current && !s.revoked_at && <Pill>aberta</Pill>}
                        {s.revoked_at && <Pill tone="muted">encerrada{s.revoke_reason ? ` · ${s.revoke_reason}` : ""}</Pill>}
                        {!s.revoked_at && !s.mfa_verified && data.account.mfa_enabled && (
                          <Pill tone="warn">sem segundo fator</Pill>
                        )}
                      </td>
                      <td>
                        {!s.current && !s.revoked_at && (
                          <Button variant="ghost" disabled={busy} onClick={() => revogar(s.id)}>
                            Encerrar
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            {data.access_changes.length > 0 && (
              <Panel title="Mudanças no seu acesso">
                <p className="note">
                  Alterações de papel, senha ou segundo fator feitas sobre a sua conta — inclusive
                  por administradores da organização. Você tem direito de saber quando o seu acesso
                  muda; quem fez a mudança não aparece aqui.
                </p>
                <table className="table">
                  <thead><tr><th>Quando</th><th>O que</th><th>Gravidade</th></tr></thead>
                  <tbody>
                    {data.access_changes.map((e: any) => (
                      <tr key={e.id}>
                        <td>{dateTime(e.at)}</td>
                        <td>{e.action}</td>
                        <td><Gravidade nivel={e.severity} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}

            <Panel title="Atividade recente" quiet>
              <table className="table">
                <thead><tr><th>Quando</th><th>Área</th><th>O que</th><th>Origem</th></tr></thead>
                <tbody>
                  {data.recent_events.map((e: any) => (
                    <tr key={e.id}>
                      <td>{dateTime(e.at)}</td>
                      <td><Pill tone="muted">{e.category}</Pill></td>
                      <td>
                        {e.action}
                        {e.resource_name && <span className="small"> · {e.resource_name}</span>}
                      </td>
                      <td className="mono small">{e.ip || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>

            <Panel title="Integrações e credenciais" quiet>
              {!data.api_keys_available && (
                <p className="note">
                  Esta instalação não emite chaves de API. Não há credencial de longa duração
                  associada à sua organização — o acesso é sempre por sessão, que vence.
                </p>
              )}
              {data.integrations.length === 0 ? (
                <p className="note">Nenhuma integração externa conectada.</p>
              ) : (
                <table className="table">
                  <thead><tr><th>Provedor</th><th>Ambiente</th><th>Estado</th><th>Último sucesso</th></tr></thead>
                  <tbody>
                    {data.integrations.map((i: any) => (
                      <tr key={i.id}>
                        <td>{i.name || i.provider}</td>
                        <td><Pill tone="muted">{i.environment}</Pill></td>
                        <td><Pill status={i.status}>{i.status}</Pill></td>
                        <td>{i.last_success_at ? dateTime(i.last_success_at) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
            <p className="note">{data.note}</p>
          </>
        )}
      </StateView>
    </>
  );
}

/* ------------------------------------------------------------------ painel de IA da organização */

function EstadoOrcamento({ b }: { b: any }) {
  if (!b || b.state === "no_budget") {
    return <Pill tone="muted">sem orçamento definido</Pill>;
  }
  const rotulo =
    b.state === "exceeded" ? "limite atingido" : b.state === "warning" ? "perto do limite" : "dentro do limite";
  const tom = b.state === "exceeded" ? "danger" : b.state === "warning" ? "warn" : "ok";
  return (
    <>
      <Pill tone={tom}>{rotulo}</Pill>
      {b.hard_stop ? <Pill tone="muted">para ao atingir</Pill> : <Pill tone="muted">apenas avisa</Pill>}
    </>
  );
}

export function PainelDeIa() {
  const uso = useLoad<any>("/v1/ai/usage");
  const pol = useLoad<any>("/v1/ai/policies");
  const { run, busy } = useAction();
  const [limite, setLimite] = useState("");
  const [parar, setParar] = useState(false);

  async function salvar() {
    const centavos = Math.round(parseFloat(limite.replace(",", ".")) * 100);
    if (!centavos || centavos < 100) return;
    await run(async () => {
      await api.put("/v1/ai/budget", { limit_cents: centavos, hard_stop: parar });
      await uso.reload();
    }, "Orçamento de IA definido.");
  }

  return (
    <>
      <PageHead
        title="Inteligência artificial"
        sub="Como a assistência por IA é usada nesta organização, quanto custa e o que a plataforma garante."
      />
      <StateView loading={uso.loading} error={uso.error} onRetry={uso.reload}>
        {uso.data && (
          <>
            <Panel title="Três controles diferentes">
              <p className="note">{uso.data.note}</p>
              <div className="metrics">
                <div className="metric">
                  <span className="metric-label">Cota do plano</span>
                  <p className="metric-value">
                    {uso.data.quota.used_this_month}
                    {uso.data.quota.limit != null && <span className="small"> de {uso.data.quota.limit}</span>}
                  </p>
                  <p className="small">chamadas neste mês</p>
                </div>
                <div className="metric">
                  <span className="metric-label">Orçamento</span>
                  <p className="metric-value">
                    {uso.data.budget && uso.data.budget.limit_cents != null
                      ? money(uso.data.budget.spent_cents || 0, "BRL")
                      : "—"}
                  </p>
                  <p className="small">
                    <EstadoOrcamento b={uso.data.budget} />
                  </p>
                </div>
                <div className="metric">
                  <span className="metric-label">Crédito</span>
                  <p className="metric-value">{uso.data.credits.balance}</p>
                  <p className="small">{uso.data.credits.note}</p>
                </div>
              </div>
              {uso.data.budget && uso.data.budget.unpriced_calls > 0 && (
                <p className="note">
                  {uso.data.budget.unpriced_calls} chamada(s) deste mês não têm preço vigente na
                  tabela do provedor e por isso <strong>não entram no gasto apurado</strong>. O
                  número de gasto mede menos do que o uso real.
                </p>
              )}
            </Panel>

            <Panel title="Definir orçamento do mês">
              <Linha>
                <label>
                  Limite em reais
                  <input
                    className="input"
                    inputMode="decimal"
                    value={limite}
                    onChange={(ev: React.ChangeEvent<HTMLInputElement>) => setLimite(ev.target.value)}
                    placeholder="500,00"
                  />
                </label>
                <label className="check">
                  <input type="checkbox" checked={parar} onChange={(ev: React.ChangeEvent<HTMLInputElement>) => setParar(ev.target.checked)} />
                  Parar as chamadas ao atingir o limite
                </label>
                <Button onClick={salvar} disabled={busy || !limite}>Salvar</Button>
              </Linha>
              <p className="note">
                Sem marcar a opção acima, o limite apenas avisa e o trabalho continua. A plataforma
                não interrompe o seu trabalho sem você pedir.
              </p>
            </Panel>

            <Panel title="Como as chamadas terminaram (30 dias)">
              {uso.data.outcomes_30d.length === 0 ? (
                <p className="note">Nenhuma chamada de IA nos últimos 30 dias.</p>
              ) : (
                <table className="table">
                  <thead><tr><th>Resultado</th><th>Chamadas</th><th>Tokens</th></tr></thead>
                  <tbody>
                    {uso.data.outcomes_30d.map((o: any) => (
                      <tr key={o.status}>
                        <td>{RESULTADO[o.status] || o.status}</td>
                        <td>{o.calls}</td>
                        <td>{o.tokens || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="note">
                “Processado localmente” significa que o resultado veio dos motores desta instalação,
                sem envio a provedor externo. É o comportamento padrão quando nenhum provedor
                externo está configurado.
              </p>
            </Panel>

            {uso.data.prompt_versions_30d.length > 0 && (
              <Panel title="Qual instrução processou o seu dado" quiet>
                <p className="note">
                  Cada chamada registra a versão da instrução usada. É isso que permite explicar
                  uma resposta depois — inclusive uma de meses atrás.
                </p>
                <table className="table">
                  <thead><tr><th>Instrução</th><th>Versão</th><th>Faixa de risco</th><th>Chamadas</th></tr></thead>
                  <tbody>
                    {uso.data.prompt_versions_30d.map((p: any) => (
                      <tr key={`${p.prompt_key}-${p.prompt_version}`}>
                        <td className="mono small">{p.prompt_key}</td>
                        <td>v{p.prompt_version}</td>
                        <td>{p.tier}</td>
                        <td>{p.calls}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}
          </>
        )}
      </StateView>

      <StateView loading={pol.loading} error={pol.error} onRetry={pol.reload}>
        {pol.data && (
          <>
            <Panel title="O que a plataforma garante">
              <ul className="list-plain">
                {pol.data.guarantees.map((g: string) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </Panel>
            <Panel title="Faixas de risco" quiet>
              <p className="note">{pol.data.note}</p>
              <table className="table">
                <thead>
                  <tr><th>Faixa</th><th>Uso</th><th>Sai da instalação?</th><th>Revisão humana</th></tr>
                </thead>
                <tbody>
                  {pol.data.tiers.map((t: any) => (
                    <tr key={t.tier}>
                      <td>{t.tier}</td>
                      <td>
                        {t.label}
                        <div className="small">{t.note}</div>
                      </td>
                      <td>
                        {t.allow_external ? <Pill tone="warn">pode sair</Pill> : <Pill tone="ok">não sai</Pill>}
                      </td>
                      <td>{t.requires_human_review ? <Pill tone="ok">obrigatória</Pill> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
          </>
        )}
      </StateView>
    </>
  );
}

const RESULTADO: Record<string, string> = {
  ok: "Provedor externo respondeu e a resposta foi usada",
  local_only: "Processado localmente (sem provedor externo configurado)",
  fallback_local: "Provedor externo falhou; processado localmente",
  invalid_output: "Provedor respondeu fora do formato e a resposta foi descartada",
  blocked_policy: "Recusado pela política da faixa de risco",
  quota_exceeded: "Cota do plano atingida",
  budget_exceeded: "Orçamento atingido",
  provider_error: "Erro do provedor",
  rejected: "Recusado",
};
