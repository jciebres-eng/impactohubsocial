// Ajuda contextual (v0.29.0): Tooltip, InfoPopover, GlossaryTerm, ContextualHelp e GlossaryContent.
//
// Uma fonte só: o texto vem de web/src/concepts.ts (gerado de config/concepts.json). Nenhum componente carrega definição própria.
// Sem biblioteca: posicionamento por getBoundingClientRect com inversão quando falta espaço; foco e teclado nativos.
// Acessibilidade: o gatilho é <button>; a dica curta usa role="tooltip" + aria-describedby e aparece com hover OU foco;
// o cartão abre com clique/Enter/Espaço/toque, fecha com Escape, clique fora ou Tab para fora, e tem role="dialog" com título.
// Tema e movimento: cores só por tokens (claro/escuro automáticos); a animação respeita prefers-reduced-motion no CSS.
import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { CONCEPT_DOMAINS, concept, type Concept } from "../concepts";
import { Link } from "../router";

type Placement = "top" | "bottom";

/** Posição fixa do balão em relação ao gatilho, invertendo quando não cabe (nunca sai da janela). */
function usePlacement(open: boolean, anchor: React.RefObject<HTMLElement | null>, box: React.RefObject<HTMLElement | null>, prefer: Placement = "bottom") {
  const [style, setStyle] = useState<{ top: number; left: number; placement: Placement } | null>(null);
  const place = useCallback(() => {
    const a = anchor.current, b = box.current;
    if (!a || !b) return;
    const r = a.getBoundingClientRect();
    const w = b.offsetWidth, h = b.offsetHeight, gap = 8, pad = 8;
    const below = window.innerHeight - r.bottom - gap, above = r.top - gap;
    const placement: Placement = prefer === "bottom" ? (below >= h || below >= above ? "bottom" : "top") : (above >= h || above >= below ? "top" : "bottom");
    const top = placement === "bottom" ? r.bottom + gap : Math.max(pad, r.top - gap - h);
    const left = Math.min(Math.max(pad, r.left + r.width / 2 - w / 2), Math.max(pad, window.innerWidth - w - pad));
    setStyle({ top, left, placement });
  }, [anchor, box, prefer]);
  useLayoutEffect(() => {
    if (!open) { setStyle(null); return; }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [open, place]);
  return style;
}

// ----------------------------------------------------------------------------------------------- Tooltip
/** Dica curta (uma frase) ligada a um elemento focável. Aparece no hover e no foco; some no Escape. Não é o lugar de texto longo. */
export function Tooltip({ text, children, id }: { text: string; children: ReactNode; id?: string }) {
  const auto = useId();
  const tid = id ?? `tip-${auto}`;
  const [open, setOpen] = useState(false);
  const anchor = useRef<HTMLSpanElement>(null);
  const box = useRef<HTMLSpanElement>(null);
  const style = usePlacement(open, anchor, box, "top");
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  return (
    <span ref={anchor} className="tip-anchor" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
      {children}
      <span ref={box} id={tid} role="tooltip" className={`tip ${open ? "tip-open" : ""} ${style ? `tip-${style.placement}` : ""}`} style={style ? { top: style.top, left: style.left } : undefined} aria-hidden={!open}>
        {text}
      </span>
    </span>
  );
}

// ----------------------------------------------------------------------------------------------- InfoPopover
/** Cartão explicativo aberto por um botão. Fecha com Escape, clique fora e Tab para fora; devolve o foco ao gatilho. */
export function InfoPopover({ title, children, trigger, label, onOpenChange }: { title: string; children: ReactNode; trigger?: ReactNode; label?: string; onOpenChange?: (open: boolean) => void }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  useEffect(() => { onOpenChange?.(open); }, [open]);   // eslint-disable-line react-hooks/exhaustive-deps
  const anchor = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const style = usePlacement(open, anchor, box, "bottom");
  const close = useCallback(() => { setOpen(false); anchor.current?.focus(); }, []);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
    const onDown = (e: MouseEvent | TouchEvent) => {
      const t = e.target as Node;
      if (box.current?.contains(t) || anchor.current?.contains(t)) return;
      setOpen(false);
    };
    const onFocus = (e: FocusEvent) => {
      const t = e.target as Node;
      if (box.current?.contains(t) || anchor.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown, { passive: true });
    document.addEventListener("focusin", onFocus);
    return () => { document.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); document.removeEventListener("touchstart", onDown); document.removeEventListener("focusin", onFocus); };
  }, [open, close]);
  useEffect(() => { if (open) box.current?.querySelector<HTMLElement>("button, a, [tabindex]")?.focus(); }, [open]);
  return (
    <>
      <button ref={anchor} type="button" className="pop-trigger" aria-expanded={open} aria-controls={open ? id : undefined} aria-haspopup="dialog" aria-label={label} onClick={() => setOpen((o) => !o)}>
        {trigger ?? <span className="pop-i" aria-hidden="true">i</span>}
      </button>
      {open && (
        <div ref={box} id={id} role="dialog" aria-labelledby={`${id}-t`} className={`pop ${style ? `pop-${style.placement}` : ""}`} style={style ? { top: style.top, left: style.left } : { visibility: "hidden" }}>
          <div className="pop-head">
            <strong id={`${id}-t`}>{title}</strong>
            <button type="button" className="pop-close" aria-label="Fechar" onClick={close}>×</button>
          </div>
          <div className="pop-body">{children}</div>
        </div>
      )}
    </>
  );
}

