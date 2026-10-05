import { Component } from "react";
import type { ReactNode } from "react";

/** Evita tela em branco: exibe mensagem clara e opção de recarregar quando uma página falha ao renderizar. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(error: unknown) { console.error("render_error", error instanceof Error ? error.message : "desconhecido"); }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="state state-error" role="alert" id="conteudo">
        <h1>Algo saiu do esperado nesta tela</h1>
        <p>Nenhum dado foi perdido. Recarregue a página; se continuar, volte ao início.</p>
        <p><button className="btn btn-ink" onClick={() => location.reload()}>Recarregar</button> <a href="/">Voltar ao início</a></p>
      </main>
    );
  }
}
