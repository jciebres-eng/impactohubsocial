// Ícones da identidade oficial entram como texto SVG (esbuild `loader: { ".svg": "text" }`) e são
// inseridos inline para herdarem `currentColor` — o guia da marca diz que SVG via <img> não herda.
declare module "*.svg" {
  const conteudo: string;
  export default conteudo;
}
