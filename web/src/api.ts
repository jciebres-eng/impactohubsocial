// Cliente da API /v1. Web: cookies httpOnly + header X-CSRF-Token. App nativo (Capacitor): tokens Bearer
// guardados no armazenamento do dispositivo (ver src/native.ts). Renova a sessão automaticamente uma vez em 401.
import { tokenStore, isNative } from "./native";

export class ApiError extends Error {
  status: number;
  code: string;
  details: any;
  constructor(status: number, code: string, message: string, details?: any) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Web: mesma origem (""). App nativo: URL absoluta da API definida no build (IMPACTO_API_BASE=https://app.exemplo.org node build.mjs).
declare const process: { env: Record<string, string> };
const BASE: string = process.env.IMPACTO_API_BASE || "";
let csrf: string | null = null;
let onUnauthenticated: () => void = () => {};

export function setCsrf(token: string | null) {
  csrf = token;
}
export function onSessionLost(fn: () => void) {
  onUnauthenticated = fn;
}

function readCookie(name: string): string | null {
  const m = document.cookie.split("; ").find((c) => c.startsWith(name + "="));
  return m ? decodeURIComponent(m.split("=")[1]) : null;
}

async function raw(method: string, path: string, body?: unknown, isForm = false): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (isNative()) {
    headers["X-Auth-Mode"] = "token";
    const t = await tokenStore.get("access");
    if (t) headers["Authorization"] = `Bearer ${t}`;
  } else if (method !== "GET") {
    const tok = csrf || readCookie("__Host-impacto_csrf") || readCookie("impacto_csrf");
    if (tok) headers["X-CSRF-Token"] = tok;
  }
  return fetch(BASE + path, {
    method,
    headers,
    credentials: BASE ? "include" : "same-origin",
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  });
}

let refreshing: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const body = isNative() ? { refresh_token: await tokenStore.get("refresh") } : {};
      const r = await raw("POST", "/v1/auth/refresh", body);
      if (!r.ok) return false;
      const data = await r.json();
      await absorbSession(data);
      return true;
    })().finally(() => setTimeout(() => (refreshing = null), 0));
  }
  return refreshing;
}

export async function absorbSession(data: any) {
  if (data?.csrf_token) setCsrf(data.csrf_token);
  if (isNative() && data?.access_token) {
    await tokenStore.set("access", data.access_token);
    await tokenStore.set("refresh", data.refresh_token);
  }
}

// Confirmação de identidade (step-up). O servidor responde 401 `step_up_required` às operações
// sensíveis quando a sessão não confirmou a identidade nos últimos 15 minutos. Até a v0.24.2 nenhuma
// tela sabia pedir essa confirmação: a resposta virava erro com "Tentar novamente", e o interruptor
// de emergência, o fechamento contábil e as aprovações financeiras eram inalcançáveis pela interface.
// Agora o cliente pede a confirmação (quem registra o pedido é o `StepUpProvider`) e repete a chamada
// UMA vez. Sem confirmação, o erro original segue para a tela.
let stepUpHandler: (() => Promise<boolean>) | null = null;
export function onStepUpRequired(fn: (() => Promise<boolean>) | null) {
  stepUpHandler = fn;
}

export async function request<T = any>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  let r = await raw(method, path, body, isForm);
  if (r.status === 401 && !path.startsWith("/v1/auth/") && stepUpHandler) {
    const peek = await r.clone().json().catch(() => null);
    if (peek?.code === "step_up_required") {
      if (await stepUpHandler()) r = await raw(method, path, body, isForm);
      if (r.status === 401) {
        const d = await r.json().catch(() => ({}));
        throw new ApiError(401, d.code || "step_up_required", d.title || "Confirme sua identidade para continuar", d.details);
      }
    }
  }
  if (r.status === 401 && !path.startsWith("/v1/auth/")) {
    // Só tenta renovar se houver indício de sessão (cookie CSRF não-httpOnly na web, ou token no app nativo).
    const hasSession = isNative() ? !!(await tokenStore.get("refresh")) : !!(readCookie("__Host-impacto_csrf") || readCookie("impacto_csrf"));
    if (hasSession && (await tryRefresh())) r = await raw(method, path, body, isForm);
    else onUnauthenticated();
  }
  if (r.status === 204) return undefined as T;
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    const d = typeof data === "object" ? data : {};
    throw new ApiError(r.status, d.code || "http_error", d.title || "Não foi possível concluir a operação.", d.details);
  }
  return data as T;
}

export const api = {
  get: <T = any>(p: string) => request<T>("GET", p),
  post: <T = any>(p: string, b: unknown = {}) => request<T>("POST", p, b),
  put: <T = any>(p: string, b: unknown) => request<T>("PUT", p, b),
  patch: <T = any>(p: string, b: unknown) => request<T>("PATCH", p, b),
  del: <T = any>(p: string) => request<T>("DELETE", p),
  upload: <T = any>(p: string, form: FormData) => request<T>("POST", p, form, true),
};

export function qs(params: Record<string, unknown>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    u.set(k, String(v));
  }
  const s = u.toString();
  return s ? "?" + s : "";
}

/** Mensagem legível para o usuário, incluindo detalhes de validação por campo. */
export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "validation_error" && Array.isArray(e.details)) {
      return e.message + ": " + e.details.map((d: any) => `${d.field.split(".").pop()} — ${d.message}`).join("; ");
    }
    if (Array.isArray(e.details?.pending)) return `${e.message}: ${e.details.pending.join(", ")}`;
    if (Array.isArray(e.details?.blockers)) return `${e.message}: ${e.details.blockers.join("; ")}`;
    if (e.status === 0 || e.code === "service_unavailable") return "Serviço indisponível no momento. Tente novamente em instantes.";
    return e.message;
  }
  if (e instanceof TypeError) return "Sem conexão com o servidor. Verifique sua internet.";
  return "Erro inesperado.";
}
