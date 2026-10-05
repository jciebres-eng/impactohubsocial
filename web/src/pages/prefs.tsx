import { useEffect, useState } from "react";
import { api } from "../api";
import { Button, Field, PageHead, Panel, Select, StateView, useAction, useLoad } from "../ui/kit";

// Tema e idioma. O tema é aplicado no atributo data-theme do <html>, que o styles.css já respeita.
const THEMES: [string, string][] = [["system", "Seguir o sistema"], ["light", "Claro"], ["dark", "Escuro"]];
const KEY = "impacto.theme";

export function applyTheme(theme: string) {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.setAttribute("data-theme", theme);
  else root.removeAttribute("data-theme");
  try { localStorage.setItem(KEY, theme); } catch { /* modo privado: só não guarda */ }
}

export function bootTheme() {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved) applyTheme(saved);
  } catch { /* ignora */ }
}

export function Preferences({ standalone }: { standalone?: boolean } = {}) {
  const { data, error, loading, reload } = useLoad<any>("/v1/me/preferences");
  const { data: locales } = useLoad<any>("/v1/public/locales");
  const { busy, run } = useAction();
  const [theme, setTheme] = useState("system");
  const [locale, setLocale] = useState("pt-BR");

  useEffect(() => {
    if (data) { setTheme(data.theme || "system"); setLocale(data.locale || "pt-BR"); applyTheme(data.theme || "system"); }
  }, [data]);

  async function save() {
    await run(async () => {
      await api.put("/v1/me/preferences", { theme, locale });
      applyTheme(theme);
      reload();
      return "Preferências salvas.";
    });
  }

  const current = locales?.items?.find((l: any) => l.code === locale);
  return (
    <StateView loading={loading} error={error} onRetry={reload}>
      {standalone && <PageHead title="Aparência e idioma" sub="Vale para esta conta, em qualquer aparelho." />}
      <Panel title="Aparência e idioma">
        <Field label="Tema" hint="“Seguir o sistema” usa a preferência do seu aparelho.">
          <Select value={theme} onChange={(v) => { setTheme(v); applyTheme(v); }} options={THEMES} />
        </Field>
        <Field label="Idioma" hint={current?.coverage_note}>
          <Select value={locale} onChange={setLocale}
                  options={(locales?.items || []).map((l: any) => [l.code, l.native_name] as [string, string])} />
        </Field>
        <Button variant="primary" busy={busy} onClick={save}>Salvar</Button>
        {locales?.note && <p className="muted small">{locales.note}</p>}
      </Panel>
    </StateView>
  );
}

// Perguntado uma vez, logo depois do primeiro acesso (prefs_set_at ainda nulo).
export function FirstRunPreferences({ onDone }: { onDone: () => void }) {
  const { data: locales } = useLoad<any>("/v1/public/locales");
  const { busy, run } = useAction();
  const [theme, setTheme] = useState("system");
  const [locale, setLocale] = useState("pt-BR");
  return (
    <Panel title="Como você prefere usar a plataforma?">
      <p>Duas escolhas rápidas. Você pode mudar depois em Conta.</p>
      <Field label="Tema"><Select value={theme} onChange={(v) => { setTheme(v); applyTheme(v); }} options={THEMES} /></Field>
      <Field label="Idioma">
        <Select value={locale} onChange={setLocale}
                options={(locales?.items || []).map((l: any) => [l.code, l.native_name] as [string, string])} />
      </Field>
      <Button variant="primary" busy={busy}
              onClick={() => run(async () => {
                await api.put("/v1/me/preferences", { theme, locale });
                applyTheme(theme); onDone();
                return "Pronto.";
              })}>Continuar</Button>
    </Panel>
  );
}
