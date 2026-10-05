import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api, onSessionLost, setCsrf } from "./api";
import { tokenStore } from "./native";

export type Org = { id: string; kind: "osc" | "company" | "individual" | "provider" | "government" | "platform"; legal_name: string; trade_name?: string; compliance_status: string; role: string };
export type Me = {
  user: { id: string; email: string; full_name: string; email_verified: boolean; mfa_enabled: boolean; mfa_verified: boolean; is_platform_admin: boolean; staff_roles?: string[] };
  active_org: Org | null;
  organizations: Org[];
  entitlements: { plans: string[]; plan_names: string[]; features: string[]; limits: Record<string, number | null> } | null;
  subscription: any;
  unread_notifications: number;
  csrf_token: string | null;
};

type Session = { me: Me | null; loading: boolean; reload: () => Promise<void>; logout: () => Promise<void>; can: (feature: string) => boolean };
const Ctx = createContext<Session>({ me: null, loading: true, reload: async () => {}, logout: async () => {}, can: () => false });

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    try {
      const data = await api.get<Me>("/v1/me");
      setCsrf(data.csrf_token);
      setMe(data);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);
  const logout = useCallback(async () => {
    try {
      await api.post("/v1/auth/logout");
    } catch {
      /* sessão já encerrada */
    }
    await tokenStore.clear();
    setMe(null);
  }, []);
  useEffect(() => {
    onSessionLost(() => setMe(null));
    reload();
  }, [reload]);
  const can = (f: string) => !!me?.entitlements && (me.entitlements.features.includes("*") || me.entitlements.features.includes(f));
  return <Ctx.Provider value={{ me, loading, reload, logout, can }}>{children}</Ctx.Provider>;
}

export const useSession = () => useContext(Ctx);
