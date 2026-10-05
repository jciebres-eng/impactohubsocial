import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app";
import { RouterProvider } from "./router";
import { SessionProvider } from "./session";
import { ToastProvider } from "./ui/kit";
import { ErrorBoundary as Boundary } from "./ui/boundary";

const ErrorBoundary = Boundary as unknown as (p: { children: any }) => any; // (componente de classe; tipagem mínima offline)

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider>
      <ToastProvider>
        <SessionProvider>
          <ErrorBoundary><App /></ErrorBoundary>
        </SessionProvider>
      </ToastProvider>
    </RouterProvider>
  </StrictMode>,
);

// PWA: registra o service worker somente em produção/HTTPS (ou localhost), e não no app nativo.
if ("serviceWorker" in navigator && !(globalThis as any).Capacitor && (location.protocol === "https:" || location.hostname === "localhost")) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
