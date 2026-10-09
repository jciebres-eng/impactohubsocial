// v0.32.0 — AVISO DE DEMONSTRAÇÃO. O ambiente demo (Railway, IMPACTO_ENV=development) fica aberto a qualquer
// pessoa com o link e aceita cadastro sem os termos aprovados (a trava jurídica só vale em staging/produção).
// Sem um aviso visível em TODA tela — inclusive cadastro e login —, alguém digita dados reais num ambiente sem as
// proteções da produção. O modo vem do servidor (`/v1/meta/config`), nunca de uma variável do build: a mesma
// imagem roda no demo e na produção.
import { useEffect, useState } from "react";
import { api } from "../api";

export function DemoBanner() {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    api.get("/v1/meta/config").then((c: any) => setDemo(c?.env === "development")).catch(() => {});
  }, []);
  if (!demo) return null;
  return (
    <div className="banner banner-warning demo-banner" role="note" aria-label="Ambiente de demonstração">
      <strong>Ambiente de demonstração.</strong> Todos os dados aqui são fictícios e podem ser apagados a qualquer
      momento. Não cadastre dados pessoais reais.
    </div>
  );
}
