import { useState } from "react";
import { api } from "../api";
import { money } from "../format";
import { Link } from "../router";
import { Button, Field, Input, PageHead, Select, StateView, useAction, useLoad } from "../ui/kit";

/** Rótulos dos estados comerciais. O backend manda o código; a tela nomeia.
 *
 * A lista espelha `free_period.STATES` no servidor. Um estado novo que chegue aqui sem rótulo
 * aparece pelo código, e não como texto vazio — ver `rotulo()` abaixo. */
const ESTADO: Record<string, string> = {
  FREE: "Gratuito",
  FREE_EXPIRING: "Gratuito — terminando",
  PAYMENT_METHOD_REQUIRED: "Gratuito — falta autorizar cobrança",
  COMMERCIAL_TERM_PENDING: "Termo comercial pendente",
  PAID_ACTIVE: "Assinatura ativa",
  CANCELLED: "Cancelada",
  SUSPENDED: "Suspensa",
  PAST_DUE: "Pagamento em atraso",
  GRACE_PERIOD: "Período de carência",
  TERMINATED: "Encerrada",
};

const rotulo = (estado: string) => ESTADO[estado] ?? estado;

const dataLonga = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric", timeZone: "America/Sao_Paulo" }) : "—";

/** Contagem regressiva do período gratuito.
 *
 * O número de dias e a data vêm PRONTOS do backend (`free_period_end`, `days_remaining`). A tela
 * não subtrai datas: o fuso comercial é America/Sao_Paulo, o navegador está em qualquer lugar, e
 * uma conta feita aqui discordaria da cobrança exatamente na virada — que é quando a pessoa olha. */
export function FreePeriodBanner() {
  const st = useLoad<any>("/v1/commercial/state");
  const s = st.data;
  if (!s?.free_period_end) return null;
  const urgente = s.days_remaining != null && s.days_remaining <= 30;
  return (
    <div className={urgente ? "banner banner-warning" : "banner"}>
      <strong>Período gratuito até {dataLonga(s.free_period_end)}</strong>
      {s.days_remaining != null && <> · faltam {s.days_remaining} dia{s.days_remaining === 1 ? "" : "s"}</>}
      <p className="muted">{s.on_expiry}</p>
      {!s.charge_authorized && (
        <p className="muted small">
          Você não precisa fazer nada: sem autorização de cobrança, a conta volta ao plano gratuito e nenhum dado é apagado.
        </p>
      )}
    </div>
  );
}

/** Página pública de preços. Lê o catálogo do servidor; nenhum valor mora nesta tela. */
export function Pricing() {
  const plans = useLoad<any>("/v1/plans");
  const [interval, setInterval_] = useState<"month" | "year">("month");
  return (
    <div className="public-page">
      <PageHead title="Planos e preços" sub="O núcleo da plataforma é gratuito. O que se paga é capacidade, automação e suporte." />
      <div className="row">
        <Button variant={interval === "month" ? "ink" : "ghost"} onClick={() => setInterval_("month")}>Mensal</Button>
        <Button variant={interval === "year" ? "ink" : "ghost"} onClick={() => setInterval_("year")}>Anual</Button>
      </div>
      <StateView loading={plans.loading} error={plans.error} onRetry={plans.reload}>
        <div className="plan-grid">
          {(plans.data?.items || []).filter((p: any) => p.available !== false).map((p: any) => {
            const cents = p.prices?.[interval];
            const piso = p.quote_floor_cents;
            return (
              <article key={p.plan_key} className="plan-card">
                <h3>{p.name}</h3>
                {p.tier === "free" ? (
                  <p className="plan-price">Gratuito<span className="muted small"> — sem prazo</span></p>
                ) : cents != null ? (
                  <p className="plan-price">{money(cents, "BRL")} / {interval === "year" ? "ano" : "mês"}</p>
                ) : piso != null ? (
                  <p className="plan-price">a partir de {money(piso, "BRL")} / mês<span className="muted small"> — sob proposta</span></p>
                ) : (
                  <p className="plan-price muted">Preço não divulgado</p>
                )}
                {cents != null && <p className="muted small">Tributos ainda não definidos para este valor.</p>}
                <ul className="plan-features">
                  {(p.features || []).slice(0, 8).map((f: string) => <li key={f}>{f}</li>)}
                </ul>
                {cents == null && piso != null
                  ? <a className="btn btn-ghost" href="mailto:comercial@impacto.app">Solicitar proposta</a>
                  : <Link to="/cadastro" className="btn btn-ink">Começar gratuitamente</Link>}
              </article>
            );
          })}
        </div>
      </StateView>
      {/* A frase mais importante desta página, e a que mais custa dizer: o que o dinheiro NÃO compra. */}
      <section className="plan-note">
        <h2>O que nenhum plano compra</h2>
        <p>
          Reputação, selo de verificação, impacto, evidência, elegibilidade a edital e qualidade de match não estão à
          venda em nenhum plano. Pagar aumenta capacidade, volume, automação e suporte — e nada além disso.
        </p>
      </section>
    </div>
  );
}

