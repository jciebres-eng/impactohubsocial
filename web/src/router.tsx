// Roteador mínimo sobre a History API (sem dependências). Rotas com parâmetros ":id".
import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

type Loc = { path: string; query: URLSearchParams };
const RouterCtx = createContext<Loc>({ path: "/", query: new URLSearchParams() });

function current(): Loc {
  return { path: location.pathname, query: new URLSearchParams(location.search) };
}

export function navigate(to: string, replace = false) {
  if (replace) history.replaceState(null, "", to);
  else history.pushState(null, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const [loc, setLoc] = useState<Loc>(current());
  useEffect(() => {
    const on = () => setLoc(current());
    window.addEventListener("popstate", on);
    return () => window.removeEventListener("popstate", on);
  }, []);
  return <RouterCtx.Provider value={loc}>{children}</RouterCtx.Provider>;
}

export const useLocation = () => useContext(RouterCtx);

export function match(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split("/").filter(Boolean);
  const a = path.split("/").filter(Boolean);
  if (p.length !== a.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i++) {
    const seg = p[i];
    if (seg.startsWith(":")) {
      params[seg.slice(1)] = decodeURIComponent(a[i]);
      continue;
    }
    // Segmento com PREFIXO LITERAL antes do parâmetro, como "@:handle" em /@identificador.
    //
    // A URL pública do perfil é `impacto.app/@nome` — o arroba faz parte do endereço, não do valor. Sem este
    // caso, `/@:handle` nunca casaria (o segmento não começa com ":") e a página compartilhada cairia no
    // "não encontrada". Com ele, o prefixo é conferido e só o resto vira parâmetro.
    const colon = seg.indexOf(":");
    if (colon > 0) {
      const prefix = seg.slice(0, colon);
      if (!a[i].startsWith(prefix) || a[i].length === prefix.length) return null;
      params[seg.slice(colon + 1)] = decodeURIComponent(a[i].slice(prefix.length));
      continue;
    }
    if (seg !== a[i]) return null;
  }
  return params;
}

export function Link({ to, children, className, onClick, ...rest }: { to: string; children: ReactNode; className?: string; onClick?: () => void; [k: string]: any }) {
  return (
    <a
      href={to}
      className={className}
      {...rest}
      onClick={(e: any) => {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        onClick?.();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}
