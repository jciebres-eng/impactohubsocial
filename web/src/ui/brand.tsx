// Marca oficial da Plataforma Impacto (IMPACTO_DESIGN_SYSTEM v2.3, variantes transparentes).
//
// O lockup veio como RASTER 303×240 (não há vetor oficial); as variantes "tight" têm 157×151 px e o
// guia manda não ampliar além disso: ≤135×130 CSS px na barra lateral e ≤74 no cabeçalho móvel. Os
// tamanhos abaixo ficam dentro — inclusive em telas 2x, onde 64 CSS px pedem 128 px de imagem.
//
// Duas variantes, escolhidas pela SUPERFÍCIE e não pelo tema: sobre a barra lateral e o painel de
// autenticação (navy em qualquer tema) vai a de traços brancos; sobre superfície clara vai a de
// traços navy. No tema escuro a superfície de conteúdo também é escura, então ali a variante é a
// branca — por isso `surface="auto"` lê o tema, e as outras duas são explícitas.
import { Link } from "../router";

type Surface = "light" | "navy" | "auto";
type Size = "rail" | "bar" | "page" | "auth";

const SRC = {
  light: "/brand/impacto-logo-transparent-tight.png",
  navy: "/brand/impacto-logo-transparent-dark-surface-tight.png",
};
const PX: Record<Size, number> = { rail: 96, bar: 40, page: 48, auth: 120 };

function temaEscuro(): boolean {
  if (typeof document === "undefined") return false;
  const t = document.documentElement.getAttribute("data-theme");
  if (t === "dark") return true;
  if (t === "light" || t === "high-contrast") return false;
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches;
}

export function Brand({ surface = "auto", size = "page", to = "/", className = "" }:
  { surface?: Surface; size?: Size; to?: string; className?: string }) {
  const variante = surface === "auto" ? (temaEscuro() ? "navy" : "light") : surface;
  const px = PX[size];
  return (
    <Link to={to} className={`brand brand-${size} ${className}`.trim()} aria-label="Impacto — início">
      <img src={SRC[variante]} alt="" width={px} height={Math.round(px * 151 / 157)} decoding="async" />
    </Link>
  );
}
