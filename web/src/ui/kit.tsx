import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, describeError } from "../api";
import { label as statusLabel } from "../format";

// ------------------------------------------------------------------------------------------- dados
export function useLoad<T = any>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<T>(path));
    } catch (e) {
      setError(describeError(e));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload, setData };
}

let taxonomyCache: any = null;
export function useTaxonomy() {
  const [tax, setTax] = useState<any>(taxonomyCache);
  useEffect(() => {
    if (!taxonomyCache) api.get("/v1/meta/taxonomy").then((t) => setTax((taxonomyCache = t))).catch(() => {});
  }, []);
  return tax;
}

// ------------------------------------------------------------------------------------------- feedback
type Toast = { id: number; text: string; tone: "ok" | "err" };
const ToastCtx = createContext<(text: string, tone?: "ok" | "err") => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: "ok" | "err" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((x) => [...x, { id, text, tone }]);
    setTimeout(() => setItems((x) => x.filter((t) => t.id !== id)), tone === "err" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

/** Executa uma ação com estado de "ocupado", toast de sucesso e mensagem de erro clara. */
export function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = useCallback(async <T,>(fn: () => Promise<T>, success?: string): Promise<T | undefined> => {
    setBusy(true);
    try {
      const r = await fn();
      if (success) toast(success);
      return r;
    } catch (e) {
      toast(describeError(e), "err");
      return undefined;
    } finally {
      setBusy(false);
    }
  }, [toast]);
  return { busy, run };
}

export function StateView({ loading, error, empty, onRetry, children }: {
  loading?: boolean; error?: string | null; empty?: ReactNode | false; onRetry?: () => void; children?: ReactNode;
}) {
  if (loading) return <div className="loading" aria-busy="true"><span /><span /><span /></div>;
  if (error) return (
    <div className="state state-error" role="alert">
      <p>{error}</p>
      {onRetry && <Button variant="ghost" onClick={onRetry}>Tentar novamente</Button>}
    </div>
  );
  if (empty) return <div className="state state-empty">{empty}</div>;
  return <>{children}</>;
}

// ------------------------------------------------------------------------------------------- primitivas
export function Button({ children, variant = "ink", busy, type = "button", ...rest }: {
  children: ReactNode; variant?: "primary" | "ink" | "ghost" | "danger" | "link"; busy?: boolean; type?: "button" | "submit"; [k: string]: any;
}) {
  return (
    <button type={type} className={`btn btn-${variant}`} disabled={busy || rest.disabled} aria-busy={busy || undefined} {...rest}>
      {busy ? <span className="spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function Field({ label, hint, error, children, wide }: { label: string; hint?: string; error?: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={`field${wide ? " field-wide" : ""}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}

/** Grupo de controles (chips/caixas) com legenda — evita colocar botões dentro de <label>, o que contamina o nome acessível. */
export function Group({ label, children, wide = true }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <fieldset className={`field group${wide ? " field-wide" : ""}`}>
      <legend className="field-label">{label}</legend>
      {children}
    </fieldset>
  );
}

export function Input(props: { value: any; onChange: (v: string) => void; [k: string]: any }) {
  const { value, onChange, ...rest } = props;
  return <input className="input" value={value ?? ""} onChange={(e: any) => onChange(e.target.value)} {...rest} />;
}

export function TextArea(props: { value: any; onChange: (v: string) => void; rows?: number; [k: string]: any }) {
  const { value, onChange, rows = 4, ...rest } = props;
  return <textarea className="input" rows={rows} value={value ?? ""} onChange={(e: any) => onChange(e.target.value)} {...rest} />;
}

export function Select({ value, onChange, options, placeholder, ...rest }: {
  value: any; onChange: (v: string) => void; options: [string, string][]; placeholder?: string; [k: string]: any;
}) {
  return (
    <select className="input" value={value ?? ""} onChange={(e: any) => onChange(e.target.value)} {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
    </select>
  );
}

/** Seleção múltipla por fichas (causas, ODS, documentos). */
export function Chips({ options, value, onChange, max }: { options: [string, string][]; value: string[]; onChange: (v: string[]) => void; max?: number }) {
  return (
    <div className="chips" role="group">
      {options.map(([v, l]) => {
        const on = value.includes(v);
        return (
          <button key={v} type="button" className={`chip${on ? " chip-on" : ""}`} aria-pressed={on}
            onClick={() => onChange(on ? value.filter((x) => x !== v) : max && value.length >= max ? value : [...value, v])}>
            {l}
          </button>
        );
      })}
    </div>
  );
}

export function Pill({ status, tone, children }: { status?: string; tone?: string; children?: ReactNode }) {
  const t = tone || toneFor(status);
  return <span className={`pill pill-${t}`}>{children ?? statusLabel(status)}</span>;
}
export function toneFor(s?: string): string {
  if (!s) return "muted";
  if (["approved", "clean", "verified", "accepted", "validated", "confirmed", "completed", "closed", "done", "funded", "signed", "active", "eligible", "pass", "paid"].includes(s)) return "good";
  if (["rejected", "infected", "blocked", "questioned", "cancelled", "canceled", "fail", "expired", "revoked", "suspended"].includes(s)) return "bad";
  if (["pending_scan", "needs_info", "needs_review", "pending", "in_review", "submitted", "screening", "due_diligence", "interest", "warning", "past_due", "pending_review", "pending_approval", "changes_requested", "requested"].includes(s)) return "warn";
  return "muted";
}

export function Panel({ title, actions, children, id, quiet }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; id?: string; quiet?: boolean }) {
  return (
    <section className={`panel${quiet ? " panel-quiet" : ""}`} id={id}>
      {(title || actions) && (
        <header className="panel-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHead({ title, sub, actions, back }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; back?: ReactNode }) {
  return (
    <header className="page-head">
      {back}
      <div className="page-head-row">
        <div>
          <h1>{title}</h1>
          {sub && <p className="page-sub">{sub}</p>}
        </div>
        {actions && <div className="page-actions">{actions}</div>}
      </div>
    </header>
  );
}

export function Modal({ open, title, onClose, children, footer }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  const ref = useRef<any>(null);
  const id = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="modal" aria-labelledby={id} onClose={onClose} onCancel={onClose}>
      <header className="modal-head">
        <h2 id={id}>{title}</h2>
        <button className="icon-btn" aria-label="Fechar" onClick={onClose}>×</button>
      </header>
      <div className="modal-body">{open ? children : null}</div>
      {footer && <footer className="modal-foot">{footer}</footer>}
    </dialog>
  );
}

export function KeyValue({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v]) => (
        <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
      ))}
    </dl>
  );
}