/** Consumo do período, alertas e teto de gasto. */
export function Usage() {
  const uso = useLoad<any>("/v1/commercial/usage");
  const { busy, run } = useAction();
  const [limite, setLimite] = useState("");
  const [acao, setAcao] = useState<"warn" | "hard_stop">("warn");
  const u = uso.data;
  const salvar = () =>
    run(() => api.put("/v1/commercial/spend-limit", {
      limit_cents: limite.trim() === "" ? null : Math.round(Number(limite.replace(",", ".")) * 100),
      action: acao,
    })).then(() => uso.reload());
  return (
    <>
      <PageHead title="Consumo" sub="Quanto do seu plano você já usou neste mês." />
      <StateView loading={uso.loading} error={uso.error} onRetry={uso.reload}>
        <p className="banner">{u?.overage_policy}</p>
        <table className="table">
          <thead><tr><th>Recurso</th><th>Usado</th><th>Limite</th><th>Percentual</th></tr></thead>
          <tbody>
            {(u?.metrics || []).map((m: any) => (
              <tr key={m.metric} className={m.percent != null && m.percent >= 90 ? "row-warn" : undefined}>
                <td>{m.label}</td>
                <td>{m.used}</td>
                <td>{m.limit == null ? "Ilimitado" : m.limit}</td>
                <td>{m.percent == null ? "—" : `${m.percent}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted small">
          Avisamos quando você chega a {(u?.thresholds || []).join("%, ")}% do limite. Atingir o limite interrompe o
          excedente — não gera cobrança.
        </p>

        <h2>Teto de gasto mensal</h2>
        <p className="muted">
          Gasto do mês: {money(u?.spent_cents ?? 0, "BRL")}
          {u?.spend_limit?.limit_cents != null && <> · teto definido: {money(u.spend_limit.limit_cents, "BRL")}</>}
        </p>
        <Field label="Teto em reais" hint="Deixe em branco para não ter teto.">
          <Input value={limite} onChange={setLimite} placeholder="500,00" inputMode="decimal" />
        </Field>
        <Field label="Ao atingir o teto">
          <Select value={acao} onChange={(v) => setAcao(v as any)} options={[
            ["warn", "Avisar e continuar"],
            ["hard_stop", "Parar o consumo"],
          ]} />
        </Field>
        <Button onClick={salvar} busy={busy}>Salvar teto</Button>
      </StateView>
    </>
  );
}

/** Oferta, aceite e autorização de cobrança — os dois atos, separados na tela como estão no banco. */
export function Commercial() {
  const st = useLoad<any>("/v1/commercial/state");
  const ofertas = useLoad<any>("/v1/commercial/offers");
  const aceites = useLoad<any>("/v1/commercial/acceptances");
  const { busy, run } = useAction();
  const s = st.data;
  const recarregar = () => { st.reload(); ofertas.reload(); aceites.reload(); };
  const aceitar = (id: string, consent: "free_access" | "authorized") =>
    run(() => api.post(`/v1/commercial/offers/${id}/accept`, { consent_status: consent })).then(recarregar);
  const revogar = () =>
    run(() => api.post("/v1/commercial/consent/revoke", { reason: "revogado pela organização na tela de cobrança" })).then(recarregar);
  return (
    <>
      <PageHead title="Situação comercial" sub={s ? rotulo(s.state) : undefined} />
      <StateView loading={st.loading} error={st.error} onRetry={recarregar}>
        <FreePeriodBanner />

        <section>
          <h2>Autorização de cobrança</h2>
          <p>
            {s?.charge_authorized
              ? "Esta conta autorizou a cobrança. A primeira fatura sai no fim do período gratuito."
              : "Esta conta NÃO autorizou nenhuma cobrança. Nada será debitado."}
          </p>
          {/* Dito em palavras porque é a distinção que o produto inteiro protege. */}
          <p className="muted small">
            Aceitar acesso gratuito e autorizar cobrança são atos diferentes. Aceitar os termos para usar a plataforma
            de graça não autoriza nenhum débito.
          </p>
          {s?.charge_authorized && <Button variant="ghost" onClick={revogar} busy={busy}>Revogar autorização</Button>}
        </section>

        <section>
          <h2>Períodos gratuitos desta conta</h2>
          {(s?.periods || []).length === 0 ? <p className="muted">Nenhum período gratuito registrado.</p> : (
            <table className="table">
              <thead><tr><th>Origem</th><th>De</th><th>Até</th><th>Situação</th><th>Motivo</th></tr></thead>
              <tbody>
                {s.periods.map((p: any, i: number) => (
                  <tr key={i}>
                    <td>{p.source}</td><td>{dataLonga(p.started_at)}</td><td>{dataLonga(p.ends_at)}</td>
                    <td>{p.status}</td><td className="muted small">{p.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section>
          <h2>Ofertas</h2>
          {(ofertas.data?.items || []).length === 0 ? <p className="muted">Nenhuma oferta aberta.</p> : (
            <table className="table">
              <thead><tr><th>Plano</th><th>Valor</th><th>Cobrança</th><th>Meio</th><th>Situação</th><th /></tr></thead>
              <tbody>
                {ofertas.data.items.map((o: any) => (
                  <tr key={o.id}>
                    <td>{o.plan_key}</td>
                    <td>{money(o.amount_cents, o.currency)}</td>
                    <td>{o.billing_frequency === "installment" ? `Parcelado em ${o.installments}x` : o.billing_frequency === "recurring" ? "Recorrente" : "Única"}</td>
                    <td>{o.payment_method}</td>
                    <td>{o.status}</td>
                    <td>
                      {o.status === "open" && (
                        <div className="row">
                          <Button variant="ghost" onClick={() => aceitar(o.id, "free_access")} busy={busy}>Aceitar acesso</Button>
                          <Button onClick={() => aceitar(o.id, "authorized")} busy={busy}>Autorizar cobrança</Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section>
          <h2>Aceites registrados</h2>
          {(aceites.data?.items || []).length === 0 ? <p className="muted">Nenhum aceite registrado.</p> : (
            <table className="table">
              <thead><tr><th>Quando</th><th>Tipo</th><th>Plano</th><th>Termos</th><th>Revogado</th></tr></thead>
              <tbody>
                {aceites.data.items.map((a: any) => (
                  <tr key={a.id}>
                    <td>{dataLonga(a.accepted_at)}</td>
                    <td>{a.consent_status === "authorized" ? "Autorização de cobrança" : "Acesso gratuito"}</td>
                    <td>{a.plan_key}</td>
                    <td className="small">{a.terms_version} · {a.privacy_version}</td>
                    <td className="small">{a.revoked_at ? `${dataLonga(a.revoked_at)} — ${a.revoke_reason}` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </StateView>
    </>
  );
}
