// Autocomplete com PROCEDÊNCIA e sem sobrescrita silenciosa, e seções que se revelam em etapas.
//
// A regra que define este arquivo: **o que a pessoa escreveu é a verdade.** Uma sugestão pode
// preencher um campo vazio, mas nunca substitui texto digitado sem confirmação explícita — e, quando
// substitui, o componente mostra o que havia antes e oferece desfazer.
//
// A segunda regra: **toda sugestão diz de onde veio.** Carga oficial, lista editorial da plataforma
// ou histórico da própria organização aparecem como etiqueta na linha, com fonte e data quando
// existem. Sugestão sem origem é sugestão que a pessoa não pode avaliar.
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";

export type SuggestItem = {
  value: string; label: string; sublabel?: string | null;
  origin: string; origin_label: string;
  source_name?: string | null; source_date?: string | null; verified?: boolean;
  [k: string]: any;
};

export type SuggestProvenance = {
  /** De onde veio o valor atual do campo: digitado pela pessoa ou aceito de uma sugestão. */
  filled_by: "typed" | "suggestion";
  origin?: string; origin_label?: string;
  source_name?: string | null; source_date?: string | null;
  accepted_value?: string;
  /** O que a pessoa havia escrito antes de aceitar a sugestão (para desfazer e para auditoria). */
  replaced_text?: string;
};

const ORIGIN_TONE: Record<string, string> = {
  official_load: "good",
  platform_knowledge: "warn",
  platform_editorial: "info",
  your_organization: "info",
  another_organization: "warn",
};

/** Etiqueta de origem. Fica visível na linha da sugestão e ao lado do campo depois de aceita. */
export function OriginTag({ item }: { item: Pick<SuggestItem, "origin" | "origin_label" | "source_name" | "source_date"> }) {
  const tone = ORIGIN_TONE[item.origin] ?? "info";
  const title = [item.origin_label, item.source_name, item.source_date].filter(Boolean).join(" · ");
  return <span className={`pill pill-${tone} pill-origin`} title={title}>{item.origin_label}</span>;
}