// ----------------------------------------------------------------------------------------------- GlossaryContent
function SourceLine({ s }: { s: Concept["sources"][number] }) {
  const tag = s.kind === "official" ? "fonte oficial" : "documento da plataforma";
  const body = s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer">{s.label}</a> : s.path?.startsWith("/ajuda/") ? <Link to={s.path}>{s.label}</Link> : <span>{s.label}</span>;
  return <li>{body} <span className="gloss-tag">{tag}</span>{s.source_key && <span className="fineprint"> · registro {s.source_key}</span>}</li>;
}

/** O corpo completo de um conceito: usado pelo popover do termo e pela página /ajuda/glossario. Nunca mostra texto que não esteja no catálogo. */
export function GlossaryContent({ c, compact, onNavigate }: { c: Concept; compact?: boolean; onNavigate?: (id: string) => void }) {
  return (
    <div className="gloss">
      <p className="gloss-short">{c.short}</p>
      {!compact && <p>{c.long}</p>}
      <dl className="gloss-dl">
        <dt>Por que importa</dt><dd>{c.why}</dd>
        <dt>Como o IMPACTO usa</dt><dd>{c.how_impacto}</dd>
        {c.limitations && c.limitations !== "—" && <><dt>Limites</dt><dd>{c.limitations}</dd></>}
      </dl>
      {c.status === "needs_review" && <p className="fineprint">Definição em revisão por pessoa da área.</p>}
      <p className="fineprint">Fontes:</p>
      <ul className="gloss-src">{c.sources.map((s, i) => <SourceLine key={i} s={s} />)}</ul>
      {c.related.length > 0 && (
        <p className="fineprint">Veja também: {c.related.map((r, i) => {
          const rc = concept(r);
          if (!rc) return null;
          return <span key={r}>{i > 0 && ", "}{onNavigate ? <button type="button" className="btn-link" onClick={() => onNavigate(r)}>{rc.term}</button> : <Link to={`/ajuda/glossario#${r}`}>{rc.term}</Link>}</span>;
        })}</p>
      )}
      {!compact && <p className="fineprint"><Link to={`/ajuda/glossario#${c.id}`}>Abrir no glossário</Link></p>}
    </div>
  );
}

// ----------------------------------------------------------------------------------------------- GlossaryTerm
/** Termo com ajuda: hover/foco mostra a definição curta; clique/Enter/toque abre o cartão completo. `id` = chave de config/concepts.json.
 *  Sem conceito cadastrado, renderiza só o texto (nunca inventa definição). */
export function GlossaryTerm({ id, children }: { id: string; children?: ReactNode }) {
  const c = concept(id);
  const tipId = useId();
  const [cur, setCur] = useState<Concept | null>(null);   // navegação "veja também" dentro do cartão
  if (!c) return <>{children ?? id}</>;
  const shown = cur ?? c;
  return (
    <span className="gterm" data-concept={c.id}>
      <Tooltip text={c.short} id={`gt-${tipId}`}>
        <InfoPopover title={shown.term} label={`O que é ${c.term}`} onOpenChange={(o) => { if (!o) setCur(null); }} trigger={<span className="gterm-text" aria-describedby={`gt-${tipId}`}>{children ?? c.term}<span className="gterm-mark" aria-hidden="true">?</span></span>}>
          <GlossaryContent c={shown} compact onNavigate={(r) => { const n = concept(r); if (n) setCur(n); }} />
          {shown.id !== c.id && <p className="fineprint"><button type="button" className="btn-link" onClick={() => setCur(null)}>Voltar a {c.term}</button></p>}
        </InfoPopover>
      </Tooltip>
    </span>
  );
}

// ----------------------------------------------------------------------------------------------- ContextualHelp
/** Ícone "i" ao lado de um rótulo de campo ou de um número: abre o cartão do conceito sem sublinhar o texto. */
export function ContextualHelp({ id }: { id: string }) {
  const c = concept(id);
  if (!c) return null;
  return (
    <span className="ctx-i" data-concept={c.id}>
      <Tooltip text={c.short}>
        <InfoPopover title={c.term} label={`O que é ${c.term}`}>
          <GlossaryContent c={c} compact />
        </InfoPopover>
      </Tooltip>
    </span>
  );
}

export { CONCEPT_DOMAINS };
