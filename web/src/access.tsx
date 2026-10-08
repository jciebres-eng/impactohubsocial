// Contexto de acesso — a tela PERGUNTA à autoridade em vez de reimplementar a regra.
//
// Até a v0.21.0 a barra lateral da administração era uma lista fixa aqui no frontend, idêntica
// para toda a equipe interna: quem atendia chamado via "Cobrança por organização" e "Auditoria"
// no menu e levava 403 ao clicar. A regra existia em dois lugares e um deles estava errado.
//
// Agora o menu interno, o painel inicial e as permissões vêm de `GET /v1/me/context`. Se o
// servidor mudar a matriz de permissão, a tela muda no recarregamento seguinte, sem implantação.
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "./api";
import { useSession } from "./session";

export type MenuGroup = { group: string; items: { to: string; label: string; permission: string | null }[] };
export type AccessContextData = {
  user: { id: string; email: string; mfa_enabled: boolean; mfa_verified: boolean; email_verified: boolean };
  staff: { is_platform_admin: boolean; roles: string[]; permissions: string[]; read_only: boolean };
  organization: { id: string; kind: string; name: string; role: string } | null;
  commercial: { plans: string[]; subscription: null; state: string | null; free_period_end: string | null; charge_authorized: boolean };
  entitlements: { features: string[]; limits: Record<string, number | null> };
  dashboard: string;
  menu: MenuGroup[];
  step_up_window_seconds: number;
};

type Access = {
  ctx: AccessContextData | null;
  loading: boolean;
  reload: () => Promise<void>;
  /** Tem a permissão interna? Pergunta local sobre uma resposta do servidor — nunca uma regra nova. */
  has: (permission: string) => boolean;
  isStaff: boolean;
};

const Ctx = createContext<Access>({ ctx: null, loading: true, reload: async () => {}, has: () => false, isStaff: false });

export function AccessProvider({ children }: { children: ReactNode }) {
  const { me } = useSession();
  const [ctx, setCtx] = useState<AccessContextData | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    if (!me) { setCtx(null); setLoading(false); return; }
    try {
      setCtx(await api.get<AccessContextData>("/v1/me/context"));
    } catch {
      setCtx(null);   // sem contexto, a tela mostra só o que não depende dele
    } finally {
      setLoading(false);
    }
  }, [me]);
  useEffect(() => { reload(); }, [reload]);
  const has = (p: string) => !!ctx?.staff.permissions.includes(p);
  return <Ctx.Provider value={{ ctx, loading, reload, has, isStaff: !!ctx && (ctx.staff.roles.length > 0 || ctx.staff.is_platform_admin) }}>{children}</Ctx.Provider>;
}

export const useAccess = () => useContext(Ctx);

/** Confirmação de identidade para operação sensível (step-up). Vale 15 minutos no servidor. */
export async function stepUp(password: string, mfaCode?: string) {
  return api.post("/v1/auth/reauth", { password, mfa_code: mfaCode || undefined });
}