export function Suggest({
  lookup, value, onChange, onProvenance, placeholder, disabled, minChars = 2, id,
  describe, allowFreeText = true,
}: {
  /** Chave de /v1/lookups (territories, indicators, my_suppliers, …). */
  lookup: string;
  value: string;
  onChange: (v: string, item?: SuggestItem) => void;
  /** Recebe a procedência sempre que ela muda — o formulário envia isso junto com o valor. */
  onProvenance?: (p: SuggestProvenance) => void;
  placeholder?: string; disabled?: boolean; minChars?: number; id?: string;
  /** Texto da sugestão na lista; por padrão label + sublabel. */
  describe?: (i: SuggestItem) => ReactNode;
  /** Quando falso, o campo só aceita valor vindo de sugestão. */
  allowFreeText?: boolean;
}) {
  const listId = useId();
  const [items, setItems] = useState<SuggestItem[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cursor, setCursor] = useState(-1);
  const [accepted, setAccepted] = useState<SuggestItem | null>(null);
  const [pending, setPending] = useState<SuggestItem | null>(null); // aguardando confirmação
  const [undoTo, setUndoTo] = useState<string | null>(null);
  const box = useRef<HTMLDivElement | null>(null);
  const typed = useRef(value);

  // Busca com atraso: o servidor não é consultado a cada tecla.
  useEffect(() => {
    if (disabled) return;
    const term = value.trim();
    if (term.length < minChars) { setItems([]); return; }
    let alive = true;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await api.get<{ items: SuggestItem[] }>(
          `/v1/lookups/${encodeURIComponent(lookup)}?q=${encodeURIComponent(term)}&limit=8`);
        if (alive) { setItems(r.items || []); setOpen(true); setCursor(-1); }
      } catch { if (alive) setItems([]); } finally { if (alive) setBusy(false); }
    }, 250);
    return () => { alive = false; clearTimeout(t); };
  }, [lookup, value, minChars, disabled]);

  useEffect(() => {
    function away(e: MouseEvent) {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  const same = (a: string, b: string) =>
    a.trim().toLocaleLowerCase("pt-BR") === b.trim().toLocaleLowerCase("pt-BR");

  function apply(item: SuggestItem, replaced?: string) {
    setAccepted(item);
    setPending(null);
    setUndoTo(replaced && !same(replaced, item.label) ? replaced : null);
    setOpen(false);
    onChange(item.label, item);
    onProvenance?.({
      filled_by: "suggestion", origin: item.origin, origin_label: item.origin_label,
      source_name: item.source_name, source_date: item.source_date,
      accepted_value: item.value, replaced_text: replaced || undefined,
    });
  }

  function choose(item: SuggestItem) {
    const atual = value.trim();
    // A trava central: texto digitado que NÃO é apenas o começo da sugestão só é substituído com
    // confirmação. Prefixo (a pessoa estava digitando aquilo) é aceito direto.
    const isPrefix = atual === "" || item.label.toLocaleLowerCase("pt-BR")
      .startsWith(atual.toLocaleLowerCase("pt-BR"));
    if (isPrefix) apply(item, atual || undefined);
    else setPending(item);
  }

  function undo() {
    const texto = undoTo ?? "";
    setAccepted(null); setUndoTo(null);
    onChange(texto);
    onProvenance?.({ filled_by: "typed" });
  }

  const describeItem = useMemo(
    () => describe ?? ((i: SuggestItem) => (
      <>
        <span className="suggest-label">{i.label}</span>
        {i.sublabel ? <span className="suggest-sub">{i.sublabel}</span> : null}
      </>
    )), [describe]);

  return (
    <div className="suggest" ref={box}>
      <input
        id={id} className="input" role="combobox" aria-expanded={open} aria-controls={listId}
        aria-autocomplete="list" autoComplete="off" value={value} disabled={disabled}
        placeholder={placeholder} aria-busy={busy || undefined}
        onChange={(e: any) => {
          typed.current = e.target.value;
          setAccepted(null); setPending(null); setUndoTo(null);
          onChange(e.target.value);
          onProvenance?.({ filled_by: "typed" });
        }}
        onFocus={() => items.length && setOpen(true)}
        onKeyDown={(e: any) => {
          if (!open || !items.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
          else if (e.key === "Enter" && cursor >= 0) { e.preventDefault(); choose(items[cursor]); }
          else if (e.key === "Escape") setOpen(false);
        }} />

      {accepted && (
        <p className="suggest-origin">
          <OriginTag item={accepted} />
          {accepted.source_name ? <span className="suggest-source">Fonte: {accepted.source_name}{accepted.source_date ? ` (${accepted.source_date})` : ""}</span> : null}
          {undoTo ? <button type="button" className="btn btn-link" onClick={undo}>Voltar ao que eu havia escrito</button> : null}
        </p>
      )}

      {pending && (
        <div className="suggest-confirm" role="alertdialog" aria-live="polite">
          <p>
            Você escreveu <strong>{value}</strong>. Trocar por <strong>{pending.label}</strong>?
            {" "}<OriginTag item={pending} />
          </p>
          <p className="suggest-confirm-actions">
            <button type="button" className="btn btn-ink" onClick={() => apply(pending, value)}>Usar a sugestão</button>
            <button type="button" className="btn btn-ghost" onClick={() => { setPending(null); setOpen(false); }}>Manter o que escrevi</button>
          </p>
        </div>
      )}

      {open && items.length > 0 && (
        <ul className="suggest-list" id={listId} role="listbox">
          {items.map((i, n) => (
            <li key={`${i.origin}:${i.value}`} role="option" aria-selected={n === cursor}
              className={`suggest-item${n === cursor ? " suggest-item-on" : ""}`}>
              <button type="button" onMouseEnter={() => setCursor(n)} onClick={() => choose(i)}>
                {describeItem(i)}
                <OriginTag item={i} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {open && !busy && !items.length && value.trim().length >= minChars && (
        <p className="suggest-empty">
          {allowFreeText
            ? "Nenhuma sugestão. O que você escreveu vale — e fica registrado como declarado por você."
            : "Nenhuma sugestão, e este campo só aceita item do catálogo."}
        </p>
      )}
    </div>
  );
}

/** Formulário em etapas: revela a próxima seção quando a anterior está coerente, e NUNCA esconde o
 *  que já foi preenchido — progressive disclosure que oculta trabalho feito é perda de trabalho. */
export function Steps({ steps }: {
  steps: { key: string; title: string; hint?: string; ready: boolean; blocker?: string; children: ReactNode }[];
}) {
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  let liberado = true;
  return (
    <div className="form-steps">
      {steps.map((s, i) => {
        const anterior = i === 0 ? true : steps[i - 1].ready;
        const visivel = liberado && (anterior || opened[s.key] || s.ready);
        liberado = liberado && (anterior || s.ready);
        return (
          <section key={s.key} className={`form-step${visivel ? "" : " form-step-locked"}`} aria-labelledby={`form-step-${s.key}`}>
            <h3 id={`form-step-${s.key}`} className="form-step-title">
              <span className="form-step-n" aria-hidden="true">{i + 1}</span>{s.title}
              {s.ready ? <span className="pill pill-good">pronto</span> : null}
            </h3>
            {s.hint ? <p className="form-step-hint">{s.hint}</p> : null}
            {visivel ? s.children : (
              <p className="form-step-blocked">
                {steps[i - 1]?.blocker || "Conclua a etapa anterior para abrir esta."}
                {" "}
                <button type="button" className="btn btn-link" onClick={() => setOpened((o) => ({ ...o, [s.key]: true }))}>
                  Abrir agora mesmo assim
                </button>
              </p>
            )}
          </section>
        );
      })}
    </div>
  );
}
