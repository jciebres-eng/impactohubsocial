// Ponte com o app nativo (Capacitor). Na web pura, nada daqui é usado (sessão via cookies httpOnly).
// No app: tokens em @capacitor/preferences (Android: SharedPreferences privado do app / iOS: UserDefaults do app).
// Para exigência de cofre seguro (Keystore/Keychain), troque por um plugin de secure storage — ver docs/MOBILE.md.

export function isNative(): boolean {
  const cap = (globalThis as any).Capacitor;
  return !!(cap && typeof cap.isNativePlatform === "function" && cap.isNativePlatform());
}

const memory: Record<string, string | null> = {};

export const tokenStore = {
  async get(key: string): Promise<string | null> {
    const prefs = (globalThis as any).Capacitor?.Plugins?.Preferences;
    if (prefs) return (await prefs.get({ key: `impacto_${key}` })).value ?? null;
    return memory[key] ?? null;
  },
  async set(key: string, value: string | null): Promise<void> {
    const prefs = (globalThis as any).Capacitor?.Plugins?.Preferences;
    if (prefs) {
      if (value === null) await prefs.remove({ key: `impacto_${key}` });
      else await prefs.set({ key: `impacto_${key}`, value });
      return;
    }
    memory[key] = value;
  },
  async clear(): Promise<void> {
    await this.set("access", null);
    await this.set("refresh", null);
  },
};
