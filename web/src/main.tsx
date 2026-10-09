import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app";
import { RouterProvider } from "./router";
import { SessionProvider } from "./session";
import { AccessProvider } from "./access";
import { ToastProvider } from "./ui/kit";
import { StepUpProvider } from "./ui/stepup";
import { ErrorBoundary as Boundary } from "./ui/boundary";
import { bootTheme } from "./pages/prefs";
import { installScrollFocus } from "./ui/scrollfocus";
import { DemoBanner } from "./ui/demobanner";

const ErrorBoundary = Boundary as unknown as (p: { children: any }) => any; // (componente de classe; tipagem mínima offline)

// Tema salvo pela pessoa é aplicado ANTES do primeiro render, para não piscar branco e depois escuro.
bootTheme();
// Áreas com rolagem horizontal/vertical alcançáveis pelo teclado (WCAG 2.1.1).
installScrollFocus();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider>
      <ToastProvider>
        <SessionProvider>
          <AccessProvider>
            <StepUpProvider>
              <ErrorBoundary><DemoBanner /><App /></ErrorBoundary>
            </StepUpProvider>
          </AccessProvider>
        </SessionProvider>
      </ToastProvider>
    </RouterProvider>
  </StrictMode>,
);

// PWA: registra o service worker somente em produção/HTTPS (ou localhost), e não no app nativo.
if ("serviceWorker" in navigator && !(globalThis as any).Capacitor && (location.protocol === "https:" || location.hostname === "localhost")) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