export function Pager({ data, offset, setOffset }: { data: any; offset: number; setOffset: (n: number) => void }) {
  if (!data || (offset === 0 && !data.has_more)) return null;
  return (
    <nav className="pager" aria-label="Paginação">
      <Button variant="ghost" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - data.limit))}>Anteriores</Button>
      <Button variant="ghost" disabled={!data.has_more} onClick={() => setOffset(data.next_offset)}>Próximos</Button>
    </nav>
  );
}

/** Barras horizontais em SVG (sem bibliotecas). */
export function Bars({ rows, format }: { rows: { label: string; value: number; tone?: string }[]; format: (v: number) => string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <p className="muted">Sem dados ainda.</p>;
  return (
    <div className="bars" role="list">
      {rows.map((r) => (
        <div className="bar-row" role="listitem" key={r.label}>
          <span className="bar-label">{r.label}</span>
          <span className="bar-track"><span className={`bar-fill bar-${r.tone || "ink"}`} style={{ width: `${(r.value / max) * 100}%` }} /></span>
          <span className="bar-value">{format(r.value)}</span>
        </div>
      ))}
    </div>
  );
}

/** Fluxo de recurso: comprometido → desembolsado → gasto → validado, como barras sobrepostas na mesma escala. */
export function MoneyFlow({ stages }: { stages: [string, number][] }) {
  const max = Math.max(1, ...stages.map((s) => s[1]));
  return (
    <ol className="flow">
      {stages.map(([l, v], i) => (
        <li key={l}>
          <span className="flow-label">{l}</span>
          <span className="flow-track"><span className="flow-fill" style={{ width: `${(v / max) * 100}%`, opacity: 1 - i * 0.15 }} /></span>
          <span className="flow-value">{new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v / 100)}</span>
        </li>
      ))}
    </ol>
  );
}

export function useForm<T extends Record<string, any>>(initial: T) {
  const [v, setV] = useState<T>(initial);
  const set = <K extends keyof T>(k: K) => (val: T[K]) => setV((x) => ({ ...x, [k]: val }));
  return { v, set, setV };
}
