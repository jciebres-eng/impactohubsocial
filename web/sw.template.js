// Service worker da Plataforma Impacto (gerado no build). Estratégia:
// - shell estático pré-cacheado e versionado (atualiza a cada build);
// - navegação: rede primeiro, fallback para o shell em cache e, sem cache, página offline;
// - /v1 (API) e /metrics: NUNCA passam pelo cache (dados privados e sempre atuais).
const VERSION = "__VERSION__";
const CACHE = `impacto-shell-${VERSION}`;
const PRECACHE = __PRECACHE__;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith("impacto-shell-") && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/v1/") || url.pathname === "/metrics" || url.pathname.startsWith("/healthz") || url.pathname.startsWith("/readyz")) return;
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(async () => (await caches.match("/")) || (await caches.match("/offline.html"))));
    return;
  }
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request)));
});
