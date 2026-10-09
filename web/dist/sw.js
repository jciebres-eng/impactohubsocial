// Service worker da Plataforma Impacto (gerado no build). Estratégia:
// - shell estático pré-cacheado e versionado (atualiza a cada build);
// - navegação: rede primeiro, fallback para o shell em cache e, sem cache, página offline;
// - /v1 (API) e /metrics: NUNCA passam pelo cache (dados privados e sempre atuais).
const VERSION = "8f55800fc9e1";
const CACHE = `impacto-shell-${VERSION}`;
const PRECACHE = ["/assets/app-ZADDGX7Q.js","/assets/styles-Y6Y6LLTQ.css","/brand/favicon-16.png","/brand/favicon-32.png","/brand/favicon-48.png","/brand/impacto-logo-transparent-dark-surface-tight.png","/brand/impacto-logo-transparent-dark-surface.png","/brand/impacto-logo-transparent-tight.png","/brand/impacto-logo-transparent.png","/favicon.ico","/fonts/inter-Regular.woff","/fonts/inter-SemiBold.woff","/icons/apple-touch-icon.png","/icons/icon-192.png","/icons/icon-512.png","/icons/maskable-512.png","/","/manifest.webmanifest","/offline.html","/robots.txt"];

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
